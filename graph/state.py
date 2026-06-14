"""
graph/state.py
--------------
Shared state schema for the LangGraph Multi-Agent Trading Pipeline.

TradingState is a TypedDict passed between every node in the graph.
Each agent reads from and writes to specific keys in this shared state.

Key design decisions:
  - All data fields default to empty dict/list so agents can safely read
    without defensive checks for missing keys.
  - `human_approved` drives the HITL gate — the graph pauses before
    the coordinator node until this is set to True.
  - `messages` stores the full chat history for the Streamlit chat tab.
"""

from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict


class TradingState(TypedDict, total=False):
    """
    Shared state that flows through the entire LangGraph pipeline.

    Fields
    ------
    ticker          : NSE-compatible ticker symbol, e.g. "RELIANCE.NS"
    period          : yfinance period string, e.g. "3mo"
    interval        : yfinance interval string, e.g. "1d"
    image_b64       : Base64-encoded chart image string (optional, for Vision Agent)

    --- Raw tool outputs (Phase 1) ---
    technical_data      : Output of tools.data_fetcher.get_technical_data()
    fundamental_data    : Output of tools.data_fetcher.get_fundamental_data()
    options_data        : Output of tools.options_fetcher.get_option_chain()
    broker_recs         : Output of tools.scraper.get_broker_recommendations()
    market_news         : Output of tools.scraper.get_market_news()

    --- Agent analysis outputs (Phase 2) ---
    technical_analysis  : Structured output from TechnicalAgent
    fundamental_analysis: Structured output from FundamentalAgent
    risk_analysis       : Structured output from RiskAgent
    vision_analysis     : Structured output from VisionAgent (may be empty if no image)

    --- Final output ---
    final_report        : Complete trade recommendation from CoordinatorAgent
    human_approved      : HITL gate — True if user approved the report, False to reject
    rejection_reason    : Optional reason if human rejected the report

    --- Chat ---
    messages            : List of chat message dicts {role: str, content: str}
    chat_query          : Latest user chat query routed to the pipeline
    """

    # ── Input ────────────────────────────────────────────────────────────────
    ticker: str
    period: str
    interval: str
    image_b64: Optional[str]

    # ── Raw tool data ─────────────────────────────────────────────────────────
    technical_data: dict
    fundamental_data: dict
    options_data: dict
    broker_recs: dict
    market_news: dict

    # ── Agent outputs ─────────────────────────────────────────────────────────
    technical_analysis: dict
    fundamental_analysis: dict
    risk_analysis: dict
    vision_analysis: dict

    # ── Final recommendation ──────────────────────────────────────────────────
    final_report: dict
    human_approved: bool
    rejection_reason: Optional[str]

    # ── Chat ──────────────────────────────────────────────────────────────────
    messages: list
    chat_query: Optional[str]


def initial_state(
    ticker: str,
    period: str = "3mo",
    interval: str = "1d",
    image_b64: Optional[str] = None,
    chat_query: Optional[str] = None,
) -> TradingState:
    """
    Factory function — returns a fresh TradingState with safe defaults.

    Parameters
    ----------
    ticker      : NSE ticker, e.g. "RELIANCE.NS"
    period      : yfinance period string (default: "3mo")
    interval    : yfinance interval string (default: "1d")
    image_b64   : Optional Base64 chart image for vision agent
    chat_query  : Optional user query string (for chat tab)

    Returns
    -------
    TradingState with all keys initialised to safe defaults.
    """
    return TradingState(
        ticker=ticker,
        period=period,
        interval=interval,
        image_b64=image_b64,
        technical_data={},
        fundamental_data={},
        options_data={},
        broker_recs={},
        market_news={},
        technical_analysis={},
        fundamental_analysis={},
        risk_analysis={},
        vision_analysis={},
        final_report={},
        human_approved=False,
        rejection_reason=None,
        messages=[],
        chat_query=chat_query,
    )
