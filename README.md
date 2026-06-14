# 📈 Megha's Trading — Local Multi-Agent Stock Analysis System

> A 100% open-source, fully local Multi-Agent System (MAS) for Indian stock market and options analysis.  
> Powered by **Ollama** (local LLMs), **LangGraph** orchestration, and a **Streamlit** dashboard.  
> No paid APIs. No cloud dependencies. No data leaves your machine.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Agents & Their Roles](#agents--their-roles)
- [Data Tools](#data-tools)
- [LangGraph Pipeline](#langgraph-pipeline)
- [Streamlit Dashboard](#streamlit-dashboard)
- [Authentication & User Management](#authentication--user-management)
- [Alert Engine](#alert-engine)
- [Setup & Installation](#setup--installation)
- [Running the App](#running-the-app)
- [Configuration](#configuration)
- [Design Decisions](#design-decisions)

---

## Overview

**Megha's Trading** is a modular, locally-run financial analysis assistant that uses a network of specialized AI agents to:

- Fetch and analyze live OHLCV market data with technical indicators (EMA, RSI, MACD, Fibonacci)
- Pull NSE option chain data, compute Put-Call Ratio (PCR) and max-pain
- Scrape today's broker recommendations from Moneycontrol, Economic Times, and Livemint
- Run fundamental analysis (P/E, earnings, dividends) via Yahoo Finance
- Analyze uploaded chart screenshots using a multimodal vision model
- Produce structured trade recommendations with a built-in **Human-in-the-Loop (HITL)** approval gate
- Send automated price alerts via **Email** and **Discord**
- Provide role-based **multi-user access** with an admin panel

All LLM inference runs locally through **Ollama** — your data never leaves your machine.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Streamlit UI  (app.py)                          │
│  Watchlist │ Trade Today │ Future Analysis │ Analysis │ Today's     │
│  Picks │ Chat │ Vision │ Alerts │ Feedback │ [Admin]                │
└────────────────────────────┬────────────────────────────────────────┘
                             │  user commands / uploads
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  LangGraph State Machine  (graph/)                  │
│                                                                     │
│  START → [fetch_data] ──────────────────────────────────────────┐  │
│               │                                                  │  │
│    ┌──────────┼───────────┬───────────────┐                     │  │
│    ▼          ▼           ▼               ▼                     │  │
│ [technical] [fundamental] [risk]       [vision]                 │  │
│    │          │           │               │                     │  │
│    └──────────┴───────────┴───────────────┘                     │  │
│                           │                                     │  │
│              [interrupt_before="coordinator"] ◄── HITL gate     │  │
│                           │  ← Human approves / rejects         │  │
│                           ▼                                     │  │
│                    [coordinator] → Final JSON Trade Report       │  │
│                           └─→ END                               │  │
└─────────────────────────────────────────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
   │data_fetcher │   │options_     │   │  scraper    │
   │  .py        │   │fetcher.py   │   │   .py       │
   │(yfinance+ta)│   │(NSE / nsepy)│   │(BS4 / lxml) │
   └─────────────┘   └─────────────┘   └─────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│               Background Services                                   │
│  APScheduler Alert Engine → Email (SMTP) + Discord (Webhooks)       │
│  SQLite Database (users, watchlist, alerts, analyses, feedback)     │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **User** logs in and selects a ticker or types a command in the Streamlit UI
2. **LangGraph** starts the pipeline: `fetch_data` node calls all data tools
3. Four agents (`technical`, `fundamental`, `risk`, `vision`) run in the graph
4. Each agent reasons using a locally-running **Ollama** LLM — no API key needed
5. Graph **pauses** at `interrupt_before=["coordinator"]` — the HITL gate
6. **User reviews** the three agent analyses and clicks Approve or Reject
7. If approved, the **Coordinator Agent** synthesizes a final JSON trade report
8. Final recommendation is rendered in the Streamlit UI with entry, target, stop-loss, R:R, and conviction score

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **UI** | [Streamlit](https://streamlit.io) ≥ 1.35 | Dashboard, chat, file upload, 10-tab layout |
| **Orchestration** | [LangGraph](https://langchain-ai.github.io/langgraph/) ≥ 0.1 | Multi-agent state machine with HITL |
| **LLM Framework** | [LangChain](https://python.langchain.com) ≥ 0.2 | Agent prompts, tool-calling, LLM wrappers |
| **Local LLMs** | [Ollama](https://ollama.com) (local) | `qwen2.5:7b` (reasoning), `llama3.2-vision` (charts) |
| **Market Data** | [yfinance](https://github.com/ranaroussi/yfinance) ≥ 0.2.40 | OHLCV, fundamentals, dividends |
| **Technical Indicators** | [ta](https://technical-analysis-library-in-python.readthedocs.io) ≥ 0.11 | EMA, RSI, MACD, Bollinger Bands |
| **Options Data** | [nsepython](https://github.com/unofficialAPIs/nsepython) ≥ 2.9 + direct NSE API | Option chain, OI, PCR, max-pain |
| **Web Scraping** | [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) + [lxml](https://lxml.de) | Broker recommendations, market news |
| **Visualization** | [Plotly](https://plotly.com/python/) ≥ 5.22 | Interactive candlestick + indicator charts |
| **Data** | [Pandas](https://pandas.pydata.org) ≥ 2.2, [NumPy](https://numpy.org) ≥ 1.26 | Data manipulation |
| **Validation** | [Pydantic](https://docs.pydantic.dev) ≥ 2.7 | Agent state schemas |
| **Auth** | [bcrypt](https://pypi.org/project/bcrypt/) ≥ 4.1 | Password hashing, role-based access |
| **Scheduling** | [APScheduler](https://apscheduler.readthedocs.io) ≥ 3.10 | Background alert engine |
| **Timezone** | [pytz](https://pythonhosted.org/pytz/) ≥ 2024.1 | IST trading hours enforcement |
| **Database** | SQLite (stdlib) | Users, watchlist, alerts, analyses, feedback |
| **Runtime** | Python 3.10, [uv](https://github.com/astral-sh/uv) venv | Fast, reproducible environment |

### Local LLM Models (via Ollama)

| Model | Role | Why |
|-------|------|-----|
| `qwen2.5:7b` | Technical, Fundamental, Risk, Coordinator agents | Strong reasoning, excellent structured JSON output, fast on CPU |
| `llama3.2-vision` | Vision Agent (chart analysis) | Multimodal — interprets uploaded price chart images |

---

## Project Structure

```
Trading-Agent-System/
│
├── app.py                         # Streamlit entry point — 10-tab dashboard
├── main.py                        # Minimal CLI entry point
├── config.toml                    # Configuration: admin creds, email, Discord, trading hours
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
│   ├── coordinator_agent.py       # Aggregates all agents → final JSON report
│   └── vision_agent.py            # llama3.2-vision — chart image analysis
│
├── graph/                         # Phase 2: LangGraph state machine
│   ├── state.py                   # TradingState TypedDict schema + initial_state factory
│   └── pipeline.py                # Node definitions, edges, HITL interrupt, public API
│
├── pages/                         # Phase 3: Streamlit page modules
│   ├── watchlist_page.py          # Manage personal stock watchlist
│   ├── trade_today_page.py        # Full MAS pipeline with HITL approval UI
│   ├── analyse_future_page.py     # Future/swing analysis tab
│   ├── alerts_page.py             # Configure and manage price alerts
│   ├── feedback_page.py           # User feedback submission
│   └── admin_page.py              # Admin-only: user management, feedback review
│
├── auth/
│   └── auth_manager.py            # Login, logout, session, role checking (TOML-seeded admin)
│
├── db/                            # SQLite database layer
│   ├── database.py                # init_db() — schema creation
│   ├── user_db.py                 # User CRUD + bcrypt password ops
│   ├── watchlist_db.py            # Per-user watchlist CRUD
│   ├── alerts_db.py               # Alert CRUD + trigger tracking
│   ├── saved_analyses_db.py       # Save/load completed trade reports
│   └── feedback_db.py             # User feedback + unread count for admin badge
│
├── alerts/
│   ├── alert_engine.py            # APScheduler background engine (5-min poll, IST-aware)
│   ├── email_sender.py            # SMTP email delivery for alerts
│   └── discord_sender.py          # Discord webhook delivery for alerts
│
└── async_runner/
    └── task_queue.py              # Thread-pool submit helper for background alert runs
```

---

## Agents & Their Roles

### 1. 🔵 Technical Agent (`qwen2.5:7b`)
- **Input**: OHLCV data, EMA 20/50/200, RSI-14, MACD, Fibonacci retracement levels
- **Task**: Identify trend direction, momentum signals, support/resistance zones
- **Output**: `{ trend, signal, strength, key_levels: {support, resistance}, reasoning }`

### 2. 🟢 Fundamental Agent (`qwen2.5:7b`)
- **Input**: P/E, Forward P/E, P/B, EPS, quarterly revenue, dividends, analyst rating
- **Task**: Assess valuation, detect earnings anomalies, flag upcoming corporate actions
- **Output**: `{ valuation_verdict, growth_signal, red_flags[], positives[], reasoning }`

### 3. 🔴 Risk / Devil's Advocate Agent (`qwen2.5:7b`)
- **Input**: RSI extremes, volatility, news sentiment, options OI skew, broker warnings
- **Task**: Argue against the trade — identify reasons NOT to enter
- **Output**: `{ risk_level, reasons_to_avoid[], mitigating_factors[], volatility_flag, stop_loss_suggestion, reasoning }`

### 4. 🟡 Coordinator Agent (`qwen2.5:7b`)
- **Input**: All three agent outputs + PCR + broker recommendation overlap + vision analysis
- **Task**: Synthesize a final, structured recommendation
- **Output**: Complete JSON trade report:
  ```json
  {
    "ticker": "RELIANCE.NS",
    "action": "Buy | Sell | Hold | Avoid",
    "entry_price": 2850.00,
    "target_price": 3050.00,
    "stop_loss": 2780.00,
    "conviction_score": 8,
    "time_horizon": "Swing (1-2 weeks)",
    "broker_overlap": true,
    "risk_reward_ratio": 2.86,
    "summary": "..."
  }
  ```
- **Gated by**: Human-in-the-Loop `interrupt_before` — requires human approval before running

### 5. 🟣 Vision Agent (`llama3.2-vision`)
- **Input**: Uploaded chart screenshot (`.png` / `.jpg` / `.webp`)
- **Task**: Identify the ticker name(s), chart pattern, trend direction, key levels from the image
- **Output**: Pattern analysis + identified tickers — passed to the Coordinator

---

## Data Tools

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

tech  = get_technical_data("RELIANCE.NS", period="3mo", interval="1d")
# Returns: latest_price, EMA_20/50/200, RSI_14, MACD, Fibonacci levels,
#          full OHLCV DataFrame as list of dicts (last 60 candles)

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

chain = get_option_chain("NIFTY")
# Returns: underlying_value, calls[], puts[], PCR, max_pain,
#          top 5 support strikes (put OI), top 5 resistance strikes (call OI)

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

recs = get_broker_recommendations(max_results=20)
# Returns merged list from Moneycontrol → Economic Times → Livemint
# Deduplicated by ticker, with: action, target_price, stop_loss, broker, source

news = get_market_news(max_headlines=15)
# Returns latest headlines from ET + Moneycontrol
```

**Scraping Strategy:**
1. Moneycontrol — structured table parsing, falls back to card/article regex
2. Economic Times — article headline parsing with broker/target extraction
3. Livemint — headline regex for action keywords
4. Random User-Agent rotation + retry logic (up to 2 retries with backoff)
5. Deduplication by ticker before returning results

---

## LangGraph Pipeline

The pipeline lives in `graph/pipeline.py` and `graph/state.py`.

### Graph Structure

```python
builder = StateGraph(TradingState)

# Nodes
builder.add_node("fetch_data",  fetch_data_node)
builder.add_node("technical",   technical_agent_node)
builder.add_node("fundamental", fundamental_agent_node)
builder.add_node("risk",        risk_agent_node)
builder.add_node("vision",      vision_agent_node)
builder.add_node("coordinator", coordinator_agent_node)

# Edges: fetch_data fans out to all four agents
builder.add_edge("fetch_data",  "technical")
builder.add_edge("fetch_data",  "fundamental")
builder.add_edge("fetch_data",  "risk")
builder.add_edge("fetch_data",  "vision")

# All agents converge at coordinator
builder.add_edge("technical",   "coordinator")
builder.add_edge("fundamental", "coordinator")
builder.add_edge("risk",        "coordinator")
builder.add_edge("vision",      "coordinator")

# HITL gate — pauses execution before coordinator runs
graph = builder.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["coordinator"]
)
```

### Public API

```python
from graph.pipeline import run_pipeline, resume_pipeline

# Start analysis — returns state at HITL pause + a thread ID
state, thread_id = run_pipeline("RELIANCE.NS", period="3mo", interval="1d")

# After human review, resume (approved=True) or reject (approved=False)
final_state = resume_pipeline(thread_id, approved=True)
report = final_state["final_report"]
```

### Shared State (`TradingState`)

A `TypedDict` shared across all graph nodes with safe empty defaults:

| Key | Set by | Read by |
|-----|--------|---------|
| `ticker`, `period`, `interval`, `image_b64` | Caller | All nodes |
| `technical_data`, `fundamental_data`, `options_data`, `broker_recs`, `market_news` | `fetch_data` node | Agent nodes |
| `technical_analysis`, `fundamental_analysis`, `risk_analysis`, `vision_analysis` | Agent nodes | Coordinator |
| `human_approved` | UI (HITL gate) | Coordinator |
| `final_report` | Coordinator | UI |

---

## Streamlit Dashboard

The dashboard (`app.py`) has **10 tabs**:

| Tab | Description |
|-----|-------------|
| **📋 Watchlist** | Manage your personal stock watchlist — add/remove tickers, view quick metrics |
| **📈 Trade Today** | Full MAS pipeline: run analysis, review 3 agent outputs, approve/reject via HITL, get final trade report |
| **🔮 Future Analysis** | Swing/positional trade analysis with longer time horizons |
| **📊 Analysis** | Technical charting: Plotly candlestick + EMA overlays + RSI + MACD subplots |
| **🎯 Today's Picks** | Live broker recommendations from 3 sources + latest market news feed |
| **💬 Megha Chat** | Conversational interface — type natural queries like "Analyze TCS", "PCR for NIFTY", "news" |
| **👁️ Vision** | Upload a chart screenshot → Vision Agent identifies ticker, pattern, trend → optionally add to watchlist |
| **🔔 Alerts** | Set configurable alerts per ticker: interval, email/Discord notifications, trading-hours-only toggle |
| **💬 Feedback** | Submit feedback to admin |
| **🛡️ Admin** | Admin-only: user management (create/delete), unread feedback review, system status |

---

## Authentication & User Management

The system uses a lightweight but secure auth layer built on Streamlit session state + SQLite:

- **Login gate**: `require_login()` in `auth/auth_manager.py` shows a styled login form and calls `st.stop()` if the user is not authenticated
- **Password hashing**: `bcrypt` — passwords are never stored in plain text
- **Roles**: `admin` and `user`. Admins can access the Admin Panel tab, see the feedback unread badge, and manage users
- **Admin bootstrap**: On first startup, the admin user is seeded from `config.toml` via `bootstrap_admin()` — no manual DB setup required
- **Session management**: User dict stored in `st.session_state["user"]`; `logout()` clears it

### Adding Users

Users can be added by the admin from the Admin Panel tab in the running app, or programmatically:
```python
from db.user_db import create_user
create_user("alice", "securepassword", role="user", display_name="Alice")
```

---

## Alert Engine

The alert engine runs as a **background daemon thread** powered by APScheduler, started once at app launch via `start_alert_engine()`.

### How It Works

1. Every **5 minutes**, the scheduler calls `_check_all_alerts()`
2. For each active alert, it checks:
   - Is the configured **interval** (e.g. every 30 min) elapsed since last trigger?
   - Is `trading_hours_only` enabled? If so, is it currently **NSE market hours** (9:15–15:30 IST, Mon–Fri)?
3. If due, the alert runs the **MAS pipeline** (`fetch_data → technical → risk → coordinator`) automatically — HITL is **bypassed** for automated alerts
4. The final trade report is sent via:
   - 📧 **Email** (Gmail SMTP) — configured in `config.toml`
   - 💬 **Discord** (webhook) — configurable per-alert or globally

### Alert Configuration (UI)
Users set up alerts in the **🔔 Alerts** tab:
- Ticker symbol
- Check interval (minutes)
- Trading hours only toggle
- Email address and/or Discord webhook URL

---

## Setup & Installation

### Prerequisites

- **Python 3.10** (managed by `.python-version`)
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

### 5. Configure the app

Edit `config.toml` before first launch:

```toml
[admin]
username = "megha"
password = "your_strong_password"   # Change this!
display_name = "Megha (Admin)"

[email]
smtp_host = "smtp.gmail.com"
smtp_port = 587
sender_email = "yourname@gmail.com"
sender_app_password = "xxxx xxxx xxxx xxxx"   # Gmail App Password

[discord]
default_webhook_url = "https://discord.com/api/webhooks/..."   # Optional

[trading_hours]
market_open_hour = 9
market_open_minute = 15
market_close_hour = 15
market_close_minute = 30
timezone = "Asia/Kolkata"
```

---

## Running the App

```bash
# 1. Make sure Ollama is running (in a separate terminal):
ollama serve

# 2. Activate your virtual environment:
source .venv/bin/activate

# 3. Launch the Streamlit dashboard:
streamlit run app.py
```

The app opens at **http://localhost:8501**

**Default login credentials** (from `config.toml`):
- Username: `megha`
- Password: `admin123` ← Change this before sharing!

---

## Configuration

### `config.toml`

| Section | Key | Description |
|---------|-----|-------------|
| `[admin]` | `username`, `password`, `display_name` | Seeded on first startup |
| `[email]` | `smtp_host`, `smtp_port`, `sender_email`, `sender_app_password` | Gmail SMTP for alert emails |
| `[discord]` | `default_webhook_url` | Global Discord webhook for alerts |
| `[trading_hours]` | `market_open_hour/minute`, `market_close_hour/minute` | NSE hours for alert engine |

### `data/watchlist.json`

Customise your stock universe:

```json
{
  "watchlist": {
    "Nifty50":   ["RELIANCE.NS", "TCS.NS", "..."],
    "BankNifty": ["HDFCBANK.NS", "ICICIBANK.NS", "..."],
    "Custom":    ["ZOMATO.NS", "DMART.NS"]
  },
  "indices": {
    "Nifty50":   "^NSEI",
    "BankNifty": "^NSEBANK"
  }
}
```

### Ollama Model Selection

To swap the LLM used by any agent, change the model name in the agent file:

```python
# In agents/technical_agent.py (or any agent)
llm = OllamaLLM(model="mistral:7b")   # swap any Ollama-supported model
```

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| **`ta` library instead of `pandas-ta`** | `pandas-ta` requires Python ≥ 3.12. The `ta` library covers EMA, RSI, MACD with a clean API and works on Python 3.10 |
| **Dual-source NSE options fetching** | `nsepython` fails outside market hours or after NSE rate-limits; direct NSE API with cookie priming is the fallback. Never a hard failure |
| **Three scraper sources** | Financial news sites frequently block scrapers. Running Moneycontrol → ET → Livemint in sequence maximises coverage. All errors are caught; partial results still returned |
| **All tools return dicts, never raise** | Agents need predictable inputs. Every tool wraps its core logic in `try/except` and returns `{"error": "..."}` on failure so the rest of the pipeline continues |
| **LangGraph over plain LangChain** | LangGraph's directed graph allows isolated agents, conditional edges, and built-in `interrupt_before` for HITL with `MemorySaver` checkpointing |
| **HITL before coordinator** | The Coordinator is the only agent that produces the final actionable recommendation. Pausing before it ensures humans can review all upstream reasoning before a trade signal is finalized |
| **APScheduler daemon thread** | Alerts need to run in the background without blocking the Streamlit event loop. APScheduler with `daemon=True` is lightweight, survives Streamlit reruns, and has fine-grained interval control |
| **bcrypt for auth** | Industry-standard adaptive hash — safe against brute-force even if the SQLite file is leaked. Admin is seeded from `config.toml` so no separate DB init script is needed |
| **SQLite, not PostgreSQL** | This is a local, single-machine tool. SQLite has zero setup, works out of the box, and is perfectly sufficient for one admin + a few users |
| **Modular files, not a monolith** | Each file has one responsibility with full docstrings, making it easy to read, test, and extend independently |

---

## Disclaimer

> **This project is for educational and research purposes only.**  
> It does not constitute financial advice. Stock markets involve risk. Always consult a SEBI-registered financial advisor before making investment decisions.  
> The authors are not responsible for any trading losses incurred using this tool.

---

## License

MIT License — free to use, modify, and distribute with attribution.
