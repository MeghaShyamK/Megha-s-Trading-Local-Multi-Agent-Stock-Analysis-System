"""db/feedback_db.py — Feedback storage."""
from __future__ import annotations
from db.database import get_conn


def submit_feedback(user_id: int, username: str, text: str, image_path: str = "") -> bool:
    try:
        conn = get_conn()
        conn.execute(
            "INSERT INTO feedback (user_id, username, text_content, image_path) VALUES (?,?,?,?)",
            (user_id, username, text, image_path)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"[feedback_db] submit error: {e}")
        return False


def get_all_feedback(unread_only: bool = False) -> list[dict]:
    conn = get_conn()
    query = "SELECT * FROM feedback"
    if unread_only:
        query += " WHERE is_read=0"
    query += " ORDER BY submitted_at DESC"
    rows = conn.execute(query).fetchall()
    return [dict(r) for r in rows]


def mark_read(feedback_id: int):
    conn = get_conn()
    conn.execute("UPDATE feedback SET is_read=1 WHERE id=?", (feedback_id,))
    conn.commit()


def delete_feedback(feedback_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM feedback WHERE id=?", (feedback_id,))
    conn.commit()


def unread_count() -> int:
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) FROM feedback WHERE is_read=0").fetchone()
    return row[0] if row else 0
