"""
theme.py
Central theme manager for the AI Resume Analyzer dashboard.
Holds the color tokens for both LIGHT and DARK themes and exposes
helpers to read/toggle the active theme via st.session_state.
"""

import streamlit as st

LIGHT_THEME = {
    "name": "light",
    "bg": "#F8FAFC",
    "bg_gradient": "linear-gradient(180deg, #F8FAFC 0%, #EEF2F9 100%)",
    "surface": "#FFFFFF",
    "surface_alt": "#F1F5F9",
    "border": "#E7ECF3",
    "text": "#0F172A",
    "text_secondary": "#5B6472",
    "text_muted": "#94A3B8",
    "primary": "#2563EB",
    "primary_soft": "#EAF0FE",
    "primary_gradient": "linear-gradient(135deg, #2563EB 0%, #4F8CFF 100%)",
    "success": "#22C55E",
    "success_soft": "#E9FBF0",
    "warning": "#F59E0B",
    "warning_soft": "#FEF6E7",
    "danger": "#EF4444",
    "danger_soft": "#FDECEC",
    "shadow": "0 10px 30px rgba(15, 23, 42, 0.06)",
    "shadow_hover": "0 16px 40px rgba(15, 23, 42, 0.10)",
    "sidebar_bg": "#FFFFFF",
    "chart_grid": "#E7ECF3",
}

DARK_THEME = {
    "name": "dark",
    "bg": "#07111F",
    "bg_gradient": "linear-gradient(180deg, #07111F 0%, #0B1A2C 100%)",
    "surface": "#10243B",
    "surface_alt": "#0D1E33",
    "border": "#1E3A56",
    "text": "#EAF2FB",
    "text_secondary": "#9DB2C9",
    "text_muted": "#6C86A0",
    "primary": "#22C55E",
    "primary_soft": "#123524",
    "primary_gradient": "linear-gradient(135deg, #22C55E 0%, #10B981 100%)",
    "success": "#22C55E",
    "success_soft": "#123524",
    "warning": "#F59E0B",
    "warning_soft": "#3A2A0E",
    "danger": "#EF4444",
    "danger_soft": "#3A1414",
    "shadow": "0 10px 30px rgba(0, 0, 0, 0.35)",
    "shadow_hover": "0 18px 45px rgba(0, 0, 0, 0.45)",
    "sidebar_bg": "#0B1A2C",
    "chart_grid": "#1E3A56",
}


def init_theme():
    """Ensure a theme key exists in session_state. Defaults to light."""
    if "theme_mode" not in st.session_state:
        st.session_state.theme_mode = "light"


def get_theme():
    """Return the active theme color dict."""
    init_theme()
    return DARK_THEME if st.session_state.theme_mode == "dark" else LIGHT_THEME


def toggle_theme():
    st.session_state.theme_mode = (
        "dark" if st.session_state.theme_mode == "light" else "light"
    )
