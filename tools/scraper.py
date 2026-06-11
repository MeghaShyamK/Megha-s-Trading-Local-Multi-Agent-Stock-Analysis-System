"""
tools/scraper.py
----------------
Tool 5: Web Scraper for Daily Broker Recommendations & Financial News

Responsibilities:
  - Scrape "Top Broker Recommendations" from public financial news sites
      * Moneycontrol (primary)
      * Economic Times Markets (secondary)
      * Livemint (tertiary)
  - Scrape latest market news headlines
  - Parse and return structured, JSON-serialisable data

Design philosophy:
  - Each source has its own scraper function so failures are isolated
  - All scrapers use a rotating set of headers to reduce 403/block rate
  - Results are merged and deduplicated by ticker
  - Every function has robust error handling with meaningful error messages
  - The caller always gets a valid dict back, never an exception

Usage:
  from tools.scraper import get_broker_recommendations, get_market_news
  recs  = get_broker_recommendations()
  news  = get_market_news()
"""

from __future__ import annotations

import re
import traceback
from datetime import datetime
from typing import Optional
import random
import time

import requests
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────────────────────────────────────
# Request configuration
# ─────────────────────────────────────────────────────────────────────────────

_TIMEOUT = 12      # seconds per request
_MAX_RETRIES = 2   # retry count on transient errors

# A pool of real browser User-Agent strings to rotate
_USER_AGENTS = [
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) "
        "Gecko/20100101 Firefox/124.0"
    ),
]

# Action/call types we recognise in broker recommendations
_KNOWN_ACTIONS = {
    "buy", "strong buy", "add", "accumulate",
    "sell", "strong sell", "reduce",
    "hold", "neutral",
    "outperform", "underperform", "market perform",
}


def _get_headers(referer: str = "") -> dict:
    """Return randomised browser-like request headers."""
    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": referer or "https://www.google.com/",
        "Connection": "keep-alive",
        "DNT": "1",
    }


def _safe_get(url: str, referer: str = "") -> Optional[BeautifulSoup]:
    """
    Perform an HTTP GET request with retry logic.

    Returns a BeautifulSoup object on success, or None on failure.
    Errors are printed to stderr (not raised) so callers stay stable.
    """
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = requests.get(
                url,
                headers=_get_headers(referer),
                timeout=_TIMEOUT,
                allow_redirects=True,
            )
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else "?"
            print(f"[scraper] ⚠️  HTTP {status} on attempt {attempt}/{_MAX_RETRIES}: {url}")
            if status in (403, 429, 503):
                # Likely rate-limited — back off before retry
                time.sleep(2 * attempt)
        except requests.exceptions.Timeout:
            print(f"[scraper] ⚠️  Timeout on attempt {attempt}/{_MAX_RETRIES}: {url}")
        except requests.exceptions.ConnectionError:
            print(f"[scraper] ⚠️  Connection error on attempt {attempt}/{_MAX_RETRIES}: {url}")
        except Exception as e:
            print(f"[scraper] ❌ Unexpected error fetching {url}: {e}")
            break  # Don't retry on unexpected errors

    print(f"[scraper] ❌ Failed to fetch: {url}")
    return None


def _clean_ticker(raw: str) -> str:
    """Normalise a ticker string: strip whitespace, uppercase, remove .NS/.BO if present."""
    t = raw.strip().upper()
    t = re.sub(r"\.(NS|BO|NSE|BSE)$", "", t)
    return t


def _classify_action(text: str) -> str:
    """Map raw recommendation text to a canonical action label."""
    text_lower = text.lower().strip()
    for action in _KNOWN_ACTIONS:
        if action in text_lower:
            return action.title()
    return text.strip().title()


# ─────────────────────────────────────────────────────────────────────────────
# Source 1: Moneycontrol — Broker Recommendations
# ─────────────────────────────────────────────────────────────────────────────

_MC_RECO_URL = "https://www.moneycontrol.com/markets/indian-indices/top-stock-market-recommendations.html"


def _scrape_moneycontrol_recommendations() -> list[dict]:
    """
    Scrape broker stock recommendations from Moneycontrol.

    Returns a list of recommendation dicts:
      { ticker, company_name, action, target_price, stop_loss, broker, source }

    Returns empty list on failure.
    """
    results = []
    soup = _safe_get(_MC_RECO_URL, referer="https://www.moneycontrol.com/")

    if soup is None:
        print("[scraper] ℹ️  Moneycontrol recommendations unavailable.")
        return results

    try:
        # Moneycontrol renders recommendations in a table or card layout.
        # We look for common patterns — this may need updating if they
        # redesign their HTML.

        # Try structured table approach first
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 4:
                    try:
                        raw_name = cols[0].get_text(strip=True)
                        raw_action = cols[1].get_text(strip=True)
                        raw_target = cols[2].get_text(strip=True)

                        # Skip header rows or empty rows
                        if not raw_name or raw_name.lower() in ("company", "stock", "scrip"):
                            continue

                        results.append({
                            "ticker":       _clean_ticker(raw_name),
                            "company_name": raw_name,
                            "action":       _classify_action(raw_action),
                            "target_price": _parse_price(raw_target),
                            "stop_loss":    _parse_price(cols[3].get_text(strip=True)) if len(cols) > 3 else None,
                            "broker":       cols[4].get_text(strip=True) if len(cols) > 4 else "Moneycontrol",
                            "source":       "Moneycontrol",
                            "url":          _MC_RECO_URL,
                        })
                    except Exception:
                        continue

        # If tables yielded nothing, fall back to article/card scraping
        if not results:
            cards = soup.find_all(
                ["div", "article", "li"],
                class_=re.compile(r"(reco|recommend|pick|stock)", re.I),
            )
            for card in cards:
                text = card.get_text(" ", strip=True)
                # Look for patterns like "BUY Reliance at 2900, target 3100"
                match = re.search(
                    r"(buy|sell|hold|add|accumulate|reduce)\s+([A-Z][A-Za-z\s&]+)",
                    text, re.I
                )
                if match:
                    action = match.group(1)
                    name   = match.group(2).strip()
                    results.append({
                        "ticker":       _clean_ticker(name.split()[0]),
                        "company_name": name,
                        "action":       _classify_action(action),
                        "target_price": None,
                        "stop_loss":    None,
                        "broker":       "Moneycontrol",
                        "source":       "Moneycontrol",
                        "url":          _MC_RECO_URL,
                    })

    except Exception as e:
        print(f"[scraper] ❌ Moneycontrol parse error: {e}")
        traceback.print_exc()

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Source 2: Economic Times Markets — Broker Calls
# ─────────────────────────────────────────────────────────────────────────────

_ET_RECO_URL = "https://economictimes.indiatimes.com/markets/stocks/recos"


def _scrape_economic_times_recommendations() -> list[dict]:
    """
    Scrape broker call articles from Economic Times Markets section.

    Returns a list of recommendation dicts with best-effort data extraction.
    """
    results = []
    soup = _safe_get(_ET_RECO_URL, referer="https://economictimes.indiatimes.com/")

    if soup is None:
        print("[scraper] ℹ️  Economic Times recommendations unavailable.")
        return results

    try:
        # ET shows recommendations as article cards
        articles = soup.find_all("article") or soup.find_all(
            "div", class_=re.compile(r"(eachStory|article|story|card)", re.I)
        )

        for article in articles[:30]:  # Limit to avoid huge response sets
            headline_tag = article.find(["h2", "h3", "h4", "a"])
            if not headline_tag:
                continue

            headline = headline_tag.get_text(strip=True)
            link_tag = article.find("a", href=True)
            url = link_tag["href"] if link_tag else _ET_RECO_URL
            if url.startswith("/"):
                url = "https://economictimes.indiatimes.com" + url

            # Parse action and ticker from headline
            # Common ET headline format: "Buy Infosys; target price Rs 1800: Motilal Oswal"
            action_match = re.search(
                r"\b(buy|sell|hold|add|accumulate|reduce|strong buy|strong sell)\b",
                headline, re.I
            )
            # Try to extract ticker/company name — word after action keyword
            name_match = re.search(
                r"\b(?:buy|sell|hold|add|accumulate|reduce)\s+([A-Z][A-Za-z\s&]+?)(?:;|,|\bat\b|target|\Z)",
                headline, re.I
            )
            # Broker often appears after last colon
            broker = headline.rsplit(":", 1)[-1].strip() if ":" in headline else "Economic Times"

            # Target price
            target_match = re.search(r"(?:target|target price)[\s:]*(?:Rs\.?|₹)?\s*([\d,]+)", headline, re.I)
            target_price = _parse_price(target_match.group(1)) if target_match else None

            results.append({
                "ticker":       _clean_ticker(name_match.group(1).strip().split()[0]) if name_match else "UNKNOWN",
                "company_name": name_match.group(1).strip() if name_match else headline[:50],
                "action":       _classify_action(action_match.group(1)) if action_match else "See Article",
                "target_price": target_price,
                "stop_loss":    None,
                "broker":       broker[:60],
                "source":       "Economic Times",
                "url":          url,
                "headline":     headline,
            })

    except Exception as e:
        print(f"[scraper] ❌ Economic Times parse error: {e}")
        traceback.print_exc()

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Source 3: Livemint — Stock Recommendations
# ─────────────────────────────────────────────────────────────────────────────

_LIVEMINT_URL = "https://www.livemint.com/market/stock-market-news"


def _scrape_livemint_recommendations() -> list[dict]:
    """
    Scrape stock recommendation headlines from Livemint.

    Returns a list of headline-level recommendation dicts.
    """
    results = []
    soup = _safe_get(_LIVEMINT_URL, referer="https://www.livemint.com/")

    if soup is None:
        print("[scraper] ℹ️  Livemint unavailable.")
        return results

    try:
        # Livemint uses <h2> tags in a card grid
        items = soup.find_all(["h2", "h3"], limit=50)
        for item in items:
            text = item.get_text(strip=True)
            # Only collect items that mention a recommendation action
            if not re.search(
                r"\b(buy|sell|hold|add|accumulate|reduce|target)\b", text, re.I
            ):
                continue

            link_tag = item.find("a", href=True) or item.parent.find("a", href=True)
            url = ""
            if link_tag:
                url = link_tag.get("href", "")
                if url.startswith("/"):
                    url = "https://www.livemint.com" + url

            action_match = re.search(
                r"\b(buy|sell|hold|add|accumulate|reduce)\b", text, re.I
            )
            name_match = re.search(
                r"\b(?:buy|sell|hold|add|accumulate|reduce)\s+([A-Z][A-Za-z\s&]+?)(?:\s+at|\s+for|;|,|\Z)",
                text, re.I
            )

            results.append({
                "ticker":       _clean_ticker(name_match.group(1).strip().split()[0]) if name_match else "UNKNOWN",
                "company_name": name_match.group(1).strip() if name_match else text[:60],
                "action":       _classify_action(action_match.group(1)) if action_match else "See Article",
                "target_price": None,
                "stop_loss":    None,
                "broker":       "Livemint",
                "source":       "Livemint",
                "url":          url,
                "headline":     text,
            })

    except Exception as e:
        print(f"[scraper] ❌ Livemint parse error: {e}")
        traceback.print_exc()

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Price parser utility
# ─────────────────────────────────────────────────────────────────────────────

def _parse_price(raw: str) -> Optional[float]:
    """Extract a float price from strings like '₹2,900', 'Rs 3100', '2900.50'."""
    if not raw:
        return None
    cleaned = re.sub(r"[₹,\s]|Rs\.?", "", raw, flags=re.I).strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Market News Scraper
# ─────────────────────────────────────────────────────────────────────────────

_NEWS_SOURCES = [
    {
        "name": "Economic Times",
        "url": "https://economictimes.indiatimes.com/markets/stocks/news",
        "referer": "https://economictimes.indiatimes.com/",
        "selectors": ["article", "div.eachStory", "div.story"],
    },
    {
        "name": "Moneycontrol",
        "url": "https://www.moneycontrol.com/news/business/markets/",
        "referer": "https://www.moneycontrol.com/",
        "selectors": ["li.clearfix", "div.fleft.news-details"],
    },
]


def _scrape_news_from_source(source: dict) -> list[dict]:
    """Scrape headlines from a single news source config."""
    headlines = []
    soup = _safe_get(source["url"], referer=source["referer"])
    if soup is None:
        return headlines

    try:
        for selector in source["selectors"]:
            # Support both tag and tag.class formats
            if "." in selector:
                tag, cls = selector.split(".", 1)
                items = soup.find_all(tag, class_=cls) if tag else soup.find_all(class_=cls)
            else:
                items = soup.find_all(selector)

            for item in items[:20]:
                h_tag = item.find(["h2", "h3", "h4", "a"])
                if not h_tag:
                    continue
                text = h_tag.get_text(strip=True)
                if not text or len(text) < 15:
                    continue
                link = h_tag.get("href") if h_tag.name == "a" else (
                    item.find("a", href=True) or {}).get("href", "")
                if link and link.startswith("/"):
                    link = source["url"].split("/")[0] + "//" + source["url"].split("/")[2] + link

                headlines.append({
                    "headline": text,
                    "source":   source["name"],
                    "url":      link or source["url"],
                })

            if headlines:
                break  # Stop trying selectors once we found results

    except Exception as e:
        print(f"[scraper] ❌ News parse error from {source['name']}: {e}")

    return headlines


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def get_broker_recommendations(max_results: int = 20) -> dict:
    """
    Aggregate broker recommendations from multiple financial news sources.

    Strategy:
      1. Try Moneycontrol (structured table/card)
      2. Try Economic Times (article headlines)
      3. Try Livemint (article headlines)
      4. Merge results, deduplicate by ticker (keep the first occurrence)
      5. Filter out UNKNOWN tickers
      6. Return top `max_results`

    Parameters
    ----------
    max_results : int   Maximum number of recommendations to return (default 20)

    Returns
    -------
    dict with keys:
      fetched_at      : ISO timestamp
      total_found     : int
      recommendations : list[dict] — each has ticker, company_name, action,
                        target_price, stop_loss, broker, source, url
      sources_tried   : list[str]
      errors          : list[str]
    """
    result = {
        "fetched_at":       datetime.utcnow().isoformat() + "Z",
        "total_found":      0,
        "recommendations":  [],
        "sources_tried":    [],
        "errors":           [],
    }

    all_recs: list[dict] = []

    # ── Source 1: Moneycontrol ─────────────────────────────────────────────
    try:
        result["sources_tried"].append("Moneycontrol")
        mc_recs = _scrape_moneycontrol_recommendations()
        all_recs.extend(mc_recs)
        print(f"[scraper] ✅ Moneycontrol: {len(mc_recs)} recommendations")
    except Exception as e:
        result["errors"].append(f"Moneycontrol: {str(e)}")

    # ── Source 2: Economic Times ───────────────────────────────────────────
    try:
        result["sources_tried"].append("Economic Times")
        et_recs = _scrape_economic_times_recommendations()
        all_recs.extend(et_recs)
        print(f"[scraper] ✅ Economic Times: {len(et_recs)} recommendations")
    except Exception as e:
        result["errors"].append(f"Economic Times: {str(e)}")

    # ── Source 3: Livemint ────────────────────────────────────────────────
    try:
        result["sources_tried"].append("Livemint")
        lm_recs = _scrape_livemint_recommendations()
        all_recs.extend(lm_recs)
        print(f"[scraper] ✅ Livemint: {len(lm_recs)} recommendations")
    except Exception as e:
        result["errors"].append(f"Livemint: {str(e)}")

    # ── Dedup by ticker (first occurrence wins) ───────────────────────────
    seen_tickers: set[str] = set()
    deduped: list[dict] = []
    for rec in all_recs:
        ticker = rec.get("ticker", "UNKNOWN")
        if ticker == "UNKNOWN" or len(ticker) < 2:
            continue
        if ticker not in seen_tickers:
            seen_tickers.add(ticker)
            deduped.append(rec)

    result["recommendations"] = deduped[:max_results]
    result["total_found"]     = len(deduped)

    if not deduped:
        result["errors"].append(
            "No recommendations could be scraped. "
            "Financial sites may have changed their HTML structure or are blocking requests. "
            "Consider using their official APIs or RSS feeds as an alternative."
        )

    return result


def get_market_news(max_headlines: int = 15) -> dict:
    """
    Fetch latest market news headlines from multiple sources.

    Parameters
    ----------
    max_headlines : int   Max total headlines to return (default 15)

    Returns
    -------
    dict with keys:
      fetched_at : ISO timestamp
      headlines  : list[dict] — each has headline, source, url
      error      : str | None
    """
    result = {
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "headlines":  [],
        "error":      None,
    }

    all_headlines = []
    for source in _NEWS_SOURCES:
        try:
            headlines = _scrape_news_from_source(source)
            all_headlines.extend(headlines)
            print(f"[scraper] ✅ News from {source['name']}: {len(headlines)} headlines")
        except Exception as e:
            print(f"[scraper] ❌ News error from {source['name']}: {e}")

    # Deduplicate by headline text
    seen = set()
    unique = []
    for h in all_headlines:
        key = h["headline"][:80].lower()
        if key not in seen:
            seen.add(key)
            unique.append(h)

    result["headlines"] = unique[:max_headlines]

    if not result["headlines"]:
        result["error"] = (
            "Could not fetch any news headlines. "
            "Check your internet connection or try later."
        )

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Quick self-test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    print("=" * 60)
    print("BROKER RECOMMENDATIONS (max 10)")
    print("=" * 60)
    recs = get_broker_recommendations(max_results=10)
    print(f"Sources tried: {recs['sources_tried']}")
    print(f"Total found:   {recs['total_found']}")
    print(f"Errors:        {recs['errors']}")
    print("\nTop recommendations:")
    for r in recs["recommendations"][:5]:
        print(f"  {r['ticker']:15s} | {r['action']:12s} | Target: {r.get('target_price')} | {r['broker']}")

    print("\n" + "=" * 60)
    print("MARKET NEWS (max 5)")
    print("=" * 60)
    news = get_market_news(max_headlines=5)
    for h in news["headlines"]:
        print(f"  [{h['source']}] {h['headline'][:80]}")
