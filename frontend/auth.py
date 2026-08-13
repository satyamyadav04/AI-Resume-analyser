"""
frontend/auth.py
Login and Signup UI — matches existing card aesthetic from styles.py.
Uses auth_service for real password hashing and user creation.
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from backend.database.db import init_db
from backend.services.auth_service import login, register


def _ensure_db():
    """Initialize DB on first use."""
    if not st.session_state.get("_db_initialized"):
        init_db()
        st.session_state._db_initialized = True


def render_auth(t: dict):
    """Render login/signup tabs. Sets st.session_state.user on success."""
    _ensure_db()

    st.markdown(
        f"""
        <div style="display:flex;justify-content:center;align-items:center;
                    min-height:60vh;flex-direction:column;gap:1.5rem;">
            <div style="text-align:center;">
                <div style="font-size:2.8rem;margin-bottom:0.4rem;">🤖</div>
                <div style="font-size:1.8rem;font-weight:800;color:{t['text']};
                            letter-spacing:-0.03em;">AI Resume Analyzer</div>
                <div style="font-size:0.92rem;color:{t['text_secondary']};margin-top:0.2rem;">
                    Enterprise ATS powered by AI
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Center the form
    _, center, _ = st.columns([1, 1.4, 1])
    with center:
        tab_login, tab_signup = st.tabs(["🔐  Sign In", "✨  Create Account"])

        with tab_login:
            _render_login_form(t)

        with tab_signup:
            _render_signup_form(t)


def _render_login_form(t: dict):
    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    with st.form("login_form", clear_on_submit=False):
        st.markdown(
            f'<div style="font-size:1.1rem;font-weight:700;color:{t["text"]};margin-bottom:0.8rem;">'
            "Sign in to your workspace</div>",
            unsafe_allow_html=True,
        )
        email = st.text_input("Email", placeholder="you@company.com", key="login_email")
        password = st.text_input("Password", type="password", placeholder="••••••••", key="login_password")
        remember = st.checkbox("Remember me", value=True, key="login_remember")

        st.markdown("<div style='height:0.3rem'></div>", unsafe_allow_html=True)
        st.markdown('<div class="arx-primary-btn">', unsafe_allow_html=True)
        submitted = st.form_submit_button("Sign In →", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        if submitted:
            if not email or not password:
                st.error("Please fill in all fields.")
            else:
                with st.spinner("Signing in..."):
                    user = login(email, password)
                if user:
                    st.session_state.user = user
                    st.session_state.company_id = user["company_id"]
                    st.session_state.page = "Dashboard"
                    st.success(f"Welcome back, {user['name'].split()[0]}! 👋")
                    st.rerun()
                else:
                    st.error("Invalid email or password. Please try again.")

    st.markdown(
        f"""
        <div style="text-align:center;font-size:0.8rem;color:{t['text_muted']};margin-top:1rem;">
            Demo credentials: <b>demo@company.com</b> / <b>demo1234</b>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _ensure_demo_account()


def _render_signup_form(t: dict):
    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    with st.form("signup_form", clear_on_submit=True):
        st.markdown(
            f'<div style="font-size:1.1rem;font-weight:700;color:{t["text"]};margin-bottom:0.8rem;">'
            "Create your ATS workspace</div>",
            unsafe_allow_html=True,
        )
        name = st.text_input("Full Name", placeholder="Ritika Talwar", key="signup_name")
        company = st.text_input("Company Name", placeholder="Acme Corp", key="signup_company")
        email = st.text_input("Work Email", placeholder="you@company.com", key="signup_email")
        c1, c2 = st.columns(2)
        with c1:
            password = st.text_input("Password", type="password", placeholder="Min. 6 chars", key="signup_password")
        with c2:
            confirm = st.text_input("Confirm Password", type="password", placeholder="Repeat", key="signup_confirm")

        st.markdown("<div style='height:0.3rem'></div>", unsafe_allow_html=True)
        st.markdown('<div class="arx-primary-btn">', unsafe_allow_html=True)
        submitted = st.form_submit_button("Create Account →", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        if submitted:
            if not all([name, company, email, password, confirm]):
                st.error("Please fill in all fields.")
            elif password != confirm:
                st.error("Passwords do not match.")
            else:
                try:
                    with st.spinner("Creating your workspace..."):
                        user = register(name, company, email, password)
                    st.session_state.user = user
                    st.session_state.company_id = user["company_id"]
                    st.session_state.page = "Dashboard"
                    st.success(f"Welcome, {user['name'].split()[0]}! Your workspace is ready. 🎉")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Registration failed: {exc}")


def _ensure_demo_account():
    """Create a demo account if it doesn't exist (first run convenience)."""
    if st.session_state.get("_demo_checked"):
        return
    st.session_state._demo_checked = True
    try:
        from backend.repositories.user_repo import email_exists
        if not email_exists("demo@company.com"):
            register("Demo HR Manager", "Demo Company", "demo@company.com", "demo1234")
    except Exception:
        pass
