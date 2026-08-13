"""
reports.py
Single final-report download center.
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from components import card_open, card_close
from backend.services.report_service import generate_final_report


def render(t: dict):
    company_id = st.session_state.get("company_id")
    active_jd = st.session_state.get("active_jd")
    jd_id = active_jd["id"] if active_jd else None
    jd_label = active_jd["title"] if active_jd else "All JDs"
    selected_id = st.session_state.get("selected_candidate_id")

    st.markdown("<div style='height:0.4rem;'></div>", unsafe_allow_html=True)

    card_open()
    st.markdown('<div class="arx-section-title">Final Hiring Report</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div style="font-size:0.88rem;color:{t['text_secondary']};line-height:1.6;margin-bottom:0.9rem;">
            Ek hi final report generate hogi jisme summary, candidate ranking, analytics aur pipeline sab ek workbook
            me honge.<br>Active JD: <b>{jd_label}</b>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if selected_id:
        from backend.repositories.candidate_repo import get_candidate

        candidate = get_candidate(selected_id)
        if candidate:
            st.markdown(
                f'<div style="font-size:0.82rem;color:{t["text_secondary"]};margin-bottom:0.8rem;">'
                f'Selected candidate sheet bhi include hogi: <b>{candidate.get("name", "Candidate")}</b></div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            f'<div style="font-size:0.82rem;color:{t["text_muted"]};margin-bottom:0.8rem;">'
            f'Agar kisi specific candidate ka detailed tab bhi final report me chahiye, to pehle Ranked Candidates se candidate select kar lijiye.</div>',
            unsafe_allow_html=True,
        )

    report_bytes = generate_final_report(
        company_id=company_id,
        jd_id=jd_id,
        jd_label=jd_label,
        selected_candidate_id=selected_id,
    )
    st.download_button(
        "Download Final Report",
        data=report_bytes,
        file_name="final_hiring_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        key="dl_final_report",
    )

    if not selected_id and st.button("Go to Ranked Candidates", key="reports_goto_rank"):
        st.session_state.page = "Ranked Candidates"
        st.rerun()

    card_close()
