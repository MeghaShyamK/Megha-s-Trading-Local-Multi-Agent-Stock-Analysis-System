"""db/watchlist_db.py — Per-user watchlist CRUD."""
from __future__ import annotations
from db.database import get_conn


def add_ticker(user_id: int, ticker: str, company_name: str = "", sector: str = "") -> bool:
    try:
        conn = get_conn()
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (user_id, ticker, company_name, sector) VALUES (?,?,?,?)",
            (user_id, ticker.upper(), company_name, sector)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"[watchlist_db] add_ticker error: {e}")
        return False


def remove_ticker(user_id: int, ticker: str) -> bool:
    try:
        conn = get_conn()
        conn.execute("DELETE FROM watchlist WHERE user_id=? AND ticker=?", (user_id, ticker.upper()))
        conn.commit()
        return True
    except Exception:
        return False


def get_watchlist(user_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM watchlist WHERE user_id=? ORDER BY added_at DESC", (user_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def ticker_exists(user_id: int, ticker: str) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM watchlist WHERE user_id=? AND ticker=?", (user_id, ticker.upper())
    ).fetchone()
    return row is not None


def update_notes(user_id: int, ticker: str, notes: str):
    conn = get_conn()
    conn.execute("UPDATE watchlist SET notes=? WHERE user_id=? AND ticker=?", (notes, user_id, ticker.upper()))
    conn.commit()
