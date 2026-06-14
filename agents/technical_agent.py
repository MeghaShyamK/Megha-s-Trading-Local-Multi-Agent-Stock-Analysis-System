"""
agents/technical_agent.py
--------------------------
Technical Analysis Agent (Phase 2)

Responsibilities:
  - Read raw OHLCV + indicator data from TradingState.technical_data
  - Build a structured prompt summarising EMA, RSI, MACD, Fibonacci levels
  - Use OllamaLLM (qwen2.5:7b) to reason about trend & momentum
  - Parse the LLM output into a clean structured dict
  - Write the result to TradingState.technical_analysis

Output schema:
  {
    "trend":      "Bullish" | "Bearish" | "Sideways",
    "signal":     "Buy" | "Sell" | "Hold" | "Watch",
    "strength":   "Strong" | "Moderate" | "Weak",
    "key_levels": { "support": float, "resistance": float },
    "reasoning":  str,
    "error":      str | None
  }
"""

from __future__ import annotations

import json
import re
import traceback

from langchain_ollama import OllamaLLM

from graph.state import TradingState

# ─────────────────────────────────────────────────────────────────────────────
# LLM instance — shared, lazy-loaded
# ─────────────────────────────────────────────────────────────────────────────

_LLM: OllamaLLM | None = None


def _get_llm() -> OllamaLLM:
    global _LLM
    if _LLM is None:
        _LLM = OllamaLLM(model="qwen2.5:7b", temperature=0.1)
    return _LLM


# ─────────────────────────────────────────────────────────────────────────────
# Prompt builder
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an expert technical analyst for Indian equity markets.
You will be given the latest price and technical indicator data for a stock.
Your job is to assess trend direction, momentum, and key price levels.

ALWAYS respond with ONLY a valid JSON object — no prose, no markdown, no explanation outside the JSON.
The JSON must have exactly these keys:
{
  "trend": "<Bullish|Bearish|Sideways>",
  "signal": "<Buy|Sell|Hold|Watch>",
  "strength": "<Strong|Moderate|Weak>",
  "key_levels": {"support": <number>, "resistance": <number>},
  "reasoning": "<2-3 sentence explanation of your analysis>"
}"""


def _build_prompt(tech_data: dict) -> str:
    """Build a concise technical summary prompt from raw indicator data."""
    indicators = tech_data.get("indicators", {})
    fib = indicators.get("Fibonacci_60d", {})
    ticker = tech_data.get("ticker", "UNKNOWN")
    price = tech_data.get("latest_price", "N/A")

    fib_str = ", ".join(f"{k}: {v}" for k, v in fib.items()) if fib else "N/A"

    prompt = f"""Analyze the following technical data for {ticker}:

CURRENT PRICE: {price}

MOVING AVERAGES:
  EMA 20:  {indicators.get('EMA_20', 'N/A')}
  EMA 50:  {indicators.get('EMA_50', 'N/A')}
  EMA 200: {indicators.get('EMA_200', 'N/A')}

MOMENTUM:
  RSI (14):        {indicators.get('RSI_14', 'N/A')}
  MACD:            {indicators.get('MACD', 'N/A')}
  MACD Signal:     {indicators.get('MACD_Signal', 'N/A')}
  MACD Histogram:  {indicators.get('MACD_Histogram', 'N/A')}

FIBONACCI RETRACEMENT (60-day swing):
  Swing High: {indicators.get('swing_high_60d', 'N/A')}
  Swing Low:  {indicators.get('swing_low_60d', 'N/A')}
  Levels: {fib_str}

Based on this data, provide your technical analysis as a JSON object."""

    return prompt


# ─────────────────────────────────────────────────────────────────────────────
# JSON parser (LLM output can be messy)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_llm_json(raw_output: str) -> dict:
    """
    Extract and parse a JSON object from the LLM's raw string response.
    Handles cases where the LLM wraps the JSON in markdown code fences.
    """
    # Strip markdown code fences if present
    text = re.sub(r"```(?:json)?", "", raw_output).strip()

    # Try to extract the JSON block
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group())

    raise ValueError(f"No JSON object found in LLM output: {raw_output[:200]}")


# ─────────────────────────────────────────────────────────────────────────────
# Agent node (called by LangGraph)
# ─────────────────────────────────────────────────────────────────────────────

def technical_agent_node(state: TradingState) -> dict:
    """
    LangGraph node function for the Technical Analysis Agent.

    Reads  : state["technical_data"]
    Writes : state["technical_analysis"]

    Parameters
    ----------
    state : TradingState

    Returns
    -------
    dict   Partial state update: { "technical_analysis": {...} }
    """
    result = {
        "trend": "Sideways",
        "signal": "Hold",
        "strength": "Weak",
        "key_levels": {"support": None, "resistance": None},
        "reasoning": "Analysis could not be completed.",
        "error": None,
    }

    tech_data = state.get("technical_data", {})

    if tech_data.get("error"):
        result["error"] = f"Skipped — data fetch error: {tech_data['error']}"
        return {"technical_analysis": result}

    if not tech_data.get("indicators"):
        result["error"] = "Skipped — no indicator data available."
        return {"technical_analysis": result}

    try:
        llm = _get_llm()
        full_prompt = f"{_SYSTEM_PROMPT}\n\n{_build_prompt(tech_data)}"
        raw_output = llm.invoke(full_prompt)
        parsed = _parse_llm_json(raw_output)

        # Merge parsed output into result (keep defaults for missing keys)
        result.update(parsed)
        result["error"] = None

        print(f"[technical_agent] ✅ Analysis complete for {tech_data.get('ticker')}: {result['signal']} ({result['trend']})")

    except json.JSONDecodeError as e:
        result["error"] = f"JSON parse error: {e}"
        print(f"[technical_agent] ❌ JSON parse error: {e}")
    except Exception as e:
        result["error"] = f"Agent error: {str(e)}"
        traceback.print_exc()
        print(f"[technical_agent] ❌ Error: {e}")

    return {"technical_analysis": result}
