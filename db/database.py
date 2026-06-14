"""
db/database.py
--------------
SQLite database manager for the Trading Agent System v2.
Creates and manages all tables. Thread-safe using threading.local().
"""
from __future__ import annotations
import sqlite3
import threading
import os
from datetime import datetime

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(_BASE_DIR, "data", "trading.db")

_local = threading.local()


def get_conn() -> sqlite3.Connection:
    """Return a thread-local SQLite connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def init_db():
    """Create all tables if they don't exist. Called at app startup."""
    os.makedirs(os.path.join(_BASE_DIR, "data", "feedback_images"), exist_ok=True)
    conn = get_conn()
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'user',
        display_name TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS watchlist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        ticker TEXT NOT NULL,
        company_name TEXT,
        sector TEXT,
        added_at TEXT DEFAULT (datetime('now')),
        notes TEXT,
        UNIQUE(user_id, ticker),
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT NOT NULL,
        text_content TEXT,
        image_path TEXT,
        submitted_at TEXT DEFAULT (datetime('now')),
        is_read INTEGER DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS saved_analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        ticker TEXT NOT NULL,
        label TEXT,
        analysis_json TEXT NOT NULL,
        timeframe TEXT,
        analysis_type TEXT DEFAULT 'future',
        saved_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        alert_name TEXT,
        ticker TEXT NOT NULL,
        instrument_type TEXT DEFAULT 'stock',
        indicators_json TEXT DEFAULT '[]',
        fundamentals_json TEXT DEFAULT '[]',
        interval_minutes INTEGER DEFAULT 60,
        trading_hours_only INTEGER DEFAULT 1,
        send_email INTEGER DEFAULT 0,
        send_discord INTEGER DEFAULT 0,
        email_address TEXT,
        discord_webhook TEXT,
        is_active INTEGER DEFAULT 1,
        last_triggered TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)
    conn.commit()
    print("[db] ✅ Database initialised at", DB_PATH)
