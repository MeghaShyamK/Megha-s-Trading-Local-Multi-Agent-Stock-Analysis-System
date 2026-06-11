"""
tools/__init__.py
-----------------
Convenience re-exports for the tools package.
Import directly from sub-modules for full docstrings and type hints.
"""

from tools.watchlist import get_watchlist, get_index_symbol, add_custom_ticker
from tools.data_fetcher import get_technical_data, get_fundamental_data
from tools.options_fetcher import get_option_chain, get_pcr
from tools.scraper import get_broker_recommendations, get_market_news

__all__ = [
    "get_watchlist",
    "get_index_symbol",
    "add_custom_ticker",
    "get_technical_data",
    "get_fundamental_data",
    "get_option_chain",
    "get_pcr",
    "get_broker_recommendations",
    "get_market_news",
]
