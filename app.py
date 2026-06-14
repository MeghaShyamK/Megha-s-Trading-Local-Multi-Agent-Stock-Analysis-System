"""
app.py — Megha's Trading System v2
------------------------------------
Login-gated multi-user Streamlit dashboard.
Tabs: Watchlist | Trade Today | Analyse Future | 📊 Analysis | Today's Picks |
      Chat | Vision | Alerts | Feedback | [Admin Panel — admin only]
"""
from __future__ import annotations
import streamlit as st

# ── Page config — MUST be first Streamlit call ────────────────────────────────
st.set_page_config(
    page_title="Megha's Trading — AI Stock Analysis",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Bootstrap: DB + admin user on first run ───────────────────────────────────
@st.cache_resource
def _bootstrap():
    from db.database import init_db
    from auth.auth_manager import bootstrap_admin
    from alerts.alert_engine import start_alert_engine
    init_db()
    bootstrap_admin()
    start_alert_engine()
    return True

_bootstrap()

# ── Auth check ────────────────────────────────────────────────────────────────
from auth.auth_manager import require_login, current_user, logout, is_admin
from db.feedback_db import unread_count

require_login()   # Shows login form and stops if not authenticated

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] { font-family: 'Inter', sans-serif; background: #0a0e1a; color: #e2e8f0; }
.stApp { background: linear-gradient(135deg, #0a0e1a 0%, #0d1529 40%, #0a1628 100%); }
.main .block-container { padding: 1.5rem 2rem 3rem 2rem; max-width: 1400px; }
.stTabs [data-baseweb="tab-list"] { background: rgba(255,255,255,0.03); border-radius: 12px; padding: 4px; border: 1px solid rgba(255,255,255,0.06); gap: 4px; }
.stTabs [data-baseweb="tab"] { border-radius: 8px; color: #64748b; font-weight: 500; font-size: 0.85rem; padding: 0.45rem 1rem; transition: all 0.2s ease; border: none !important; background: transparent; }
.stTabs [aria-selected="true"] { background: linear-gradient(135deg,rgba(96,165,250,0.2),rgba(167,139,250,0.2)) !important; color: #e2e8f0 !important; border: 1px solid rgba(96,165,250,0.3) !important; }
.stButton > button { background: linear-gradient(135deg,#3b82f6,#6366f1); color: white; border: none; border-radius: 10px; font-weight: 600; font-size: 0.9rem; padding: 0.6rem 1.5rem; transition: all 0.2s ease; }
.stButton > button:hover { background: linear-gradient(135deg,#2563eb,#4f46e5); transform: translateY(-1px); box-shadow: 0 4px 20px rgba(59,130,246,0.4); }
.stTextInput > div > div > input, .stSelectbox > div > div > div { background: rgba(255,255,255,0.05) !important; border: 1px solid rgba(255,255,255,0.1) !important; border-radius: 10px !important; color: #e2e8f0 !important; }
[data-testid="stMetric"] { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.07); border-radius: 12px; padding: 1rem 1.2rem; }
[data-testid="stMetricLabel"] { color: #64748b; font-size: 0.8rem; }
[data-testid="stMetricValue"] { color: #e2e8f0; font-size: 1.4rem; font-weight: 700; }
.glass-card { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 1.5rem; backdrop-filter: blur(10px); margin-bottom: 1rem; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-thumb { background: rgba(100,116,139,0.4); border-radius: 3px; }
.stAlert { border-radius: 10px !important; }
</style>
""", unsafe_allow_html=True)

# ── Header + User info ────────────────────────────────────────────────────────
user = current_user()
header_col, user_col = st.columns([4, 1])
with header_col:
    st.markdown(f"""
    <div style="padding:1rem 0 0.5rem 0;">
        <span style="font-size:1.6rem;font-weight:800;background:linear-gradient(135deg,#60a5fa,#a78bfa);
              -webkit-background-clip:text;-webkit-text-fill-color:transparent;">📈 Megha's Trading</span>
        <span style="color:#475569;font-size:0.85rem;margin-left:1rem;">Multi-Agent Stock Analysis System</span>
    </div>
    """, unsafe_allow_html=True)
with user_col:
    st.markdown(f"""
    <div style="text-align:right;padding:1rem 0 0.5rem 0;">
        <span style="color:#64748b;font-size:0.82rem;">Signed in as </span>
        <span style="color:#60a5fa;font-weight:600;">{user.get('display_name', user['username'])}</span>
        {"<span style='background:#3b82f6;color:white;font-size:0.7rem;padding:2px 8px;border-radius:10px;margin-left:6px;font-weight:600;'>ADMIN</span>" if is_admin() else ""}
    </div>
    """, unsafe_allow_html=True)
    if st.button("Sign Out", key="signout_btn"):
        logout()
        st.rerun()

# ── Build tabs ────────────────────────────────────────────────────────────────
unread = unread_count() if is_admin() else 0
feedback_label = f"💬 Feedback {'🔴' if unread > 0 else ''}"

tab_labels = [
    "📋 Watchlist",
    "📈 Trade Today",
    "🔮 Future Analysis",
    "📊 Analysis",
    "🎯 Today's Picks",
    "💬 Megha Chat",
    "👁️ Vision",
    "🔔 Alerts",
    feedback_label,
]
if is_admin():
    tab_labels.append(f"🛡️ Admin {f'({unread})' if unread else ''}")

tabs = st.tabs(tab_labels)

# ── Tab 1: Watchlist ──────────────────────────────────────────────────────────
with tabs[0]:
    from pages.watchlist_page import render as render_watchlist
    render_watchlist()

# ── Tab 2: Trade Today ────────────────────────────────────────────────────────
with tabs[1]:
    from pages.trade_today_page import render as render_trade_today
    render_trade_today()

# ── Tab 3: Future Analysis ────────────────────────────────────────────────────
with tabs[2]:
    from pages.analyse_future_page import render as render_future
    render_future()

# ── Tab 4: Analysis (original) ────────────────────────────────────────────────
with tabs[3]:
    import base64, json, re
    from datetime import datetime
    import pandas as pd
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    st.markdown("## 📊 Technical Analysis")
    st.caption("Full charting with MAS pipeline and HITL approval.")

    ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4 = st.columns([3, 2, 2, 2])
    with ctrl_col1:
        ticker_input = st.text_input("NSE Ticker", value="RELIANCE.NS", key="analysis_ticker")
    with ctrl_col2:
        period_sel = st.selectbox("Period", ["1mo","3mo","6mo","1y","2y"], index=1, key="analysis_period")
    with ctrl_col3:
        interval_sel = st.selectbox("Interval", ["1d","1wk","1mo"], index=0, key="analysis_interval")
    with ctrl_col4:
        st.markdown("<br>", unsafe_allow_html=True)
        run_analysis = st.button("🚀 Run MAS Pipeline", key="run_analysis_btn", use_container_width=True)

    if ticker_input:
        from tools.data_fetcher import get_technical_data
        with st.spinner(f"Loading {ticker_input}..."):
            tech_data = get_technical_data(ticker_input, period=period_sel, interval=interval_sel)

        if tech_data.get("error"):
            st.error(f"❌ {tech_data['error']}")
        else:
            inds = tech_data.get("indicators", {})
            price = tech_data.get("latest_price", 0)
            rsi = inds.get("RSI_14")
            ema20 = inds.get("EMA_20"); ema50 = inds.get("EMA_50"); ema200 = inds.get("EMA_200")
            macd = inds.get("MACD")

            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("💰 Price", f"₹{price:,.2f}" if price else "N/A")
            m2.metric("RSI 14", f"{rsi:.1f}" if rsi else "N/A",
                      "Overbought" if rsi and rsi > 70 else "Oversold" if rsi and rsi < 30 else "Neutral")
            m3.metric("EMA 20", f"₹{ema20:,.2f}" if ema20 else "N/A",
                      "↑" if (price and ema20 and price > ema20) else "↓")
            m4.metric("EMA 50", f"₹{ema50:,.2f}" if ema50 else "N/A",
                      "↑" if (price and ema50 and price > ema50) else "↓")
            m5.metric("EMA 200", f"₹{ema200:,.2f}" if ema200 else "N/A",
                      "↑" if (price and ema200 and price > ema200) else "↓")
            m6.metric("MACD", f"{macd:.3f}" if macd else "N/A",
                      "Bullish" if (macd and inds.get("MACD_Histogram", 0) > 0) else "Bearish")

            # Chart
            ohlcv = tech_data.get("ohlcv", [])
            if ohlcv:
                df = pd.DataFrame(ohlcv)
                date_col = df.columns[0]
                fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.55, 0.25, 0.2],
                                    vertical_spacing=0.04, subplot_titles=("Price & EMAs", "RSI", "MACD"))
                fig.add_trace(go.Candlestick(x=df[date_col], open=df["Open"], high=df["High"],
                    low=df["Low"], close=df["Close"], increasing_line_color="#10b981",
                    decreasing_line_color="#ef4444"), row=1, col=1)
                for ema, color in [("EMA_20","#60a5fa"),("EMA_50","#f59e0b"),("EMA_200","#a78bfa")]:
                    if ema in df.columns:
                        fig.add_trace(go.Scatter(x=df[date_col], y=df[ema], name=ema.replace("_"," "),
                            line=dict(color=color, width=1.5)), row=1, col=1)
                if "RSI_14" in df.columns:
                    fig.add_trace(go.Scatter(x=df[date_col], y=df["RSI_14"], name="RSI",
                        line=dict(color="#34d399")), row=2, col=1)
                    fig.add_hline(y=70, line=dict(color="#ef4444", dash="dot"), row=2, col=1)
                    fig.add_hline(y=30, line=dict(color="#10b981", dash="dot"), row=2, col=1)
                if "MACD_12_26_9" in df.columns:
                    fig.add_trace(go.Scatter(x=df[date_col], y=df["MACD_12_26_9"], name="MACD",
                        line=dict(color="#60a5fa")), row=3, col=1)
                if "MACDs_12_26_9" in df.columns:
                    fig.add_trace(go.Scatter(x=df[date_col], y=df["MACDs_12_26_9"], name="Signal",
                        line=dict(color="#f59e0b")), row=3, col=1)
                fig.update_layout(height=600, paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(10,14,26,0.6)", font=dict(color="#94a3b8"),
                    xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=30,b=0))
                st.plotly_chart(fig, use_container_width=True)

    if run_analysis and ticker_input:
        from graph.pipeline import run_pipeline, resume_pipeline
        with st.spinner("🧠 Running full MAS pipeline..."):
            state, thread_id = run_pipeline(ticker=ticker_input, period=period_sel, interval=interval_sel)
            st.session_state["analysis_state"] = state
            st.session_state["analysis_thread"] = thread_id
            st.session_state["analysis_hitl"] = True
            st.session_state["analysis_report"] = None

    if st.session_state.get("analysis_hitl") and st.session_state.get("analysis_state"):
        state = st.session_state["analysis_state"]
        st.success("✅ Agents complete — review and approve below.")
        a1, a2, a3 = st.columns(3)
        for col, label, key in [(a1,"🔵 Technical","technical_analysis"),
                                  (a2,"🟢 Fundamental","fundamental_analysis"),
                                  (a3,"🔴 Risk","risk_analysis")]:
            with col:
                with st.expander(label):
                    d = state.get(key, {})
                    for k, v in d.items():
                        if k != "error":
                            st.markdown(f"**{k}**: {v}")
        ap_col, rj_col = st.columns(2)
        with ap_col:
            if st.button("✅ Approve → Final Report", key="ap_btn2"):
                from graph.pipeline import resume_pipeline
                with st.spinner("Generating final report..."):
                    final = resume_pipeline(st.session_state["analysis_thread"], approved=True)
                st.session_state["analysis_report"] = final.get("final_report", {})
                st.session_state["analysis_hitl"] = False
                st.rerun()
        with rj_col:
            if st.button("❌ Reject", key="rj_btn2"):
                from graph.pipeline import resume_pipeline
                resume_pipeline(st.session_state["analysis_thread"], approved=False)
                st.session_state["analysis_hitl"] = False
                st.warning("Analysis rejected.")
                st.rerun()

    if st.session_state.get("analysis_report"):
        r = st.session_state["analysis_report"]
        action = r.get("action", "Hold")
        color = {"Buy":"#10b981","Sell":"#ef4444","Hold":"#f59e0b"}.get(action,"#94a3b8")
        st.markdown(f"### Final Report: <span style='color:{color}'>{action}</span>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Entry", f"₹{r.get('entry_price'):,.2f}" if r.get('entry_price') else "N/A")
        c2.metric("Target", f"₹{r.get('target_price'):,.2f}" if r.get('target_price') else "N/A")
        c3.metric("Stop Loss", f"₹{r.get('stop_loss'):,.2f}" if r.get('stop_loss') else "N/A")
        c4.metric("Conviction", f"{r.get('conviction_score',0)}/10")
        if r.get("summary"):
            st.info(r["summary"])

# ── Tab 5: Today's Picks ──────────────────────────────────────────────────────
with tabs[4]:
    st.markdown("## 🎯 Today's Picks")
    st.caption("MAS momentum picks vs broker recommendations, with overlap highlighting.")
    from tools.scraper import get_broker_recommendations, get_market_news
    from tools.data_fetcher import get_technical_data

    if st.button("🔄 Refresh", key="picks_refresh"):
        st.cache_data.clear()

    with st.spinner("Fetching broker data..."):
        broker_data = get_broker_recommendations(max_results=20)
    recs = broker_data.get("recommendations", [])

    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown("#### 📰 Broker Recommendations")
        if recs:
            for rec in recs[:15]:
                action = rec.get("action", "N/A")
                target = rec.get("target_price")
                action_color = "#10b981" if "buy" in action.lower() else "#ef4444" if "sell" in action.lower() else "#f59e0b"
                st.markdown(f"""
                <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
                            border-radius:8px;padding:0.6rem 0.8rem;margin-bottom:0.3rem;">
                    <span style="font-weight:700;color:#e2e8f0;">{rec.get('ticker','N/A')}</span>
                    <span style="color:{action_color};font-weight:700;margin-left:0.5rem;">{action}</span>
                    <span style="color:#64748b;font-size:0.8rem;margin-left:0.5rem;">
                        Target: {'₹{:,.2f}'.format(target) if target else 'N/A'} | {rec.get('broker','')[:20]}
                    </span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No broker recs fetched. Try during market hours.")

    with col_right:
        st.markdown("#### 📡 Market News")
        with st.spinner("Fetching news..."):
            news = get_market_news(max_headlines=10)
        for h in news.get("headlines", []):
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.02);border-radius:8px;padding:0.5rem 0.8rem;margin-bottom:0.3rem;">
                <span style="color:#475569;font-size:0.72rem;">[{h.get('source','')}]</span>
                <span style="color:#94a3b8;font-size:0.82rem;"> {h.get('headline','')[:90]}</span>
            </div>
            """, unsafe_allow_html=True)

# ── Tab 6: Chat ───────────────────────────────────────────────────────────────
with tabs[5]:
    st.markdown("## 💬 Megha Chat")
    if not st.session_state.get("chat_messages"):
        st.session_state["chat_messages"] = []

    for msg in st.session_state["chat_messages"]:
        role_class = "user" if msg["role"] == "user" else "assistant"
        prefix = "🧑 You" if msg["role"] == "user" else "🤖 Megha"
        bg = "rgba(59,130,246,0.1)" if msg["role"] == "user" else "rgba(255,255,255,0.03)"
        st.markdown(f'<div style="background:{bg};border-radius:10px;padding:0.6rem 0.8rem;margin:0.3rem 0;"><b style="color:#64748b;font-size:0.72rem;">{prefix}</b><br>{msg["content"]}</div>', unsafe_allow_html=True)

    with st.form("chat_form_v2", clear_on_submit=True):
        c1, c2 = st.columns([5, 1])
        with c1:
            user_q = st.text_input("Ask Megha...", placeholder="e.g. Analyze TCS.NS | PCR for NIFTY | News", label_visibility="collapsed")
        with c2:
            send = st.form_submit_button("Send ↗", use_container_width=True)

    if send and user_q:
        from tools.data_fetcher import get_technical_data, get_fundamental_data
        from tools.options_fetcher import get_pcr
        from tools.scraper import get_market_news

        st.session_state["chat_messages"].append({"role": "user", "content": user_q})
        q_lower = user_q.lower()
        tk_match = re.search(r"\b([A-Z]{2,10}(?:\.NS|\.BO)?)\b", user_q.upper())
        chat_tk = tk_match.group(1) if tk_match else None
        if chat_tk and "." not in chat_tk and not chat_tk.startswith("^"):
            chat_tk += ".NS"

        if "news" in q_lower:
            news = get_market_news(5)
            response = "📰 **Latest Headlines**\n\n" + "\n".join(f"• [{h['source']}] {h['headline'][:80]}" for h in news.get("headlines", []))
        elif "pcr" in q_lower or "put call" in q_lower:
            sym = re.sub(r"\.(NS|BO)$", "", chat_tk.upper()) if chat_tk else "NIFTY"
            pcr = get_pcr(sym)
            response = f"📊 **{sym} PCR**: `{pcr.get('pcr','N/A')}` — {pcr.get('sentiment','N/A')} | Max Pain: ₹{pcr.get('max_pain','N/A')}"
        elif chat_tk and any(k in q_lower for k in ["technical","rsi","ema","macd","chart","price"]):
            td = get_technical_data(chat_tk, "3mo", "1d")
            inds = td.get("indicators", {})
            response = f"📈 **{chat_tk}**: ₹{td.get('latest_price','N/A')} | RSI: {inds.get('RSI_14','N/A')} | MACD: {inds.get('MACD','N/A')} | EMA20: {inds.get('EMA_20','N/A')}"
        elif chat_tk and any(k in q_lower for k in ["fundamental","pe","eps","dividend"]):
            fd = get_fundamental_data(chat_tk)
            response = f"📊 **{fd.get('company_name', chat_tk)}** | P/E: {fd.get('pe_ratio_ttm','N/A')} | EPS: {fd.get('eps_ttm','N/A')} | Div: {fd.get('dividend_yield_pct','N/A')}%"
        elif "help" in q_lower:
            response = "I can help with: **Analyze TICKER** | **PCR for NIFTY** | **RSI/EMA for TCS** | **Fundamentals for INFY** | **Latest news** · Use Trade Today tab for full analysis."
        else:
            response = f"Try: 'Analyze {chat_tk or 'RELIANCE.NS'}' or 'PCR for NIFTY' or 'news'. Use the 📈 Trade Today tab for full analysis."

        st.session_state["chat_messages"].append({"role": "assistant", "content": response})
        st.rerun()

    if st.session_state.get("chat_messages") and st.button("🗑️ Clear Chat", key="chat_clear"):
        st.session_state["chat_messages"] = []
        st.rerun()

# ── Tab 7: Vision ─────────────────────────────────────────────────────────────
with tabs[6]:
    st.markdown("## 👁️ Vision Analyst")
    st.caption("Upload a stock chart. AI will detect patterns AND extract stock names from the image.")

    from auth.auth_manager import current_user as cu
    from db.watchlist_db import add_ticker as wl_add, ticker_exists as wl_exists

    uploaded = st.file_uploader("Upload chart image", type=["png","jpg","jpeg","webp"], key="vision_v2")

    if uploaded:
        col_img, col_res = st.columns(2)
        with col_img:
            st.image(uploaded, use_column_width=True)

        with col_res:
            if st.button("🔍 Analyse Chart", key="vision_analyse_v2"):
                import base64
                img_bytes = uploaded.read()
                img_b64 = base64.b64encode(img_bytes).decode()

                with st.spinner("👁️ llama3.2-vision analysing..."):
                    try:
                        from agents.vision_agent import vision_agent_node
                        from graph.state import initial_state as gs_init
                        state = gs_init(ticker="CHART", image_b64=img_b64)
                        result = vision_agent_node(state)
                        st.session_state["vision_v2_result"] = result.get("vision_analysis", {})
                    except Exception as e:
                        st.session_state["vision_v2_result"] = {"error": str(e)}

            vr = st.session_state.get("vision_v2_result", {})
            if vr:
                if vr.get("error"):
                    st.error(vr["error"])
                else:
                    st.metric("Pattern", vr.get("chart_pattern","N/A"))
                    st.metric("Trend", vr.get("trend","N/A"))
                    if vr.get("commentary"):
                        st.info(vr["commentary"])

                    # Smart watchlist/analyse prompt
                    identified = vr.get("ticker_identified")
                    if identified and identified not in ("null", None, ""):
                        tickers_found = [t.strip() for t in identified.replace(",", " ").split() if len(t) > 1]
                        if tickers_found:
                            st.markdown("---")
                            st.markdown(f"**Found tickers in image:** `{'`, `'.join(tickers_found)}`")
                            st.markdown("What would you like to do?")

                            cur_user = cu()
                            uid = cur_user["id"]

                            sel_analyse = st.selectbox("Select one to Analyse", tickers_found, key="vision_analyse_sel")
                            vision_action = st.radio("Action", ["Analyse selected, save rest to Watchlist",
                                                                "Save all to Watchlist",
                                                                "Analyse selected only"], horizontal=True, key="vision_action")

                            if st.button("▶️ Proceed", key="vision_proceed"):
                                for tk in tickers_found:
                                    full_tk = tk if "." in tk else tk + ".NS"
                                    if not wl_exists(uid, full_tk):
                                        if tk != sel_analyse or "save all" in vision_action.lower():
                                            wl_add(uid, full_tk, full_tk)

                                if "analyse" in vision_action.lower():
                                    analyse_tk = sel_analyse if "." in sel_analyse else sel_analyse + ".NS"
                                    st.success(f"Navigate to 📈 Trade Today tab to analyse **{analyse_tk}**.")
                                    st.session_state["tt_custom"] = analyse_tk
                                else:
                                    st.success(f"All tickers saved to your Watchlist!")

# ── Tab 8: Alerts ─────────────────────────────────────────────────────────────
with tabs[7]:
    from pages.alerts_page import render as render_alerts
    render_alerts()

# ── Tab 9: Feedback ───────────────────────────────────────────────────────────
with tabs[8]:
    from pages.feedback_page import render as render_feedback
    render_feedback()

# ── Tab 10: Admin (admin only) ────────────────────────────────────────────────
if is_admin():
    with tabs[9]:
        from pages.admin_page import render as render_admin
        render_admin()

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center;padding:2rem 0 1rem;margin-top:2rem;border-top:1px solid rgba(255,255,255,0.05);">
    <p style="color:#334155;font-size:0.78rem;">📈 Megha's Trading v2 — 100% Local · Open Source · Privacy First</p>
    <p style="color:#1e293b;font-size:0.72rem;">⚠️ For educational purposes only. Not financial advice.</p>
</div>
""", unsafe_allow_html=True)
