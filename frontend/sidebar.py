"""
sidebar.py
Renders the left navigation rail with real logged-in user data,
live storage stats, and new nav items.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

NAV_ITEMS = [
    ("Dashboard", "🏠"),
    ("Resume Analysis", "📤"),
    ("Job Description", "📝"),
    ("Ranked Candidates", "🏆"),
    ("Analytics", "📊"),
    ("Recruitment Pipeline", "🔄"),
    ("Reports", "📋"),
    ("Settings", "⚙"),
]


def render_sidebar(t: dict):
    user = st.session_state.get("user", {})
    company_id = st.session_state.get("company_id")

    with st.sidebar:
        st.markdown(
            f"""
            <div style="padding:0.4rem 0.2rem 1.2rem 0.2rem;">
                <div style="font-size:1.25rem;font-weight:800;color:{t['text']};">
                    🤖 AI Resume Analyzer
                </div>
                <div style="font-size:0.78rem;color:{t['text_secondary']};margin-top:0.1rem;">
                    {user.get('company_name', 'Enterprise ATS')}
                </div>
            </div>
            <div class="arx-divider"></div>
            """,
            unsafe_allow_html=True,
        )

        if "page" not in st.session_state:
            st.session_state.page = "Dashboard"

        for label, icon in NAV_ITEMS:
            active = st.session_state.page == label
            btn_label = f"{icon}  {label}"
            if st.button(btn_label, key=f"nav_{label}", use_container_width=True):
                st.session_state.page = label
                st.rerun()
            if active:
                st.markdown(
                    f"""<div style="height:2px;background:{t['primary']};
                        border-radius:2px;margin:-8px 0 8px 0;width:36px;"></div>""",
                    unsafe_allow_html=True,
                )

        st.markdown('<div class="arx-divider"></div>', unsafe_allow_html=True)

        # Active JD indicator
        active_jd = st.session_state.get("active_jd")
        if active_jd:
            st.markdown(
                f"""
                <div style="background:{t['primary_soft']};border-radius:12px;
                            padding:0.65rem 0.9rem;margin-bottom:0.9rem;">
                    <div style="font-size:0.72rem;font-weight:600;color:{t['primary']};
                                text-transform:uppercase;letter-spacing:0.06em;margin-bottom:0.2rem;">
                        Active JD
                    </div>
                    <div style="font-size:0.82rem;font-weight:700;color:{t['text']};
                                white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                        📝 {active_jd.get('title', 'Unnamed JD')}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Storage usage (real resume count)
        resume_count = _get_resume_count(company_id)
        storage_pct = min(int((resume_count / 500) * 100), 100)
        st.markdown(
            f"""
            <div style="margin-bottom:1rem;">
                <div style="display:flex;justify-content:space-between;font-size:0.76rem;
                            color:{t['text_secondary']};font-weight:600;margin-bottom:0.3rem;">
                    <span>Resumes Stored</span><span>{resume_count} / 500</span>
                </div>
                <div class="arx-progress-track">
                    <div class="arx-progress-fill" style="width:{storage_pct}%;"></div>
                </div>
            </div>
            <div class="arx-divider"></div>
            """,
            unsafe_allow_html=True,
        )

        # Current user + logout
        initials = user.get("avatar_initials", "??")
        st.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.6rem;">
                <div class="arx-avatar">{initials}</div>
                <div>
                    <div style="font-weight:700;font-size:0.85rem;color:{t['text']};">
                        {user.get('name', 'User')}
                    </div>
                    <div style="font-size:0.72rem;color:{t['text_muted']};">
                        {user.get('role', 'HR Manager').replace('_', ' ').title()}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("🚪 Logout", key="nav_logout", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


def _get_resume_count(company_id) -> int:
    """Return total resumes stored for this company."""
    if not company_id:
        return 0
    try:
        from backend.database.db import get_db
        with get_db() as db:
            row = db.execute(
                "SELECT COUNT(*) FROM candidates WHERE company_id = ?", (company_id,)
            ).fetchone()
            return row[0] if row else 0
    except Exception:
        return 0
