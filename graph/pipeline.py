"""
graph/pipeline.py
------------------
LangGraph Multi-Agent Pipeline — State Machine Definition (Phase 2)

Graph Structure:
  START
    └─→ [fetch_data]          Fetches all raw data from tools (tools/ package)
         └─→ [technical]      Technical analysis agent
         └─→ [fundamental]    Fundamental analysis agent
         └─→ [risk]           Risk / Devil's Advocate agent
         └─→ [vision]         Vision chart agent (skips if no image)
              └─→ ┐
  [interrupt_before="coordinator"]   ← HITL gate pauses here
                   ↓ (after human approval)
              [coordinator]   Synthesise final trade report
                   └─→ END

Usage:
  from graph.pipeline import run_pipeline, resume_pipeline

  # Start a new analysis (returns state at HITL interrupt point)
  state, thread_id = run_pipeline("RELIANCE.NS")

  # After human approval, resume to get final report
  final_state = resume_pipeline(thread_id, approved=True)
"""

from __future__ import annotations

import uuid
from typing import Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from graph.state import TradingState, initial_state
from agents import (
    technical_agent_node,
    fundamental_agent_node,
    risk_agent_node,
    vision_agent_node,
    coordinator_agent_node,
)
from tools.data_fetcher import get_technical_data, get_fundamental_data
from tools.options_fetcher import get_option_chain
from tools.scraper import get_broker_recommendations, get_market_news

# ─────────────────────────────────────────────────────────────────────────────
# Data Fetch Node — calls all Phase 1 tools
# ─────────────────────────────────────────────────────────────────────────────

def fetch_data_node(state: TradingState) -> dict:
    """
    Fetches all raw market data for the ticker before agents run.

    Calls:
      - get_technical_data()      → OHLCV + indicators
      - get_fundamental_data()    → P/E, earnings, dividends
      - get_option_chain()        → NSE option chain, PCR, max-pain
      - get_broker_recommendations() → broker calls from Moneycontrol/ET/Livemint
      - get_market_news()         → latest market headlines

    Writes: technical_data, fundamental_data, options_data, broker_recs, market_news
    """
    ticker = state.get("ticker", "")
    period = state.get("period", "3mo")
    interval = state.get("interval", "1d")

    print(f"\n[pipeline] 🔄 Fetching data for {ticker}...")

    # Derive NSE options symbol (strip .NS/.BO suffix)
    import re
    options_symbol = re.sub(r"\.(NS|BO)$", "", ticker.upper())

    # Fetch all data sources in parallel-ish (sequential for simplicity)
    tech_data = get_technical_data(ticker, period=period, interval=interval)
    print(f"[pipeline] ✅ Technical data: price={tech_data.get('latest_price')}")

    funda_data = get_fundamental_data(ticker)
    print(f"[pipeline] ✅ Fundamental data: company={funda_data.get('company_name')}")

    options_data = get_option_chain(options_symbol)
    pcr = options_data.get("pcr", {}).get("pcr", "N/A")
    print(f"[pipeline] ✅ Options data: PCR={pcr}")

    broker_recs = get_broker_recommendations(max_results=20)
    print(f"[pipeline] ✅ Broker recs: {broker_recs.get('total_found', 0)} found")

    market_news = get_market_news(max_headlines=10)
    print(f"[pipeline] ✅ Market news: {len(market_news.get('headlines', []))} headlines")

    return {
        "technical_data": tech_data,
        "fundamental_data": funda_data,
        "options_data": options_data,
        "broker_recs": broker_recs,
        "market_news": market_news,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Graph builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_graph() -> StateGraph:
    """Build and compile the LangGraph StateGraph with HITL interrupt."""
    builder = StateGraph(TradingState)

    # ── Register nodes ────────────────────────────────────────────────────────
    builder.add_node("fetch_data",    fetch_data_node)
    builder.add_node("technical",     technical_agent_node)
    builder.add_node("fundamental",   fundamental_agent_node)
    builder.add_node("risk",          risk_agent_node)
    builder.add_node("vision",        vision_agent_node)
    builder.add_node("coordinator",   coordinator_agent_node)

    # ── Entry point ───────────────────────────────────────────────────────────
    builder.set_entry_point("fetch_data")

    # ── Edges: fetch_data → all analysis agents in parallel ──────────────────
    builder.add_edge("fetch_data", "technical")
    builder.add_edge("fetch_data", "fundamental")
    builder.add_edge("fetch_data", "risk")
    builder.add_edge("fetch_data", "vision")

    # ── Edges: all agents → coordinator ──────────────────────────────────────
    builder.add_edge("technical",   "coordinator")
    builder.add_edge("fundamental", "coordinator")
    builder.add_edge("risk",        "coordinator")
    builder.add_edge("vision",      "coordinator")

    # ── Terminal edge ─────────────────────────────────────────────────────────
    builder.add_edge("coordinator", END)

    return builder


# ─────────────────────────────────────────────────────────────────────────────
# Compiled graph with memory checkpointer (enables HITL interrupts)
# ─────────────────────────────────────────────────────────────────────────────

_checkpointer = MemorySaver()

_compiled_graph = _build_graph().compile(
    checkpointer=_checkpointer,
    interrupt_before=["coordinator"],   # ← HITL gate: pause before coordinator
)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(
    ticker: str,
    period: str = "3mo",
    interval: str = "1d",
    image_b64: Optional[str] = None,
    chat_query: Optional[str] = None,
) -> tuple[dict, str]:
    """
    Start a new analysis pipeline for the given ticker.

    The graph will run through:
      fetch_data → technical + fundamental + risk + vision agents

    Then it PAUSES at the coordinator node (HITL interrupt_before).
    The caller must inspect the returned state, then call resume_pipeline()
    to proceed after human approval.

    Parameters
    ----------
    ticker      : NSE ticker, e.g. "RELIANCE.NS"
    period      : yfinance period (default "3mo")
    interval    : yfinance interval (default "1d")
    image_b64   : Optional Base64 chart image for vision agent
    chat_query  : Optional chat query text

    Returns
    -------
    (state: dict, thread_id: str)
      state     — the current TradingState at the interrupt point
      thread_id — use this to resume the pipeline via resume_pipeline()
    """
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    state = initial_state(
        ticker=ticker,
        period=period,
        interval=interval,
        image_b64=image_b64,
        chat_query=chat_query,
    )

    print(f"\n[pipeline] 🚀 Starting pipeline for {ticker} (thread: {thread_id[:8]}...)")

    # Run graph until HITL interrupt
    final_state = _compiled_graph.invoke(state, config=config)

    print(f"[pipeline] ⏸️  Pipeline paused for HITL review (thread: {thread_id[:8]}...)")

    return final_state, thread_id


def resume_pipeline(thread_id: str, approved: bool, rejection_reason: str = "") -> dict:
    """
    Resume the pipeline after the HITL interrupt gate.

    Parameters
    ----------
    thread_id        : Thread ID returned by run_pipeline()
    approved         : True = user approved, False = rejected
    rejection_reason : Optional reason if rejected

    Returns
    -------
    dict — the final TradingState with the completed report (or rejection note)
    """
    config = {"configurable": {"thread_id": thread_id}}

    # Update the state with HITL decision
    state_update = {
        "human_approved": approved,
        "rejection_reason": rejection_reason if not approved else None,
    }

    if approved:
        print(f"[pipeline] ✅ Human approved — resuming coordinator for thread {thread_id[:8]}...")
    else:
        print(f"[pipeline] ❌ Human rejected — skipping coordinator for thread {thread_id[:8]}...")

    # Resume the graph from the interrupt point
    final_state = _compiled_graph.invoke(state_update, config=config)

    print(f"[pipeline] 🏁 Pipeline complete for thread {thread_id[:8]}.")
    return final_state


def get_pipeline_state(thread_id: str) -> Optional[dict]:
    """
    Retrieve the current state of a pipeline by thread ID.
    Useful for checking the state at the HITL interrupt point.

    Parameters
    ----------
    thread_id : str   Thread ID returned by run_pipeline()

    Returns
    -------
    dict | None — The current state dict, or None if thread not found.
    """
    config = {"configurable": {"thread_id": thread_id}}
    try:
        snapshot = _compiled_graph.get_state(config)
        return dict(snapshot.values) if snapshot else None
    except Exception as e:
        print(f"[pipeline] ❌ Could not retrieve state for thread {thread_id}: {e}")
        return None
