from __future__ import annotations

import streamlit as st
import uuid

from i18n import tr
from storage import authenticate_account, create_account, find_account, ACTIVE_SESSIONS


def render_login_page(all_data: dict) -> None:
    language = st.session_state.language
    
    lang_cols = st.columns([3.8, 2.2])
    with lang_cols[1]:
        lc = st.columns(5)
        if lc[0].button("🇬🇧", key="login_lang_en", use_container_width=True, type="primary" if language == "en" else "secondary"):
            st.session_state.language = "en"
            st.rerun()
        if lc[1].button("🇫🇷", key="login_lang_fr", use_container_width=True, type="primary" if language == "fr" else "secondary"):
            st.session_state.language = "fr"
            st.rerun()
        if lc[2].button("🇩🇪", key="login_lang_de", use_container_width=True, type="primary" if language == "de" else "secondary"):
            st.session_state.language = "de"
            st.rerun()
        if lc[3].button("🇮🇹", key="login_lang_it", use_container_width=True, type="primary" if language == "it" else "secondary"):
            st.session_state.language = "it"
            st.rerun()
        if lc[4].button("🇪🇸", key="login_lang_es", use_container_width=True, type="primary" if language == "es" else "secondary"):
            st.session_state.language = "es"
            st.rerun()
            
    language = st.session_state.language
    
    st.html(
        f"""
        <div class="login-hero">
            <span style="font-size: 3.8rem; filter: drop-shadow(0 8px 16px rgba(31, 111, 235, 0.15));">✈️</span>
            <h1 class="login-hero-title">{tr(language, "app_title")}</h1>
            <p class="login-hero-subtitle">{tr(language, "welcome_logbook")}</p>
        </div>
        """
    )
    
    left_space, center_col, right_space = st.columns([1, 2.2, 1])
    with center_col:
        mode_options = {
            "login": tr(language, "login"),
            "register": tr(language, "create_account"),
            "demo": tr(language, "use_demo_account")
        }
        selected_mode = st.segmented_control(
            "Account Mode",
            options=list(mode_options),
            format_func=lambda key: mode_options[key],
            default="login",
            key="login_page_mode",
            label_visibility="collapsed"
        )
        
        pref_username = ""
        requested_account = st.query_params.get("account")
        if isinstance(requested_account, list):
            requested_account = requested_account[0] if requested_account else None
        if requested_account:
            pref_username = requested_account
            
        st.markdown("<div style='height: 1.2rem;'></div>", unsafe_allow_html=True)
        
        if selected_mode == "login":
            with st.form("login_form_page"):
                login_user = st.text_input(tr(language, "account_email_local_id"), value=pref_username, placeholder="e.g. pilot123")
                login_pass = st.text_input(tr(language, "password"), type="password")
                if st.form_submit_button(tr(language, "login"), type="primary", width="stretch"):
                    logged_in = authenticate_account(all_data, login_user, login_pass)
                    if logged_in:
                        token = uuid.uuid4().hex
                        uid = logged_in["user_id"]
                        ACTIVE_SESSIONS[uid] = token
                        st.session_state.current_user_id = uid
                        st.session_state.session_token = token
                        st.query_params["account"] = uid
                        st.query_params["session_token"] = token
                        st.success(tr(language, "success_logged_in"))
                        st.rerun()
                    else:
                        st.error(tr(language, "login_error"))
                        
        elif selected_mode == "register":
            with st.form("register_form_page"):
                reg_email = st.text_input(tr(language, "email"), placeholder="arthur@example.com")
                reg_username = st.text_input(tr(language, "username"), placeholder="arthur")
                reg_password = st.text_input(tr(language, "password"), type="password")
                if st.form_submit_button(tr(language, "create_account"), type="primary", width="stretch"):
                    ok, msg, user_id = create_account(all_data, reg_email, reg_username, reg_password)
                    if ok and user_id:
                        token = uuid.uuid4().hex
                        ACTIVE_SESSIONS[user_id] = token
                        st.session_state.current_user_id = user_id
                        st.session_state.session_token = token
                        st.query_params["account"] = user_id
                        st.query_params["session_token"] = token
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                        
        elif selected_mode == "demo":
            st.html(
                f"""
                <div class="demo-intro-box">
                    <p class="demo-intro-text">{tr(language, "demo_intro")}</p>
                </div>
                """
            )
            if st.button(tr(language, "launch_demo"), type="primary", width="stretch"):
                logged_in = authenticate_account(all_data, "demo", "demo")
                if logged_in:
                    token = uuid.uuid4().hex
                    uid = logged_in["user_id"]
                    ACTIVE_SESSIONS[uid] = token
                    st.session_state.current_user_id = uid
                    st.session_state.session_token = token
                    st.query_params["account"] = uid
                    st.query_params["session_token"] = token
                    st.rerun()
