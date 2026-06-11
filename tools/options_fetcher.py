"""
tools/options_fetcher.py
------------------------
Tool 3: NSE Options Chain, OI & Put-Call Ratio Fetcher

Responsibilities:
  - Fetch the full option chain (calls & puts) for an NSE symbol + expiry
  - Calculate Put-Call Ratio (PCR) from total OI
  - Identify max-pain price
  - Identify top OI buildup strikes (support & resistance zones)
  - Return clean, JSON-serialisable dicts

Strategy:
  Primary  → nsepython library (clean wrapper around NSE API)
  Fallback → Direct NSE API via requests with browser-like headers

NSE blocks automated requests without valid headers; the fallback
includes the necessary cookie + header handling.

Usage:
  from tools.options_fetcher import get_option_chain, get_pcr
  chain = get_option_chain("NIFTY")
  pcr   = get_pcr("BANKNIFTY")
"""

from __future__ import annotations

import traceback
from datetime import datetime
from typing import Optional

import pandas as pd
import requests

# ─────────────────────────────────────────────────────────────────────────────
# NSE request helpers (headers + session)
# ─────────────────────────────────────────────────────────────────────────────

_NSE_BASE = "https://www.nseindia.com"
_NSE_OPTION_CHAIN_URL = "https://www.nseindia.com/api/option-chain-indices"
_NSE_OPTION_CHAIN_EQ_URL = "https://www.nseindia.com/api/option-chain-equities"

# Headers that mimic a real browser — NSE 403's plain Python requests
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/option-chain",
    "Connection": "keep-alive",
    "X-Requested-With": "XMLHttpRequest",
}

# Symbols that use the "indices" endpoint vs the "equities" endpoint
_INDEX_SYMBOLS = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"}


def _get_nse_session() -> requests.Session:
    """
    Create a requests Session with NSE cookies by first visiting the homepage.
    NSE requires the cookie from the homepage before it serves API responses.
    """
    session = requests.Session()
    session.headers.update(_HEADERS)
    try:
        # Prime the session with NSE cookies
        session.get(_NSE_BASE, timeout=10)
    except Exception:
        pass  # Proceed even if cookie pre-fetch fails
    return session


def _fetch_nse_option_chain_raw(symbol: str) -> Optional[dict]:
    """
    Low-level fetch of the NSE option chain JSON for a given symbol.

    Parameters
    ----------
    symbol : str  e.g. "NIFTY", "BANKNIFTY", "RELIANCE"

    Returns
    -------
    dict | None  Raw NSE JSON or None on failure.
    """
    symbol = symbol.upper().strip()
    session = _get_nse_session()

    if symbol in _INDEX_SYMBOLS:
        url = _NSE_OPTION_CHAIN_URL
    else:
        url = _NSE_OPTION_CHAIN_EQ_URL

    try:
        resp = session.get(url, params={"symbol": symbol}, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        print(f"[options_fetcher] ❌ HTTP error fetching option chain for {symbol}: {e}")
    except requests.exceptions.Timeout:
        print(f"[options_fetcher] ❌ Timeout fetching option chain for {symbol}")
    except requests.exceptions.RequestException as e:
        print(f"[options_fetcher] ❌ Request error for {symbol}: {e}")
    except Exception as e:
        print(f"[options_fetcher] ❌ Unexpected error for {symbol}: {e}")

    return None


# ─────────────────────────────────────────────────────────────────────────────
# nsepython-based primary fetcher
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_via_nsepython(symbol: str) -> Optional[dict]:
    """
    Try fetching option chain via the nsepython library.
    Returns the raw JSON dict or None if nsepython is unavailable / fails.
    """
    try:
        from nsepython import nse_optionchain_scrapper  # type: ignore
        data = nse_optionchain_scrapper(symbol.upper())
        return data
    except ImportError:
        print("[options_fetcher] ℹ️  nsepython not installed, using direct NSE API fallback.")
    except Exception as e:
        print(f"[options_fetcher] ⚠️  nsepython failed for {symbol}: {e}")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Parser: Raw NSE JSON → clean DataFrames
# ─────────────────────────────────────────────────────────────────────────────

def _parse_option_chain(raw: dict, expiry_filter: Optional[str] = None) -> dict:
    """
    Parse raw NSE option chain JSON into structured data.

    Parameters
    ----------
    raw           : dict   Raw NSE option chain JSON
    expiry_filter : str    e.g. "27-Jun-2024". If None, uses the nearest expiry.

    Returns
    -------
    dict with keys:
        underlying_value, expiry_dates, selected_expiry,
        calls (list[dict]), puts (list[dict])
    """
    records = raw.get("records", {})
    filtered = raw.get("filtered", {})

    underlying_value = records.get("underlyingValue") or filtered.get("underlyingValue")
    expiry_dates: list[str] = records.get("expiryDates", [])

    # Choose expiry — nearest available if not specified
    selected_expiry = expiry_filter if expiry_filter in expiry_dates else (
        expiry_dates[0] if expiry_dates else None
    )

    calls, puts = [], []

    all_data = records.get("data", []) or filtered.get("data", [])
    for item in all_data:
        # Each item has expiryDate, strikePrice, CE (call), PE (put) keys
        if item.get("expiryDate") != selected_expiry and selected_expiry:
            continue

        strike = item.get("strikePrice")

        if "CE" in item:
            ce = item["CE"]
            calls.append({
                "strike":          strike,
                "expiry":          item.get("expiryDate"),
                "oi":              ce.get("openInterest", 0),
                "change_oi":       ce.get("changeinOpenInterest", 0),
                "volume":          ce.get("totalTradedVolume", 0),
                "iv":              ce.get("impliedVolatility", 0),
                "ltp":             ce.get("lastPrice", 0),
                "bid":             ce.get("bidprice", 0),
                "ask":             ce.get("askPrice", 0),
                "net_change":      ce.get("change", 0),
                "pct_change":      ce.get("pChange", 0),
            })

        if "PE" in item:
            pe = item["PE"]
            puts.append({
                "strike":          strike,
                "expiry":          item.get("expiryDate"),
                "oi":              pe.get("openInterest", 0),
                "change_oi":       pe.get("changeinOpenInterest", 0),
                "volume":          pe.get("totalTradedVolume", 0),
                "iv":              pe.get("impliedVolatility", 0),
                "ltp":             pe.get("lastPrice", 0),
                "bid":             pe.get("bidprice", 0),
                "ask":             pe.get("askPrice", 0),
                "net_change":      pe.get("change", 0),
                "pct_change":      pe.get("pChange", 0),
            })

    return {
        "underlying_value": underlying_value,
        "expiry_dates":     expiry_dates,
        "selected_expiry":  selected_expiry,
        "calls":            calls,
        "puts":             puts,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Analytics helpers
# ─────────────────────────────────────────────────────────────────────────────

def _calculate_pcr(calls: list[dict], puts: list[dict]) -> dict:
    """Compute Put-Call Ratio from OI totals."""
    total_call_oi = sum(c.get("oi", 0) for c in calls)
    total_put_oi  = sum(p.get("oi", 0) for p in puts)

    pcr = round(total_put_oi / total_call_oi, 4) if total_call_oi > 0 else None

    sentiment = "Neutral"
    if pcr is not None:
        if pcr > 1.2:
            sentiment = "Bullish (heavy put writing → market expects support)"
        elif pcr < 0.8:
            sentiment = "Bearish (heavy call writing → market expects resistance)"

    return {
        "total_call_oi": total_call_oi,
        "total_put_oi":  total_put_oi,
        "pcr":           pcr,
        "sentiment":     sentiment,
    }


def _calculate_max_pain(calls: list[dict], puts: list[dict]) -> Optional[float]:
    """
    Calculate the max-pain strike: the strike where total options writers lose
    the least money (buyers lose the most).

    Returns the max-pain strike price or None if insufficient data.
    """
    all_strikes = sorted(set(c["strike"] for c in calls) | set(p["strike"] for p in puts))
    if not all_strikes:
        return None

    # Build lookup: strike → OI
    call_oi = {c["strike"]: c.get("oi", 0) for c in calls}
    put_oi  = {p["strike"]: p.get("oi", 0) for p in puts}

    min_pain = float("inf")
    max_pain_strike = all_strikes[0]

    for target in all_strikes:
        # Pain to call holders: for each call OI, how much is ITM?
        call_pain = sum(
            max(0, target - strike) * oi
            for strike, oi in call_oi.items()
        )
        put_pain = sum(
            max(0, strike - target) * oi
            for strike, oi in put_oi.items()
        )
        total_pain = call_pain + put_pain
        if total_pain < min_pain:
            min_pain = total_pain
            max_pain_strike = target

    return max_pain_strike


def _top_oi_strikes(options: list[dict], n: int = 5, label: str = "") -> list[dict]:
    """Return the top-n strikes by Open Interest."""
    sorted_opts = sorted(options, key=lambda x: x.get("oi", 0), reverse=True)
    return [
        {"strike": o["strike"], "oi": o["oi"], "type": label}
        for o in sorted_opts[:n]
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def get_option_chain(symbol: str, expiry: Optional[str] = None) -> dict:
    """
    Fetch and parse the NSE option chain for a given symbol.

    Parameters
    ----------
    symbol : str          NSE symbol e.g. "NIFTY", "BANKNIFTY", "RELIANCE"
    expiry : str, opt     Expiry date string e.g. "27-Jun-2024".
                          Defaults to the nearest available expiry.

    Returns
    -------
    dict with keys:
      symbol, fetched_at, underlying_value, selected_expiry, expiry_dates,
      pcr (dict), max_pain, support_strikes (top put OI), resistance_strikes
      (top call OI), calls (list), puts (list), error
    """
    result = {
        "symbol":              symbol.upper(),
        "fetched_at":          datetime.utcnow().isoformat() + "Z",
        "underlying_value":    None,
        "selected_expiry":     expiry,
        "expiry_dates":        [],
        "pcr":                 {},
        "max_pain":            None,
        "support_strikes":     [],   # Top put OI → price support zones
        "resistance_strikes":  [],   # Top call OI → price resistance zones
        "calls":               [],
        "puts":                [],
        "error":               None,
    }

    try:
        # ── Try nsepython first ────────────────────────────────────────────
        raw = _fetch_via_nsepython(symbol)

        # ── Fall back to direct NSE API ────────────────────────────────────
        if raw is None:
            raw = _fetch_nse_option_chain_raw(symbol)

        if raw is None:
            result["error"] = (
                f"Could not fetch option chain for '{symbol}'. "
                "NSE may be closed or rate-limiting. Try again during market hours."
            )
            return result

        # ── Parse ─────────────────────────────────────────────────────────
        parsed = _parse_option_chain(raw, expiry_filter=expiry)

        result["underlying_value"]   = parsed["underlying_value"]
        result["selected_expiry"]    = parsed["selected_expiry"]
        result["expiry_dates"]       = parsed["expiry_dates"]
        result["calls"]              = parsed["calls"]
        result["puts"]               = parsed["puts"]

        # ── Analytics ─────────────────────────────────────────────────────
        result["pcr"]                = _calculate_pcr(parsed["calls"], parsed["puts"])
        result["max_pain"]           = _calculate_max_pain(parsed["calls"], parsed["puts"])
        result["support_strikes"]    = _top_oi_strikes(parsed["puts"],  n=5, label="PUT")
        result["resistance_strikes"] = _top_oi_strikes(parsed["calls"], n=5, label="CALL")

    except Exception as exc:
        result["error"] = f"Option chain processing failed for '{symbol}': {str(exc)}"
        traceback.print_exc()

    return result


def get_pcr(symbol: str, expiry: Optional[str] = None) -> dict:
    """
    Convenience wrapper — returns only the PCR summary for a symbol.

    Returns
    -------
    dict with keys: symbol, pcr, total_call_oi, total_put_oi, sentiment, error
    """
    chain = get_option_chain(symbol, expiry=expiry)
    pcr_data = chain.get("pcr", {})
    return {
        "symbol":        symbol.upper(),
        "selected_expiry": chain.get("selected_expiry"),
        "pcr":           pcr_data.get("pcr"),
        "total_call_oi": pcr_data.get("total_call_oi"),
        "total_put_oi":  pcr_data.get("total_put_oi"),
        "sentiment":     pcr_data.get("sentiment"),
        "max_pain":      chain.get("max_pain"),
        "error":         chain.get("error"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Quick self-test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    print("=" * 60)
    print("PCR: NIFTY")
    print("=" * 60)
    pcr = get_pcr("NIFTY")
    print(json.dumps(pcr, indent=2, default=str))

    print("\n" + "=" * 60)
    print("OPTION CHAIN SUMMARY: BANKNIFTY (top 3 calls & puts)")
    print("=" * 60)
    chain = get_option_chain("BANKNIFTY")
    summary = {k: v for k, v in chain.items() if k not in ("calls", "puts")}
    print(json.dumps(summary, indent=2, default=str))
    print(f"\nCalls rows: {len(chain.get('calls', []))}")
    print(f"Puts rows:  {len(chain.get('puts', []))}")
