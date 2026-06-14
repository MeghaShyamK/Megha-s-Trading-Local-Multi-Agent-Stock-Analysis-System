"""
pages/alerts_page.py
---------------------
Alert configuration tab:
  - Up to 5 alerts per user
  - Ticker, instrument, indicators, fundamentals, interval
  - Trading hours only toggle
  - Email + Discord delivery
  - Enable/disable + delete per alert
"""
from __future__ import annotations
import streamlit as st

from auth.auth_manager import current_user
from db.watchlist_db import get_watchlist as get_user_watchlist
from db.alerts_db import (create_alert, get_alerts, delete_alert,
                           toggle_alert, count_alerts, MAX_ALERTS_PER_USER)

INTERVALS = {
    "Every 15 Min": 15, "Every 30 Min": 30, "Every 1 Hour": 60,
    "Every 2 Hours": 120, "Every 4 Hours": 240,
}

TECH_INDICATORS = ["RSI", "MACD", "EMA 20", "EMA 50", "EMA 200",
                   "Bollinger Bands", "Fibonacci", "Volume"]
FUND_METRICS = ["P/E Ratio", "EPS", "Revenue Growth", "Dividend Yield", "Analyst Rating"]
INSTRUMENTS = ["Stock", "Options", "Futures", "Derivatives"]


def render():
    user = current_user()
    user_id = user["id"]

    st.markdown("## 🔔 Alert Manager")
    st.caption("Get trade analysis delivered to your email or Discord during market hours. Maximum 5 alerts.")

    current_count = count_alerts(user_id)
    st.progress(current_count / MAX_ALERTS_PER_USER,
                text=f"{current_count}/{MAX_ALERTS_PER_USER} alerts used")

    # ── Create new alert form ─────────────────────────────────────────────────
    if current_count < MAX_ALERTS_PER_USER:
        with st.expander("➕ Create New Alert", expanded=current_count == 0):
            wl = get_user_watchlist(user_id)
            wl_tickers = [w["ticker"] for w in wl]

            c1, c2, c3 = st.columns(3)
            with c1:
                alert_name = st.text_input("Alert Name", placeholder="e.g. NIFTY Morning Check", key="al_name")
                src = st.radio("Ticker from", ["My Watchlist", "Custom"], horizontal=True, key="al_src")
                if src == "My Watchlist" and wl_tickers:
                    al_ticker = st.selectbox("Stock", wl_tickers, key="al_wl_sel")
                else:
                    al_ticker = st.text_input("Ticker", placeholder="NIFTY or RELIANCE.NS", key="al_custom_tk")
                    if al_ticker and "." not in al_ticker and not al_ticker.startswith("^"):
                        al_ticker += ".NS"
                al_instrument = st.selectbox("Instrument", INSTRUMENTS, key="al_instr")

            with c2:
                al_interval_label = st.selectbox("Alert Interval", list(INTERVALS.keys()), index=2, key="al_interval")
                al_interval = INTERVALS[al_interval_label]
                al_trading_hours = st.toggle("Trading hours only (9:15 AM – 3:30 PM IST)",
                                             value=True, key="al_trhrs")
                al_tech = st.multiselect("Technical Indicators", TECH_INDICATORS,
                                         default=["RSI", "MACD"], key="al_tech")
                al_fund = st.multiselect("Fundamental Metrics", FUND_METRICS,
                                         default=[], key="al_fund")

            with c3:
                st.markdown("**Delivery Channels**")
                al_email_on = st.checkbox("📧 Email", key="al_email_on")
                al_email_addr = ""
                if al_email_on:
                    al_email_addr = st.text_input("Email address", placeholder="you@gmail.com", key="al_email_addr")

                al_discord_on = st.checkbox("🎮 Discord", key="al_discord_on")
                al_discord_url = ""
                if al_discord_on:
                    al_discord_url = st.text_input("Discord Webhook URL",
                                                    placeholder="https://discord.com/api/webhooks/...",
                                                    key="al_discord_url")

                st.markdown("")
                if st.button("✅ Create Alert", key="al_create_btn", use_container_width=True):
                    if not alert_name:
                        st.error("Please give the alert a name.")
                    elif not al_ticker:
                        st.error("Please select or enter a ticker.")
                    elif not al_email_on and not al_discord_on:
                        st.error("Please select at least one delivery channel (Email or Discord).")
                    elif al_email_on and not al_email_addr:
                        st.error("Please enter an email address.")
                    elif al_discord_on and not al_discord_url:
                        st.error("Please enter a Discord webhook URL.")
                    else:
                        ok, msg = create_alert(
                            user_id=user_id, alert_name=alert_name,
                            ticker=al_ticker, instrument_type=al_instrument,
                            indicators=al_tech, fundamentals=al_fund,
                            interval_minutes=al_interval,
                            trading_hours_only=al_trading_hours,
                            send_email=al_email_on, email_address=al_email_addr,
                            send_discord=al_discord_on, discord_webhook=al_discord_url,
                        )
                        if ok:
                            st.success(f"✅ {msg}")
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")
    else:
        st.warning(f"Maximum of {MAX_ALERTS_PER_USER} alerts reached. Delete an existing alert to create a new one.")

    # ── Existing alerts list ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### My Alerts")

    alerts = get_alerts(user_id)
    if not alerts:
        st.markdown("""
        <div style="text-align:center;padding:3rem;background:rgba(255,255,255,0.02);
                    border:1px solid rgba(255,255,255,0.05);border-radius:12px;">
            <p style="font-size:2rem;">🔔</p>
            <p style="color:#64748b;">No alerts yet. Create one above to get started.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        for al in alerts:
            active = bool(al.get("is_active", 1))
            status_color = "#10b981" if active else "#475569"
            status_label = "🟢 Active" if active else "⚫ Paused"
            last = al.get("last_triggered", "Never")
            if last and last != "Never":
                last = last[:16].replace("T", " ")

            with st.container():
                al_c1, al_c2 = st.columns([5, 1])
                with al_c1:
                    channels = []
                    if al.get("send_email"): channels.append(f"📧 {al.get('email_address', '')[:25]}")
                    if al.get("send_discord"): channels.append("🎮 Discord")
                    channel_str = " | ".join(channels) or "No channels"

                    indicators_str = ", ".join(al.get("indicators", [])) or "None"
                    fund_str = ", ".join(al.get("fundamentals", [])) or "None"
                    interval_min = al.get("interval_minutes", 60)
                    interval_label = next(
                        (k for k, v in INTERVALS.items() if v == interval_min),
                        f"Every {interval_min} min"
                    )

                    st.markdown(f"""
                    <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
                                border-radius:10px;padding:1rem;margin-bottom:0.5rem;">
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <span style="font-weight:700;color:#e2e8f0;">{al.get('alert_name', al['ticker'])}</span>
                            <span style="color:{status_color};font-size:0.82rem;">{status_label}</span>
                        </div>
                        <div style="font-size:0.82rem;color:#64748b;margin-top:0.4rem;display:flex;gap:1.5rem;flex-wrap:wrap;">
                            <span>📊 {al['ticker']} ({al.get('instrument_type','stock')})</span>
                            <span>⏱️ {interval_label}</span>
                            <span>{'🕐 Trading hours' if al.get('trading_hours_only') else '🕛 Always'}</span>
                        </div>
                        <div style="font-size:0.78rem;color:#475569;margin-top:0.3rem;display:flex;gap:1.5rem;flex-wrap:wrap;">
                            <span>Indicators: {indicators_str[:40]}</span>
                            <span>Delivery: {channel_str}</span>
                            <span>Last: {last}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                with al_c2:
                    toggle_label = "⏸️ Pause" if active else "▶️ Resume"
                    if st.button(toggle_label, key=f"al_toggle_{al['id']}"):
                        toggle_alert(al["id"], user_id, not active)
                        st.rerun()
                    if st.button("🗑️", key=f"al_del_{al['id']}", help="Delete alert"):
                        delete_alert(al["id"], user_id)
                        st.rerun()

    # ── Setup guide ───────────────────────────────────────────────────────────
    with st.expander("⚙️ How to set up Email & Discord alerts"):
        st.markdown("""
        ### 📧 Gmail Email Alerts

        1. Go to your Google Account → **Security** → **2-Step Verification** (enable it)
        2. Then go to **App Passwords** → Select app: `Mail` → Select device: `Mac`
        3. Click **Generate** — you'll get a 16-character password like `abcd efgh ijkl mnop`
        4. Open `config.toml` in the project folder and fill in:
        ```toml
        [email]
        sender_email = "your@gmail.com"
        sender_app_password = "abcdefghijklmnop"  # no spaces
        ```
        5. Restart the app — alerts will now send via Gmail.

        ---

        ### 🎮 Discord Webhook Alerts

        1. Open **Discord** → go to the channel you want alerts in
        2. Click **⚙️ Edit Channel** → **Integrations** → **Webhooks** → **New Webhook**
        3. Give it a name (e.g. "Trading Alerts"), copy the **Webhook URL**
        4. Paste the URL when creating an alert above — done! No bot, no coding.

        The URL looks like: `https://discord.com/api/webhooks/123456/abcdef...`
        """)
