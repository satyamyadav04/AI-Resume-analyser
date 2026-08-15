"""
resume_analysis.py
Bulk upload page with real AI processing, per-file progress, queue display,
and stored analysis viewer.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from components import score_ring, progress_bar, skill_badges, card_open, card_close
from formatting import format_timestamp
from backend.services import dataset_service, upload_service, jd_service
from backend.services.candidate_service import get_candidate_profile


def render(t: dict):
    user = st.session_state.get("user", {})
    company_id = st.session_state.get("company_id")
    active_jd = st.session_state.get("active_jd")
    jd_id = active_jd["id"] if active_jd else None
    user_id = user.get("id")

    left, right = st.columns([1, 1.4])

    # ── LEFT: Upload Panel ────────────────────────────────────────────────────
    with left:
        card_open()
        st.markdown('<div class="arx-section-title">📁 Bulk Resume Upload</div>', unsafe_allow_html=True)

        if not active_jd:
            if st.button("Use Dataset JD", key="ra_dataset_jd", use_container_width=True):
                active = dataset_service.ensure_dataset_job_description(company_id, user_id)
                st.session_state.active_jd = active
                st.success("Dataset JD activated. You can now import candidates.")
                st.rerun()
            st.warning("⚠️ No active Job Description found. Create one first to enable AI matching.")
            if st.button("📝 Create JD", key="ra_create_jd"):
                st.session_state.page = "Job Description"
                st.rerun()
            card_close()
            return

        company_name = user.get("company_name", "Your Company")
        info_col, action_col = st.columns([3.2, 1.1])
        with info_col:
            st.markdown(
                f"""
                <div style="background:{t['primary_soft']};border-radius:10px;padding:0.75rem 0.9rem;
                            margin-bottom:0.9rem;display:flex;align-items:center;gap:0.6rem;">
                    <span>📝</span>
                    <div>
                        <div style="font-size:0.74rem;color:{t['primary']};font-weight:700;">CURRENT HIRING POSITION</div>
                        <div style="font-size:0.9rem;font-weight:700;color:{t['text']};">
                            {active_jd['title']}
                        </div>
                        <div style="font-size:0.76rem;color:{t['text_muted']};margin-top:0.1rem;">
                            Company: {company_name} · All resume matching uses this active JD only
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with action_col:
            if st.button("Change Active JD", key="resume_change_active_jd", use_container_width=True):
                st.session_state.page = "Job Description"
                st.rerun()

        dataset_limit = st.number_input(
            "Dataset candidates",
            min_value=10,
            max_value=200,
            value=50,
            step=10,
            help="Import challenge dataset candidates against the active JD.",
        )
        if st.button("Use Challenge Dataset", key="ra_import_dataset", use_container_width=True):
            with st.spinner("Importing dataset candidates..."):
                result = dataset_service.import_challenge_candidates(
                    company_id=company_id,
                    jd_id=jd_id,
                    user_id=user_id,
                    limit=int(dataset_limit),
                )
            if result["imported"]:
                st.session_state.view_candidate_id = result["last_candidate_id"]
                st.success(
                    f"Imported {result['imported']} candidates from the {result['dataset_source']}. "
                    f"Skipped {result['skipped']} duplicates."
                )
                st.rerun()
            else:
                st.info(f"No new candidates imported. Skipped {result['skipped']} duplicates.")

        uploaded_files = st.file_uploader(
            "Upload Resumes",
            type=["pdf", "docx", "txt", "zip"],
            accept_multiple_files=True,
            label_visibility="collapsed",
            help="Upload up to 100 resumes. ZIP files are automatically extracted.",
        )

        if uploaded_files:
            n = len(uploaded_files)
            st.markdown(
                f"""
                <div style="font-size:0.85rem;color:{t['text']};font-weight:600;margin-bottom:0.5rem;">
                    {n} file{'s' if n != 1 else ''} selected
                </div>
                """,
                unsafe_allow_html=True,
            )
            # File list preview
            for uf in uploaded_files[:5]:
                size_kb = round(uf.size / 1024, 1)
                st.markdown(
                    f"""
                    <div style="display:flex;justify-content:space-between;padding:0.3rem 0;
                                border-bottom:1px solid {t['border']};font-size:0.8rem;">
                        <span style="color:{t['text']};font-weight:600;">📎 {uf.name[:35]}</span>
                        <span style="color:{t['text_muted']};">{size_kb} KB</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            if n > 5:
                st.markdown(
                    f'<div style="font-size:0.78rem;color:{t["text_muted"]};margin-top:0.3rem;">... and {n-5} more</div>',
                    unsafe_allow_html=True,
                )

            st.markdown("<div style='height:0.8rem;'></div>", unsafe_allow_html=True)
            st.markdown('<div class="arx-primary-btn">', unsafe_allow_html=True)
            start_upload = st.button(
                f"🚀 Analyze {n} Resume{'s' if n != 1 else ''}", use_container_width=True, key="bulk_analyze"
            )
            st.markdown("</div>", unsafe_allow_html=True)

            if start_upload:
                jd_text = jd_service.get_active_jd_text(company_id)
                _run_bulk_upload(uploaded_files, company_id, jd_id, user_id, jd_text, t)

        else:
            st.markdown(
                f"""
                <div class="arx-upload" style="margin-top:0.5rem;">
                    <div style="font-size:2.5rem;margin-bottom:0.5rem;">📂</div>
                    <div style="font-weight:700;color:{t['text']};font-size:0.92rem;">
                        Drop resumes here or click Browse
                    </div>
                    <div style="font-size:0.78rem;color:{t['text_muted']};margin-top:0.4rem;">
                        PDF, DOCX, TXT — or a ZIP of multiple resumes
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Upload history
        _render_upload_history(company_id, jd_id, t)
        card_close()

    # ── RIGHT: Analysis Viewer ─────────────────────────────────────────────────
    with right:
        selected_id = st.session_state.get("view_candidate_id") or st.session_state.get("last_analyzed", {}).get("candidate_id")

        if selected_id:
            _render_analysis_viewer(selected_id, t)
        else:
            card_open("min-height:400px;")
            st.markdown('<div class="arx-section-title">🧠 AI Analysis Viewer</div>', unsafe_allow_html=True)
            st.markdown(
                f"""<div style="text-align:center;padding:4rem 0;color:{t['text_muted']};">
                    <div style="font-size:3rem;margin-bottom:0.8rem;">🔍</div>
                    <div style="font-size:0.9rem;font-weight:600;">Upload a resume to see full AI analysis</div>
                    <div style="font-size:0.8rem;margin-top:0.3rem;">
                        Or select a candidate from the Ranked Candidates page.
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )
            card_close()


def _run_bulk_upload(uploaded_files, company_id, jd_id, user_id, jd_text, t):
    """Run bulk upload with UI progress tracking."""
    all_files = []
    for uf in uploaded_files:
        data = uf.read()
        if uf.name.lower().endswith(".zip"):
            expanded = upload_service.expand_zip(data)
            all_files.extend(expanded)
        else:
            all_files.append((uf.name, data))

    total = len(all_files)
    if total == 0:
        st.warning("No valid resume files found.")
        return

    theme_color = t.get("text", "#000000")
    st.markdown(
        f'<div style="font-weight:700;margin:0.8rem 0 0.4rem 0;color:{theme_color}">Processing {total} resumes...</div>',
        unsafe_allow_html=True,
    )

    progress_bar_ui = st.progress(0)
    status_box = st.empty()
    results_placeholder = st.empty()

    successes = []
    failures = []

    for i, (filename, file_bytes) in enumerate(all_files):
        status_box.markdown(
            f'<div style="font-size:0.83rem;color:#666;">Processing {i+1}/{total}: <b>{filename}</b></div>',
            unsafe_allow_html=True,
        )
        progress_bar_ui.progress((i + 1) / total)

        result = upload_service.process_resume(
            file_bytes=file_bytes,
            filename=filename,
            company_id=company_id,
            jd_id=jd_id,
            user_id=user_id,
            jd_text=jd_text,
        )
        if result["success"]:
            successes.append(result)
            st.session_state.last_analyzed = result
        else:
            failures.append(result)

    # Summary
    status_box.empty()
    progress_bar_ui.empty()

    if successes:
        st.success(f"✅ {len(successes)} resume{'s' if len(successes) != 1 else ''} analyzed successfully!")
    if failures:
        with st.expander(f"⚠️ {len(failures)} file(s) failed — click to expand"):
            for f in failures:
                st.error(f"❌ {f['filename']}: {f['error']}")

    if successes:
        # Show last analyzed in viewer
        st.session_state.view_candidate_id = successes[-1]["candidate_id"]
        st.rerun()


def _render_analysis_viewer(candidate_id: int, t: dict):
    """Display full AI analysis for a candidate."""
    profile = get_candidate_profile(candidate_id)
    if not profile:
        st.error("Candidate data not found.")
        return

    analysis = profile.get("analysis") or {}
    score_pct = profile.get("score_pct", 0)
    rec = profile.get("recommendation", "—")

    card_open()
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:0.9rem;margin-bottom:1rem;">
            <div class="arx-avatar" style="width:52px;height:52px;font-size:1.1rem;">
                {"".join([p[0] for p in profile.get("name","?").split()[:2]]).upper()}
            </div>
            <div>
                <div style="font-weight:800;font-size:1.1rem;color:{t['text']};">{profile.get('name','Unknown')}</div>
                <div style="font-size:0.82rem;color:{t['text_secondary']};">{profile.get('current_title','')}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([1, 1.4])
    with c1:
        score_ring(score_pct, t, size=170)
    with c2:
        pill_cls = "arx-pill-success" if score_pct >= 75 else "arx-pill-warning" if score_pct >= 55 else "arx-pill-danger"
        st.markdown(
            f"""
            <div style="padding-top:0.5rem;">
                <div class="arx-caption">Recommendation</div>
                <span class="arx-pill {pill_cls}">{rec}</span>
                <div class="arx-caption" style="margin-top:0.8rem;">Experience</div>
                <div style="font-weight:700;color:{t['text']};font-size:0.95rem;">
                    {profile.get('experience_years', 0):.1f} years
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:0.4rem;'></div>", unsafe_allow_html=True)
    st.markdown('<div class="arx-section-title">Score Breakdown</div>', unsafe_allow_html=True)
    breakdown = [
        ("Skill Match", profile.get("skill_match_pct", 0)),
        ("Semantic Match", profile.get("semantic_match_pct", 0)),
        ("Experience", profile.get("experience_match_pct", 0)),
        ("Education", profile.get("education_match_pct", 0)),
        ("Projects", profile.get("project_match_pct", 0)),
    ]
    for label, pct in breakdown:
        progress_bar(label, pct, t)

    # Skills
    skills_list = [s["name"] for s in profile.get("skills", [])[:8] if s.get("name")]
    if skills_list:
        st.markdown('<div class="arx-section-title" style="margin-top:0.8rem;">Technical Skills</div>', unsafe_allow_html=True)
        skill_badges(skills_list)

    # Missing skills
    missing = analysis.get("missing_skills", [])
    if missing:
        st.markdown('<div class="arx-section-title" style="margin-top:0.8rem;">Missing Skills</div>', unsafe_allow_html=True)
        badges_html = "".join(
            f'<span class="arx-pill arx-pill-danger">{s}</span>' for s in missing[:8]
        )
        st.markdown(f"<div>{badges_html}</div>", unsafe_allow_html=True)

    # AI Summary
    ai_sum = analysis.get("ai_summary", "")
    if ai_sum:
        st.markdown('<div class="arx-section-title" style="margin-top:0.8rem;">AI Summary</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div style="font-size:0.85rem;color:{t["text_secondary"]};line-height:1.6;">{ai_sum}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)
    if st.button("📋 View Full Profile", key="goto_profile", use_container_width=True):
        st.session_state.selected_candidate_id = candidate_id
        st.session_state.page = "Candidate Profile"
        st.rerun()

    card_close()


def _render_upload_history(company_id, jd_id, t):
    """Show recent upload queue below upload panel."""
    try:
        from backend.repositories.candidate_repo import get_recent_uploads
        from backend.services import upload_service

        uploads = get_recent_uploads(company_id, limit=6)
        if not uploads:
            return

        st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)
        st.markdown('<div class="arx-caption" style="margin-bottom:0.4rem;">Recent Uploads</div>', unsafe_allow_html=True)

        for up in uploads:
            if jd_id and up.get("jd_id") != jd_id:
                continue

            status = up.get("status", "")
            icon = {"completed": "✅", "failed": "❌", "processing": "⏳", "uploaded": "📄"}.get(status, "📄")
            info_col, action_col = st.columns([4.5, 1.2])
            with info_col:
                size_kb = round(float(up.get("file_size") or 0) / 1024, 1)
                candidate_name = up.get("candidate_name") or "Analysis pending"
                st.markdown(
                    f"""<div style="font-size:0.78rem;color:{t['text_secondary']};
                                    padding:0.2rem 0;border-bottom:1px solid {t['border']};">
                        {icon} {up.get('filename','')[:32]} — <span style="color:{t['text_muted']};">{format_timestamp(up.get('created_at'))}</span>
                    </div>""",
                    unsafe_allow_html=True,
                )
                st.caption(f"{candidate_name} · {size_kb} KB · Status: {status or 'uploaded'}")
            with action_col:
                if st.button("🗑 Delete", key=f"delete_upload_{up['id']}", help=f"Delete {up.get('filename', '')}", use_container_width=True):
                    try:
                        upload_service.delete_uploaded_resume(upload_id=up["id"], company_id=company_id)
                        st.success(f"Deleted: {up.get('filename', '')}")
                        st.rerun()
                    except Exception as exc:
                        st.warning(str(exc))
    except Exception:
        pass
