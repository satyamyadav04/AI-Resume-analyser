"""
styles.py
Injects the global CSS that transforms default Streamlit into a
premium SaaS dashboard. All colors are pulled from the active theme
dict so the whole app re-skins instantly on toggle.
"""

import streamlit as st


def inject_global_css(t: dict):
    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }}

    /* ---------- Hide Streamlit chrome ---------- */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header {{visibility: hidden;}}
    div[data-testid="stToolbar"] {{display: none;}}
    div[data-testid="stDecoration"] {{display: none;}}
    div[data-testid="stStatusWidget"] {{display: none;}}

    /* ---------- App background ---------- */
    .stApp {{
        background: {t['bg_gradient']};
        color: {t['text']};
    }}

    section[data-testid="stSidebar"] > div {{
        background: {t['sidebar_bg']};
        border-right: 1px solid {t['border']};
    }}

    .block-container {{
        padding-top: 1.4rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }}

    /* ---------- Typography helpers ---------- */
    .arx-title {{
        font-size: 1.9rem;
        font-weight: 800;
        color: {t['text']};
        letter-spacing: -0.02em;
        margin-bottom: 0.15rem;
    }}
    .arx-subtitle {{
        font-size: 0.95rem;
        color: {t['text_secondary']};
        font-weight: 400;
        margin-bottom: 0;
    }}
    .arx-section-title {{
        font-size: 1.15rem;
        font-weight: 700;
        color: {t['text']};
        margin: 0 0 0.9rem 0;
        letter-spacing: -0.01em;
    }}
    .arx-caption {{
        font-size: 0.78rem;
        color: {t['text_muted']};
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }}

    /* ---------- Generic card ---------- */
    .arx-card {{
        background: {t['surface']};
        border: 1px solid {t['border']};
        border-radius: 18px;
        padding: 1.4rem 1.5rem;
        box-shadow: {t['shadow']};
        transition: box-shadow 0.25s ease, transform 0.25s ease;
        margin-bottom: 1.1rem;
    }}
    .arx-card:hover {{
        box-shadow: {t['shadow_hover']};
    }}

    /* ---------- KPI metric card ---------- */
    .arx-metric {{
        background: {t['surface']};
        border: 1px solid {t['border']};
        border-radius: 18px;
        padding: 1.25rem 1.4rem;
        box-shadow: {t['shadow']};
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        height: 100%;
    }}
    .arx-metric:hover {{
        transform: translateY(-3px);
        box-shadow: {t['shadow_hover']};
    }}
    .arx-metric-icon {{
        width: 42px; height: 42px;
        border-radius: 12px;
        display: flex; align-items: center; justify-content: center;
        font-size: 1.2rem;
        background: {t['primary_soft']};
        margin-bottom: 0.7rem;
    }}
    .arx-metric-value {{
        font-size: 1.75rem;
        font-weight: 800;
        color: {t['text']};
        letter-spacing: -0.02em;
        line-height: 1.1;
    }}
    .arx-metric-label {{
        font-size: 0.82rem;
        color: {t['text_secondary']};
        margin-top: 0.25rem;
        font-weight: 500;
    }}
    .arx-metric-delta {{
        display: inline-block;
        margin-top: 0.55rem;
        font-size: 0.76rem;
        font-weight: 700;
        padding: 0.15rem 0.55rem;
        border-radius: 999px;
    }}
    .arx-delta-up {{ background: {t['success_soft']}; color: {t['success']}; }}
    .arx-delta-down {{ background: {t['danger_soft']}; color: {t['danger']}; }}

    /* ---------- Badges / pills ---------- */
    .arx-pill {{
        display: inline-block;
        padding: 0.22rem 0.7rem;
        border-radius: 999px;
        font-size: 0.76rem;
        font-weight: 700;
        margin: 0.12rem 0.25rem 0.12rem 0;
    }}
    .arx-pill-success {{ background: {t['success_soft']}; color: {t['success']}; }}
    .arx-pill-warning {{ background: {t['warning_soft']}; color: {t['warning']}; }}
    .arx-pill-danger  {{ background: {t['danger_soft']}; color: {t['danger']}; }}
    .arx-pill-primary {{ background: {t['primary_soft']}; color: {t['primary']}; }}

    .arx-skill-badge {{
        display: inline-block;
        background: {t['surface_alt']};
        border: 1px solid {t['border']};
        color: {t['text_secondary']};
        padding: 0.22rem 0.65rem;
        border-radius: 8px;
        font-size: 0.74rem;
        font-weight: 600;
        margin: 0.12rem 0.25rem 0.12rem 0;
    }}

    /* ---------- Progress bars ---------- */
    .arx-progress-track {{
        width: 100%;
        height: 8px;
        border-radius: 999px;
        background: {t['surface_alt']};
        overflow: hidden;
        margin-top: 0.35rem;
    }}
    .arx-progress-fill {{
        height: 100%;
        border-radius: 999px;
        background: {t['primary_gradient']};
    }}

    /* ---------- Upload area ---------- */
    .arx-upload {{
        border: 1.5px dashed {t['border']};
        border-radius: 16px;
        background: {t['surface_alt']};
        padding: 2rem 1rem;
        text-align: center;
        transition: border-color 0.2s ease, background 0.2s ease;
    }}
    .arx-upload:hover {{
        border-color: {t['primary']};
    }}

    section[data-testid="stFileUploaderDropzone"] {{
        background: {t['surface_alt']} !important;
        border: 1.5px dashed {t['border']} !important;
        border-radius: 16px !important;
    }}

    /* ---------- Buttons ---------- */
    .stButton > button, .stDownloadButton > button {{
        border-radius: 12px !important;
        font-weight: 700 !important;
        border: 1px solid {t['border']} !important;
        padding: 0.55rem 1.1rem !important;
        transition: all 0.18s ease !important;
        background: {t['surface']} !important;
        color: {t['text']} !important;
    }}
    .stButton > button:hover, .stDownloadButton > button:hover {{
        border-color: {t['primary']} !important;
        color: {t['primary']} !important;
        transform: translateY(-1px);
    }}
    div[data-testid="stFormSubmitButton"] > button,
    .arx-primary-btn button {{
        background: {t['primary_gradient']} !important;
        color: white !important;
        border: none !important;
        box-shadow: {t['shadow']};
    }}
    .arx-primary-btn button:hover {{
        filter: brightness(1.05);
        color: white !important;
    }}

    /* ---------- Inputs ---------- */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {{
        border-radius: 12px !important;
        border: 1px solid {t['border']} !important;
        background: {t['surface']} !important;
        color: {t['text']} !important;
    }}
    .stTextArea textarea {{
        font-family: 'Inter', sans-serif !important;
    }}

    /* ---------- Tables ---------- */
    .arx-table {{
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        font-size: 0.85rem;
    }}
    .arx-table th {{
        text-align: left;
        color: {t['text_muted']};
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 0.7rem 0.9rem;
        border-bottom: 1px solid {t['border']};
    }}
    .arx-table td {{
        padding: 0.85rem 0.9rem;
        border-bottom: 1px solid {t['border']};
        color: {t['text']};
        vertical-align: middle;
    }}
    .arx-table tr:hover td {{
        background: {t['surface_alt']};
    }}

    /* ---------- Sidebar nav ---------- */
    .arx-nav-item {{
        display: flex;
        align-items: center;
        gap: 0.6rem;
        padding: 0.6rem 0.8rem;
        border-radius: 10px;
        color: {t['text_secondary']};
        font-weight: 600;
        font-size: 0.9rem;
        margin-bottom: 0.15rem;
        cursor: pointer;
    }}
    .arx-nav-item-active {{
        background: {t['primary_soft']};
        color: {t['primary']};
    }}

    section[data-testid="stSidebar"] .stButton > button {{
        text-align: left !important;
        justify-content: flex-start !important;
        background: transparent !important;
        border: none !important;
        font-weight: 600 !important;
        color: {t['text_secondary']} !important;
        padding: 0.55rem 0.8rem !important;
        box-shadow: none !important;
    }}
    section[data-testid="stSidebar"] .stButton > button:hover {{
        background: {t['surface_alt']} !important;
        color: {t['primary']} !important;
        transform: none;
    }}

    /* ---------- Misc ---------- */
    hr {{ border-color: {t['border']}; }}
    .arx-divider {{
        height: 1px;
        background: {t['border']};
        margin: 0.9rem 0;
        border: none;
    }}
    ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
    ::-webkit-scrollbar-thumb {{ background: {t['border']}; border-radius: 8px; }}

    .arx-avatar {{
        width: 40px; height: 40px;
        border-radius: 50%;
        background: {t['primary_gradient']};
        display: flex; align-items: center; justify-content: center;
        color: white; font-weight: 700; font-size: 0.95rem;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
