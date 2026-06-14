"""
agents/fundamental_agent.py
----------------------------
Fundamental Analysis Agent (Phase 2)

Responsibilities:
  - Read raw fundamental data from TradingState.fundamental_data
  - Build a structured prompt with P/E, EPS, market cap, dividends, analyst rec
  - Use OllamaLLM (qwen2.5:7b) to assess valuation and growth signals
  - Parse the LLM output into a clean structured dict
  - Write the result to TradingState.fundamental_analysis

Output schema:
  {
    "valuation_verdict": "Undervalued" | "Fairly Valued" | "Overvalued",
    "growth_signal":     "Strong" | "Moderate" | "Weak" | "Negative",
    "red_flags":         [str, ...],   # list of concerns
    "positives":         [str, ...],   # list of bullish fundamentals
    "reasoning":         str,
    "error":             str | None
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

_SYSTEM_PROMPT = """You are an expert equity analyst specialising in Indian stock markets.
You will be given fundamental financial data for a company.
Your job is to assess its valuation, growth trajectory, and flag any red flags.

ALWAYS respond with ONLY a valid JSON object — no prose, no markdown, no explanation outside the JSON.
The JSON must have exactly these keys:
{
  "valuation_verdict": "<Undervalued|Fairly Valued|Overvalued>",
  "growth_signal": "<Strong|Moderate|Weak|Negative>",
  "red_flags": ["<concern 1>", "<concern 2>"],
  "positives": ["<positive 1>", "<positive 2>"],
  "reasoning": "<2-3 sentence explanation of your analysis>"
}"""


def _fmt(value, prefix: str = "", suffix: str = "", decimals: int = 2) -> str:
    """Format a value with prefix/suffix, or return 'N/A' if None."""
    if value is None:
        return "N/A"
    try:
        return f"{prefix}{float(value):.{decimals}f}{suffix}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_market_cap(cap) -> str:
    """Format market cap in crores (Indian notation)."""
    if cap is None:
        return "N/A"
    try:
        crores = float(cap) / 1e7
        if crores >= 1e5:
            return f"₹{crores/1e5:.2f} Lakh Cr"
        return f"₹{crores:,.0f} Cr"
    except (TypeError, ValueError):
        return str(cap)


def _build_prompt(funda_data: dict) -> str:
    """Build a fundamental analysis prompt from raw data."""
    ticker = funda_data.get("ticker", "UNKNOWN")
    company = funda_data.get("company_name", ticker)
    sector = funda_data.get("sector", "N/A")
    industry = funda_data.get("industry", "N/A")

    # Format quarterly earnings summary
    quarterly = funda_data.get("quarterly_earnings", [])
    if quarterly:
        q_lines = []
        for q in quarterly[:4]:  # Show last 4 quarters
            rev = _fmt(q.get("total_revenue"), prefix="₹", suffix="", decimals=0)
            net = _fmt(q.get("net_income"), prefix="₹", suffix="", decimals=0)
            q_lines.append(f"  {q.get('period', 'N/A')}: Revenue {rev} | Net Income {net}")
        q_summary = "\n".join(q_lines)
    else:
        q_summary = "  N/A"

    # Recent dividends
    divs = funda_data.get("dividends_recent", [])
    div_str = ", ".join(f"₹{d.get('amount', 'N/A')} ({d.get('date', '')})" for d in divs[-3:]) or "None"

    prompt = f"""Analyze the following fundamental data for {company} ({ticker}):

COMPANY PROFILE:
  Sector:   {sector}
  Industry: {industry}
  Market Cap: {_fmt_market_cap(funda_data.get('market_cap'))}

VALUATION RATIOS:
  Trailing P/E:  {_fmt(funda_data.get('pe_ratio_ttm'))}
  Forward P/E:   {_fmt(funda_data.get('pe_ratio_forward'))}
  P/B Ratio:     {_fmt(funda_data.get('pb_ratio'))}
  EPS (TTM):     {_fmt(funda_data.get('eps_ttm'), prefix='₹')}
  Dividend Yield:{_fmt(funda_data.get('dividend_yield_pct'), suffix='%')}

52-WEEK RANGE:
  High: {_fmt(funda_data.get('week_52_high'), prefix='₹')}
  Low:  {_fmt(funda_data.get('week_52_low'),  prefix='₹')}

ANALYST RECOMMENDATION: {funda_data.get('analyst_recommendation', 'N/A')}

QUARTERLY FINANCIALS (recent 4 quarters):
{q_summary}

RECENT DIVIDENDS: {div_str}

Based on this data, provide your fundamental analysis as a JSON object."""

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

def fundamental_agent_node(state: TradingState) -> dict:
    """
    LangGraph node function for the Fundamental Analysis Agent.

    Reads  : state["fundamental_data"]
    Writes : state["fundamental_analysis"]
    """
    result = {
        "valuation_verdict": "Fairly Valued",
        "growth_signal": "Weak",
        "red_flags": [],
        "positives": [],
        "reasoning": "Analysis could not be completed.",
        "error": None,
    }

    funda_data = state.get("fundamental_data", {})

    if funda_data.get("error"):
        result["error"] = f"Skipped — data fetch error: {funda_data['error']}"
        return {"fundamental_analysis": result}

    if not funda_data.get("company_name") and not funda_data.get("ticker"):
        result["error"] = "Skipped — no fundamental data available."
        return {"fundamental_analysis": result}

    try:
        llm = _get_llm()
        full_prompt = f"{_SYSTEM_PROMPT}\n\n{_build_prompt(funda_data)}"
        raw_output = llm.invoke(full_prompt)
        parsed = _parse_llm_json(raw_output)

        result.update(parsed)
        result["error"] = None

        print(f"[fundamental_agent] ✅ Analysis complete for {funda_data.get('ticker')}: {result['valuation_verdict']}")

    except json.JSONDecodeError as e:
        result["error"] = f"JSON parse error: {e}"
        print(f"[fundamental_agent] ❌ JSON parse error: {e}")
    except Exception as e:
        result["error"] = f"Agent error: {str(e)}"
        traceback.print_exc()

    return {"fundamental_analysis": result}
