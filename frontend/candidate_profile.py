"""
candidate_profile.py
Full candidate profile page: AI scores, skills, experience, timeline, notes, interview scheduling.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from components import score_ring, progress_bar, skill_badges, card_open, card_close
from formatting import format_timestamp
from backend.services.candidate_service import (
    get_candidate_profile, move_to_stage, add_note, schedule_interview,
    get_resume_file_path, STAGE_LABELS
)
from backend.repositories.candidate_repo import PIPELINE_STAGES
from backend.services.report_service import generate_candidate_report


def render(t: dict):
    candidate_id = st.session_state.get("selected_candidate_id")
    user = st.session_state.get("user", {})
    company_id = st.session_state.get("company_id")
    user_id = user.get("id")

    if not candidate_id:
        st.info("No candidate selected. Please select a candidate from the Ranked Candidates page.")
        if st.button("→ Go to Ranked Candidates"):
            st.session_state.page = "Ranked Candidates"
            st.rerun()
        return

    profile = get_candidate_profile(candidate_id)
    if not profile:
        st.error("Candidate not found.")
        return

    analysis = profile.get("analysis") or {}
    jd_id = profile.get("jd_id")

    # ── Back button ───────────────────────────────────────────────────────────
    if st.button("← Back to Ranked Candidates", key="cp_back"):
        st.session_state.page = "Ranked Candidates"
        st.rerun()

    st.markdown("<div style='height:0.4rem;'></div>", unsafe_allow_html=True)

    # ── Top Row: Identity + Scores ────────────────────────────────────────────
    id_col, score_col, action_col = st.columns([1.4, 1.6, 1])

    with id_col:
        card_open()
        name = profile.get("name", "Unknown")
        initials = "".join([p[0] for p in name.split()[:2]]).upper()
        stage = profile.get("pipeline_stage", "NEW")
        stage_label, stage_cls = STAGE_LABELS.get(stage, (stage, "primary"))
        rec = profile.get("recommendation", "—")
        pill_cls = "arx-pill-success" if "Strong" in rec or "Good" in rec else "arx-pill-warning" if "Possible" in rec else "arx-pill-danger"

        st.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:0.9rem;margin-bottom:0.9rem;">
                <div class="arx-avatar" style="width:68px;height:68px;font-size:1.4rem;">{initials}</div>
                <div>
                    <div style="font-weight:800;font-size:1.25rem;color:{t['text']};">{name}</div>
                    <div style="font-size:0.85rem;color:{t['text_secondary']};margin-bottom:0.3rem;">
                        {profile.get('current_title','—')}
                    </div>
                    <span class="arx-pill arx-pill-{stage_cls}">{stage_label}</span>
                    <span class="arx-pill {pill_cls}">{rec}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        contact_rows = [
            ("📧", profile.get("email", "—")),
            ("📞", profile.get("phone", "—")),
            ("📍", profile.get("location", "—")),
            ("🔗", profile.get("github", "—")),
            ("💼", profile.get("linkedin", "—")),
        ]
        for icon, val in contact_rows:
            if val and val != "—":
                st.markdown(
                    f'<div style="font-size:0.8rem;color:{t["text_secondary"]};margin-bottom:0.2rem;">'
                    f'{icon} {val[:50]}</div>',
                    unsafe_allow_html=True,
                )
        card_close()

    with score_col:
        card_open()
        score_pct = profile.get("score_pct", 0)
        r1, r2 = st.columns([1, 1.3])
        with r1:
            score_ring(score_pct, t, size=165)
        with r2:
            breakdown = [
                ("Skill Match", profile.get("skill_match_pct", 0)),
                ("Semantic", profile.get("semantic_match_pct", 0)),
                ("Experience", profile.get("experience_match_pct", 0)),
                ("Education", profile.get("education_match_pct", 0)),
                ("Projects", profile.get("project_match_pct", 0)),
            ]
            for label, pct in breakdown:
                progress_bar(label, pct, t)
        card_close()

    with action_col:
        card_open()
        st.markdown('<div class="arx-section-title">Actions</div>', unsafe_allow_html=True)

        new_stage = st.selectbox(
            "Move to Stage",
            PIPELINE_STAGES,
            index=PIPELINE_STAGES.index(stage) if stage in PIPELINE_STAGES else 0,
            key="cp_stage_sel",
        )
        st.markdown('<div class="arx-primary-btn">', unsafe_allow_html=True)
        if st.button("✅ Move to Stage", key="cp_move_stage", use_container_width=True):
            move_to_stage(candidate_id, new_stage, user_id)
            st.success(f"Moved to {new_stage}")
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div style='height:0.4rem;'></div>", unsafe_allow_html=True)

        # Download resume
        file_path = get_resume_file_path(candidate_id)
        if file_path and os.path.exists(file_path):
            with open(file_path, "rb") as f:
                st.download_button(
                    "📥 Download Resume",
                    data=f.read(),
                    file_name=os.path.basename(file_path),
                    use_container_width=True,
                    key="cp_dl_resume",
                )

            confirm_delete = st.checkbox(
                "Confirm resume deletion",
                key="cp_confirm_delete_resume",
                help="This removes the uploaded resume and its linked candidate analysis.",
            )
            if st.button(
                "Delete Resume",
                key="cp_delete_resume",
                use_container_width=True,
                disabled=not confirm_delete,
            ):
                from backend.services import upload_service

                upload_id = profile.get("upload_id")
                if upload_id:
                    upload_service.delete_uploaded_resume(int(upload_id), company_id)
                    st.session_state.pop("selected_candidate_id", None)
                    st.session_state.page = "Resume Analysis"
                    st.success("Resume and its candidate record were deleted.")
                    st.rerun()

        # Download report
        report_bytes = generate_candidate_report(candidate_id)
        st.download_button(
            "📋 Download Report",
            data=report_bytes,
            file_name=f"candidate_{name.replace(' ','_')}_report.csv",
            mime="text/csv",
            use_container_width=True,
            key="cp_dl_report",
        )
        card_close()

    # ── Tabs: Skills | AI Analysis | Timeline | Notes | Interview | Education ──
    tab_names = ["🛠 Skills", "🧠 AI Analysis", "📅 Timeline", "📝 Notes", "📞 Interview", "🎓 Education & Projects"]
    tabs = st.tabs(tab_names)

    # ── Skills tab ─────────────────────────────────────────────────────────────
    with tabs[0]:
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            card_open()
            st.markdown('<div class="arx-section-title">Technical Skills</div>', unsafe_allow_html=True)
            skills = profile.get("skills", [])
            if skills:
                skill_badges([s["name"] for s in skills if s.get("name")])
                for s in skills:
                    if s.get("name"):
                        months = s.get("duration_months", 0)
                        prof = s.get("proficiency", "intermediate")
                        st.markdown(
                            f'<div style="display:flex;justify-content:space-between;font-size:0.78rem;color:{t["text_secondary"]};padding:0.15rem 0;">'
                            f'<span>{s["name"]}</span><span>{prof} · {months}mo</span></div>',
                            unsafe_allow_html=True,
                        )
            else:
                st.markdown(f'<div style="color:{t["text_muted"]};font-size:0.85rem;">No skills extracted.</div>', unsafe_allow_html=True)
            card_close()

        with col_s2:
            card_open()
            st.markdown('<div class="arx-section-title">Missing Skills</div>', unsafe_allow_html=True)
            missing = analysis.get("missing_skills", [])
            if missing:
                badges = "".join(f'<span class="arx-pill arx-pill-danger">{s}</span>' for s in missing)
                st.markdown(f"<div>{badges}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f'<div style="color:{t["text_muted"]};font-size:0.85rem;">No significant skill gaps detected.</div>', unsafe_allow_html=True)

            st.markdown("<div style='height:0.8rem;'></div>", unsafe_allow_html=True)
            strengths = analysis.get("strengths", [])
            weaknesses = analysis.get("weaknesses", [])
            if strengths:
                st.markdown('<div class="arx-section-title">Strengths</div>', unsafe_allow_html=True)
                for s in strengths:
                    st.markdown(f'<div style="font-size:0.82rem;color:{t["success"]};margin-bottom:0.3rem;">✓ {s}</div>', unsafe_allow_html=True)
            if weaknesses:
                st.markdown('<div class="arx-section-title">Areas of Concern</div>', unsafe_allow_html=True)
                for w in weaknesses:
                    st.markdown(f'<div style="font-size:0.82rem;color:{t["danger"]};margin-bottom:0.3rem;">⚠ {w}</div>', unsafe_allow_html=True)
            card_close()

    # ── AI Analysis tab ────────────────────────────────────────────────────────
    with tabs[1]:
        card_open()
        st.markdown('<div class="arx-section-title">AI Summary</div>', unsafe_allow_html=True)
        ai_sum = analysis.get("ai_summary", "")
        if ai_sum:
            st.markdown(f'<div style="font-size:0.88rem;color:{t["text_secondary"]};line-height:1.65;">{ai_sum}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="color:{t["text_muted"]};">No AI summary available.</div>', unsafe_allow_html=True)

        st.markdown("<div style='height:0.8rem;'></div>", unsafe_allow_html=True)
        st.markdown('<div class="arx-section-title">Recruiter Reasoning</div>', unsafe_allow_html=True)
        reasoning = analysis.get("reasoning", "")
        if reasoning:
            st.markdown(f'<div style="font-size:0.85rem;color:{t["text_secondary"]};line-height:1.65;">{reasoning}</div>', unsafe_allow_html=True)
        card_close()

    # ── Timeline tab ───────────────────────────────────────────────────────────
    with tabs[2]:
        card_open()
        st.markdown('<div class="arx-section-title">Candidate Timeline</div>', unsafe_allow_html=True)
        timeline = profile.get("timeline", [])
        if timeline:
            for ev in reversed(timeline):
                st.markdown(
                    f"""
                    <div style="display:flex;gap:0.8rem;padding:0.6rem 0;border-bottom:1px solid {t['border']};">
                        <div style="min-width:36px;text-align:center;font-size:0.8rem;">🕐</div>
                        <div>
                            <div style="font-size:0.85rem;font-weight:700;color:{t['text']};">{ev.get('event_type','')}</div>
                            <div style="font-size:0.78rem;color:{t['text_secondary']};margin-top:0.1rem;">{ev.get('event_detail','')}</div>
                            <div style="font-size:0.72rem;color:{t['text_muted']};margin-top:0.2rem;">
                                {format_timestamp(ev.get('created_at'))} · {ev.get('actor_name','System')}
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(f'<div style="color:{t["text_muted"]};font-size:0.85rem;padding:1rem 0;">No timeline events yet.</div>', unsafe_allow_html=True)
        card_close()

    # ── Notes tab ──────────────────────────────────────────────────────────────
    with tabs[3]:
        col_n1, col_n2 = st.columns([1.4, 1])
        with col_n1:
            card_open()
            st.markdown('<div class="arx-section-title">Add Note</div>', unsafe_allow_html=True)
            note_text = st.text_area("Note", placeholder="Add a recruiter note...", height=100, key="cp_note_input", label_visibility="collapsed")
            if st.button("💬 Save Note", key="cp_save_note"):
                if note_text.strip():
                    add_note(candidate_id, user_id, note_text)
                    st.success("Note saved!")
                    st.rerun()
                else:
                    st.warning("Note cannot be empty.")
            card_close()

        with col_n2:
            card_open()
            st.markdown('<div class="arx-section-title">Notes History</div>', unsafe_allow_html=True)
            notes = profile.get("notes", [])
            if notes:
                for note in notes:
                    st.markdown(
                        f"""
                        <div style="padding:0.5rem 0;border-bottom:1px solid {t['border']};">
                            <div style="font-size:0.82rem;color:{t['text']};line-height:1.5;">{note.get('note_text','')}</div>
                            <div style="font-size:0.72rem;color:{t['text_muted']};margin-top:0.2rem;">
                                {note.get('author_name','?')} · {format_timestamp(note.get('created_at'))}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(f'<div style="color:{t["text_muted"]};font-size:0.85rem;">No notes yet.</div>', unsafe_allow_html=True)
            card_close()

    # ── Interview tab ──────────────────────────────────────────────────────────
    with tabs[4]:
        card_open()
        st.markdown('<div class="arx-section-title">Schedule Interview</div>', unsafe_allow_html=True)
        existing = profile.get("interview")
        candidate_email = (profile.get("email") or "").strip()
        if candidate_email:
            st.caption(f"Saving this interview will email the candidate at {candidate_email}.")
        else:
            st.warning("Candidate email is missing. Interview will be saved, but no email can be sent.")
        with st.form("interview_form"):
            ic1, ic2 = st.columns(2)
            with ic1:
                i_round = st.selectbox("Round", ["Technical Round 1", "Technical Round 2", "HR Round", "Final Round"], index=0)
                i_date = st.date_input("Date", value=None)
                i_time = st.time_input("Time")
            with ic2:
                i_interviewer = st.text_input("Interviewer", value=existing.get("interviewer", "") if existing else "")
                i_link = st.text_input("Meeting Link", value=existing.get("meeting_link", "") if existing else "")
            st.markdown('<div class="arx-primary-btn">', unsafe_allow_html=True)
            save_interview = st.form_submit_button("📅 Save Interview", use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

            if save_interview and i_date:
                mail_result = schedule_interview(
                    candidate_id, company_id, jd_id or 0, user_id,
                    {
                        "round": i_round,
                        "date": str(i_date),
                        "time": str(i_time),
                        "interviewer": i_interviewer,
                        "link": i_link,
                    },
                )
                if mail_result.get("sent"):
                    st.success(str(mail_result.get("message", "Interview scheduled and email sent!")))
                else:
                    st.warning(str(mail_result.get("message", "Interview scheduled.")))
                st.rerun()

        if existing:
            st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)
            st.markdown('<div class="arx-section-title">Scheduled Interview</div>', unsafe_allow_html=True)
            st.markdown(
                f"""
                <div style="background:{t['surface_alt']};border-radius:12px;padding:0.9rem;">
                    <div>📅 <b>{existing.get('interview_date','')} {existing.get('interview_time','')}</b></div>
                    <div>🔄 {existing.get('round_name','')}</div>
                    <div>👤 {existing.get('interviewer','')}</div>
                    <div>🔗 {existing.get('meeting_link','')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        card_close()

    # ── Education & Projects tab ───────────────────────────────────────────────
    with tabs[5]:
        ec1, ec2 = st.columns(2)
        with ec1:
            card_open()
            st.markdown('<div class="arx-section-title">Education</div>', unsafe_allow_html=True)
            education = profile.get("education", [])
            if education:
                for edu in education:
                    if isinstance(edu, dict):
                        st.markdown(
                            f"""
                            <div style="padding:0.4rem 0;border-bottom:1px solid {t['border']};">
                                <div style="font-weight:600;font-size:0.85rem;color:{t['text']};">{edu.get('degree','')}</div>
                                <div style="font-size:0.78rem;color:{t['text_secondary']};">{edu.get('institution','')} · {edu.get('year','')}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(f'<div style="font-size:0.85rem;padding:0.3rem 0;">{edu}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div style="color:{t["text_muted"]};">No education data.</div>', unsafe_allow_html=True)

            st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)
            st.markdown('<div class="arx-section-title">Certifications</div>', unsafe_allow_html=True)
            certs = profile.get("certificates", [])
            if certs:
                for cert in certs:
                    cert_name = cert.get("name","") if isinstance(cert, dict) else str(cert)
                    st.markdown(f'<span class="arx-skill-badge">🏅 {cert_name[:40]}</span>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div style="color:{t["text_muted"]};">No certifications.</div>', unsafe_allow_html=True)
            card_close()

        with ec2:
            card_open()
            st.markdown('<div class="arx-section-title">Projects</div>', unsafe_allow_html=True)
            projects = profile.get("projects", [])
            if projects:
                for proj in projects:
                    if isinstance(proj, dict):
                        st.markdown(
                            f"""
                            <div style="padding:0.5rem 0;border-bottom:1px solid {t['border']};">
                                <div style="font-weight:600;font-size:0.85rem;color:{t['text']};">{proj.get('name','')}</div>
                                <div style="font-size:0.78rem;color:{t['text_secondary']};margin-top:0.15rem;">{proj.get('description','')[:120]}</div>
                                <div style="margin-top:0.3rem;">{_tech_badges(proj.get('technologies',''))}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(f'<div style="font-size:0.82rem;padding:0.3rem 0;">{str(proj)[:120]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div style="color:{t["text_muted"]};">No projects data.</div>', unsafe_allow_html=True)
            card_close()

    # ── Experience section ─────────────────────────────────────────────────────
    card_open()
    st.markdown('<div class="arx-section-title">💼 Work Experience</div>', unsafe_allow_html=True)
    experience = profile.get("experience", [])
    if experience:
        for exp in experience:
            if isinstance(exp, dict):
                months = exp.get("duration_months", 0)
                yrs = f"{months//12}y {months%12}m" if months else ""
                st.markdown(
                    f"""
                    <div style="padding:0.55rem 0;border-bottom:1px solid {t['border']};">
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <div style="font-weight:700;font-size:0.88rem;color:{t['text']};">{exp.get('title','')}</div>
                            <div style="font-size:0.76rem;color:{t['text_muted']};">{yrs}</div>
                        </div>
                        <div style="font-size:0.8rem;color:{t['text_secondary']};margin-top:0.1rem;">{exp.get('company','')}</div>
                        <div style="font-size:0.78rem;color:{t['text_muted']};margin-top:0.2rem;">{exp.get('description','')[:200]}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.markdown(f'<div style="color:{t["text_muted"]};font-size:0.85rem;">No experience data extracted.</div>', unsafe_allow_html=True)
    card_close()


def _tech_badges(technologies: str) -> str:
    if not technologies:
        return ""
    techs = [t.strip() for t in technologies.replace(",", " ").split() if t.strip()][:5]
    return " ".join(f'<span class="arx-skill-badge">{tech}</span>' for tech in techs)
