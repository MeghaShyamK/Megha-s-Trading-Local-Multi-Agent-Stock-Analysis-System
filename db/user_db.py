"""db/user_db.py — User CRUD operations."""
from __future__ import annotations
from db.database import get_conn
import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


def create_user(username: str, password: str, role: str = "user", display_name: str = "") -> bool:
    try:
        conn = get_conn()
        pw_hash = hash_password(password)
        conn.execute(
            "INSERT INTO users (username, password_hash, role, display_name) VALUES (?,?,?,?)",
            (username.lower().strip(), pw_hash, role, display_name or username)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"[user_db] create_user error: {e}")
        return False


def get_user(username: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username.lower().strip(),)
    ).fetchone()
    return dict(row) if row else None


def list_users() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT id, username, role, display_name, created_at FROM users ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def delete_user(user_id: int) -> bool:
    try:
        conn = get_conn()
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return True
    except Exception:
        return False


def ensure_admin_exists(username: str, password: str, display_name: str = "Admin"):
    """Seed the admin user if not already in DB."""
    existing = get_user(username)
    if not existing:
        create_user(username, password, role="admin", display_name=display_name)
        print(f"[user_db] ✅ Admin user '{username}' created.")
    elif existing["role"] != "admin":
        conn = get_conn()
        conn.execute("UPDATE users SET role='admin' WHERE username=?", (username,))
        conn.commit()
