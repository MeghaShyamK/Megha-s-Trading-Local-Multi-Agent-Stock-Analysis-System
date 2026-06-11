"""
tools/data_fetcher.py
---------------------
Tool 2: OHLCV, Technical Indicators & Fundamental Data Fetcher

Responsibilities:
  - Fetch historical OHLCV data for any ticker via yfinance
  - Calculate technical indicators with pandas-ta:
      * EMA (20, 50, 200)
      * RSI (14)
      * MACD (12, 26, 9)
      * Fibonacci Retracement levels
  - Fetch fundamental data: P/E ratio, EPS, quarterly earnings,
    dividends, and corporate actions
  - Return all results as clean Python dicts (JSON-serialisable)

All public functions are wrapped with try/except to ensure the
calling code (agents / UI) never crashes on bad data.

Usage:
  from tools.data_fetcher import get_technical_data, get_fundamental_data
  tech  = get_technical_data("RELIANCE.NS", period="3mo", interval="1d")
  funda = get_fundamental_data("RELIANCE.NS")
"""

from __future__ import annotations

import traceback
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import ta as ta_lib               # `ta` library — Python 3.10 compatible
import yfinance as yf

# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────


def _safe_float(value) -> Optional[float]:
    """Convert a value to float, returning None if not possible."""
    try:
        v = float(value)
        return None if np.isnan(v) or np.isinf(v) else round(v, 4)
    except (TypeError, ValueError):
        return None


def _df_tail_to_records(df: pd.DataFrame, n: int = 60) -> list[dict]:
    """
    Convert the last `n` rows of a DataFrame to a list of JSON-safe dicts.
    Index (dates) are stringified.
    """
    df = df.tail(n).copy()
    df.index = df.index.astype(str)          # datetime → "2024-01-15"
    df = df.replace([np.inf, -np.inf], None)
    df = df.where(df.notna(), None)          # NaN → None (JSON null)
    return df.reset_index().rename(columns={"index": "Date"}).to_dict(orient="records")


# ─────────────────────────────────────────────────────────────────────────────
# Fibonacci Retracement Calculator
# ─────────────────────────────────────────────────────────────────────────────


def _calculate_fibonacci(high: float, low: float) -> dict[str, float]:
    """
    Calculate the standard Fibonacci retracement levels between a swing high
    and swing low.

    Levels: 0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%

    Parameters
    ----------
    high : float   Swing high price
    low  : float   Swing low price

    Returns
    -------
    dict mapping level label → price
    """
    diff = high - low
    return {
        "0.0%":   round(high, 2),
        "23.6%":  round(high - 0.236 * diff, 2),
        "38.2%":  round(high - 0.382 * diff, 2),
        "50.0%":  round(high - 0.500 * diff, 2),
        "61.8%":  round(high - 0.618 * diff, 2),
        "78.6%":  round(high - 0.786 * diff, 2),
        "100.0%": round(low, 2),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Public API: Technical Data
# ─────────────────────────────────────────────────────────────────────────────


def get_technical_data(
    ticker: str,
    period: str = "3mo",
    interval: str = "1d",
) -> dict:
    """
    Fetch OHLCV data and compute technical indicators for a given ticker.

    Parameters
    ----------
    ticker   : str  e.g. "RELIANCE.NS" or "^NSEI"
    period   : str  yfinance period string: "1d","5d","1mo","3mo","6mo","1y","2y"
    interval : str  yfinance interval: "1m","5m","15m","30m","1h","1d","1wk","1mo"

    Returns
    -------
    dict with keys:
      ticker        : str
      period        : str
      interval      : str
      fetched_at    : ISO timestamp
      latest_price  : float | None
      latest_volume : int | None
      indicators    : dict  (latest values of EMA, RSI, MACD, Fibonacci)
      ohlcv         : list[dict]  (last 60 candles with all indicator columns)
      error         : str | None  (populated only on failure)
    """
    result = {
        "ticker": ticker,
        "period": period,
        "interval": interval,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "latest_price": None,
        "latest_volume": None,
        "indicators": {},
        "ohlcv": [],
        "error": None,
    }

    try:
        # ── 1. Download raw OHLCV ──────────────────────────────────────────
        raw: pd.DataFrame = yf.download(
            ticker,
            period=period,
            interval=interval,
            auto_adjust=True,   # adjust for splits & dividends
            progress=False,
            threads=False,
        )

        if raw.empty:
            result["error"] = f"No data returned for ticker '{ticker}'. Check if the symbol is correct."
            return result

        # yfinance sometimes returns MultiIndex columns — flatten them
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = [col[0] for col in raw.columns]

        df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.dropna(subset=["Close"], inplace=True)

        # ── 2. Technical Indicators ────────────────────────────────────────
        # EMA (Exponential Moving Averages) via ta.trend.EMAIndicator
        df["EMA_20"]  = ta_lib.trend.EMAIndicator(df["Close"], window=20).ema_indicator()
        df["EMA_50"]  = ta_lib.trend.EMAIndicator(df["Close"], window=50).ema_indicator()
        df["EMA_200"] = ta_lib.trend.EMAIndicator(df["Close"], window=200).ema_indicator()

        # RSI (Relative Strength Index, 14-period)
        df["RSI_14"]  = ta_lib.momentum.RSIIndicator(df["Close"], window=14).rsi()

        # MACD (12, 26, signal 9)
        _macd = ta_lib.trend.MACD(
            df["Close"], window_fast=12, window_slow=26, window_sign=9
        )
        df["MACD_12_26_9"]  = _macd.macd()
        df["MACDs_12_26_9"] = _macd.macd_signal()
        df["MACDh_12_26_9"] = _macd.macd_diff()   # histogram

        # ── 3. Fibonacci Retracement (last 60 candles) ────────────────────
        lookback = df.tail(60)
        swing_high = float(lookback["High"].max())
        swing_low  = float(lookback["Low"].min())
        fib_levels = _calculate_fibonacci(swing_high, swing_low)

        # ── 4. Latest values for the summary block ────────────────────────
        last = df.iloc[-1]
        result["latest_price"]  = _safe_float(last["Close"])
        result["latest_volume"] = int(last["Volume"]) if not pd.isna(last["Volume"]) else None

        result["indicators"] = {
            "EMA_20":         _safe_float(last.get("EMA_20")),
            "EMA_50":         _safe_float(last.get("EMA_50")),
            "EMA_200":        _safe_float(last.get("EMA_200")),
            "RSI_14":         _safe_float(last.get("RSI_14")),
            "MACD":           _safe_float(last.get("MACD_12_26_9")),
            "MACD_Signal":    _safe_float(last.get("MACDs_12_26_9")),
            "MACD_Histogram": _safe_float(last.get("MACDh_12_26_9")),
            "Fibonacci_60d":  fib_levels,
            "swing_high_60d": swing_high,
            "swing_low_60d":  swing_low,
        }

        # ── 5. OHLCV + indicator records for charts ────────────────────────
        result["ohlcv"] = _df_tail_to_records(df, n=60)

    except Exception as exc:
        result["error"] = f"Technical data fetch failed for '{ticker}': {str(exc)}"
        # Print the full traceback to terminal for debugging, don't crash caller
        traceback.print_exc()

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Public API: Fundamental Data
# ─────────────────────────────────────────────────────────────────────────────


def get_fundamental_data(ticker: str) -> dict:
    """
    Fetch fundamental / company-level data for a given ticker.

    Data points fetched:
      - Company name, sector, industry, market cap
      - Trailing P/E, Forward P/E, PB ratio
      - EPS (TTM), Dividend yield
      - 52-week high/low
      - Quarterly earnings (revenue & net income)
      - Dividends history (last 5 payouts)
      - Corporate actions / splits (last 5 events)
      - Analyst recommendation

    Parameters
    ----------
    ticker : str  e.g. "RELIANCE.NS"

    Returns
    -------
    dict with all fundamental data or an error key on failure.
    """
    result = {
        "ticker": ticker,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "company_name": None,
        "sector": None,
        "industry": None,
        "market_cap": None,
        "pe_ratio_ttm": None,
        "pe_ratio_forward": None,
        "pb_ratio": None,
        "eps_ttm": None,
        "dividend_yield_pct": None,
        "week_52_high": None,
        "week_52_low": None,
        "analyst_recommendation": None,
        "quarterly_earnings": [],
        "dividends_recent": [],
        "stock_splits_recent": [],
        "error": None,
    }

    try:
        stock = yf.Ticker(ticker)
        info: dict = stock.info or {}

        # ── Company profile ────────────────────────────────────────────────
        result["company_name"]  = info.get("longName") or info.get("shortName")
        result["sector"]        = info.get("sector")
        result["industry"]      = info.get("industry")
        result["market_cap"]    = info.get("marketCap")

        # ── Valuation ratios ──────────────────────────────────────────────
        result["pe_ratio_ttm"]     = _safe_float(info.get("trailingPE"))
        result["pe_ratio_forward"] = _safe_float(info.get("forwardPE"))
        result["pb_ratio"]         = _safe_float(info.get("priceToBook"))
        result["eps_ttm"]          = _safe_float(info.get("trailingEps"))

        # Dividend yield comes as a decimal (0.02 = 2%) — convert to %
        raw_yield = info.get("dividendYield")
        result["dividend_yield_pct"] = (
            round(raw_yield * 100, 2) if raw_yield is not None else None
        )

        result["week_52_high"] = _safe_float(info.get("fiftyTwoWeekHigh"))
        result["week_52_low"]  = _safe_float(info.get("fiftyTwoWeekLow"))
        result["analyst_recommendation"] = info.get("recommendationKey", "N/A")

        # ── Quarterly earnings ─────────────────────────────────────────────
        try:
            earnings_q: pd.DataFrame = stock.quarterly_financials
            if earnings_q is not None and not earnings_q.empty:
                # Transpose so dates are rows; grab revenue & net income
                eq = earnings_q.T
                rows = []
                for date_idx, row in eq.iterrows():
                    rows.append({
                        "period": str(date_idx)[:10],
                        "total_revenue": _safe_float(row.get("Total Revenue")),
                        "net_income":    _safe_float(row.get("Net Income")),
                    })
                # Most recent 8 quarters (2 years)
                result["quarterly_earnings"] = rows[:8]
        except Exception as e_earn:
            result["quarterly_earnings"] = []
            print(f"[data_fetcher] ⚠️  Could not fetch quarterly earnings for {ticker}: {e_earn}")

        # ── Dividends history ─────────────────────────────────────────────
        try:
            divs: pd.Series = stock.dividends
            if divs is not None and not divs.empty:
                div_list = []
                for date_idx, amount in divs.tail(5).items():
                    div_list.append({
                        "date":   str(date_idx)[:10],
                        "amount": _safe_float(amount),
                    })
                result["dividends_recent"] = div_list
        except Exception as e_div:
            result["dividends_recent"] = []
            print(f"[data_fetcher] ⚠️  Could not fetch dividends for {ticker}: {e_div}")

        # ── Stock splits ───────────────────────────────────────────────────
        try:
            splits: pd.Series = stock.splits
            if splits is not None and not splits.empty:
                split_list = []
                for date_idx, ratio in splits.tail(5).items():
                    split_list.append({
                        "date":  str(date_idx)[:10],
                        "ratio": _safe_float(ratio),
                    })
                result["stock_splits_recent"] = split_list
        except Exception as e_split:
            result["stock_splits_recent"] = []
            print(f"[data_fetcher] ⚠️  Could not fetch splits for {ticker}: {e_split}")

    except Exception as exc:
        result["error"] = f"Fundamental data fetch failed for '{ticker}': {str(exc)}"
        traceback.print_exc()

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Quick self-test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    print("=" * 60)
    print("TECHNICAL DATA: RELIANCE.NS")
    print("=" * 60)
    tech = get_technical_data("RELIANCE.NS", period="3mo", interval="1d")
    # Print summary (skip the full ohlcv list for brevity)
    summary = {k: v for k, v in tech.items() if k != "ohlcv"}
    print(json.dumps(summary, indent=2, default=str))
    print(f"\nOHLCV rows returned: {len(tech.get('ohlcv', []))}")

    print("\n" + "=" * 60)
    print("FUNDAMENTAL DATA: TCS.NS")
    print("=" * 60)
    funda = get_fundamental_data("TCS.NS")
    print(json.dumps(funda, indent=2, default=str))
