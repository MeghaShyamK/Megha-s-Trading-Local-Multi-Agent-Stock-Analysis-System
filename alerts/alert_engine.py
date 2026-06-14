"""
alerts/alert_engine.py
-----------------------
APScheduler-based alert engine.
Runs in a background thread. Checks all active alerts, respects trading hours,
fetches data, runs the MAS pipeline, and sends notifications.
"""
from __future__ import annotations
import json
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # Python 3.10 backport
import os
from datetime import datetime, time as dtime
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from db.alerts_db import get_all_active_alerts, update_last_triggered
from alerts.email_sender import send_alert_email, format_alert_email
from alerts.discord_sender import send_discord_alert

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_PATH = os.path.join(_BASE_DIR, "config.toml")

_scheduler: BackgroundScheduler | None = None
_IST = pytz.timezone("Asia/Kolkata")


def _load_trading_hours() -> dict:
    try:
        with open(_CONFIG_PATH, "rb") as f:
            return tomllib.load(f).get("trading_hours", {})
    except Exception:
        return {}


def _is_trading_hours() -> bool:
    """Check if current IST time is within NSE market hours."""
    th = _load_trading_hours()
    now_ist = datetime.now(_IST).time()
    open_t = dtime(th.get("market_open_hour", 9), th.get("market_open_minute", 15))
    close_t = dtime(th.get("market_close_hour", 15), th.get("market_close_minute", 30))
    # Also check it's a weekday (Mon=0 ... Fri=4)
    weekday = datetime.now(_IST).weekday()
    return open_t <= now_ist <= close_t and weekday < 5


def _run_alert(alert: dict):
    """Execute a single alert: fetch data → run agents → send notification."""
    try:
        ticker = alert["ticker"]
        alert_id = alert["id"]
        indicators = alert.get("indicators", [])

        print(f"[alert_engine] 🔔 Running alert #{alert_id} for {ticker}")

        # Fetch technical data
        from tools.data_fetcher import get_technical_data, get_fundamental_data
        tech_data = get_technical_data(ticker, period="1mo", interval="1d")

        if tech_data.get("error"):
            print(f"[alert_engine] ⚠️ Data error for {ticker}: {tech_data['error']}")
            return

        # Build a minimal state and run coordinator directly for speed
        from graph.state import initial_state
        from agents.technical_agent import technical_agent_node
        from agents.risk_agent import risk_agent_node
        from agents.coordinator_agent import coordinator_agent_node

        state = initial_state(ticker=ticker)
        state["technical_data"] = tech_data
        state["fundamental_data"] = get_fundamental_data(ticker) if "PE" in indicators or "EPS" in indicators else {}
        state["options_data"] = {}
        state["broker_recs"] = {}
        state["market_news"] = {}

        # Run agents
        state.update(technical_agent_node(state))
        state.update(risk_agent_node(state))

        # Skip HITL — directly approve for automated alerts
        state["human_approved"] = True
        state.update(coordinator_agent_node(state))

        report = state.get("final_report", {})
        if not report or report.get("status") == "awaiting_approval":
            print(f"[alert_engine] ⚠️ No report generated for {ticker}")
            return

        # Send notifications
        if alert.get("send_email") and alert.get("email_address"):
            subject, body = format_alert_email(ticker, report)
            ok, msg = send_alert_email(alert["email_address"], subject, body)
            print(f"[alert_engine] Email → {ok}: {msg}")

        if alert.get("send_discord") and alert.get("discord_webhook"):
            ok, msg = send_discord_alert(alert["discord_webhook"], ticker, report)
            print(f"[alert_engine] Discord → {ok}: {msg}")

        update_last_triggered(alert_id)

    except Exception as e:
        print(f"[alert_engine] ❌ Alert error: {e}")
        import traceback
        traceback.print_exc()


def _check_all_alerts():
    """Job function: check all active alerts and fire ones that are due."""
    alerts = get_all_active_alerts()
    now = datetime.utcnow()

    for alert in alerts:
        # Check trading hours restriction
        if alert.get("trading_hours_only") and not _is_trading_hours():
            continue

        # Check interval — has enough time passed since last trigger?
        last = alert.get("last_triggered")
        interval_min = alert.get("interval_minutes", 60)
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                elapsed = (now - last_dt).total_seconds() / 60
                if elapsed < interval_min:
                    continue
            except Exception:
                pass

        # Run the alert in a thread
        from async_runner.task_queue import submit
        submit(_run_alert, alert)


def start_alert_engine():
    """Start the background scheduler. Call once at app startup."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return  # Already running

    _scheduler = BackgroundScheduler(daemon=True)
    # Check every 5 minutes — _check_all_alerts handles finer intervals internally
    _scheduler.add_job(
        _check_all_alerts,
        trigger=IntervalTrigger(minutes=5),
        id="alert_checker",
        replace_existing=True,
    )
    _scheduler.start()
    print("[alert_engine] ✅ Alert engine started (checking every 5 minutes).")


def stop_alert_engine():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
