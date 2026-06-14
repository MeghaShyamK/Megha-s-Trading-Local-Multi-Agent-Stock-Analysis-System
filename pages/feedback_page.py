"""pages/feedback_page.py — User feedback submission."""
from __future__ import annotations
import os
import uuid
import streamlit as st
from auth.auth_manager import current_user
from db.feedback_db import submit_feedback

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_IMG_DIR = os.path.join(_BASE_DIR, "data", "feedback_images")


def render():
    user = current_user()
    st.markdown("## 💬 Feedback")
    st.caption("Share your thoughts, report issues, or suggest improvements.")

    with st.form("feedback_form"):
        feedback_text = st.text_area(
            "Your feedback",
            placeholder="Tell us what's working, what's not, or what you'd like to see next...",
            height=150,
        )
        uploaded = st.file_uploader(
            "Attach a screenshot (optional)",
            type=["png", "jpg", "jpeg"],
            help="Attach a chart or screenshot to illustrate your feedback."
        )
        submitted = st.form_submit_button("📨 Submit Feedback", use_container_width=True)

    if submitted:
        if not feedback_text.strip():
            st.error("Please write some feedback before submitting.")
            return

        # Save image if uploaded
        img_path = ""
        if uploaded:
            os.makedirs(_IMG_DIR, exist_ok=True)
            ext = uploaded.name.rsplit(".", 1)[-1].lower()
            fname = f"{uuid.uuid4().hex}.{ext}"
            img_path = os.path.join(_IMG_DIR, fname)
            with open(img_path, "wb") as f:
                f.write(uploaded.read())

        ok = submit_feedback(
            user_id=user["id"],
            username=user["username"],
            text=feedback_text.strip(),
            image_path=img_path,
        )
        if ok:
            st.success("✅ Thank you! Your feedback has been submitted.")
            st.balloons()
        else:
            st.error("❌ Failed to submit feedback. Please try again.")
