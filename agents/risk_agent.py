"""
agents/risk_agent.py
---------------------
Risk / Devil's Advocate Agent (Phase 2)

Responsibilities:
  - Read technical data, options data, and fundamental analysis from state
  - Play Devil's Advocate — identify reasons NOT to enter the trade
  - Flag RSI extremes, high volatility, bearish PCR, news risks
  - Use OllamaLLM (qwen2.5:7b) to reason about downside risks
  - Write the result to TradingState.risk_analysis

Output schema:
  {
    "risk_level":      "High" | "Medium" | "Low",
    "volatility_flag": True | False,
    "reasons_to_avoid": [str, ...],
    "mitigating_factors": [str, ...],
    "stop_loss_suggestion": float | None,
    "reasoning": str,
    "error": str | None
  }
"""

from __future__ import annotations

import json
import re
import traceback

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
# Prompt builder
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a risk manager and Devil's Advocate for an Indian equity trading desk.
Your ONLY job is to identify risks and reasons NOT to enter a trade.
Do not be bullish — focus exclusively on what could go wrong.

ALWAYS respond with ONLY a valid JSON object — no prose, no markdown, no explanation outside the JSON.
The JSON must have exactly these keys:
{
  "risk_level": "<High|Medium|Low>",
  "volatility_flag": <true|false>,
  "reasons_to_avoid": ["<risk 1>", "<risk 2>", "<risk 3>"],
  "mitigating_factors": ["<factor 1>", "<factor 2>"],
  "stop_loss_suggestion": <number or null>,
  "reasoning": "<2-3 sentence summary of the key risks>"
}"""


def _build_prompt(state: TradingState) -> str:
    """Build a risk analysis prompt from all available state data."""
    tech_data = state.get("technical_data", {})
    options_data = state.get("options_data", {})
    tech_analysis = state.get("technical_analysis", {})
    funda_analysis = state.get("fundamental_analysis", {})

    ticker = state.get("ticker", "UNKNOWN")
    indicators = tech_data.get("indicators", {})
    price = tech_data.get("latest_price", "N/A")

    rsi = indicators.get("RSI_14", "N/A")
    macd = indicators.get("MACD", "N/A")
    macd_hist = indicators.get("MACD_Histogram", "N/A")
    swing_high = indicators.get("swing_high_60d", "N/A")
    swing_low = indicators.get("swing_low_60d", "N/A")

    # PCR and options data
    pcr_data = options_data.get("pcr", {})
    pcr = pcr_data.get("pcr", "N/A")
    pcr_sentiment = pcr_data.get("sentiment", "N/A")
    max_pain = options_data.get("max_pain", "N/A")

    # Prior agent conclusions
    ta_signal = tech_analysis.get("signal", "N/A")
    ta_trend = tech_analysis.get("trend", "N/A")
    fa_verdict = funda_analysis.get("valuation_verdict", "N/A")
    fa_red_flags = funda_analysis.get("red_flags", [])
    fa_flags_str = "; ".join(fa_red_flags) if fa_red_flags else "None identified"

    prompt = f"""Perform a RISK ASSESSMENT for {ticker}:

CURRENT PRICE: {price}
52-WEEK RANGE: High {swing_high} | Low {swing_low}

TECHNICAL RISK SIGNALS:
  RSI (14):        {rsi}   ← RSI > 70 = overbought, < 30 = oversold
  MACD:            {macd}
  MACD Histogram:  {macd_hist}  ← Negative = bearish momentum
  Technical Signal (from Tech Agent): {ta_signal} | Trend: {ta_trend}

OPTIONS MARKET RISK SIGNALS:
  Put-Call Ratio (PCR): {pcr}
  PCR Sentiment:        {pcr_sentiment}
  Max Pain Strike:      {max_pain}
  ← PCR < 0.8 = bearish (heavy call writing = resistance expected)
  ← Price far from max pain = risk of pull-back toward max pain

FUNDAMENTAL RISK FLAGS:
  Valuation:  {fa_verdict}
  Red Flags:  {fa_flags_str}

Based on all this data, identify the key risks and provide your risk assessment as a JSON object.
Be thorough and pessimistic — argue against entering this trade."""

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
# Agent node (called by LangGraph)
# ─────────────────────────────────────────────────────────────────────────────

def risk_agent_node(state: TradingState) -> dict:
    """
    LangGraph node function for the Risk / Devil's Advocate Agent.

    Reads  : state["technical_data"], state["options_data"],
             state["technical_analysis"], state["fundamental_analysis"]
    Writes : state["risk_analysis"]
    """
    result = {
        "risk_level": "Medium",
        "volatility_flag": False,
        "reasons_to_avoid": [],
        "mitigating_factors": [],
        "stop_loss_suggestion": None,
        "reasoning": "Risk analysis could not be completed.",
        "error": None,
    }

    tech_data = state.get("technical_data", {})
    if not tech_data:
        result["error"] = "Skipped — no technical data in state."
        return {"risk_analysis": result}

    try:
        llm = _get_llm()
        full_prompt = f"{_SYSTEM_PROMPT}\n\n{_build_prompt(state)}"
        raw_output = llm.invoke(full_prompt)
        parsed = _parse_llm_json(raw_output)

        result.update(parsed)
        result["error"] = None

        ticker = state.get("ticker", "?")
        print(f"[risk_agent] ✅ Risk assessment for {ticker}: {result['risk_level']} risk")

    except json.JSONDecodeError as e:
        result["error"] = f"JSON parse error: {e}"
        print(f"[risk_agent] ❌ JSON parse error: {e}")
    except Exception as e:
        result["error"] = f"Agent error: {str(e)}"
        traceback.print_exc()

    return {"risk_analysis": result}
