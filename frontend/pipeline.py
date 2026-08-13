"""
pipeline.py
Recruitment Pipeline — Kanban view of candidates across all hiring stages.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from components import score_pill, card_open, card_close
from backend.services.candidate_service import get_candidates_by_stage, move_to_stage, STAGE_LABELS
from backend.repositories.candidate_repo import PIPELINE_STAGES


def render(t: dict):
    company_id = st.session_state.get("company_id")
    active_jd = st.session_state.get("active_jd")
    jd_id = active_jd["id"] if active_jd else None
    user_id = st.session_state.get("user", {}).get("id")

    # Filter row
    f1, f2 = st.columns([3, 1])
    with f1:
        st.markdown(
            f'<div style="font-size:0.85rem;color:{t["text_secondary"]};padding:0.4rem 0;">'
            f'Pipeline for: <b>{active_jd["title"] if active_jd else "All Roles"}</b></div>',
            unsafe_allow_html=True,
        )
    with f2:
        if st.button("🔄 Refresh", key="pipeline_refresh", use_container_width=True):
            st.rerun()

    # ── Stage Summary ─────────────────────────────────────────────────────────
    # Count per stage
    stage_counts = {}
    stage_candidates = {}
    for stage in PIPELINE_STAGES:
        rows = get_candidates_by_stage(company_id, jd_id, stage)
        stage_counts[stage] = len(rows)
        stage_candidates[stage] = rows

    # Summary KPIs row
    top_stages = ["NEW", "AI_ANALYZED", "SHORTLISTED", "INTERVIEW_SCHEDULED", "HIRED"]
    kpi_cols = st.columns(len(top_stages))
    for col, stage in zip(kpi_cols, top_stages):
        label, cls = STAGE_LABELS.get(stage, (stage, "primary"))
        count = stage_counts.get(stage, 0)
        color_map = {"success": t["success"], "warning": t["warning"], "danger": t["danger"], "primary": t["primary"]}
        color = color_map.get(cls, t["primary"])
        with col:
            st.markdown(
                f"""
                <div class="arx-metric" style="text-align:center;">
                    <div style="font-size:1.6rem;font-weight:800;color:{t['text']};">{count}</div>
                    <div style="font-size:0.72rem;color:{t['text_secondary']};font-weight:600;">{label}</div>
                    <div style="height:3px;background:{color};border-radius:3px;margin-top:0.5rem;"></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:0.8rem;'></div>", unsafe_allow_html=True)

    # ── Kanban Board: 4 columns ────────────────────────────────────────────────
    # Group into two rows for readability
    kanban_groups = [
        ["NEW", "AI_ANALYZED", "SHORTLISTED"],
        ["INTERVIEW_SCHEDULED", "TECHNICAL_ROUND", "HR_ROUND"],
        ["OFFER_SENT", "HIRED", "REJECTED"],
    ]

    for group in kanban_groups:
        cols = st.columns(len(group))
        for col, stage in zip(cols, group):
            label, cls = STAGE_LABELS.get(stage, (stage, "primary"))
            candidates = stage_candidates.get(stage, [])
            color_map = {"success": t["success"], "warning": t["warning"], "danger": t["danger"], "primary": t["primary"]}
            header_color = color_map.get(cls, t["primary"])

            with col:
                # Stage header
                st.markdown(
                    f"""
                    <div style="background:{t['surface']};border:1px solid {t['border']};
                                border-radius:14px 14px 0 0;padding:0.7rem 0.9rem;
                                border-bottom:3px solid {header_color};margin-bottom:0.2rem;">
                        <div style="font-weight:700;font-size:0.85rem;color:{t['text']};">{label}</div>
                        <div style="font-size:0.72rem;color:{t['text_muted']};">{len(candidates)} candidates</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if not candidates:
                    st.markdown(
                        f"""<div style="background:{t['surface']};border:1px solid {t['border']};
                                         border-radius:0 0 14px 14px;padding:1.2rem 0.8rem;
                                         text-align:center;color:{t['text_muted']};font-size:0.78rem;">
                            Empty
                        </div>""",
                        unsafe_allow_html=True,
                    )
                else:
                    for c in candidates[:6]:
                        c_id = c.get("id")
                        c_name = c.get("name", "Unknown")
                        c_title = c.get("current_title", "")
                        c_score = c.get("score_pct", 0)
                        c_skills = c.get("skills", [])[:2]
                        initials = "".join([p[0] for p in c_name.split()[:2]]).upper()

                        st.markdown(
                            f"""
                            <div style="background:{t['surface']};border:1px solid {t['border']};
                                        border-radius:10px;padding:0.65rem 0.8rem;
                                        margin-bottom:0.4rem;cursor:pointer;">
                                <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.3rem;">
                                    <div class="arx-avatar" style="width:28px;height:28px;font-size:0.65rem;">{initials}</div>
                                    <div>
                                        <div style="font-size:0.8rem;font-weight:700;color:{t['text']};">{c_name[:22]}</div>
                                        <div style="font-size:0.68rem;color:{t['text_muted']};">{c_title[:25]}</div>
                                    </div>
                                </div>
                                <div style="display:flex;align-items:center;justify-content:space-between;">
                                    {score_pill(c_score)}
                                    <div style="font-size:0.68rem;color:{t['text_muted']};">
                                        {"".join(f'<span style="margin-right:2px;">{s}</span>' for s in c_skills[:2])}
                                    </div>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        # Quick action buttons
                        btn_cols = st.columns(2)
                        with btn_cols[0]:
                            if st.button("👁", key=f"pipe_view_{stage}_{c_id}", help=f"View {c_name}"):
                                st.session_state.selected_candidate_id = c_id
                                st.session_state.page = "Candidate Profile"
                                st.rerun()
                        with btn_cols[1]:
                            # Move button — advance to next stage
                            next_stage_idx = PIPELINE_STAGES.index(stage) + 1 if stage in PIPELINE_STAGES and PIPELINE_STAGES.index(stage) < len(PIPELINE_STAGES) - 1 else -1
                            if next_stage_idx >= 0 and PIPELINE_STAGES[next_stage_idx] not in ("HIRED", "REJECTED"):
                                next_s = PIPELINE_STAGES[next_stage_idx]
                                if st.button("→", key=f"pipe_move_{stage}_{c_id}", help=f"Move to {next_s}"):
                                    move_to_stage(c_id, next_s, user_id)
                                    st.rerun()

                    if len(candidates) > 6:
                        st.markdown(
                            f'<div style="font-size:0.75rem;color:{t["text_muted"]};text-align:center;padding:0.3rem;">+{len(candidates)-6} more</div>',
                            unsafe_allow_html=True,
                        )

        st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
