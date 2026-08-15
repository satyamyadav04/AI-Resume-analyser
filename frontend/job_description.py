"""
job_description.py
Real CRUD for Job Descriptions — create, activate, edit, delete, duplicate.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from formatting import format_timestamp
from components import card_open, card_close
from backend.services import jd_service


def render(t: dict):
    user = st.session_state.get("user", {})
    company_id = st.session_state.get("company_id")
    user_id = user.get("id")

    st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)

    left, right = st.columns([1.6, 1])

    # ── LEFT: Create / Edit JD ────────────────────────────────────────────────
    with left:
        # Check if editing
        edit_jd = st.session_state.get("editing_jd")

        card_open()
        mode = "Edit Job Description" if edit_jd else "Create Job Description"
        st.markdown(f'<div class="arx-section-title">📝 {mode}</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div style="font-size:0.8rem;color:{t["text_muted"]};margin-bottom:0.8rem;">Only one job description can stay active at a time.</div>',
            unsafe_allow_html=True,
        )

        with st.form("jd_form", clear_on_submit=not bool(edit_jd)):
            jd_title = st.text_input(
                "Job Title *",
                value=edit_jd.get("title", "") if edit_jd else "",
                placeholder="e.g. Senior Frontend Engineer",
            )
            jd_desc = st.text_area(
                "Job Description *",
                value=edit_jd.get("description", "") if edit_jd else "",
                height=200,
                placeholder="Describe the role, responsibilities, and requirements...",
            )
            jd_reqs = st.text_area(
                "Skills & Requirements",
                value=edit_jd.get("requirements", "") if edit_jd else "",
                height=80,
                placeholder="List required skills, e.g. React, TypeScript, 4+ years...",
            )
            make_active = st.checkbox(
                "Set as Active Job Description",
                value=True if not edit_jd else bool(edit_jd.get("is_active")),
            )

            char_count = len(jd_desc)
            st.markdown(
                f"""
                <div style="display:flex;justify-content:space-between;align-items:center;margin-top:0.4rem;">
                    <span style="font-size:0.76rem;color:{t['text_muted']};">{char_count} characters</span>
                    <span style="font-size:0.76rem;color:{t['text_muted']};">Recommended: 200–2000 characters</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)
            col_save, col_cancel = st.columns([2, 1])
            with col_save:
                st.markdown('<div class="arx-primary-btn">', unsafe_allow_html=True)
                save_label = "💾 Update JD" if edit_jd else "🚀 Save & Activate"
                submitted = st.form_submit_button(save_label, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
            with col_cancel:
                cancel = st.form_submit_button("Cancel", use_container_width=True)

            if cancel and edit_jd:
                del st.session_state["editing_jd"]
                st.rerun()

            if submitted:
                if not jd_title.strip() or not jd_desc.strip():
                    st.error("Job Title and Description are required.")
                else:
                    try:
                        if edit_jd:
                            jd_service.update_job_description(
                                company_id, edit_jd["id"], jd_title, jd_desc, jd_reqs
                            )
                            if make_active:
                                jd_service.activate_jd(company_id, edit_jd["id"])
                            del st.session_state["editing_jd"]
                            st.success(f"✅ Job Description '{jd_title}' updated!")
                        else:
                            jd_id = jd_service.create_job_description(
                                company_id, user_id, jd_title, jd_desc, jd_reqs, make_active
                            )
                            st.success(f"✅ Job Description '{jd_title}' created! (#{jd_id})")

                        # Refresh active JD in session
                        _refresh_active_jd(company_id)
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))

        card_close()

    # ── RIGHT: Tips + Active Postings ─────────────────────────────────────────
    with right:
        card_open()
        st.markdown('<div class="arx-section-title">💡 Tips for a Great JD</div>', unsafe_allow_html=True)
        for tip in [
            "List required skills clearly and separately from nice-to-haves.",
            "Specify minimum years of experience for accurate AI matching.",
            "Mention required education level if relevant.",
            "Include tools & technologies explicitly, e.g. React, AWS, SQL.",
        ]:
            st.markdown(
                f"""
                <div style="display:flex;gap:0.6rem;margin-bottom:0.7rem;">
                    <span style="color:{t['primary']};">✓</span>
                    <span style="font-size:0.83rem;color:{t['text_secondary']};">{tip}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        card_close()

        # Active JD Postings
        card_open()
        st.markdown('<div class="arx-section-title">📌 Job Postings</div>', unsafe_allow_html=True)
        jds = jd_service.list_job_descriptions(company_id)

        if not jds:
            st.markdown(
                f'<div style="color:{t["text_muted"]};font-size:0.85rem;padding:0.5rem 0;">No job descriptions yet.</div>',
                unsafe_allow_html=True,
            )
        else:
            for jd in jds:
                is_active = bool(jd.get("is_active"))
                active_badge = f'<span class="arx-pill arx-pill-success" style="font-size:0.68rem;">● Active</span>' if is_active else ""
                st.markdown(
                    f"""
                    <div style="padding:0.6rem 0;border-bottom:1px solid {t['border']};">
                        <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                            <div style="flex:1;min-width:0;">
                                <div style="font-size:0.85rem;font-weight:700;color:{t['text']};
                                            white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                                    {jd['title']}
                                </div>
                                <div style="font-size:0.73rem;color:{t['text_muted']};margin-top:0.15rem;">
                                    {jd.get('resume_count', 0)} resumes · {format_timestamp(jd.get('created_at'), 10)}
                                </div>
                            </div>
                            <div style="margin-left:0.5rem;">{active_badge}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                btn_cols = st.columns(4)
                with btn_cols[0]:
                    if st.button("⚡ Activate", key=f"act_{jd['id']}", use_container_width=True, disabled=is_active):
                        jd_service.activate_jd(company_id, jd["id"])
                        _refresh_active_jd(company_id)
                        st.success(f"Activated: {jd['title']}")
                        st.rerun()
                with btn_cols[1]:
                    if st.button("✏️ Edit", key=f"edit_{jd['id']}", use_container_width=True):
                        st.session_state["editing_jd"] = jd
                        st.rerun()
                with btn_cols[2]:
                    if st.button("⧉ Dupe", key=f"dupe_{jd['id']}", use_container_width=True):
                        new_id = jd_service.duplicate_job_description(company_id, user_id, jd["id"])
                        st.success(f"Duplicated → #{new_id}")
                        st.rerun()
                with btn_cols[3]:
                    if st.button("🗑 Del", key=f"del_{jd['id']}", use_container_width=True):
                        try:
                            jd_service.delete_job_description(company_id, jd["id"])
                            _refresh_active_jd(company_id)
                            st.success("Deleted.")
                            st.rerun()
                        except ValueError as exc:
                            st.warning(str(exc))

        card_close()


def _refresh_active_jd(company_id: int):
    """Update session state with the current active JD."""
    active = jd_service.get_active_jd(company_id)
    st.session_state.active_jd = active
