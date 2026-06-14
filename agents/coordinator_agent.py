"""
agents/coordinator_agent.py
-----------------------------
Coordinator Agent — Final Trade Report Synthesizer (Phase 2)

Responsibilities:
  - Read all three agent outputs (technical, fundamental, risk) from state
  - Read vision analysis (if available) from state
  - Read broker recommendations from state to check for overlap
  - Synthesise a final, structured trade recommendation JSON
  - This node is placed BEHIND the HITL interrupt gate in the graph

The graph pauses BEFORE calling this node (interrupt_before=["coordinator"]).
The Streamlit UI presents the draft analyses and asks the user to Approve/Reject.
If approved, the graph resumes and this node runs to produce the final report.
If rejected, the graph sets human_approved=False and returns without running.

Output schema:
  {
    "ticker":           str,
    "action":           "Buy" | "Sell" | "Hold" | "Avoid",
    "entry_price":      float | None,
    "target_price":     float | None,
    "stop_loss":        float | None,
    "conviction_score": int,          # 0-10
    "time_horizon":     "Intraday" | "Swing (1-2 weeks)" | "Positional (1-3 months)" | "Long Term",
    "broker_overlap":   bool,         # True if any broker also recommends this
    "summary":          str,
    "risk_reward_ratio": float | None,
    "error":            str | None
  }
"""

from __future__ import annotations

import json
import re
import traceback
from typing import Optional

from langchain_ollama import OllamaLLM

from graph.state import TradingState

# ─────────────────────────────────────────────────────────────────────────────
# LLM instance
# ─────────────────────────────────────────────────────────────────────────────

_LLM: OllamaLLM | None = None


def _get_llm() -> OllamaLLM:
    global _LLM
    if _LLM is None:
        _LLM = OllamaLLM(model="qwen2.5:7b", temperature=0.1)
    return _LLM


# ─────────────────────────────────────────────────────────────────────────────
# Broker overlap checker
# ─────────────────────────────────────────────────────────────────────────────

def _check_broker_overlap(ticker: str, broker_recs: dict) -> tuple[bool, list[dict]]:
    """
    Check if any broker also recommends the same ticker.

    Returns (has_overlap: bool, matching_recs: list[dict])
    """
    recs = broker_recs.get("recommendations", [])
    # Normalise: remove .NS/.BO suffix for comparison
    clean_ticker = re.sub(r"\.(NS|BO)$", "", ticker.upper())

    matches = []
    for rec in recs:
        rec_ticker = re.sub(r"\.(NS|BO)$", "", rec.get("ticker", "").upper())
        if rec_ticker == clean_ticker:
            matches.append(rec)

    return len(matches) > 0, matches


# ─────────────────────────────────────────────────────────────────────────────
# Prompt builder
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are the Chief Investment Officer of a quantitative trading desk specialising in Indian equities.
You have received analysis from three specialist agents: Technical, Fundamental, and Risk.
Your job is to synthesise all inputs into a final, actionable trade recommendation.

Be decisive. Give a clear action with a specific entry price, target, and stop-loss.
The conviction score (0-10) reflects your overall confidence: 8-10 = high conviction, 4-7 = moderate, 0-3 = low conviction.

ALWAYS respond with ONLY a valid JSON object — no prose, no markdown, no explanation outside the JSON:
{
  "action": "<Buy|Sell|Hold|Avoid>",
  "entry_price": <number or null>,
  "target_price": <number or null>,
  "stop_loss": <number or null>,
  "conviction_score": <integer 0-10>,
  "time_horizon": "<Intraday|Swing (1-2 weeks)|Positional (1-3 months)|Long Term>",
  "summary": "<3-4 sentence comprehensive recommendation rationale>"
}"""


def _build_prompt(state: TradingState, broker_matches: list[dict]) -> str:
    """Build the coordinator synthesis prompt."""
    ticker = state.get("ticker", "UNKNOWN")
    tech_analysis = state.get("technical_analysis", {})
    funda_analysis = state.get("fundamental_analysis", {})
    risk_analysis = state.get("risk_analysis", {})
    vision_analysis = state.get("vision_analysis", {})
    tech_data = state.get("technical_data", {})

    price = tech_data.get("latest_price", "N/A")

    # Format broker overlaps
    if broker_matches:
        broker_str = "; ".join(
            f"{b.get('broker', '?')}: {b.get('action', '?')}, Target ₹{b.get('target_price', 'N/A')}"
            for b in broker_matches[:3]
        )
    else:
        broker_str = "No broker recommendations found for this ticker."

    # Vision analysis
    vision_str = "Not available (no chart uploaded)."
    if vision_analysis and vision_analysis.get("chart_pattern") != "No image provided":
        vision_str = (
            f"Pattern: {vision_analysis.get('chart_pattern', 'N/A')} | "
            f"Trend: {vision_analysis.get('trend', 'N/A')} | "
            f"{vision_analysis.get('commentary', '')}"
        )

    prompt = f"""Synthesise the following analyses for {ticker} into a final trade recommendation.

CURRENT PRICE: {price}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TECHNICAL ANALYSIS:
  Trend:    {tech_analysis.get('trend', 'N/A')}
  Signal:   {tech_analysis.get('signal', 'N/A')}
  Strength: {tech_analysis.get('strength', 'N/A')}
  Support:  {tech_analysis.get('key_levels', {}).get('support', 'N/A')}
  Resistance:{tech_analysis.get('key_levels', {}).get('resistance', 'N/A')}
  Reasoning: {tech_analysis.get('reasoning', 'N/A')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FUNDAMENTAL ANALYSIS:
  Valuation: {funda_analysis.get('valuation_verdict', 'N/A')}
  Growth:    {funda_analysis.get('growth_signal', 'N/A')}
  Red Flags: {'; '.join(funda_analysis.get('red_flags', [])) or 'None'}
  Positives: {'; '.join(funda_analysis.get('positives', [])) or 'None'}
  Reasoning: {funda_analysis.get('reasoning', 'N/A')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RISK ASSESSMENT (Devil's Advocate):
  Risk Level:      {risk_analysis.get('risk_level', 'N/A')}
  Volatility Flag: {risk_analysis.get('volatility_flag', 'N/A')}
  Risks:           {'; '.join(risk_analysis.get('reasons_to_avoid', [])) or 'None'}
  Mitigants:       {'; '.join(risk_analysis.get('mitigating_factors', [])) or 'None'}
  Suggested Stop:  {risk_analysis.get('stop_loss_suggestion', 'N/A')}
  Reasoning:       {risk_analysis.get('reasoning', 'N/A')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VISION ANALYSIS (Chart):
  {vision_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BROKER RECOMMENDATIONS (external validation):
  {broker_str}

Now synthesise all the above into a single final trade recommendation JSON."""

    return prompt


# ─────────────────────────────────────────────────────────────────────────────
# JSON parser
# ─────────────────────────────────────────────────────────────────────────────

def _parse_llm_json(raw_output: str) -> dict:
    text = re.sub(r"```(?:json)?", "", raw_output).strip()
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group())
    raise ValueError(f"No JSON object found in LLM output: {raw_output[:200]}")


# ─────────────────────────────────────────────────────────────────────────────
# Agent node (called by LangGraph — behind HITL gate)
# ─────────────────────────────────────────────────────────────────────────────

def coordinator_agent_node(state: TradingState) -> dict:
    """
    LangGraph node function for the Coordinator Agent.

    This node runs ONLY AFTER human approval (post HITL interrupt).
    If human_approved is False, it returns without producing a report.

    Reads  : all agent analysis fields from state
    Writes : state["final_report"]
    """
    ticker = state.get("ticker", "UNKNOWN")

    # ── HITL gate check ──────────────────────────────────────────────────────
    if not state.get("human_approved", False):
        print(f"[coordinator_agent] ⏸️  Waiting for human approval for {ticker}.")
        return {"final_report": {"status": "awaiting_approval", "ticker": ticker}}

    result = {
        "ticker": ticker,
        "action": "Hold",
        "entry_price": None,
        "target_price": None,
        "stop_loss": None,
        "conviction_score": 5,
        "time_horizon": "Swing (1-2 weeks)",
        "broker_overlap": False,
        "summary": "Final report could not be generated.",
        "risk_reward_ratio": None,
        "error": None,
    }

    try:
        # Check broker overlap
        broker_overlap, broker_matches = _check_broker_overlap(
            ticker, state.get("broker_recs", {})
        )
        result["broker_overlap"] = broker_overlap

        # Build and run the synthesis prompt
        llm = _get_llm()
        full_prompt = f"{_SYSTEM_PROMPT}\n\n{_build_prompt(state, broker_matches)}"
        raw_output = llm.invoke(full_prompt)
        parsed = _parse_llm_json(raw_output)

        result.update(parsed)
        result["ticker"] = ticker  # Ensure ticker is not overwritten
        result["broker_overlap"] = broker_overlap
        result["error"] = None

        # Calculate risk/reward ratio
        entry = result.get("entry_price")
        target = result.get("target_price")
        stop = result.get("stop_loss")
        if all(v is not None for v in [entry, target, stop]) and (entry - stop) != 0:
            rr = round(abs(target - entry) / abs(entry - stop), 2)
            result["risk_reward_ratio"] = rr

        print(
            f"[coordinator_agent] ✅ Final report for {ticker}: "
            f"{result['action']} | Conviction: {result['conviction_score']}/10 | "
            f"R:R {result.get('risk_reward_ratio', 'N/A')}"
        )

    except json.JSONDecodeError as e:
        result["error"] = f"JSON parse error: {e}"
        print(f"[coordinator_agent] ❌ JSON parse error: {e}")
    except Exception as e:
        result["error"] = f"Agent error: {str(e)}"
        traceback.print_exc()

    return {"final_report": result}
