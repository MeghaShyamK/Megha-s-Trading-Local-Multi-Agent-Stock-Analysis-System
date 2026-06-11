# 📈 Megha's Trading — Local Multi-Agent Stock Analysis System

> A 100% open-source, fully local Multi-Agent System (MAS) for Indian stock market and options analysis.  
> Powered by **Ollama** (local LLMs), **LangGraph** orchestration, and **Streamlit** UI.  
> No paid APIs. No cloud dependencies. No data leaves your machine.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Agents & Their Roles](#agents--their-roles)
- [Data Tools (Phase 1)](#data-tools-phase-1)
- [LangGraph MAS (Phase 2)](#langgraph-mas-phase-2)
- [Streamlit UI (Phase 3)](#streamlit-ui-phase-3)
- [Setup & Installation](#setup--installation)
- [Running the App](#running-the-app)
- [Configuration](#configuration)
- [Design Decisions](#design-decisions)
- [Roadmap](#roadmap)

---

## Overview

**Megha's Trading** is a modular, locally-run financial analysis assistant that uses a network of specialized AI agents to:

- Fetch and analyze live OHLCV market data with technical indicators
- Pull NSE option chain data, compute Put-Call Ratio (PCR) and max-pain
- Scrape today's broker recommendations from Moneycontrol, Economic Times, and Livemint
- Run fundamental analysis (P/E, earnings, dividends) via Yahoo Finance
- Analyze uploaded chart screenshots using a vision model
- Produce structured trade recommendations with a built-in **Human-in-the-Loop** approval gate

All LLM inference runs locally through **Ollama** — your data never leaves your machine.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Streamlit UI  (app.py)                       │
│  Tab: Analysis │ Today's Picks │ Weekly Picks │ Chat │ Vision Analyst│
└────────────────────────────┬────────────────────────────────────────┘
                             │  user commands / uploads
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   LangGraph State Machine  (graph/)                 │
│                                                                     │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐         │
│   │  Technical   │    │ Fundamental  │    │  Risk/Devil's│         │
│   │    Agent     │    │    Agent     │    │  Advocate    │         │
│   │ (qwen2.5:7b) │    │ (qwen2.5:7b) │    │ (qwen2.5:7b) │         │
│   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘         │
│          │                   │                   │                 │
│          └───────────────────┼───────────────────┘                 │
│                              ▼                                      │
│                   ┌──────────────────┐                             │
│                   │  Coordinator     │ ◄── Vision Agent            │
│                   │     Agent        │     (llama3.2-vision)       │
│                   │  (qwen2.5:7b)    │                             │
│                   └────────┬─────────┘                             │
│                            │                                        │
│                   [HITL: interrupt_before]                          │
│                            │  ← Human approves/rejects             │
│                            ▼                                        │
│                   Final Trade Report (JSON)                         │
└─────────────────────────────────────────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
   │data_fetcher │   │options_     │   │  scraper    │
   │  .py        │   │fetcher.py   │   │   .py       │
   │(yfinance+ta)│   │(NSE / nsepy)│   │(BS4 / lxml) │
   └─────────────┘   └─────────────┘   └─────────────┘
```

### Data Flow

1. **User** selects a ticker or types a command in the Streamlit UI
2. **LangGraph** routes the request through the appropriate agent nodes
3. Each agent calls the relevant **data tools** to fetch live market data
4. Agents reason using **Ollama** (local LLM — no API key needed)
5. **Coordinator Agent** aggregates all agent outputs into a JSON report
6. **HITL gate** (`interrupt_before`) pauses execution for human approval
7. Final recommendation is rendered back in the Streamlit UI

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **UI** | [Streamlit](https://streamlit.io) ≥ 1.35 | Dashboard, chat, file upload |
| **Orchestration** | [LangGraph](https://langchain-ai.github.io/langgraph/) ≥ 0.1 | Multi-agent state machine with HITL |
| **LLM Framework** | [LangChain](https://python.langchain.com) ≥ 0.2 | Agent prompts, tool-calling, memory |
| **Local LLMs** | [Ollama](https://ollama.com) (local) | `qwen2.5:7b` (reasoning), `llama3.2-vision` (charts) |
| **Market Data** | [yfinance](https://github.com/ranaroussi/yfinance) ≥ 0.2.40 | OHLCV, fundamentals, dividends |
| **Technical Indicators** | [ta](https://technical-analysis-library-in-python.readthedocs.io) ≥ 0.11 | EMA, RSI, MACD, Bollinger Bands |
| **Options Data** | [nsepython](https://github.com/unofficialAPIs/nsepython) ≥ 2.9 + direct NSE API | Option chain, OI, PCR |
| **Web Scraping** | [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) + [lxml](https://lxml.de) | Broker recommendations, news |
| **Visualization** | [Plotly](https://plotly.com/python/) ≥ 5.22 | Interactive candlestick & indicator charts |
| **Data** | [Pandas](https://pandas.pydata.org) ≥ 2.2, [NumPy](https://numpy.org) ≥ 1.26 | Data manipulation |
| **Validation** | [Pydantic](https://docs.pydantic.dev) ≥ 2.7 | Agent state schemas |
| **Runtime** | Python 3.10, [uv](https://github.com/astral-sh/uv) venv | Fast, reproducible environment |

### Local LLM Models (via Ollama)

| Model | Role | Why |
|-------|------|-----|
| `qwen2.5:7b` | Technical, Fundamental, Risk, Coordinator agents | Strong reasoning, follows structured JSON instructions, fast on CPU |
| `llama3.2-vision` | Vision Agent (chart analysis) | Multimodal — can interpret price chart images |

---

## Project Structure

```
Trading-Agent-System/
│
├── app.py                         # Streamlit entry point (Phase 3)
├── requirements.txt               # All Python dependencies
├── pyproject.toml                 # Project metadata (uv)
│
├── data/
│   └── watchlist.json             # Nifty50, BankNifty, Custom tickers + index symbols
│
├── tools/                         # Phase 1: Data fetching & scraping tools
│   ├── __init__.py                # Package exports
│   ├── watchlist.py               # Tool 1: Load/filter/add tickers
│   ├── data_fetcher.py            # Tool 2 & 4: OHLCV + indicators + fundamentals
│   ├── options_fetcher.py         # Tool 3: NSE option chain, OI, PCR, max-pain
│   └── scraper.py                 # Tool 5: Broker recs + market news scraper
│
├── agents/                        # Phase 2: LangChain agent definitions
│   ├── __init__.py
│   ├── technical_agent.py         # Momentum, indicators analysis
│   ├── fundamental_agent.py       # Balance sheet, events, anomalies
│   ├── risk_agent.py              # Devil's advocate — volatility flags
│   ├── coordinator_agent.py       # Aggregates all agents → final report
│   └── vision_agent.py            # llama3.2-vision — chart image analysis
│
└── graph/                         # Phase 2: LangGraph state machine
    ├── __init__.py
    ├── state.py                   # TypedDict graph state schema
    └── pipeline.py                # Node definitions, edges, HITL interrupt
```

---

## Agents & Their Roles

### 1. 🔵 Technical Agent (`qwen2.5:7b`)
- **Input**: OHLCV data, EMA 20/50/200, RSI-14, MACD, Fibonacci levels
- **Task**: Identify trend direction, momentum signals, support/resistance zones
- **Output**: `{ trend, signal, key_levels, reasoning }`

### 2. 🟢 Fundamental Agent (`qwen2.5:7b`)
- **Input**: P/E, Forward P/E, P/B, EPS, quarterly revenue, dividends, analyst rating
- **Task**: Assess valuation, detect earnings anomalies, flag upcoming corporate actions
- **Output**: `{ valuation_verdict, growth_signal, red_flags, reasoning }`

### 3. 🔴 Risk / Devil's Advocate Agent (`qwen2.5:7b`)
- **Input**: RSI extremes, volatility, news sentiment, options OI skew
- **Task**: Argue against the trade — identify reasons NOT to enter
- **Output**: `{ risk_level, reasons_to_avoid, volatility_flag }`

### 4. 🟡 Coordinator Agent (`qwen2.5:7b`)
- **Input**: All three agent outputs + PCR + broker recommendation overlap
- **Task**: Synthesize a final, structured recommendation
- **Output**: Complete JSON trade report with entry, target, stop-loss, conviction score
- **Gated by**: Human-in-the-Loop `interrupt_before` — you must approve before it finalizes

### 5. 🟣 Vision Agent (`llama3.2-vision`)
- **Input**: Uploaded chart screenshot (`.png` / `.jpg`)
- **Task**: Identify the ticker, chart pattern, trend direction, key levels from the image
- **Output**: Pattern analysis passed to the Coordinator

---

## Data Tools (Phase 1)

### `tools/watchlist.py`
Manages the stock universe:
```python
from tools.watchlist import get_watchlist, get_index_symbol, add_custom_ticker

tickers = get_watchlist("Nifty50")       # → list of 50 .NS tickers
tickers = get_watchlist("BankNifty")     # → list of 12 .NS tickers
symbol  = get_index_symbol("Nifty50")   # → "^NSEI"
add_custom_ticker("ZOMATO.NS")          # persists to watchlist.json
```

### `tools/data_fetcher.py`
OHLCV + all technical indicators + fundamental data:
```python
from tools.data_fetcher import get_technical_data, get_fundamental_data

# Technical analysis
tech = get_technical_data("RELIANCE.NS", period="3mo", interval="1d")
# Returns: latest_price, EMA_20/50/200, RSI_14, MACD, Fibonacci levels,
#          full OHLCV DataFrame as list of dicts (last 60 candles)

# Fundamental analysis
funda = get_fundamental_data("TCS.NS")
# Returns: PE/PB/EPS, market_cap, quarterly_earnings, dividends,
#          stock_splits, analyst_recommendation
```

**Indicators calculated:**

| Indicator | Parameters | Library |
|-----------|-----------|---------|
| EMA | 20, 50, 200 periods | `ta.trend.EMAIndicator` |
| RSI | 14 periods | `ta.momentum.RSIIndicator` |
| MACD | Fast 12, Slow 26, Signal 9 | `ta.trend.MACD` |
| Fibonacci Retracement | 60-day swing high/low | Custom (0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%) |

### `tools/options_fetcher.py`
NSE derivatives data with dual-source fallback:
```python
from tools.options_fetcher import get_option_chain, get_pcr

# Full option chain for nearest expiry
chain = get_option_chain("NIFTY")
# Returns: underlying_value, calls[], puts[], PCR, max_pain,
#          top 5 support strikes (put OI), top 5 resistance strikes (call OI)

# Quick PCR check
pcr = get_pcr("BANKNIFTY")
# Returns: pcr value, sentiment label ("Bullish" / "Bearish" / "Neutral")
```

**PCR Interpretation:**
- PCR > 1.2 → Bullish (heavy put writing = market expects support)
- PCR < 0.8 → Bearish (heavy call writing = market expects resistance)
- 0.8 – 1.2 → Neutral

**Fallback Strategy**: `nsepython` → direct NSE API with browser headers + cookie priming

### `tools/scraper.py`
Multi-source broker recommendation aggregator:
```python
from tools.scraper import get_broker_recommendations, get_market_news

recs  = get_broker_recommendations(max_results=20)
# Returns merged list from Moneycontrol → Economic Times → Livemint
# Deduplicated by ticker, with: action, target_price, stop_loss, broker, source

news  = get_market_news(max_headlines=15)
# Returns latest headlines from ET + Moneycontrol
```

**Scraping Strategy:**
1. Moneycontrol — structured table parsing, falls back to card/article regex
2. Economic Times — article headline parsing with broker/target extraction
3. Livemint — headline regex for action keywords
4. Random User-Agent rotation + retry logic (up to 2 retries with backoff)
5. Deduplication by ticker before returning results

---

## LangGraph MAS (Phase 2)

> ⏳ **Status: Awaiting approval — not yet implemented**

The LangGraph pipeline will be a directed graph where:

- **Nodes** = individual agents (each is a LangChain `RunnableSequence`)
- **Edges** = conditional routing based on agent outputs
- **State** = a shared `TypedDict` passed between all nodes
- **HITL** = `interrupt_before=["coordinator"]` pauses execution for human review

```python
# Simplified graph structure (graph/pipeline.py)
builder = StateGraph(TradingState)
builder.add_node("technical",    technical_agent_node)
builder.add_node("fundamental",  fundamental_agent_node)
builder.add_node("risk",         risk_agent_node)
builder.add_node("coordinator",  coordinator_agent_node)
builder.add_node("vision",       vision_agent_node)

builder.add_edge("technical",   "coordinator")
builder.add_edge("fundamental", "coordinator")
builder.add_edge("risk",        "coordinator")
builder.add_edge("vision",      "coordinator")

graph = builder.compile(interrupt_before=["coordinator"])
```

---

## Streamlit UI (Phase 3)

> ⏳ **Status: Placeholder implemented — full UI pending Phase 2**

The `app.py` Streamlit dashboard will have **5 tabs**:

| Tab | Description |
|-----|-------------|
| **📊 Analysis** | Index/watchlist dropdown, individual ticker input, technical chart with indicator overlays (Plotly) |
| **🎯 Today's Picks** | Col A: Top 20 MAS momentum picks. Col B: Top 20 broker recs. Overlapping tickers highlighted |
| **📅 Weekly Picks** | Col A: Options swing trades (1 week). Col B: Cash delivery/buy-hold. Agent reasoning shown |
| **💬 Megha (Chat)** | Persistent chat — type "Megha, analyze Infosys" → runs LangGraph pipeline → replies in chat |
| **👁️ Vision Analyst** | Upload chart PNG/JPG → Vision Agent analyzes → returns pattern, ticker, trend |

---

## Setup & Installation

### Prerequisites

- **Python 3.10** (exact version — managed by `.python-version`)
- **[uv](https://github.com/astral-sh/uv)** — fast Python package manager
- **[Ollama](https://ollama.com)** — local LLM server

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd Trading-Agent-System
```

### 2. Create and activate virtual environment

```bash
uv venv --python 3.10
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
uv pip install -r requirements.txt
```

### 4. Pull Ollama models

```bash
# Install Ollama first: https://ollama.com/download
ollama pull qwen2.5:7b           # Text reasoning model (~4.7 GB)
ollama pull llama3.2-vision      # Vision model (~2.0 GB)
```

### 5. Verify the tools work

```bash
# Test watchlist
.venv/bin/python tools/watchlist.py

# Test data fetcher (requires internet — calls Yahoo Finance)
.venv/bin/python tools/data_fetcher.py

# Test options fetcher (works only during NSE market hours)
.venv/bin/python tools/options_fetcher.py

# Test scraper
.venv/bin/python tools/scraper.py
```

---

## Running the App

```bash
# Make sure Ollama is running:
ollama serve

# Launch the Streamlit dashboard:
streamlit run app.py
```

The app will open at `http://localhost:8501`

---

## Configuration

### `data/watchlist.json`

Modify this file to customise your stock universe:

```json
{
  "watchlist": {
    "Nifty50":   ["RELIANCE.NS", "TCS.NS", ...],
    "BankNifty": ["HDFCBANK.NS", "ICICIBANK.NS", ...],
    "Custom":    ["ZOMATO.NS", "DMART.NS"]      ← add your picks here
  },
  "indices": {
    "Nifty50":   "^NSEI",
    "BankNifty": "^NSEBANK"
  }
}
```

You can also add tickers programmatically:
```python
from tools.watchlist import add_custom_ticker
add_custom_ticker("IRFC.NS")
```

### Ollama Model Selection

The model names used by agents are defined in `agents/` config (Phase 2).  
To use a different model (e.g. `mistral:7b`), change the model name in the agent file:

```python
llm = OllamaLLM(model="mistral:7b")   # swap any Ollama model here
```

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| **`ta` library instead of `pandas-ta`** | `pandas-ta` requires Python ≥ 3.12 (both PyPI versions). The `ta` library covers EMA, RSI, MACD with a clean API and works on Python 3.10 |
| **Dual-source NSE options fetching** | `nsepython` fails outside market hours or after NSE rate-limits; direct NSE API with cookie priming is the fallback. Never a hard failure |
| **Three scraper sources** | Financial news sites frequently block scrapers. Running Moneycontrol → ET → Livemint in sequence maximises coverage. All errors are caught; partial results still returned |
| **All tools return dicts, never raise** | Agents need predictable inputs. Every tool wraps its core logic in `try/except` and returns `{"error": "..."}` on failure so the rest of the pipeline continues |
| **LangGraph over plain LangChain** | LangGraph's graph-based routing allows each agent to be isolated, enables conditional edges (e.g. skip Fundamental if only options analysis requested), and provides built-in `interrupt_before` for HITL |
| **Qwen2.5:7b for all text agents** | Strong instruction-following, excellent at structured JSON output, fast on consumer hardware. Easily swappable via one config line |
| **Modular files, not a monolith** | Designed for a Python learner — each file has one responsibility with full docstrings, making it easy to read, test, and extend independently |

---

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 1** | ✅ Complete | Data tools — watchlist, OHLCV+indicators, options, scraper |
| **Phase 2** | ⏳ Awaiting approval | LangGraph MAS — 5 agents, state machine, HITL gate |
| **Phase 3** | ⏳ Pending Phase 2 | Full Streamlit UI — 5 tabs, charts, chat, vision upload |
| **Future** | 🗺️ Planned | Backtesting engine, paper trading mode, alerting via Telegram |

---

## Disclaimer

> **This project is for educational and research purposes only.**  
> It does not constitute financial advice. Stock markets involve risk. Always consult a SEBI-registered financial advisor before making investment decisions.  
> The authors are not responsible for any trading losses incurred using this tool.

---

## License

MIT License — free to use, modify, and distribute with attribution.
