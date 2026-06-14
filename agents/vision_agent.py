"""
agents/vision_agent.py
-----------------------
Vision Agent (Phase 2)

Responsibilities:
  - Read a Base64-encoded chart image from TradingState.image_b64
  - Use OllamaLLM with llama3.2-vision to analyze the chart
  - Identify chart pattern, trend, key levels, and possible ticker
  - Write the result to TradingState.vision_analysis

If no image is in state, gracefully skips and returns an empty analysis.

Output schema:
  {
    "ticker_identified": str | None,
    "chart_pattern":     str,
    "trend":             "Bullish" | "Bearish" | "Sideways",
    "key_levels":        { "support": float | None, "resistance": float | None },
    "commentary":        str,
    "error":             str | None
  }
"""

from __future__ import annotations

import base64
import json
import re
import traceback

from langchain_ollama import OllamaLLM

from graph.state import TradingState

# ─────────────────────────────────────────────────────────────────────────────
# LLM instance (vision-capable)
# ─────────────────────────────────────────────────────────────────────────────

_LLM: OllamaLLM | None = None


def _get_llm() -> OllamaLLM:
    global _LLM
    if _LLM is None:
        _LLM = OllamaLLM(model="llama3.2-vision", temperature=0.1)
    return _LLM


# ─────────────────────────────────────────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────────────────────────────────────────

_VISION_PROMPT = """You are an expert technical chart analyst for Indian equity markets.
Analyze the provided stock chart image carefully.

Identify:
1. The stock ticker or company name (if visible in the chart)
2. The dominant chart pattern (e.g., "Head and Shoulders", "Double Bottom", "Cup and Handle", "Ascending Triangle", "Flag", "Breakout", "Consolidation", etc.)
3. The overall trend direction
4. Key support and resistance price levels (read from the chart's Y-axis)
5. Your overall commentary and trade implication

ALWAYS respond with ONLY a valid JSON object — no prose, no markdown, no explanation outside the JSON:
{
  "ticker_identified": "<ticker or null if not visible>",
  "chart_pattern": "<pattern name>",
  "trend": "<Bullish|Bearish|Sideways>",
  "key_levels": {"support": <number or null>, "resistance": <number or null>},
  "commentary": "<2-3 sentence analysis of the chart>"
}"""


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

def vision_agent_node(state: TradingState) -> dict:
    """
    LangGraph node function for the Vision Agent.

    Reads  : state["image_b64"]
    Writes : state["vision_analysis"]

    If no image is provided, returns an empty analysis without error.
    """
    result = {
        "ticker_identified": None,
        "chart_pattern": "No image provided",
        "trend": "Sideways",
        "key_levels": {"support": None, "resistance": None},
        "commentary": "No chart image was uploaded for vision analysis.",
        "error": None,
    }

    image_b64 = state.get("image_b64")

    # ── No image — skip gracefully ──────────────────────────────────────────
    if not image_b64:
        print("[vision_agent] ℹ️  No image in state — skipping vision analysis.")
        return {"vision_analysis": result}

    try:
        # Validate the base64 string is decodable
        try:
            base64.b64decode(image_b64, validate=True)
        except Exception:
            result["error"] = "Invalid base64 image data."
            return {"vision_analysis": result}

        # OllamaLLM with llama3.2-vision — pass image via images parameter
        llm = _get_llm()

        # Build the multimodal message
        # langchain-ollama passes images as part of the invoke call
        raw_output = llm.invoke(
            _VISION_PROMPT,
            images=[image_b64],
        )

        parsed = _parse_llm_json(raw_output)
        result.update(parsed)
        result["error"] = None

        print(f"[vision_agent] ✅ Chart analysis: {result['chart_pattern']} | {result['trend']}")

    except json.JSONDecodeError as e:
        result["error"] = f"JSON parse error: {e}"
        print(f"[vision_agent] ❌ JSON parse error: {e}")
    except Exception as e:
        result["error"] = f"Vision agent error: {str(e)}"
        result["commentary"] = "Vision analysis failed. Ensure Ollama is running with llama3.2-vision pulled."
        traceback.print_exc()
        print(f"[vision_agent] ❌ Error: {e}")

    return {"vision_analysis": result}
