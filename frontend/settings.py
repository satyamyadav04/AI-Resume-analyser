"""
settings.py
Settings page — real user profile, persisted preferences via settings_repo.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from components import card_open, card_close
from theme import toggle_theme
from backend.repositories.settings_repo import get_settings, save_settings
from backend.services.auth_service import update_profile


def render(t: dict):
    user = st.session_state.get("user", {})
    user_id = user.get("id")

    # Load persisted settings
    prefs = get_settings(user_id)
    notif = prefs.get("notifications", {})

    st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)
    left, right = st.columns(2)

    with left:
        # Theme
        card_open()
        st.markdown('<div class="arx-section-title">🎨 Appearance</div>', unsafe_allow_html=True)
        current = "Light" if t["name"] == "light" else "Dark"
        choice = st.radio("Theme", ["Light", "Dark"], index=0 if current == "Light" else 1, horizontal=True)
        if choice.lower() != t["name"]:
            toggle_theme()
            save_settings(user_id, {**prefs, "theme": choice.lower()})
            st.rerun()
        card_close()

        # Language
        card_open()
        st.markdown('<div class="arx-section-title">🌐 Language</div>', unsafe_allow_html=True)
        lang_options = ["English (US)", "English (UK)", "Hindi", "Spanish", "French"]
        lang_idx = lang_options.index(prefs.get("language", "English (US)")) if prefs.get("language") in lang_options else 0
        language = st.selectbox("Language", lang_options, index=lang_idx, label_visibility="collapsed")
        card_close()

        # Notifications
        card_open()
        st.markdown('<div class="arx-section-title">🔔 Notifications</div>', unsafe_allow_html=True)
        email_notif = st.toggle("Email notifications for new analyses", value=notif.get("email", True))
        weekly_notif = st.toggle("Weekly summary digest", value=notif.get("weekly", True))
        reminder_notif = st.toggle("Shortlist reminders", value=notif.get("reminders", False))
        card_close()

    with right:
        # AI Model
        card_open()
        st.markdown('<div class="arx-section-title">🤖 AI Model</div>', unsafe_allow_html=True)
        model_opts = ["Resume-Analyzer v3 (Recommended)", "Resume-Analyzer v2", "Fast Mode (Lite)"]
        model_idx = model_opts.index(prefs.get("ai_model", model_opts[0])) if prefs.get("ai_model") in model_opts else 0
        ai_model = st.selectbox("AI Model", model_opts, index=model_idx, label_visibility="collapsed")
        st.markdown(
            f'<div style="font-size:0.78rem;color:{t["text_muted"]};margin-top:0.4rem;">'
            'Sets the analysis engine for scoring, ranking, and AI summaries.</div>',
            unsafe_allow_html=True,
        )
        card_close()

        # Analysis Mode
        card_open()
        st.markdown('<div class="arx-section-title">🎯 Analysis Mode</div>', unsafe_allow_html=True)
        mode_opts = ["Balanced", "Strict Matching", "Lenient / Broad Matching"]
        mode_idx = mode_opts.index(prefs.get("analysis_mode", "Balanced")) if prefs.get("analysis_mode") in mode_opts else 0
        analysis_mode = st.radio("Analysis Mode", mode_opts, index=mode_idx)
        card_close()

        # Account
        card_open()
        st.markdown('<div class="arx-section-title">👤 Account</div>', unsafe_allow_html=True)
        new_name = st.text_input("Full Name", value=user.get("name", ""))
        new_email = st.text_input("Email", value=user.get("email", ""))
        with st.expander("Change Password"):
            new_pw = st.text_input("New Password", type="password", placeholder="Leave empty to keep current")
            confirm_pw = st.text_input("Confirm Password", type="password", placeholder="")

        st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
        st.markdown('<div class="arx-primary-btn">', unsafe_allow_html=True)
        save_clicked = st.button("💾 Save Changes", use_container_width=True, key="settings_save")
        st.markdown("</div>", unsafe_allow_html=True)

        if save_clicked:
            # Save preferences
            save_settings(user_id, {
                "theme": t["name"],
                "language": language,
                "notifications": {"email": email_notif, "weekly": weekly_notif, "reminders": reminder_notif},
                "analysis_mode": analysis_mode,
                "ai_model": ai_model,
                "default_jd_id": prefs.get("default_jd_id"),
            })

            # Save profile
            try:
                pw_to_set = new_pw if new_pw else None
                if new_pw and new_pw != confirm_pw:
                    st.error("Passwords do not match.")
                else:
                    updated_user = update_profile(user_id, new_name, new_email, pw_to_set)
                    st.session_state.user = updated_user
                    st.success("✅ Settings saved successfully!")
                    st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        card_close()

    # Company info section
    card_open()
    st.markdown('<div class="arx-section-title">🏢 Workspace</div>', unsafe_allow_html=True)
    company_name = user.get("company_name", "—")
    company_id = st.session_state.get("company_id", "—")
    st.markdown(
        f"""
        <div style="display:flex;gap:2rem;flex-wrap:wrap;">
            <div>
                <div class="arx-caption">Company</div>
                <div style="font-weight:700;color:{t['text']};margin-top:0.2rem;">{company_name}</div>
            </div>
            <div>
                <div class="arx-caption">Role</div>
                <div style="font-weight:700;color:{t['text']};margin-top:0.2rem;">
                    {user.get('role','hr_manager').replace('_',' ').title()}
                </div>
            </div>
            <div>
                <div class="arx-caption">Member Since</div>
                <div style="font-weight:700;color:{t['text']};margin-top:0.2rem;">Today</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    card_close()
