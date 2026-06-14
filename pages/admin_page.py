"""pages/admin_page.py — Admin panel: feedback viewer + user management."""
from __future__ import annotations
import streamlit as st
from auth.auth_manager import current_user, is_admin
from db.feedback_db import get_all_feedback, mark_read, delete_feedback, unread_count
from db.user_db import list_users, create_user, delete_user


def render():
    if not is_admin():
        st.error("⛔ Access denied. Admin only.")
        return

    st.markdown("## 🛡️ Admin Panel")

    tab_feedback, tab_users = st.tabs(["💬 Feedback", "👥 Users"])

    # ── Feedback tab ──────────────────────────────────────────────────────────
    with tab_feedback:
        unread = unread_count()
        st.markdown(f"### Feedback ({unread} unread)")

        filter_col1, filter_col2 = st.columns([2, 1])
        with filter_col2:
            show_unread = st.checkbox("Show unread only", value=False)
        with filter_col1:
            if st.button("Mark all as read"):
                feedbacks = get_all_feedback()
                for fb in feedbacks:
                    mark_read(fb["id"])
                st.rerun()

        feedbacks = get_all_feedback(unread_only=show_unread)
        if not feedbacks:
            st.info("No feedback yet." if not show_unread else "No unread feedback.")
        else:
            for fb in feedbacks:
                is_read = bool(fb.get("is_read", 0))
                border_color = "rgba(255,255,255,0.06)" if is_read else "rgba(96,165,250,0.3)"
                bg = "rgba(255,255,255,0.02)" if is_read else "rgba(59,130,246,0.06)"

                with st.container():
                    st.markdown(f"""
                    <div style="background:{bg};border:1px solid {border_color};
                                border-radius:10px;padding:1rem;margin-bottom:0.6rem;">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;">
                            <span style="color:#60a5fa;font-weight:700;">@{fb.get('username','?')}</span>
                            <span style="color:#475569;font-size:0.78rem;">{str(fb.get('submitted_at',''))[:16]}</span>
                            {'<span style="color:#3b82f6;font-size:0.72rem;font-weight:600;">UNREAD</span>' if not is_read else ''}
                        </div>
                        <p style="color:#e2e8f0;margin:0;font-size:0.9rem;">{fb.get('text_content','')}</p>
                    </div>
                    """, unsafe_allow_html=True)

                    # Show attached image if any
                    img_path = fb.get("image_path", "")
                    if img_path:
                        try:
                            st.image(img_path, width=300, caption="Attached screenshot")
                        except Exception:
                            st.caption(f"Image: {img_path}")

                    btn_c1, btn_c2, _ = st.columns([1, 1, 4])
                    with btn_c1:
                        if not is_read and st.button("✓ Mark read", key=f"admin_read_{fb['id']}"):
                            mark_read(fb["id"])
                            st.rerun()
                    with btn_c2:
                        if st.button("🗑️ Delete", key=f"admin_del_fb_{fb['id']}"):
                            delete_feedback(fb["id"])
                            st.rerun()

    # ── Users tab ─────────────────────────────────────────────────────────────
    with tab_users:
        st.markdown("### User Management")

        users = list_users()
        current_admin = current_user()

        for u in users:
            role_color = "#60a5fa" if u["role"] == "admin" else "#94a3b8"
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
                        border-radius:8px;padding:0.75rem 1rem;margin-bottom:0.4rem;
                        display:flex;justify-content:space-between;align-items:center;">
                <span style="color:#e2e8f0;font-weight:600;">{u.get('display_name', u['username'])}</span>
                <span style="color:#64748b;font-size:0.8rem;">@{u['username']}</span>
                <span style="color:{role_color};font-size:0.78rem;font-weight:600;">{u['role'].upper()}</span>
                <span style="color:#475569;font-size:0.75rem;">{str(u.get('created_at',''))[:10]}</span>
            </div>
            """, unsafe_allow_html=True)
            # Don't allow deleting self
            if u["id"] != current_admin["id"]:
                if st.button(f"🗑️ Delete @{u['username']}", key=f"admin_del_user_{u['id']}"):
                    delete_user(u["id"])
                    st.success(f"Deleted user @{u['username']}")
                    st.rerun()

        st.markdown("---")
        st.markdown("#### Create New User")
        with st.form("admin_create_user"):
            new_uname = st.text_input("Username")
            new_display = st.text_input("Display Name")
            new_pw = st.text_input("Password", type="password")
            new_role = st.selectbox("Role", ["user", "admin"])
            if st.form_submit_button("Create User"):
                if not new_uname or not new_pw:
                    st.error("Username and password are required.")
                else:
                    ok = create_user(new_uname, new_pw, new_role, new_display or new_uname)
                    if ok:
                        st.success(f"✅ User @{new_uname} created.")
                        st.rerun()
                    else:
                        st.error("Username already exists.")
