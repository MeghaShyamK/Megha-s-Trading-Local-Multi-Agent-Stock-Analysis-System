"""
pages/trade_today_page.py
--------------------------
Trade Today / Invest Today tab:
  - Select stock from watchlist or type custom ticker
  - Choose instrument: Stock | Options | Futures | Derivatives | Bonds
  - Technical indicators checkboxes
  - Fundamental metrics checkboxes
  - Timeframe 1min → 1Month
  - Async MAS pipeline → Buy/Sell/Hold + Entry/Target/SL + R:R
  - Inline chat for follow-up questions
"""
from __future__ import annotations
import streamlit as st

from auth.auth_manager import current_user
from db.watchlist_db import get_watchlist as get_user_watchlist
from async_runner.task_queue import submit, get_status, get_result

TIMEFRAMES = {
    "1 Min": ("1m", "1d"), "5 Min": ("5m", "5d"), "15 Min": ("15m", "5d"),
    "30 Min": ("30m", "1mo"), "1 Hour": ("1h", "3mo"), "4 Hour": ("4h", "3mo"),
    "1 Day": ("1d", "6mo"), "1 Week": ("1wk", "2y"), "1 Month": ("1mo", "5y"),
}

TECH_INDICATORS = ["RSI", "MACD", "EMA 20", "EMA 50", "EMA 200",
                   "Bollinger Bands", "Fibonacci", "Volume"]
FUND_METRICS = ["P/E Ratio", "Forward P/E", "EPS", "Revenue Growth",
                "Dividend Yield", "Analyst Rating", "P/B Ratio"]
INSTRUMENTS = ["Stock", "Options", "Futures", "Derivatives", "Bonds"]


def _run_trade_pipeline(ticker: str, interval: str, period: str,
                        indicators: list, fund_metrics: list) -> dict:
    """Run the MAS pipeline. Executed in background thread."""
    from tools.data_fetcher import get_technical_data, get_fundamental_data
    from tools.options_fetcher import get_option_chain
    from tools.scraper import get_broker_recommendations
    from agents.technical_agent import technical_agent_node
    from agents.fundamental_agent import fundamental_agent_node
    from agents.risk_agent import risk_agent_node
    from agents.coordinator_agent import coordinator_agent_node
    from graph.state import initial_state
    import re

    state = initial_state(ticker=ticker, period=period, interval=interval)

    # Fetch data based on selected metrics
    state["technical_data"] = get_technical_data(ticker, period=period, interval=interval)
    state["fundamental_data"] = get_fundamental_data(ticker) if fund_metrics else {}
    opt_sym = re.sub(r"\.(NS|BO)$", "", ticker.upper())
    state["options_data"] = get_option_chain(opt_sym)
    state["broker_recs"] = get_broker_recommendations(max_results=20)
    state["market_news"] = {}

    # Run agents
    state.update(technical_agent_node(state))
    if fund_metrics:
        state.update(fundamental_agent_node(state))
    state.update(risk_agent_node(state))

    # Auto-approve for Trade Today (no HITL — user is interacting live)
    state["human_approved"] = True
    state.update(coordinator_agent_node(state))

    return state


def _chat_response(query: str, ticker: str, report: dict) -> str:
    """Quick LLM chat for follow-up questions about the trade."""
    try:
        from langchain_ollama import OllamaLLM
        llm = OllamaLLM(model="qwen2.5:7b", temperature=0.2)
        context = f"""You are a trading assistant. The user just received this trade recommendation:
Ticker: {ticker}
Action: {report.get('action')}
Entry: {report.get('entry_price')}
Target: {report.get('target_price')}
Stop Loss: {report.get('stop_loss')}
Conviction: {report.get('conviction_score')}/10
Summary: {report.get('summary')}

Answer the user's follow-up question concisely (2-3 sentences max):
Question: {query}"""
        return llm.invoke(context)
    except Exception as e:
        return f"Chat error: {e}. Make sure Ollama is running."


def render():
    user = current_user()
    user_id = user["id"]

    st.markdown("## 📈 Trade Today / Invest Today")
    st.caption("Real-time analysis to decide whether to trade or invest right now.")

    # ── Controls ──────────────────────────────────────────────────────────────
    wl = get_user_watchlist(user_id)
    wl_tickers = [w["ticker"] for w in wl]
    wl_labels = {w["ticker"]: f"{w['ticker']} — {w.get('company_name', '')[:30]}" for w in wl}

    c1, c2, c3 = st.columns([3, 2, 2])
    with c1:
        ticker_source = st.radio("Ticker from", ["My Watchlist", "Custom"], horizontal=True, key="tt_src")
        if ticker_source == "My Watchlist" and wl_tickers:
            ticker = st.selectbox("Select Stock", wl_tickers,
                                  format_func=lambda t: wl_labels.get(t, t), key="tt_wl_sel")
        else:
            ticker = st.text_input("Enter Ticker", placeholder="RELIANCE.NS", key="tt_custom")
            if ticker and "." not in ticker:
                ticker += ".NS"

    with c2:
        instrument = st.selectbox("Instrument", INSTRUMENTS, key="tt_instrument")
        tf_label = st.selectbox("Timeframe", list(TIMEFRAMES.keys()), index=6, key="tt_tf")

    with c3:
        tech_inds = st.multiselect("Technical Indicators", TECH_INDICATORS,
                                   default=["RSI", "MACD", "EMA 20", "EMA 50"], key="tt_tech")
        fund_mets = st.multiselect("Fundamental Metrics", FUND_METRICS,
                                   default=[], key="tt_fund")

    interval, period = TIMEFRAMES[tf_label]

    # ── Run Analysis button ────────────────────────────────────────────────────
    st.markdown("")
    run_col, _ = st.columns([1, 3])
    with run_col:
        run_btn = st.button("🚀 Analyse Now", key="tt_run", use_container_width=True,
                            disabled=not ticker)

    if run_btn and ticker:
        job_id = submit(_run_trade_pipeline, ticker, interval, period, tech_inds, fund_mets)
        st.session_state["tt_job_id"] = job_id
        st.session_state["tt_ticker"] = ticker
        st.session_state["tt_result"] = None
        st.session_state["tt_chat"] = []
        st.rerun()

    # ── Poll job status ────────────────────────────────────────────────────────
    job_id = st.session_state.get("tt_job_id")
    if job_id:
        status = get_status(job_id)
        if status in ("pending", "running"):
            with st.spinner(f"🧠 Agents are analysing {st.session_state.get('tt_ticker', '')}..."):
                st.markdown('<meta http-equiv="refresh" content="3">', unsafe_allow_html=True)
        elif status == "done" and not st.session_state.get("tt_result"):
            result, _ = get_result(job_id)
            st.session_state["tt_result"] = result
            st.session_state["tt_job_id"] = None
            st.rerun()
        elif status == "error":
            _, exc = get_result(job_id)
            st.error(f"❌ Pipeline error: {exc}")
            st.session_state["tt_job_id"] = None

    # ── Display results ────────────────────────────────────────────────────────
    result_state = st.session_state.get("tt_result")
    if result_state:
        report = result_state.get("final_report", {})
        ticker_used = st.session_state.get("tt_ticker", "")

        if report and report.get("status") != "awaiting_approval":
            st.markdown("---")
            action = report.get("action", "Hold")
            action_colors = {"Buy": "#10b981", "Sell": "#ef4444", "Hold": "#f59e0b", "Avoid": "#6b7280"}
            action_color = action_colors.get(action, "#94a3b8")
            conviction = report.get("conviction_score", 5)
            entry = report.get("entry_price")
            target = report.get("target_price")
            stop = report.get("stop_loss")
            rr = report.get("risk_reward_ratio")

            # ── Main recommendation card ──────────────────────────────────────
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,rgba(59,130,246,0.07),rgba(99,102,241,0.07));
                        border:1px solid rgba(96,165,250,0.2);border-radius:16px;padding:1.5rem;margin-bottom:1rem;">
                <p style="color:#64748b;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.1em;margin:0;">
                TRADE RECOMMENDATION — {ticker_used}</p>
                <p style="font-size:2rem;font-weight:800;color:{action_color};margin:0.4rem 0;">
                {action} {'▲' if action == 'Buy' else '▼' if action == 'Sell' else '◆'}</p>
            </div>
            """, unsafe_allow_html=True)

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Entry Price", f"₹{entry:,.2f}" if entry else "Market")
            m2.metric("Target Price", f"₹{target:,.2f}" if target else "N/A",
                      f"+{((target-entry)/entry*100):.1f}%" if (target and entry) else None)
            m3.metric("Stop Loss", f"₹{stop:,.2f}" if stop else "N/A",
                      f"-{((entry-stop)/entry*100):.1f}%" if (stop and entry) else None)
            m4.metric("Risk:Reward", f"{rr:.2f}:1" if rr else "N/A")
            m5.metric("Conviction", f"{conviction}/10")

            # ── Why Buy / Why Sell ────────────────────────────────────────────
            ta = result_state.get("technical_analysis", {})
            fa = result_state.get("fundamental_analysis", {})
            ra = result_state.get("risk_analysis", {})

            why_col, risk_col = st.columns(2)
            with why_col:
                positives = fa.get("positives", []) + [ta.get("reasoning", "")]
                st.markdown("#### ✅ Why to Trade")
                st.markdown(f"**Trend:** {ta.get('trend', 'N/A')} | **Signal:** {ta.get('signal', 'N/A')}")
                for p in positives[:3]:
                    if p:
                        st.markdown(f"• {p}")

            with risk_col:
                risks = ra.get("reasons_to_avoid", [])
                st.markdown("#### ⚠️ Key Risks")
                st.markdown(f"**Risk Level:** {ra.get('risk_level', 'N/A')}")
                for r in risks[:3]:
                    st.markdown(f"• {r}")

            # ── Where to buy / Where to sell ──────────────────────────────────
            fib = result_state.get("technical_data", {}).get("indicators", {}).get("Fibonacci_60d", {})
            if fib:
                st.markdown("#### 📐 Key Price Levels (Fibonacci)")
                fib_cols = st.columns(len(fib))
                for i, (level, price_val) in enumerate(fib.items()):
                    fib_cols[i].metric(level, f"₹{price_val:,.2f}" if price_val else "N/A")

            # Summary
            if report.get("summary"):
                st.markdown(f"""
                <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
                            border-radius:10px;padding:1rem;margin-top:0.5rem;">
                    <p style="color:#64748b;font-size:0.75rem;margin:0 0 0.4rem;">AI SUMMARY</p>
                    <p style="color:#e2e8f0;margin:0;font-size:0.9rem;">{report['summary']}</p>
                </div>
                """, unsafe_allow_html=True)

            # ── Inline Chat ───────────────────────────────────────────────────
            st.markdown("---")
            st.markdown("#### 💬 Ask a follow-up question")

            chat_history = st.session_state.get("tt_chat", [])
            for msg in chat_history:
                role_style = "user" if msg["role"] == "user" else "assistant"
                prefix = "🧑 You" if msg["role"] == "user" else "🤖 AI"
                css = ("background:rgba(59,130,246,0.1);border-radius:10px;padding:0.6rem;margin:0.3rem 0;"
                       if msg["role"] == "user"
                       else "background:rgba(255,255,255,0.03);border-radius:10px;padding:0.6rem;margin:0.3rem 0;")
                st.markdown(f'<div style="{css}"><b style="color:#64748b;font-size:0.75rem;">{prefix}</b><br>{msg["content"]}</div>',
                            unsafe_allow_html=True)

            with st.form("tt_chat_form", clear_on_submit=True):
                chat_q = st.text_input("Your question", placeholder="Why is the stop loss there? What's the best entry?",
                                       label_visibility="collapsed")
                if st.form_submit_button("Ask →"):
                    if chat_q:
                        chat_history.append({"role": "user", "content": chat_q})
                        with st.spinner("Thinking..."):
                            ans = _chat_response(chat_q, ticker_used, report)
                        chat_history.append({"role": "assistant", "content": ans})
                        st.session_state["tt_chat"] = chat_history
                        st.rerun()
    else:
        st.markdown("""
        <div style="text-align:center;padding:4rem 2rem;background:rgba(255,255,255,0.02);
                    border:1px solid rgba(255,255,255,0.05);border-radius:12px;margin-top:1rem;">
            <p style="font-size:2.5rem;">📈</p>
            <p style="color:#64748b;">Select a stock, choose your indicators, and click Analyse Now.</p>
        </div>
        """, unsafe_allow_html=True)
