"""
shortlisted.py
"Shortlisted" page — card-based layout of shortlisted candidates
with View Resume / Shortlist / Reject action buttons.
"""

import streamlit as st
from components import score_pill, skill_badges, card_open, card_close, section_header
from demo_data import CANDIDATES


def render(t: dict):
    st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)

    shortlisted = CANDIDATES[:4]
    cols = st.columns(2)

    for i, c in enumerate(shortlisted):
        with cols[i % 2]:
            card_open()
            initials = "".join([p[0] for p in c["name"].split()[:2]]).upper()
            st.markdown(
                f"""
                <div style="display:flex;align-items:center;gap:0.8rem;margin-bottom:0.8rem;">
                    <div class="arx-avatar" style="width:50px;height:50px;">{initials}</div>
                    <div style="flex:1;">
                        <div style="font-weight:700;color:{t['text']};">{c['name']}</div>
                        <div style="font-size:0.8rem;color:{t['text_secondary']};">{c['role']}</div>
                    </div>
                    <div>{score_pill(c['score'])}</div>
                </div>
                <div style="font-size:0.8rem;color:{t['text_secondary']};margin-bottom:0.5rem;">
                    Experience: {c['experience']} &nbsp;·&nbsp; {c['education']}
                </div>
                """,
                unsafe_allow_html=True,
            )
            skill_badges(c["skills"])
            st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)
            b1, b2, b3 = st.columns(3)
            with b1:
                st.button("👁 View", key=f"view_{c['rank']}", use_container_width=True)
            with b2:
                st.button("⭐ Shortlist", key=f"short_{c['rank']}", use_container_width=True)
            with b3:
                st.button("✕ Reject", key=f"reject_{c['rank']}", use_container_width=True)
            card_close()
