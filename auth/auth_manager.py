"""
auth/auth_manager.py
---------------------
Authentication manager for the Trading Agent System v2.
Handles login, session management, and role checking.
"""
from __future__ import annotations
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # Python 3.10 backport
import os
import streamlit as st
from db.user_db import get_user, verify_password, ensure_admin_exists

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_PATH = os.path.join(_BASE_DIR, "config.toml")


def load_config() -> dict:
    """Load config.toml. Returns empty dict if missing."""
    try:
        with open(_CONFIG_PATH, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"[auth] Config load error: {e}")
        return {}


def bootstrap_admin():
    """Seed the admin user from config.toml on first startup."""
    cfg = load_config()
    admin_cfg = cfg.get("admin", {})
    username = admin_cfg.get("username", "admin")
    password = admin_cfg.get("password", "admin123")
    display = admin_cfg.get("display_name", "Admin")
    ensure_admin_exists(username, password, display)


def login(username: str, password: str) -> dict | None:
    """
    Verify credentials. Returns user dict on success, None on failure.
    Stores user in st.session_state["user"] on success.
    """
    user = get_user(username)
    if user and verify_password(password, user["password_hash"]):
        st.session_state["user"] = user
        return user
    return None


def logout():
    """Clear the session user."""
    st.session_state["user"] = None
    st.session_state.pop("user", None)


def current_user() -> dict | None:
    return st.session_state.get("user")


def is_logged_in() -> bool:
    return current_user() is not None


def is_admin() -> bool:
    u = current_user()
    return u is not None and u.get("role") == "admin"


def require_login():
    """Call at top of any page that needs auth. Shows login form if not logged in."""
    if not is_logged_in():
        _render_login_form()
        st.stop()


def _render_login_form():
    """Render the login page."""
    st.markdown("""
    <style>
    .login-container {
        max-width: 400px; margin: 8vh auto; padding: 2.5rem;
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 20px; backdrop-filter: blur(10px);
    }
    .login-title {
        font-size: 1.8rem; font-weight: 800;
        background: linear-gradient(135deg, #60a5fa, #a78bfa);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        text-align: center; margin-bottom: 0.3rem;
    }
    .login-sub { color: #64748b; text-align: center; font-size: 0.9rem; margin-bottom: 1.5rem; }
    </style>
    """, unsafe_allow_html=True)

    col = st.columns([1, 2, 1])[1]
    with col:
        st.markdown('<div class="login-title">📈 Megha\'s Trading</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">Sign in to continue</div>', unsafe_allow_html=True)

        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter username")
            password = st.text_input("Password", type="password", placeholder="Enter password")
            submitted = st.form_submit_button("Sign In →", use_container_width=True)

        if submitted:
            if login(username.strip(), password):
                st.success(f"Welcome back, {current_user()['display_name']}!")
                st.rerun()
            else:
                st.error("❌ Invalid username or password.")
