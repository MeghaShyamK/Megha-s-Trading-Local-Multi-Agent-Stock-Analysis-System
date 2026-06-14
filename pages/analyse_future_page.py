"""
pages/analyse_future_page.py
-----------------------------
Analyse for Future tab:
  - Same controls as Trade Today
  - Output includes Save / Delete buttons
  - Right sidebar: saved analyses list with expand/delete
"""
from __future__ import annotations
import json
import streamlit as st
from datetime import datetime

from auth.auth_manager import current_user
from db.watchlist_db import get_watchlist as get_user_watchlist
from db.saved_analyses_db import save_analysis, get_saved_analyses, delete_analysis
from async_runner.task_queue import submit, get_status, get_result

TIMEFRAMES = {
    "1 Day": ("1d", "6mo"), "1 Week": ("1wk", "2y"),
    "1 Month": ("1mo", "5y"), "3 Months": ("3mo", "5y"),
}

TECH_INDICATORS = ["RSI", "MACD", "EMA 20", "EMA 50", "EMA 200",
                   "Bollinger Bands", "Fibonacci", "Volume"]
FUND_METRICS = ["P/E Ratio", "Forward P/E", "EPS", "Revenue Growth",
                "Dividend Yield", "Analyst Rating"]


def _run_future_pipeline(ticker: str, interval: str, period: str,
                         indicators: list, fund_metrics: list) -> dict:
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
    state["technical_data"] = get_technical_data(ticker, period=period, interval=interval)
    state["fundamental_data"] = get_fundamental_data(ticker) if fund_metrics else {}
    opt_sym = re.sub(r"\.(NS|BO)$", "", ticker.upper())
    state["options_data"] = get_option_chain(opt_sym)
    state["broker_recs"] = get_broker_recommendations(max_results=20)
    state["market_news"] = {}

    state.update(technical_agent_node(state))
    if fund_metrics:
        state.update(fundamental_agent_node(state))
    state.update(risk_agent_node(state))
    state["human_approved"] = True
    state.update(coordinator_agent_node(state))
    return state


def _fmt_price(v) -> str:
    return f"₹{v:,.2f}" if v else "N/A"


def render():
    user = current_user()
    user_id = user["id"]

    st.markdown("## 🔮 Analyse for Future")
    st.caption("Analyse using current data to plan a future trade. Save results to review later.")

    # ── Layout: main left + saved sidebar right ───────────────────────────────
    main_col, saved_col = st.columns([2, 1])

    with main_col:
        # ── Controls ──────────────────────────────────────────────────────────
        wl = get_user_watchlist(user_id)
        wl_tickers = [w["ticker"] for w in wl]
        wl_labels = {w["ticker"]: f"{w['ticker']} — {w.get('company_name', '')[:30]}" for w in wl}

        c1, c2 = st.columns(2)
        with c1:
            src = st.radio("Ticker from", ["My Watchlist", "Custom"], horizontal=True, key="af_src")
            if src == "My Watchlist" and wl_tickers:
                ticker = st.selectbox("Select Stock", wl_tickers,
                                      format_func=lambda t: wl_labels.get(t, t), key="af_wl")
            else:
                ticker = st.text_input("Enter Ticker", placeholder="RELIANCE.NS", key="af_custom")
                if ticker and "." not in ticker and not ticker.startswith("^"):
                    ticker += ".NS"

        with c2:
            tf_label = st.selectbox("Timeframe", list(TIMEFRAMES.keys()), key="af_tf")
            tech_inds = st.multiselect("Technical Indicators", TECH_INDICATORS,
                                       default=["RSI", "MACD", "EMA 20"], key="af_tech")
            fund_mets = st.multiselect("Fundamental Metrics", FUND_METRICS,
                                       default=["P/E Ratio"], key="af_fund")

        interval, period = TIMEFRAMES[tf_label]

        run_btn = st.button("🔮 Analyse for Future", key="af_run", use_container_width=True,
                            disabled=not ticker)

        if run_btn and ticker:
            job_id = submit(_run_future_pipeline, ticker, interval, period, tech_inds, fund_mets)
            st.session_state["af_job_id"] = job_id
            st.session_state["af_ticker"] = ticker
            st.session_state["af_tf"] = tf_label
            st.session_state["af_result"] = None
            st.rerun()

        # ── Poll ──────────────────────────────────────────────────────────────
        job_id = st.session_state.get("af_job_id")
        if job_id:
            status = get_status(job_id)
            if status in ("pending", "running"):
                st.spinner(f"🧠 Analysing {st.session_state.get('af_ticker', '')}...")
                st.markdown('<meta http-equiv="refresh" content="3">', unsafe_allow_html=True)
            elif status == "done" and not st.session_state.get("af_result"):
                result, _ = get_result(job_id)
                st.session_state["af_result"] = result
                st.session_state["af_job_id"] = None
                st.rerun()
            elif status == "error":
                _, exc = get_result(job_id)
                st.error(f"❌ {exc}")
                st.session_state["af_job_id"] = None

        # ── Display results ───────────────────────────────────────────────────
        result_state = st.session_state.get("af_result")
        if result_state:
            report = result_state.get("final_report", {})
            ticker_used = st.session_state.get("af_ticker", "")
            tf_used = st.session_state.get("af_tf", "")

            if report and report.get("status") != "awaiting_approval":
                action = report.get("action", "Hold")
                action_colors = {"Buy": "#10b981", "Sell": "#ef4444", "Hold": "#f59e0b", "Avoid": "#6b7280"}
                color = action_colors.get(action, "#94a3b8")
                conviction = report.get("conviction_score", 5)

                st.markdown(f"""
                <div style="background:linear-gradient(135deg,rgba(167,139,250,0.08),rgba(99,102,241,0.08));
                            border:1px solid rgba(167,139,250,0.2);border-radius:16px;padding:1.5rem;">
                    <p style="color:#64748b;font-size:0.75rem;text-transform:uppercase;margin:0;">
                    FUTURE ANALYSIS — {ticker_used} ({tf_used})</p>
                    <p style="font-size:2rem;font-weight:800;color:{color};margin:0.4rem 0;">{action}</p>
                </div>
                """, unsafe_allow_html=True)

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Entry", _fmt_price(report.get("entry_price")))
                m2.metric("Target", _fmt_price(report.get("target_price")))
                m3.metric("Stop Loss", _fmt_price(report.get("stop_loss")))
                m4.metric("Conviction", f"{conviction}/10")

                if report.get("summary"):
                    st.markdown(f"""
                    <div style="background:rgba(255,255,255,0.03);border-radius:10px;
                                padding:1rem;margin-top:0.5rem;">
                        <p style="color:#94a3b8;font-size:0.75rem;margin:0 0 0.3rem;">ANALYSIS</p>
                        <p style="color:#e2e8f0;margin:0;font-size:0.9rem;">{report['summary']}</p>
                    </div>
                    """, unsafe_allow_html=True)

                # ── Save / Delete buttons ─────────────────────────────────────
                st.markdown("")
                save_col1, save_col2 = st.columns([2, 1])
                with save_col1:
                    save_label = st.text_input("Save as label",
                                               value=f"{ticker_used} {action} — {tf_used}",
                                               key="af_save_label")
                with save_col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("💾 Save Analysis", key="af_save_btn"):
                        # Compile full report for saving
                        full_report = {
                            "final_report": report,
                            "technical_analysis": result_state.get("technical_analysis", {}),
                            "fundamental_analysis": result_state.get("fundamental_analysis", {}),
                            "risk_analysis": result_state.get("risk_analysis", {}),
                        }
                        aid = save_analysis(user_id, ticker_used, save_label,
                                           full_report, interval, "future")
                        st.success(f"✅ Saved! (ID #{aid})")
                        st.rerun()

                if st.button("🗑️ Discard Analysis", key="af_discard"):
                    st.session_state["af_result"] = None
                    st.rerun()

    # ── Saved analyses sidebar ────────────────────────────────────────────────
    with saved_col:
        st.markdown("### 📁 Saved Analyses")
        saved = get_saved_analyses(user_id, analysis_type="future")

        if not saved:
            st.markdown("""
            <div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);
                        border-radius:10px;padding:1.5rem;text-align:center;">
                <p style="color:#475569;font-size:0.85rem;">No saved analyses yet.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            for s in saved:
                with st.expander(f"📄 {s.get('label', s['ticker'])} [{s['saved_at'][:10]}]"):
                    analysis = s.get("analysis", {})
                    report = analysis.get("final_report", {})
                    action = report.get("action", "N/A")
                    color = {"Buy": "#10b981", "Sell": "#ef4444"}.get(action, "#f59e0b")
                    st.markdown(f"**Action:** <span style='color:{color};font-weight:700;'>{action}</span>",
                                unsafe_allow_html=True)
                    st.markdown(f"**Entry:** {_fmt_price(report.get('entry_price'))} | "
                                f"**Target:** {_fmt_price(report.get('target_price'))} | "
                                f"**SL:** {_fmt_price(report.get('stop_loss'))}")
                    st.markdown(f"**Conviction:** {report.get('conviction_score', 'N/A')}/10")
                    summary = report.get("summary", "")
                    if summary:
                        st.caption(summary[:200] + "...")
                    if st.button("🗑️ Delete", key=f"af_del_{s['id']}"):
                        delete_analysis(s["id"], user_id)
                        st.rerun()
