"""
app.py
Entry point for the AI Resume Analyzer ATS dashboard.
Adds authentication gate, new pages, and real session management.
Run with: streamlit run frontend/app.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from backend.database.db import init_db
from theme import init_theme, get_theme
from styles import inject_global_css
from sidebar import render_sidebar
from header import render_header

import dashboard
import resume_analysis
import job_description
import ranking
import analytics
import pipeline
import candidate_profile
import settings
import reports
import auth
from backend.services import jd_service

st.set_page_config(
    page_title="AI Resume Analyzer — ATS",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Initialize Database ─────────────────────────────────────────────────────
if not st.session_state.get("_db_initialized"):
    init_db()
    st.session_state._db_initialized = True

# ── Theme ────────────────────────────────────────────────────────────────────
init_theme()
t = get_theme()
inject_global_css(t)

# ── Auth Gate ────────────────────────────────────────────────────────────────
if not st.session_state.get("user"):
    auth.render_auth(t)
    st.stop()

# ── Authenticated App ─────────────────────────────────────────────────────────
company_id = st.session_state.get("company_id")
if company_id:
    st.session_state.active_jd = jd_service.get_active_jd(company_id)

render_sidebar(t)

PAGE_TITLES = {
    "Dashboard": (
        f"Welcome back, {st.session_state.user['name'].split()[0]} 👋",
        "Here's what's happening with your candidate pipeline today.",
    ),
    "Resume Analysis": ("Resume Upload & Analysis", "Upload resumes and get AI-powered evaluations instantly."),
    "Job Description": ("Job Descriptions", "Create, manage, and activate job postings for AI matching."),
    "Ranked Candidates": ("Ranked Candidates", "Your candidate pool, sorted by AI match score."),
    "Analytics": ("Analytics", "Aggregate insights across all analyzed resumes."),
    "Recruitment Pipeline": ("Recruitment Pipeline", "Track candidates across all hiring stages."),
    "Candidate Profile": ("Candidate Profile", "Full AI analysis and recruitment history for this candidate."),
    "Reports": ("Reports & Exports", "Download rankings, pipeline reports, and analytics."),
    "Settings": ("Settings", "Manage your workspace preferences."),
}

page = st.session_state.get("page", "Dashboard")
title, subtitle = PAGE_TITLES.get(page, PAGE_TITLES["Dashboard"])
render_header(t, title=title, subtitle=subtitle)

PAGES = {
    "Dashboard": dashboard.render,
    "Resume Analysis": resume_analysis.render,
    "Job Description": job_description.render,
    "Ranked Candidates": ranking.render,
    "Analytics": analytics.render,
    "Recruitment Pipeline": pipeline.render,
    "Candidate Profile": candidate_profile.render,
    "Reports": reports.render,
    "Settings": settings.render,
}

PAGES.get(page, dashboard.render)(t)
