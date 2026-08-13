"""
analytics.py
All charts powered by live DB data — zero demo_data.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from components import card_open, card_close
from backend.services import analytics_service


def render(t: dict):
    company_id = st.session_state.get("company_id")
    active_jd = st.session_state.get("active_jd")
    jd_id = active_jd["id"] if active_jd else None

    # JD selector in filter row
    f1, f2 = st.columns([3, 1])
    with f1:
        st.markdown(
            f'<div style="font-size:0.85rem;color:{t["text_secondary"]};padding:0.5rem 0;">'
            f'Analytics for: <b>{active_jd["title"] if active_jd else "All Job Descriptions"}</b></div>',
            unsafe_allow_html=True,
        )
    with f2:
        if st.button("📊 Refresh", key="analytics_refresh", use_container_width=True):
            st.rerun()

    st.markdown("<div style='height:0.3rem;'></div>", unsafe_allow_html=True)

    # ── Row 1 ─────────────────────────────────────────────────────────────────
    c1, c2 = st.columns(2)

    with c1:
        card_open()
        st.markdown('<div class="arx-section-title">📊 Score Distribution</div>', unsafe_allow_html=True)
        sd = analytics_service.get_score_distribution(company_id, jd_id)
        if any(sd["counts"]):
            fig = go.Figure(go.Bar(
                x=sd["buckets"], y=sd["counts"],
                marker=dict(color=t["primary"], opacity=0.85),
                text=sd["counts"], textposition="outside",
            ))
            fig.update_layout(**_chart_layout(t))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            _empty_chart(t, "No analysis data yet.")
        card_close()

    with c2:
        card_open()
        st.markdown('<div class="arx-section-title">🛠 Top Skills in Pool</div>', unsafe_allow_html=True)
        sc = analytics_service.get_skills_coverage(company_id, jd_id)
        if sc["skills"]:
            fig = go.Figure(go.Bar(
                x=sc["coverage"], y=sc["skills"],
                orientation="h",
                marker=dict(color=t["success"], opacity=0.85),
                text=sc["coverage"], textposition="auto",
            ))
            fig.update_layout(**_chart_layout(t, height=320))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            _empty_chart(t, "No skills data yet.")
        card_close()

    # ── Row 2 ─────────────────────────────────────────────────────────────────
    c3, c4 = st.columns(2)

    with c3:
        card_open()
        st.markdown('<div class="arx-section-title">⏱ Experience Distribution</div>', unsafe_allow_html=True)
        ed = analytics_service.get_experience_distribution(company_id, jd_id)
        if any(ed["counts"]):
            fig = go.Figure(go.Bar(
                x=ed["labels"], y=ed["counts"],
                marker=dict(color=t["warning"], opacity=0.85),
                text=ed["counts"], textposition="outside",
            ))
            fig.update_layout(**_chart_layout(t))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            _empty_chart(t, "No experience data yet.")
        card_close()

    with c4:
        card_open()
        st.markdown('<div class="arx-section-title">🎓 Education Breakdown</div>', unsafe_allow_html=True)
        eb = analytics_service.get_education_breakdown(company_id, jd_id)
        if any(eb["counts"]):
            fig = go.Figure(go.Pie(
                labels=eb["labels"], values=eb["counts"],
                hole=0.5,
                marker=dict(colors=[t["primary"], t["success"], t["warning"], t["danger"], t["text_muted"]]),
            ))
            fig.update_layout(**_chart_layout(t, showlegend=True))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            _empty_chart(t, "No education data yet.")
        card_close()

    # ── Row 3 ─────────────────────────────────────────────────────────────────
    c5, c6 = st.columns(2)

    with c5:
        card_open()
        st.markdown('<div class="arx-section-title">🚫 Commonly Missing Skills</div>', unsafe_allow_html=True)
        ms = analytics_service.get_missing_skills(company_id, jd_id)
        if ms.get("skills"):
            fig = go.Figure(go.Bar(
                x=ms["counts"], y=ms["skills"],
                orientation="h",
                marker=dict(color=t["danger"], opacity=0.85),
                text=ms["counts"], textposition="auto",
            ))
            fig.update_layout(**_chart_layout(t, height=300))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            _empty_chart(t, "No missing skills data yet.")
        card_close()

    with c6:
        card_open()
        st.markdown('<div class="arx-section-title">🔄 Hiring Pipeline Funnel</div>', unsafe_allow_html=True)
        hf = analytics_service.get_hiring_funnel(company_id, jd_id)
        # Only show stages with candidates
        stages = hf["stages"]
        counts = hf["counts"]
        visible = [(s, c) for s, c in zip(stages, counts) if c > 0]

        if visible:
            v_stages = [v[0].replace("_", " ") for v in visible]
            v_counts = [v[1] for v in visible]
            fig = go.Figure(go.Funnel(
                y=v_stages, x=v_counts,
                textinfo="value+percent initial",
                marker=dict(color=[t["primary"]] * len(v_stages)),
            ))
            fig.update_layout(**_chart_layout(t, height=300))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            _empty_chart(t, "No pipeline data yet.")
        card_close()


def _chart_layout(t: dict, height: int = 280, showlegend: bool = False) -> dict:
    return {
        "height": height,
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": t["text_secondary"], "size": 11},
        "margin": {"l": 20, "r": 20, "t": 20, "b": 20},
        "showlegend": showlegend,
        "xaxis": {"gridcolor": t["chart_grid"], "linecolor": t["border"]},
        "yaxis": {"gridcolor": t["chart_grid"], "linecolor": t["border"]},
    }


def _empty_chart(t: dict, message: str):
    st.markdown(
        f"""<div style="text-align:center;padding:2.5rem 0;color:{t['text_muted']};font-size:0.88rem;">
            <div style="font-size:2rem;margin-bottom:0.5rem;">📊</div>
            {message}
        </div>""",
        unsafe_allow_html=True,
    )
