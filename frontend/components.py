"""
components.py
Reusable HTML/Plotly building blocks used across every page:
metric cards, score rings, progress bars, skill badges, pills,
candidate cards and the ranked-candidates table.
"""

import streamlit as st
import plotly.graph_objects as go


def metric_card(icon: str, value: str, label: str, delta: str = None, delta_up: bool = True):
    delta_html = ""
    if delta:
        cls = "arx-delta-up" if delta_up else "arx-delta-down"
        arrow = "▲" if delta_up else "▼"
        delta_html = f'<span class="arx-metric-delta {cls}">{arrow} {delta}</span>'
    st.markdown(
        f"""
        <div class="arx-metric">
            <div class="arx-metric-icon">{icon}</div>
            <div class="arx-metric-value">{value}</div>
            <div class="arx-metric-label">{label}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def score_ring(score: int, t: dict, size: int = 190, label: str = "Overall Match"):
    color = t["success"] if score >= 75 else t["warning"] if score >= 50 else t["danger"]
    fig = go.Figure(
        data=[
            go.Pie(
                values=[score, 100 - score],
                hole=0.78,
                marker=dict(colors=[color, t["surface_alt"]], line=dict(width=0)),
                textinfo="none",
                sort=False,
                direction="clockwise",
                rotation=0,
            )
        ]
    )
    fig.update_layout(
        showlegend=False,
        margin=dict(l=0, r=0, t=0, b=0),
        width=size,
        height=size,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        annotations=[
            dict(
                text=f"<b>{score}</b>",
                x=0.5, y=0.56, font=dict(size=size * 0.19, color=t["text"]),
                showarrow=False,
            ),
            dict(
                text=label,
                x=0.5, y=0.38, font=dict(size=size * 0.065, color=t["text_secondary"]),
                showarrow=False,
            ),
        ],
    )
    st.plotly_chart(fig, use_container_width=False, config={"displayModeBar": False})


def progress_bar(label: str, pct: int, t: dict):
    color = t["success"] if pct >= 75 else t["warning"] if pct >= 50 else t["danger"]
    st.markdown(
        f"""
        <div style="margin-bottom:0.85rem;">
            <div style="display:flex;justify-content:space-between;font-size:0.82rem;
                        color:{t['text_secondary']};font-weight:600;margin-bottom:0.3rem;">
                <span>{label}</span><span style="color:{t['text']}">{pct}%</span>
            </div>
            <div class="arx-progress-track">
                <div class="arx-progress-fill" style="width:{pct}%;background:{color};"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def skill_badges(skills: list):
    badges = "".join(f'<span class="arx-skill-badge">{s}</span>' for s in skills)
    st.markdown(f'<div>{badges}</div>', unsafe_allow_html=True)


def score_pill(score: int):
    if score >= 75:
        cls, txt = "arx-pill-success", "Strong"
    elif score >= 50:
        cls, txt = "arx-pill-warning", "Moderate"
    else:
        cls, txt = "arx-pill-danger", "Weak"
    return f'<span class="arx-pill {cls}">{score}% · {txt}</span>'


def recommendation_pill(rec: str):
    mapping = {
        "Strong Fit": "arx-pill-success",
        "Good Fit": "arx-pill-primary",
        "Possible Fit": "arx-pill-warning",
        "Not a Fit": "arx-pill-danger",
    }
    cls = mapping.get(rec, "arx-pill-primary")
    return f'<span class="arx-pill {cls}">{rec}</span>'


def candidate_card(candidate: dict, t: dict, key_suffix=""):
    initials = "".join([p[0] for p in candidate["name"].split()[:2]]).upper()
    skills_html = "".join(f'<span class="arx-skill-badge">{s}</span>' for s in candidate["skills"][:4])
    st.markdown(
        f"""
        <div class="arx-card">
            <div style="display:flex;align-items:center;gap:0.8rem;margin-bottom:0.9rem;">
                <div class="arx-avatar" style="width:52px;height:52px;font-size:1.1rem;">{initials}</div>
                <div>
                    <div style="font-weight:700;color:{t['text']};font-size:1.02rem;">{candidate['name']}</div>
                    <div style="font-size:0.82rem;color:{t['text_secondary']};">{candidate['role']}</div>
                </div>
                <div style="margin-left:auto;">{score_pill(candidate['score'])}</div>
            </div>
            <div style="font-size:0.8rem;color:{t['text_secondary']};margin-bottom:0.5rem;">
                {candidate['experience']} experience &nbsp;·&nbsp; {candidate['education']}
            </div>
            <div style="margin-bottom:0.9rem;">{skills_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def ranked_table(candidates: list, t: dict):
    rows = ""
    for c in candidates:
        skills_html = "".join(f'<span class="arx-skill-badge">{s}</span>' for s in c["skills"][:3])
        rows += f"""
        <tr>
            <td><b>#{c['rank']}</b></td>
            <td>
                <div style="display:flex;align-items:center;gap:0.6rem;">
                    <div class="arx-avatar" style="width:32px;height:32px;font-size:0.72rem;">
                        {''.join([p[0] for p in c['name'].split()[:2]]).upper()}
                    </div>
                    <div>
                        <div style="font-weight:600;">{c['name']}</div>
                        <div style="font-size:0.72rem;color:{t['text_muted']};">{c['role']}</div>
                    </div>
                </div>
            </td>
            <td>{score_pill(c['score'])}</td>
            <td style="min-width:120px;">
                <div class="arx-progress-track"><div class="arx-progress-fill" style="width:{c['skills_match']}%;"></div></div>
                <div style="font-size:0.72rem;color:{t['text_muted']};margin-top:2px;">{c['skills_match']}%</div>
            </td>
            <td style="min-width:120px;">
                <div class="arx-progress-track"><div class="arx-progress-fill" style="width:{c['experience_match']}%;"></div></div>
                <div style="font-size:0.72rem;color:{t['text_muted']};margin-top:2px;">{c['experience_match']}%</div>
            </td>
            <td>{c['education']}</td>
            <td>{skills_html}</td>
            <td>{recommendation_pill(c['recommendation'])}</td>
            <td>
                <span class="arx-skill-badge" style="cursor:pointer;">View</span>
                <span class="arx-skill-badge" style="cursor:pointer;">★ Shortlist</span>
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
                        <th>Experience</th><th>Education</th><th>Top Skills</th>
                        <th>Recommendation</th><th>Actions</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str = None):
    sub = f'<div class="arx-subtitle">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f'<div class="arx-title">{title}</div>{sub}',
        unsafe_allow_html=True,
    )


def card_open(extra_style=""):
    st.markdown(f'<div class="arx-card" style="{extra_style}">', unsafe_allow_html=True)


def card_close():
    st.markdown("</div>", unsafe_allow_html=True)
