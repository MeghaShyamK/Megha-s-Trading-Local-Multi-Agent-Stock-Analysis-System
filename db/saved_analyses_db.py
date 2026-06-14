"""db/saved_analyses_db.py — Saved analysis results storage."""
from __future__ import annotations
import json
from db.database import get_conn


def save_analysis(user_id: int, ticker: str, label: str, analysis: dict,
                  timeframe: str = "1d", analysis_type: str = "future") -> int:
    """Save an analysis. Returns the new row ID."""
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO saved_analyses (user_id, ticker, label, analysis_json, timeframe, analysis_type)
           VALUES (?,?,?,?,?,?)""",
        (user_id, ticker.upper(), label, json.dumps(analysis), timeframe, analysis_type)
    )
    conn.commit()
    return cur.lastrowid


def get_saved_analyses(user_id: int, analysis_type: str = None) -> list[dict]:
    conn = get_conn()
    if analysis_type:
        rows = conn.execute(
            "SELECT * FROM saved_analyses WHERE user_id=? AND analysis_type=? ORDER BY saved_at DESC",
            (user_id, analysis_type)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM saved_analyses WHERE user_id=? ORDER BY saved_at DESC",
            (user_id,)
        ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        try:
            d["analysis"] = json.loads(d.get("analysis_json", "{}"))
        except Exception:
            d["analysis"] = {}
        results.append(d)
    return results


def delete_analysis(analysis_id: int, user_id: int) -> bool:
    try:
        conn = get_conn()
        conn.execute("DELETE FROM saved_analyses WHERE id=? AND user_id=?", (analysis_id, user_id))
        conn.commit()
        return True
    except Exception:
        return False
