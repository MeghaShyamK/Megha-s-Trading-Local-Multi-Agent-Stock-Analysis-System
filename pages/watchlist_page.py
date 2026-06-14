"""
pages/watchlist_page.py
------------------------
Enhanced Watchlist tab with:
  - Per-user watchlist from SQLite
  - Real company names + live prices
  - Click any stock → OHLCV overview panel + mini chart
  - Add/Remove tickers
  - Devil's Advocate panel (right column) — "Do Not Touch" list by timeframe
"""
from __future__ import annotations
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from auth.auth_manager import current_user
from db.watchlist_db import get_watchlist, add_ticker, remove_ticker, ticker_exists
from async_runner.task_queue import submit, get_status, get_result

TIMEFRAMES = {
    "1 Min": "1m", "5 Min": "5m", "15 Min": "15m", "30 Min": "30m",
    "1 Hour": "1h", "4 Hour": "4h", "1 Day": "1d", "1 Week": "1wk"
}

PERIOD_FOR_INTERVAL = {
    "1m": "1d", "5m": "5d", "15m": "5d", "30m": "1mo",
    "1h": "3mo", "4h": "3mo", "1d": "6mo", "1wk": "2y"
}


def _fetch_ticker_info(ticker: str) -> dict:
    """Fetch live quote + company info from yfinance."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.info or {}
        fast = t.fast_info
        return {
            "ticker": ticker,
            "company_name": info.get("longName") or info.get("shortName", ticker),
            "sector": info.get("sector", ""),
            "price": getattr(fast, "last_price", None),
            "prev_close": getattr(fast, "previous_close", None),
            "open": getattr(fast, "open", None),
            "day_high": getattr(fast, "day_high", None),
            "day_low": getattr(fast, "day_low", None),
            "volume": getattr(fast, "three_month_average_volume", None),
            "market_cap": info.get("marketCap"),
            "week_52_high": info.get("fiftyTwoWeekHigh"),
            "week_52_low": info.get("fiftyTwoWeekLow"),
            "pe_ratio": info.get("trailingPE"),
        }
    except Exception as e:
        return {"ticker": ticker, "company_name": ticker, "error": str(e)}


def _mini_chart(ticker: str, interval: str = "1d") -> go.Figure:
    """Build a small candlestick chart for watchlist overview."""
    from tools.data_fetcher import get_technical_data
    period = PERIOD_FOR_INTERVAL.get(interval, "3mo")
    td = get_technical_data(ticker, period=period, interval=interval)
    ohlcv = td.get("ohlcv", [])

    fig = go.Figure()
    if ohlcv:
        df = pd.DataFrame(ohlcv)
        date_col = df.columns[0]
        fig.add_trace(go.Candlestick(
            x=df[date_col], open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"],
            increasing_line_color="#10b981", decreasing_line_color="#ef4444",
            showlegend=False,
        ))

    fig.update_layout(
        height=250, margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(10,14,26,0.4)",
        xaxis=dict(showgrid=False, rangeslider_visible=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
        font=dict(color="#94a3b8", size=10),
    )
    return fig


def render():
    user = current_user()
    user_id = user["id"]

    st.markdown("## 📋 My Watchlist")

    # ── Timeframe selector (for Devil's Advocate) ────────────────────────────
    tf_col1, tf_col2 = st.columns([3, 1])
    with tf_col2:
        selected_tf_label = st.selectbox(
            "Timeframe", list(TIMEFRAMES.keys()), index=6, key="wl_timeframe"
        )
    selected_tf = TIMEFRAMES[selected_tf_label]

    # ── Add ticker form ───────────────────────────────────────────────────────
    with st.expander("➕ Add to Watchlist", expanded=False):
        add_col1, add_col2 = st.columns([3, 1])
        with add_col1:
            new_ticker = st.text_input(
                "NSE Ticker", placeholder="e.g. RELIANCE.NS, TCS.NS",
                key="wl_add_ticker"
            )
        with add_col2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Add", key="wl_add_btn"):
                if new_ticker:
                    tk = new_ticker.strip().upper()
                    if not tk.endswith(".NS") and not tk.endswith(".BO") and not tk.startswith("^"):
                        tk += ".NS"
                    if ticker_exists(user_id, tk):
                        st.warning(f"{tk} is already in your watchlist.")
                    else:
                        with st.spinner(f"Fetching {tk} info..."):
                            info = _fetch_ticker_info(tk)
                        add_ticker(user_id, tk, info.get("company_name", tk), info.get("sector", ""))
                        st.success(f"✅ Added {info.get('company_name', tk)} ({tk})")
                        st.rerun()

    # ── Load watchlist ────────────────────────────────────────────────────────
    wl = get_watchlist(user_id)

    if not wl:
        st.markdown("""
        <div style="text-align:center;padding:3rem;background:rgba(255,255,255,0.02);
                    border:1px solid rgba(255,255,255,0.06);border-radius:12px;margin-top:1rem;">
            <p style="font-size:2rem;">📋</p>
            <p style="color:#64748b;">Your watchlist is empty. Add tickers above to get started.</p>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Main layout: watchlist left, Devil's Advocate right ──────────────────
    main_col, devil_col = st.columns([2, 1])

    devil_avoid = []   # tickers flagged as "do not touch"

    with main_col:
        st.markdown(f"**{len(wl)} stocks tracked**")

        for item in wl:
            ticker = item["ticker"]
            company = item.get("company_name") or ticker

            # ── Stock row card ───────────────────────────────────────────────
            with st.container():
                row_col1, row_col2 = st.columns([5, 1])

                with row_col1:
                    # Fetch live price (cached per ticker per session)
                    cache_key = f"wl_info_{ticker}"
                    if cache_key not in st.session_state:
                        with st.spinner(f"Loading {ticker}..."):
                            st.session_state[cache_key] = _fetch_ticker_info(ticker)
                    info = st.session_state[cache_key]

                    price = info.get("price")
                    prev_close = info.get("prev_close")
                    change = None
                    change_pct = None
                    if price and prev_close and prev_close != 0:
                        change = price - prev_close
                        change_pct = (change / prev_close) * 100

                    change_color = "#10b981" if (change_pct or 0) >= 0 else "#ef4444"
                    change_str = (f"{'▲' if change_pct >= 0 else '▼'} {abs(change_pct):.2f}%"
                                  if change_pct is not None else "")

                    st.markdown(f"""
                    <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
                                border-radius:10px;padding:0.75rem 1rem;margin-bottom:0.4rem;cursor:pointer;">
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <div>
                                <span style="font-weight:700;color:#e2e8f0;font-size:0.95rem;">{ticker}</span>
                                <span style="color:#64748b;font-size:0.8rem;margin-left:0.5rem;">{company[:35]}</span>
                            </div>
                            <div style="text-align:right;">
                                <span style="font-weight:700;color:#e2e8f0;">{'₹{:,.2f}'.format(price) if price else 'N/A'}</span>
                                <span style="color:{change_color};font-size:0.82rem;margin-left:0.5rem;">{change_str}</span>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                with row_col2:
                    detail_key = f"wl_show_{ticker}"
                    if st.button("📊", key=f"wl_detail_{ticker}", help="View OHLCV overview"):
                        st.session_state[detail_key] = not st.session_state.get(detail_key, False)
                    if st.button("🗑️", key=f"wl_del_{ticker}", help="Remove from watchlist"):
                        remove_ticker(user_id, ticker)
                        st.session_state.pop(cache_key, None)
                        st.rerun()

                # ── OHLCV Detail panel ───────────────────────────────────────
                if st.session_state.get(f"wl_show_{ticker}", False):
                    info = st.session_state.get(cache_key, {})
                    with st.container():
                        st.markdown(f"#### {company} ({ticker})")
                        m1, m2, m3, m4, m5, m6 = st.columns(6)
                        m1.metric("Price", f"₹{info.get('price'):,.2f}" if info.get('price') else "N/A")
                        m2.metric("Prev Close", f"₹{info.get('prev_close'):,.2f}" if info.get('prev_close') else "N/A")
                        m3.metric("Open", f"₹{info.get('open'):,.2f}" if info.get('open') else "N/A")
                        m4.metric("Day High", f"₹{info.get('day_high'):,.2f}" if info.get('day_high') else "N/A")
                        m5.metric("Day Low", f"₹{info.get('day_low'):,.2f}" if info.get('day_low') else "N/A")
                        m6.metric("P/E Ratio", f"{info.get('pe_ratio'):.1f}" if info.get('pe_ratio') else "N/A")

                        # Mini chart
                        fig = _mini_chart(ticker, interval=selected_tf)
                        st.plotly_chart(fig, use_container_width=True)
                        st.markdown("---")

                # ── Devil's Advocate (async background check) ────────────────
                devil_key = f"devil_{ticker}_{selected_tf}"
                if devil_key not in st.session_state:
                    def _run_risk(t=ticker, tf=selected_tf):
                        from tools.data_fetcher import get_technical_data
                        from tools.options_fetcher import get_option_chain
                        from agents.risk_agent import risk_agent_node
                        from graph.state import initial_state
                        import re
                        period = PERIOD_FOR_INTERVAL.get(tf, "3mo")
                        td = get_technical_data(t, period=period, interval=tf)
                        opt_sym = re.sub(r"\.(NS|BO)$", "", t.upper())
                        od = get_option_chain(opt_sym)
                        state = initial_state(ticker=t, interval=tf)
                        state["technical_data"] = td
                        state["options_data"] = od
                        state["fundamental_analysis"] = {}
                        result = risk_agent_node(state)
                        return result.get("risk_analysis", {})

                    job_id = submit(_run_risk)
                    st.session_state[devil_key] = job_id

                job_id = st.session_state.get(devil_key)
                if job_id:
                    status = get_status(job_id)
                    if status == "done":
                        result, _ = get_result(job_id)
                        if result and result.get("risk_level") == "High":
                            devil_avoid.append({"ticker": ticker, "company": company, "risk": result})

    # ── Devil's Advocate Panel ────────────────────────────────────────────────
    with devil_col:
        st.markdown(f"### 😈 Devil's Advocate")
        st.caption(f"Timeframe: {selected_tf_label}")

        if not devil_avoid:
            st.markdown("""
            <div style="background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.2);
                        border-radius:10px;padding:1rem;text-align:center;margin-top:0.5rem;">
                <p style="color:#10b981;margin:0;font-size:0.9rem;">✅ No high-risk stocks detected on this timeframe.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.2);
                        border-radius:10px;padding:0.75rem;margin-bottom:0.5rem;">
                <p style="color:#ef4444;font-weight:700;margin:0;font-size:0.85rem;">🚫 DO NOT TOUCH</p>
            </div>
            """, unsafe_allow_html=True)

            for item in devil_avoid:
                risk = item["risk"]
                reasons = risk.get("reasons_to_avoid", [])
                st.markdown(f"""
                <div style="background:rgba(239,68,68,0.06);border:1px solid rgba(239,68,68,0.15);
                            border-radius:8px;padding:0.75rem;margin-bottom:0.5rem;">
                    <p style="color:#fca5a5;font-weight:700;margin:0 0 0.3rem 0;font-size:0.85rem;">
                        🚫 {item['ticker']}</p>
                    <p style="color:#64748b;font-size:0.75rem;margin:0;">{item['company'][:30]}</p>
                    <p style="color:#ef4444;font-size:0.78rem;margin:0.4rem 0 0 0;font-weight:600;">
                        Risk: {risk.get('risk_level', 'High')}</p>
                    {''.join(f'<p style="color:#94a3b8;font-size:0.72rem;margin:0.2rem 0 0 0;">• {r[:60]}</p>' for r in reasons[:2])}
                </div>
                """, unsafe_allow_html=True)

        st.markdown("---")
        st.caption("ℹ️ Risk is assessed asynchronously in the background. Refresh if list is empty.")
        if st.button("🔄 Re-scan", key="devil_rescan"):
            for item in wl:
                key = f"devil_{item['ticker']}_{selected_tf}"
                st.session_state.pop(key, None)
            st.rerun()
