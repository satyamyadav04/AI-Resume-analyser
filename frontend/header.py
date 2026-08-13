"""
header.py
Top header bar with real logged-in user name and initials.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from theme import toggle_theme


def render_header(t: dict, title: str = "Welcome 👋", subtitle: str = ""):
    user = st.session_state.get("user", {})
    initials = user.get("avatar_initials", "??")

    left, right = st.columns([2.4, 1.6])

    with left:
        st.markdown(
            f"""
            <div class="arx-title" style="font-size:1.6rem;">{title}</div>
            <div class="arx-subtitle">{subtitle}</div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        s1, s2, s3, s4 = st.columns([3, 1, 1, 1])
        with s1:
            search_query = st.text_input(
                "search", placeholder="🔍  Search candidates, resumes...",
                label_visibility="collapsed", key="global_search",
            )
            if search_query:
                st.session_state.page = "Ranked Candidates"
                st.session_state.search_query = search_query
        with s2:
            icon = "🌙" if t["name"] == "light" else "☀️"
            if st.button(icon, key="theme_toggle_btn", help="Toggle theme"):
                toggle_theme()
                st.rerun()
        with s3:
            st.button("🔔", key="notif_btn", help="Notifications")
        with s4:
            st.markdown(
                f'<div class="arx-avatar" style="margin-top:2px;font-size:0.78rem;" title="Logged in as {user.get("name", "User")}">{initials}</div>',
                unsafe_allow_html=True,
            )

    st.markdown('<div class="arx-divider" style="margin-top:0.6rem;"></div>', unsafe_allow_html=True)
