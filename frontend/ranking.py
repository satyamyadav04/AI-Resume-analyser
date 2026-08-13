"""
ranking.py
Ranked candidates table — real DB data with search, filter, sort, pagination.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from components import card_open, card_close, score_pill, recommendation_pill
from backend.services.candidate_service import (
    get_ranked_candidates, shortlist_candidate, reject_candidate
)


def render(t: dict):
    company_id = st.session_state.get("company_id")
    user = st.session_state.get("user", {})
    user_id = user.get("id")
    active_jd = st.session_state.get("active_jd")
    jd_id = active_jd["id"] if active_jd else None

    # ── Filter Bar ────────────────────────────────────────────────────────────
    f1, f2, f3, f4 = st.columns([2.4, 1.2, 1.2, 1.2])
    with f1:
        search = st.text_input(
            "search",
            value=st.session_state.pop("search_query", ""),
            placeholder="🔍  Search by name, email, or title...",
            label_visibility="collapsed",
            key="rank_search",
        )
    with f2:
        stage_options = ["All Stages", "NEW", "AI_ANALYZED", "SHORTLISTED",
                         "INTERVIEW_SCHEDULED", "TECHNICAL_ROUND", "HR_ROUND",
                         "OFFER_SENT", "HIRED", "REJECTED"]
        stage_filter = st.selectbox("Stage", stage_options, label_visibility="collapsed", key="rank_stage")
    with f3:
        score_options = ["Any Score", "80%+", "60–79%", "Below 60%"]
        score_filter_raw = st.selectbox("Score", score_options, label_visibility="collapsed", key="rank_score")
        score_filter = None if score_filter_raw == "Any Score" else score_filter_raw
    with f4:
        sort_options = {"Highest Score": "score_desc", "Lowest Score": "score_asc", "Newest First": "newest", "A → Z": "name_asc"}
        sort_label = st.selectbox("Sort", list(sort_options.keys()), label_visibility="collapsed", key="rank_sort")
        sort_by = sort_options[sort_label]

    page = st.session_state.get("rank_page", 1)

    # ── Fetch Candidates ──────────────────────────────────────────────────────
    candidates, total = get_ranked_candidates(
        company_id=company_id,
        jd_id=jd_id,
        search=search,
        stage_filter=None if stage_filter == "All Stages" else stage_filter,
        score_filter=score_filter,
        sort_by=sort_by,
        page=page,
        page_size=20,
    )

    page_size = 20
    total_pages = max(1, (total + page_size - 1) // page_size)

    # Summary row
    st.markdown(
        f"""
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.6rem;">
            <div style="font-size:0.85rem;color:{t['text_secondary']};">
                Showing <b style="color:{t['text']}">{len(candidates)}</b> of <b style="color:{t['text']}">{total}</b> candidates
            </div>
            <div style="font-size:0.82rem;color:{t['text_muted']};">Page {page} of {total_pages}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not candidates:
        card_open()
        st.markdown(
            f"""<div style="text-align:center;padding:2.5rem 0;color:{t['text_muted']};">
                <div style="font-size:2.5rem;margin-bottom:0.8rem;">🔍</div>
                <div style="font-size:0.9rem;font-weight:600;">No candidates found</div>
                <div style="font-size:0.8rem;margin-top:0.3rem;">
                    Try adjusting your filters or upload resumes to get started.
                </div>
            </div>""",
            unsafe_allow_html=True,
        )
        card_close()
        return

    # ── Candidates Table ──────────────────────────────────────────────────────
    _render_table(candidates, t, user_id, company_id, jd_id)

    # ── Pagination ────────────────────────────────────────────────────────────
    if total_pages > 1:
        st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
        pc1, pc2, pc3 = st.columns([1, 2, 1])
        with pc1:
            if page > 1:
                if st.button("← Previous", key="rank_prev"):
                    st.session_state.rank_page = page - 1
                    st.rerun()
        with pc2:
            st.markdown(
                f'<div style="text-align:center;color:{t["text_muted"]};font-size:0.84rem;padding-top:0.5rem;">'
                f'Page {page} of {total_pages}</div>',
                unsafe_allow_html=True,
            )
        with pc3:
            if page < total_pages:
                if st.button("Next →", key="rank_next"):
                    st.session_state.rank_page = page + 1
                    st.rerun()


def _render_table(candidates: list, t: dict, user_id: int, company_id: int, jd_id):
    """Render the ranked candidates table with action buttons."""
    # Table header
    rows_html = ""
    for c in candidates:
        skills = c.get("skills", [])[:3]
        skills_html = "".join(f'<span class="arx-skill-badge">{s}</span>' for s in skills)
        name = c.get("name", "Unknown")
        initials = "".join([p[0] for p in name.split()[:2]]).upper()
        score_pct = c.get("score_pct", 0)
        skill_pct = c.get("skill_match_pct", 0)
        exp_pct = c.get("experience_match_pct", 0)
        stage = c.get("pipeline_stage", "NEW")
        rec = c.get("recommendation", "—")

        rows_html += f"""
        <tr>
            <td><b>#{c.get('rank', '?')}</b></td>
            <td>
                <div style="display:flex;align-items:center;gap:0.6rem;">
                    <div class="arx-avatar" style="width:32px;height:32px;font-size:0.72rem;">{initials}</div>
                    <div>
                        <div style="font-weight:600;">{name}</div>
                        <div style="font-size:0.72rem;color:{t['text_muted']};">{c.get('current_title','')}</div>
                    </div>
                </div>
            </td>
            <td>{score_pill(score_pct)}</td>
            <td style="min-width:100px;">
                <div class="arx-progress-track"><div class="arx-progress-fill" style="width:{skill_pct}%;"></div></div>
                <div style="font-size:0.72rem;color:{t['text_muted']};margin-top:2px;">{skill_pct}%</div>
            </td>
            <td style="min-width:100px;">
                <div class="arx-progress-track"><div class="arx-progress-fill" style="width:{exp_pct}%;"></div></div>
                <div style="font-size:0.72rem;color:{t['text_muted']};margin-top:2px;">{exp_pct}%</div>
            </td>
            <td>{c.get('experience_years', 0):.1f} yrs</td>
            <td>{skills_html}</td>
            <td>{recommendation_pill(rec)}</td>
            <td>
                <span style="font-size:0.72rem;font-weight:700;padding:0.2rem 0.5rem;
                             border-radius:6px;background:{t['surface_alt']};color:{t['text_secondary']};">
                    {stage.replace('_',' ')}
                </span>
            </td>
        </tr>
        """

    st.markdown(
        f"""
        <div class="arx-card" style="padding:0.5rem 0.5rem 1rem 0.5rem;overflow-x:auto;">
            <table class="arx-table">
                <thead>
                    <tr>
                        <th>Rank</th><th>Candidate</th><th>Overall</th><th>Skills</th>
                        <th>Experience</th><th>Exp. Yrs</th><th>Top Skills</th>
                        <th>Recommendation</th><th>Stage</th>
                    </tr>
                </thead>
                <tbody>{rows_html}</tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Action buttons row below table
    st.markdown('<div class="arx-caption" style="margin:0.5rem 0 0.3rem 0;">Quick Actions</div>', unsafe_allow_html=True)
    for i, c in enumerate(candidates):
        c_id = c["id"]
        name = c.get("name", "Candidate")
        acols = st.columns([2, 1, 1, 1, 5])
        with acols[0]:
            st.markdown(
                f'<div style="font-size:0.8rem;font-weight:700;color:{t["text"]};padding-top:0.4rem;">#{c.get("rank")} {name[:20]}</div>',
                unsafe_allow_html=True,
            )
        with acols[1]:
            if st.button("👁 View", key=f"view_{c_id}_{i}"):
                st.session_state.selected_candidate_id = c_id
                st.session_state.page = "Candidate Profile"
                st.rerun()
        with acols[2]:
            if st.button("⭐ List", key=f"slist_{c_id}_{i}"):
                shortlist_candidate(c_id, company_id, jd_id or 0, user_id)
                st.success(f"Shortlisted {name}!")
                st.rerun()
        with acols[3]:
            if st.button("✕ Rej", key=f"rej_{c_id}_{i}"):
                reject_candidate(c_id, user_id)
                st.info(f"Rejected {name}.")
                st.rerun()
