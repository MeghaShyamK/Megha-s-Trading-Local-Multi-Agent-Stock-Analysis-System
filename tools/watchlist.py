"""
tools/watchlist.py
------------------
Tool 1: Watchlist & Index Constituents Loader

Responsibilities:
  - Load the local watchlist from data/watchlist.json
  - Optionally filter by index group (Nifty50 / BankNifty / Custom)
  - Return a clean list of ticker symbols

Usage:
  from tools.watchlist import get_watchlist
  tickers = get_watchlist(index="Nifty50")
"""

import json
import os
from typing import Optional

# Resolve the path to watchlist.json relative to this file
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WATCHLIST_PATH = os.path.join(_BASE_DIR, "data", "watchlist.json")


def get_watchlist(index: Optional[str] = None) -> list[str]:
    """
    Load tickers from the local watchlist.json file.

    Parameters
    ----------
    index : str, optional
        The index group to load: "Nifty50", "BankNifty", or "Custom".
        If None, returns ALL tickers across all groups (deduplicated).

    Returns
    -------
    list[str]
        A list of yfinance-compatible ticker symbols (e.g., "RELIANCE.NS").

    Raises
    ------
    FileNotFoundError
        If watchlist.json does not exist.
    KeyError
        If the requested index group does not exist in the watchlist.
    """
    if not os.path.exists(_WATCHLIST_PATH):
        raise FileNotFoundError(
            f"watchlist.json not found at: {_WATCHLIST_PATH}. "
            "Please ensure data/watchlist.json exists."
        )

    with open(_WATCHLIST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    watchlist: dict = data.get("watchlist", {})

    if index is not None:
        if index not in watchlist:
            available = list(watchlist.keys())
            raise KeyError(
                f"Index group '{index}' not found in watchlist. "
                f"Available groups: {available}"
            )
        return watchlist[index]

    # Return all tickers deduplicated while preserving order
    seen = set()
    all_tickers = []
    for group_tickers in watchlist.values():
        for ticker in group_tickers:
            if ticker not in seen:
                seen.add(ticker)
                all_tickers.append(ticker)

    return all_tickers


def get_index_symbol(index: str) -> str:
    """
    Get the yfinance symbol for a given index name.

    Parameters
    ----------
    index : str
        The friendly name, e.g., "Nifty50" or "BankNifty".

    Returns
    -------
    str
        The yfinance index symbol (e.g., "^NSEI").

    Raises
    ------
    KeyError
        If the index is not mapped in watchlist.json.
    """
    with open(_WATCHLIST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    indices: dict = data.get("indices", {})
    if index not in indices:
        available = list(indices.keys())
        raise KeyError(
            f"Index '{index}' not found. Available: {available}"
        )
    return indices[index]


def add_custom_ticker(ticker: str) -> None:
    """
    Append a ticker to the 'Custom' group in watchlist.json.

    Parameters
    ----------
    ticker : str
        A yfinance-compatible ticker symbol (e.g., "ZOMATO.NS").
    """
    with open(_WATCHLIST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    custom_list: list = data.setdefault("watchlist", {}).setdefault("Custom", [])
    if ticker not in custom_list:
        custom_list.append(ticker)
        with open(_WATCHLIST_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"[watchlist] ✅ Added '{ticker}' to Custom watchlist.")
    else:
        print(f"[watchlist] ℹ️  '{ticker}' already in Custom watchlist.")


# ─── Quick self-test ────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== Nifty 50 ===")
    nifty = get_watchlist("Nifty50")
    print(f"Count: {len(nifty)}")
    print(nifty[:5], "...")

    print("\n=== Bank Nifty ===")
    bnifty = get_watchlist("BankNifty")
    print(f"Count: {len(bnifty)}")
    print(bnifty)

    print("\n=== Index Symbol ===")
    print("Nifty50 symbol:", get_index_symbol("Nifty50"))
