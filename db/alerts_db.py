"""db/alerts_db.py — Alert configuration CRUD."""
from __future__ import annotations
import json
from datetime import datetime
from db.database import get_conn

MAX_ALERTS_PER_USER = 5


def count_alerts(user_id: int) -> int:
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) FROM alerts WHERE user_id=?", (user_id,)).fetchone()
    return row[0] if row else 0


def create_alert(user_id: int, alert_name: str, ticker: str, instrument_type: str,
                 indicators: list, fundamentals: list, interval_minutes: int,
                 trading_hours_only: bool, send_email: bool, email_address: str,
                 send_discord: bool, discord_webhook: str) -> tuple[bool, str]:
    if count_alerts(user_id) >= MAX_ALERTS_PER_USER:
        return False, f"Maximum of {MAX_ALERTS_PER_USER} alerts per user reached."
    try:
        conn = get_conn()
        conn.execute(
            """INSERT INTO alerts
               (user_id, alert_name, ticker, instrument_type, indicators_json,
                fundamentals_json, interval_minutes, trading_hours_only,
                send_email, send_discord, email_address, discord_webhook)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (user_id, alert_name, ticker.upper(), instrument_type,
             json.dumps(indicators), json.dumps(fundamentals),
             interval_minutes, int(trading_hours_only),
             int(send_email), int(send_discord),
             email_address, discord_webhook)
        )
        conn.commit()
        return True, "Alert created successfully."
    except Exception as e:
        return False, str(e)


def get_alerts(user_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM alerts WHERE user_id=? ORDER BY created_at DESC", (user_id,)
    ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["indicators"] = json.loads(d.get("indicators_json", "[]"))
        d["fundamentals"] = json.loads(d.get("fundamentals_json", "[]"))
        results.append(d)
    return results


def get_all_active_alerts() -> list[dict]:
    """For the alert engine — get all active alerts across all users."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM alerts WHERE is_active=1"
    ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["indicators"] = json.loads(d.get("indicators_json", "[]"))
        d["fundamentals"] = json.loads(d.get("fundamentals_json", "[]"))
        results.append(d)
    return results


def delete_alert(alert_id: int, user_id: int) -> bool:
    try:
        conn = get_conn()
        conn.execute("DELETE FROM alerts WHERE id=? AND user_id=?", (alert_id, user_id))
        conn.commit()
        return True
    except Exception:
        return False


def toggle_alert(alert_id: int, user_id: int, active: bool):
    conn = get_conn()
    conn.execute("UPDATE alerts SET is_active=? WHERE id=? AND user_id=?",
                 (int(active), alert_id, user_id))
    conn.commit()


def update_last_triggered(alert_id: int):
    conn = get_conn()
    conn.execute("UPDATE alerts SET last_triggered=? WHERE id=?",
                 (datetime.utcnow().isoformat(), alert_id))
    conn.commit()
