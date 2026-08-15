"""
dashboard.py
Dashboard landing page — all data from live SQLite, zero placeholders.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from components import metric_card, score_ring, progress_bar, skill_badges, card_open, card_close
from formatting import format_timestamp
from backend.services import analytics_service, jd_service, upload_service
from backend.repositories.candidate_repo import get_recent_uploads


def render(t: dict):
    user = st.session_state.get("user", {})
    company_id = st.session_state.get("company_id")
    active_jd = st.session_state.get("active_jd")
    jd_id = active_jd["id"] if active_jd else None

    # ── Live KPIs ─────────────────────────────────────────────────────────────
    kpis = analytics_service.get_dashboard_kpis(company_id, jd_id)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        metric_card("📄", kpis["resumes_uploaded"]["value"], "Resumes Uploaded",
                    kpis["resumes_uploaded"]["delta"], kpis["resumes_uploaded"]["up"])
    with k2:
        metric_card("✅", kpis["analyses_completed"]["value"], "Analyses Completed",
                    kpis["analyses_completed"]["delta"], kpis["analyses_completed"]["up"])
    with k3:
        metric_card("🏆", kpis["best_score"]["value"], "Best Candidate Score",
                    kpis["best_score"]["delta"], kpis["best_score"]["up"])
    with k4:
        metric_card("📊", kpis["avg_score"]["value"], "Average Match Score",
                    kpis["avg_score"]["delta"], kpis["avg_score"]["up"])

    st.markdown("<div style='height:0.4rem;'></div>", unsafe_allow_html=True)

    left, center, right = st.columns([1.05, 1.3, 1.05])

    # ── LEFT: Upload card ─────────────────────────────────────────────────────
    with left:
        card_open()
        st.markdown('<div class="arx-section-title">📤 Quick Upload</div>', unsafe_allow_html=True)

        if not active_jd:
            st.markdown(
                f"""<div style="background:{t['warning_soft']};border-radius:12px;
                             padding:0.9rem;font-size:0.84rem;color:{t['warning']};
                             margin-bottom:0.8rem;">
                    ⚠️ No active Job Description. Please create one first.
                </div>""",
                unsafe_allow_html=True,
            )
            st.markdown('<div class="arx-primary-btn">', unsafe_allow_html=True)
            if st.button("📝 Create Job Description", use_container_width=True, key="dash_create_jd"):
                st.session_state.page = "Job Description"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            company_name = user.get("company_name", "Your Company")
            st.markdown(
                f"""
                <div style="background:{t['primary_soft']};border-radius:12px;padding:0.75rem 0.9rem;
                            margin-bottom:0.8rem;">
                    <div style="font-size:0.72rem;font-weight:700;color:{t['primary']};">CURRENT HIRING POSITION</div>
                    <div style="font-size:0.9rem;font-weight:800;color:{t['text']};margin-top:0.1rem;">
                        {active_jd.get('title', 'Unnamed JD')}
                    </div>
                    <div style="font-size:0.76rem;color:{t['text_muted']};margin-top:0.15rem;">
                        Company: {company_name}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Change Active JD", use_container_width=True, key="dash_change_active_jd"):
                st.session_state.page = "Job Description"
                st.rerun()

            st.markdown(
                f"""
                <div class="arx-upload">
                    <div style="font-size:2rem;margin-bottom:0.4rem;">📁</div>
                    <div style="font-weight:700;color:{t['text']};font-size:0.9rem;">
                        Drag &amp; drop resume here
                    </div>
                    <div style="font-size:0.76rem;color:{t['text_muted']};margin:0.3rem 0 0.9rem 0;">
                        Supported: PDF, DOCX, TXT
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            uploaded = st.file_uploader(
                "Browse Resume", type=["pdf", "docx", "txt"], label_visibility="collapsed",
                key="dash_upload",
            )
            if uploaded:
                filename = uploaded.name
                st.markdown(
                    f"""
                    <div style="margin-top:0.6rem;display:flex;align-items:center;gap:0.5rem;
                                background:{t['surface_alt']};border-radius:10px;padding:0.55rem 0.8rem;">
                        <span>📎</span>
                        <span style="font-size:0.82rem;color:{t['text_secondary']};font-weight:600;">
                            {filename}
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.markdown('<div class="arx-primary-btn">', unsafe_allow_html=True)
                if st.button("🚀 Analyze Resume", use_container_width=True, key="dash_analyze_btn"):
                    jd_text = jd_service.get_active_jd_text(company_id)
                    with st.spinner(f"Processing '{filename}'..."):
                        result = upload_service.process_resume(
                            file_bytes=uploaded.read(),
                            filename=filename,
                            company_id=company_id,
                            jd_id=jd_id,
                            user_id=user["id"],
                            jd_text=jd_text,
                        )
                    if result["success"]:
                        st.session_state.last_analyzed = result
                        st.success(f"✅ {result['name']} analyzed! Score: {int(result['score']*100)}%")
                        st.rerun()
                    else:
                        st.error(f"❌ {result['error']}")
                st.markdown("</div>", unsafe_allow_html=True)
        card_close()

    # ── CENTER: AI Analysis Summary ────────────────────────────────────────────
    with center:
        card_open()
        st.markdown('<div class="arx-section-title">🧠 AI Analysis Summary</div>', unsafe_allow_html=True)

        last = st.session_state.get("last_analyzed")
        if last and last.get("success"):
            score_pct = int(last["score"] * 100)
            rc1, rc2 = st.columns([1, 1])
            with rc1:
                score_ring(score_pct, t, size=170)
            with rc2:
                rec = last.get("recommendation", "—")
                pill_cls = "arx-pill-success" if score_pct >= 75 else "arx-pill-warning" if score_pct >= 55 else "arx-pill-danger"
                st.markdown(
                    f"""
                    <div style="padding-top:0.6rem;">
                        <div class="arx-caption">Last Analyzed</div>
                        <div style="font-weight:700;color:{t['text']};font-size:1rem;margin-bottom:0.6rem;">
                            {last['name']}
                        </div>
                        <div class="arx-caption">Recommendation</div>
                        <span class="arx-pill {pill_cls}">{rec}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            # Skill breakdown from analysis
            st.markdown("<div style='height:0.4rem;'></div>", unsafe_allow_html=True)
            st.markdown('<div class="arx-caption" style="margin-bottom:0.5rem;">Score Breakdown</div>', unsafe_allow_html=True)
            if last.get("candidate_id"):
                _render_score_breakdown(last["candidate_id"], t)
        else:
            _render_empty_analysis(t)

        card_close()

    # ── RIGHT: Best Candidate ─────────────────────────────────────────────────
    with right:
        card_open()
        st.markdown('<div class="arx-section-title">🥇 Best Candidate</div>', unsafe_allow_html=True)

        raw = kpis.get("_raw", {})
        best_name = raw.get("best_candidate_name", "")
        best_score = int(raw.get("best_score", 0.0) * 100)

        if best_name and best_name != "—":
            initials = "".join([p[0] for p in best_name.split()[:2]]).upper()
            # Get best candidate's skills
            best_skills = _get_best_candidate_skills(company_id, jd_id)
            st.markdown(
                f"""
                <div style="text-align:center;padding:0.4rem 0 1rem 0;">
                    <div class="arx-avatar" style="width:72px;height:72px;font-size:1.5rem;margin:0 auto 0.8rem auto;">
                        {initials}
                    </div>
                    <div style="font-weight:800;color:{t['text']};font-size:1.05rem;">{best_name}</div>
                    <div style="font-size:0.82rem;color:{t['text_secondary']};margin-bottom:0.6rem;">
                        Top Candidate
                    </div>
                    <span class="arx-pill arx-pill-success" style="font-size:0.85rem;padding:0.3rem 0.9rem;">
                        {best_score}% Match
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if best_skills:
                st.markdown('<div class="arx-caption" style="margin-bottom:0.4rem;">Top Skills</div>', unsafe_allow_html=True)
                skill_badges(best_skills)
        else:
            st.markdown(
                f"""<div style="text-align:center;padding:1.5rem 0;color:{t['text_muted']};font-size:0.88rem;">
                    No candidates yet.<br>Upload a resume to get started.
                </div>""",
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)
        st.markdown('<div class="arx-primary-btn">', unsafe_allow_html=True)
        if st.button("View All Candidates →", key="view_best_candidate", use_container_width=True):
            st.session_state.page = "Ranked Candidates"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        card_close()

    # ── Recent Uploads ─────────────────────────────────────────────────────────
    if company_id:
        _render_recent_uploads(company_id, t)


def _render_score_breakdown(candidate_id: int, t: dict):
    try:
        from backend.repositories.candidate_repo import get_candidate_analysis
        analysis = get_candidate_analysis(candidate_id)
        if analysis:
            items = [
                ("Skill Match", int(float(analysis.get("skill_match", 0)) * 100)),
                ("Semantic Match", int(float(analysis.get("semantic_match", 0)) * 100)),
                ("Experience", int(float(analysis.get("experience_score", 0)) * 100)),
                ("Education", int(float(analysis.get("education_score", 0)) * 100)),
                ("Projects", int(float(analysis.get("project_score", 0)) * 100)),
            ]
            for label, pct in items:
                progress_bar(label, pct, t)
    except Exception:
        pass


def _render_empty_analysis(t: dict):
    st.markdown(
        f"""<div style="text-align:center;padding:2rem 0;color:{t['text_muted']};font-size:0.88rem;">
            Upload a resume above to see the AI analysis summary here.
        </div>""",
        unsafe_allow_html=True,
    )
    for label, pct in [("Skill Match", 0), ("Experience", 0), ("Education", 0), ("Projects", 0)]:
        progress_bar(label, pct, t)


def _get_best_candidate_skills(company_id: int, jd_id) -> list[str]:
    try:
        from backend.database.db import get_db
        params = [company_id]
        jd_filter = "AND c.jd_id = %s" if jd_id else ""
        if jd_id:
            params.append(jd_id)
        with get_db() as db:
            with db.cursor() as cur:
                cur.execute(
                    f"""SELECT c.id FROM candidates c
                        JOIN analysis_results ar ON ar.candidate_id = c.id
                        WHERE c.company_id = %s {jd_filter}
                        ORDER BY ar.overall_score DESC LIMIT 1""",
                    params,
                )
                row = cur.fetchone()
        if row:
            from backend.repositories.candidate_repo import get_candidate_skills
            skills = get_candidate_skills(row[0])
            return [s["name"] for s in skills[:5] if s.get("name")]
    except Exception:
        pass
    return []


def _render_recent_uploads(company_id: int, t: dict):
    try:
        from backend.services import upload_service

        uploads = get_recent_uploads(company_id, limit=5)
        if not uploads:
            return

        st.markdown("<div style='height:0.2rem;'></div>", unsafe_allow_html=True)
        card_open()
        st.markdown('<div class="arx-section-title">🕒 Recent Uploads</div>', unsafe_allow_html=True)

        for upload in uploads:
            status = upload.get("status", "unknown")
            status_color = {
                "completed": t["success"],
                "processing": t["warning"],
                "failed": t["danger"],
                "uploaded": t["text_muted"],
            }.get(status, t["text_muted"])

            row_cols = st.columns([5, 1])
            with row_cols[0]:
                size_kb = round(float(upload.get("file_size") or 0) / 1024, 1)
                candidate_name = upload.get("candidate_name") or "Analysis pending"
                st.markdown(
                    f"""
                    <div style="display:flex;justify-content:space-between;align-items:center;
                                padding:0.55rem 0;border-bottom:1px solid {t['border']};">
                        <div style="display:flex;align-items:center;gap:0.5rem;">
                            <span style="font-size:1rem;">📄</span>
                            <div>
                                <div style="font-size:0.84rem;font-weight:600;color:{t['text']};">
                                    {upload.get('filename', 'Unknown')[:40]}
                                </div>
                                <div style="font-size:0.72rem;color:{t['text_muted']};">
                                    by {upload.get('uploader_name', 'User')} · {format_timestamp(upload.get('created_at'))}
                                </div>
                            </div>
                        </div>
                        <span style="font-size:0.74rem;font-weight:700;color:{status_color};
                                     background:{status_color}22;border-radius:999px;padding:0.2rem 0.6rem;">
                            {status.upper()}
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.caption(f"Candidate: {candidate_name} · {size_kb} KB")
            with row_cols[1]:
                if st.button("🗑 Delete", key=f"dash_delete_upload_{upload['id']}", use_container_width=True):
                    try:
                        upload_service.delete_uploaded_resume(upload_id=upload["id"], company_id=company_id)
                        st.success(f"Deleted: {upload.get('filename', '')}")
                        st.rerun()
                    except Exception as exc:
                        st.warning(str(exc))
        card_close()
    except Exception:
        pass
