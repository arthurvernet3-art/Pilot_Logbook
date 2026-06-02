from __future__ import annotations

import base64
import hashlib
import html
import json
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
import pydeck as pdk
import streamlit as st

from airports import AIRPORTS
from i18n import LANGUAGES, PAGE_KEYS, tr
from rules import (
    airport_rows,
    build_sector_flights,
    deadline_status,
    format_duration,
    minutes_between,
    pax_currency,
    rounded_utc_now,
    route_event_landing_count,
    route_rows,
)
from storage import (
    delete_aircraft_image,
    get_user_data,
    load_data,
    save_aircraft_image,
    save_data,
    authenticate_account,
    create_account,
    find_account,
    normalize_user_id,
)

from ui_components import (
    NEW_AIRCRAFT,
    aircraft_form,
    aircraft_label,
    aircraft_selectbox,
    duration_input,
    normalize_utc_time,
    route_chain_inputs,
    show_aircraft_image,
    uppercase_text_input,
)



def get_current_user_id() -> str | None:
    """Return the active local account id for this session, if set."""
    return st.session_state.get("current_user_id")


def current_account_label(all_data: dict, user_id: str) -> str:
    account = all_data.get("accounts", {}).get(user_id, {})
    username = account.get("username") or user_id
    email = account.get("email") or user_id
    return f"{username} · {email}" if username != email else username


def set_active_account(user_id: str) -> None:
    st.session_state.current_user_id = user_id
    st.query_params["account"] = user_id


def logout() -> None:
    st.session_state.current_user_id = None
    if "account" in st.query_params:
        del st.query_params["account"]


def initialize_session(all_data: dict) -> None:
    st.session_state.setdefault("language", "en")
    
    requested_account = st.query_params.get("account")
    if isinstance(requested_account, list):
        requested_account = requested_account[0] if requested_account else None
    
    current_session_user = st.session_state.get("current_user_id")
    
    if requested_account:
        normalized_req = requested_account.strip().lower()
        if current_session_user != normalized_req:
            account = find_account(all_data, normalized_req)
            if account:
                if not account.get("password_hash"):
                    st.session_state.current_user_id = account["user_id"]
                    st.query_params["account"] = account["user_id"]
                else:
                    st.session_state.current_user_id = None
            else:
                st.session_state.current_user_id = None
    else:
        if "current_user_id" not in st.session_state:
            st.session_state.current_user_id = None
            
    current_user = st.session_state.get("current_user_id")
    if current_user:
        st.query_params["account"] = current_user


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
                        st.session_state.current_user_id = logged_in["user_id"]
                        st.query_params["account"] = logged_in["user_id"]
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
                        st.session_state.current_user_id = user_id
                        st.query_params["account"] = user_id
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
                    st.session_state.current_user_id = logged_in["user_id"]
                    st.query_params["account"] = logged_in["user_id"]
                    st.rerun()


def page_setup() -> None:
    language = st.session_state.get("language", "en")
    st.set_page_config(page_title=tr(language, "app_title"), page_icon="✈️", layout="wide", initial_sidebar_state="collapsed")
    st.markdown(
        """
        <style>
        /* ============================================================
           APPLE HIG DESIGN TOKENS — light mode defaults
        ============================================================ */
        :root {
            /* System backgrounds */
            --sys-bg-primary:    #f2f2f7;
            --sys-bg-secondary:  #ffffff;
            --sys-bg-tertiary:   #e5e5ea;
            --sys-bg-grouped:    #f2f2f7;

            /* Cards / surfaces */
            --card-bg:           #ffffff;
            --card-bg-alt:       #f2f2f7;
            --card-gradient:     none;
            --card-border:       rgba(0, 0, 0, 0.06);
            --card-shadow:       0 8px 24px rgba(0, 0, 0, 0.04);

            /* Text */
            --text-primary:      #000000;
            --text-secondary:    #3c3c4399; /* 60% opacity */
            --text-tertiary:     #3c3c434d; /* 30% opacity */
            --text-label:        #3c3c4399;

            /* Borders / separators */
            --border-color:      rgba(0, 0, 0, 0.08);
            --border-light:      rgba(0, 0, 0, 0.04);
            --border-input:      rgba(0, 0, 0, 0.12);
            --border-radio:      rgba(0, 0, 0, 0.15);

            /* Accent — Apple blue */
            --accent:            #007aff;
            --accent-dark:       #0056b3;
            --accent-bg:         rgba(0, 122, 255, 0.1);
            --accent-hover-bg:   rgba(0, 122, 255, 0.05);
            --accent-border:     rgba(0, 122, 255, 0.2);

            /* Secondary accent — indigo */
            --indigo:            #5856d6;

            /* Popover button */
            --popover-btn-bg:    #ffffff;
            --popover-btn-border:rgba(0, 0, 0, 0.12);

            /* Form */
            --form-bg:           #ffffff;
            --form-border:       rgba(0, 0, 0, 0.08);

            /* Radio unselected chip */
            --radio-chip-bg:     #f2f2f7;

            /* Status — Apple system green/amber/red */
            --status-ok:         #34c759;
            --status-ok-bg:      rgba(52, 199, 89, 0.12);
            --status-warn:       #ff9500;
            --status-warn-bg:    rgba(255, 149, 0, 0.12);
            --status-bad:        #ff3b30;
            --status-bad-bg:     rgba(255, 59, 48, 0.12);

            /* Home status row */
            --status-row-bg:     #f2f2f7;
            --status-row-border: rgba(0, 0, 0, 0.04);

            /* Profile card */
            --profile-bg:        #ffffff;
            --profile-border:    rgba(0, 0, 0, 0.08);

            /* Demo intro box */
            --demo-box-bg:       #f2f2f7;
            --demo-box-border:   rgba(0, 0, 0, 0.05);

            /* Aircraft placeholder */
            --aircraft-ph-bg:    rgba(0, 122, 255, 0.06);
            --aircraft-ph-border:rgba(0, 122, 255, 0.12);
            --aircraft-ph-color: #007aff;

            /* Metric widget */
            --metric-border:     rgba(0, 0, 0, 0.06);
        }

        /* ============================================================
           DARK MODE — Apple HIG dark palette
        ============================================================ */
        @media (prefers-color-scheme: dark) {
            :root {
                --sys-bg-primary:    #000000;
                --sys-bg-secondary:  #1c1c1e;
                --sys-bg-tertiary:   #2c2c2e;
                --sys-bg-grouped:    #000000;

                --card-bg:           #1c1c1e;
                --card-bg-alt:       #2c2c2e;
                --card-gradient:     none;
                --card-border:       rgba(255, 255, 255, 0.08);
                --card-shadow:       0 8px 30px rgba(0, 0, 0, 0.5);

                --text-primary:      #ffffff;
                --text-secondary:    #ebebf599; /* 60% opacity */
                --text-tertiary:     #ebebf54d; /* 30% opacity */
                --text-label:        #ebebf599;

                --border-color:      rgba(255, 255, 255, 0.1);
                --border-light:      rgba(255, 255, 255, 0.05);
                --border-input:      rgba(255, 255, 255, 0.15);
                --border-radio:      rgba(255, 255, 255, 0.2);

                --accent:            #0a84ff;
                --accent-dark:       #0066cc;
                --accent-bg:         rgba(10, 132, 255, 0.15);
                --accent-hover-bg:   rgba(10, 132, 255, 0.08);
                --accent-border:     rgba(10, 132, 255, 0.25);

                --indigo:            #5e5ce6;

                --popover-btn-bg:    #1c1c1e;
                --popover-btn-border:rgba(255, 255, 255, 0.15);

                --form-bg:           #1c1c1e;
                --form-border:       rgba(255, 255, 255, 0.08);

                --radio-chip-bg:     #2c2c2e;

                --status-ok:         #30d158;
                --status-ok-bg:      rgba(48, 209, 88, 0.15);
                --status-warn:       #ffd60a;
                --status-warn-bg:    rgba(255, 214, 10, 0.15);
                --status-bad:        #ff453a;
                --status-bad-bg:     rgba(255, 69, 58, 0.15);

                --status-row-bg:     #2c2c2e;
                --status-row-border: rgba(255, 255, 255, 0.05);

                --profile-bg:        #1c1c1e;
                --profile-border:    rgba(255, 255, 255, 0.08);

                --demo-box-bg:       #2c2c2e;
                --demo-box-border:   rgba(255, 255, 255, 0.08);

                --aircraft-ph-bg:    rgba(10, 132, 255, 0.1);
                --aircraft-ph-border:rgba(10, 132, 255, 0.2);
                --aircraft-ph-color: #0a84ff;

                --metric-border:     rgba(255, 255, 255, 0.08);
            }
        }

        /* ============================================================
           GLOBAL RESET & TYPOGRAPHY
        ============================================================ */
        html, body, [data-testid="stAppViewContainer"], .stApp, select, input, button, textarea, p, h1, h2, h3, h4, h5, h6, label {
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", "Segoe UI", Arial, sans-serif !important;
        }

        /* Explicitly preserve Streamlit's Material Icon fonts */
        [data-testid="stIcon"], .notranslate, [class*="MaterialSymbols"] {
            font-family: "Material Symbols Outlined", "Material Symbols Rounded", "Material Icons" !important;
        }

        [data-testid="stAppViewContainer"], .stApp {
            background-color: var(--sys-bg-primary) !important;
        }

        [data-testid="stHeader"] {
            background-color: transparent !important;
        }

        .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 5rem !important;
            max-width: 1080px !important;
        }

        /* Streamlit global column margin alignment */
        div[data-testid="column"] {
            gap: 1rem !important;
        }

        /* Override st.markdown and default texts */
        h1, h2, h3, h4, h5, h6, p, span, label {
            color: var(--text-primary);
        }

        h1 {
            font-size: 2.2rem !important;
            font-weight: 700 !important;
            letter-spacing: -0.03em !important;
        }

        h2 {
            font-size: 1.6rem !important;
            font-weight: 700 !important;
            letter-spacing: -0.02em !important;
            margin-top: 1.5rem !important;
            margin-bottom: 0.8rem !important;
        }

        h3 {
            font-size: 1.25rem !important;
            font-weight: 600 !important;
            letter-spacing: -0.01em !important;
            margin-top: 1.2rem !important;
            margin-bottom: 0.6rem !important;
        }

        /* ============================================================
           NATIVE STREAMLIT COMPONENT OVERRIDES
        ============================================================ */
        /* Standard buttons */
        .stButton > button {
            border-radius: 12px !important;
            font-weight: 600 !important;
            font-size: 0.92rem !important;
            min-height: 2.6rem !important;
            padding: 0.5rem 1.2rem !important;
            transition: all 0.15s ease !important;
            border: 1px solid var(--border-input) !important;
            background-color: var(--card-bg) !important;
            color: var(--text-primary) !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
        }
        .stButton > button:hover {
            border-color: var(--accent) !important;
            background-color: var(--accent-hover-bg) !important;
            color: var(--accent) !important;
        }
        .stButton > button:active {
            transform: scale(0.98);
        }

        /* Primary button override */
        .stButton > button[data-testid="baseButton-primary"] {
            background-color: var(--accent) !important;
            border-color: var(--accent) !important;
            color: #ffffff !important;
            box-shadow: 0 4px 12px rgba(10, 122, 255, 0.2) !important;
        }
        .stButton > button[data-testid="baseButton-primary"]:hover {
            background-color: var(--accent-dark) !important;
            border-color: var(--accent-dark) !important;
            color: #ffffff !important;
        }

        /* Forms */
        div[data-testid="stForm"] {
            border: 1px solid var(--card-border) !important;
            border-radius: 20px !important;
            padding: 2rem !important;
            background-color: var(--card-bg) !important;
            box-shadow: var(--card-shadow) !important;
        }

        /* Input Controls */
        div[data-baseweb="input"] {
            border: 1px solid var(--border-input) !important;
            border-radius: 12px !important;
            background-color: var(--sys-bg-secondary) !important;
            transition: all 0.2s ease !important;
        }
        div[data-baseweb="input"]:focus-within {
            border-color: var(--accent) !important;
            box-shadow: 0 0 0 3px var(--accent-bg) !important;
        }
        div[data-baseweb="input"] input {
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0.5rem 0.8rem !important;
            color: var(--text-primary) !important;
            font-size: 0.95rem !important;
        }

        /* Select boxes */
        div[data-baseweb="select"] {
            border-radius: 12px !important;
            border: 1px solid var(--border-input) !important;
            background-color: var(--sys-bg-secondary) !important;
            transition: all 0.2s ease !important;
        }
        div[data-baseweb="select"]:focus-within {
            border-color: var(--accent) !important;
        }
        div[data-baseweb="select"] > div {
            background-color: transparent !important;
            border: none !important;
        }

        /* Segmented control track */
        div[data-testid="stSegmentedControl"] {
            background-color: var(--sys-bg-tertiary) !important;
            border-radius: 12px !important;
            padding: 2px !important;
            gap: 2px !important;
            display: inline-flex !important;
            border: none !important;
            margin: 1rem auto 1.5rem auto !important;
        }
        /* Segmented control individual options */
        div[data-testid="stSegmentedControl"] button {
            border-radius: 10px !important;
            border: none !important;
            background-color: transparent !important;
            color: var(--text-secondary) !important;
            font-weight: 550 !important;
            font-size: 0.9rem !important;
            padding: 0.4rem 1.1rem !important;
            min-height: 2.2rem !important;
            box-shadow: none !important;
            transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
        }
        div[data-testid="stSegmentedControl"] button:hover {
            color: var(--text-primary) !important;
            background-color: rgba(255, 255, 255, 0.05) !important;
        }
        /* Active selected segment */
        div[data-testid="stSegmentedControl"] button[data-testid="baseButton-primary"] {
            background-color: var(--card-bg) !important;
            color: var(--text-primary) !important;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;
            font-weight: 600 !important;
        }

        /* Metrics */
        div[data-testid="stMetric"] {
            background-color: var(--card-bg) !important;
            border: 1px solid var(--card-border) !important;
            border-radius: 16px !important;
            padding: 1rem !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.02) !important;
        }
        div[data-testid="stMetric"] label {
            font-size: 0.82rem !important;
            font-weight: 600 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.05em !important;
            color: var(--text-secondary) !important;
        }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
            font-size: 1.8rem !important;
            font-weight: 700 !important;
            letter-spacing: -0.02em !important;
            color: var(--text-primary) !important;
        }

        /* ============================================================
           STATUS LABELS (inline text)
        ============================================================ */
        .status-ok  {color: var(--status-ok);  font-weight: 600;}
        .status-warn{color: var(--status-warn); font-weight: 600;}
        .status-bad {color: var(--status-bad);  font-weight: 600;}

        /* Status badges used in cards */
        .badge-ok   {background: var(--status-ok-bg);   color: var(--status-ok);  border-radius:999px; padding:.25rem .65rem; font-weight:600; font-size:.78rem; white-space:nowrap;}
        .badge-warn {background: var(--status-warn-bg); color: var(--status-warn); border-radius:999px; padding:.25rem .65rem; font-weight:600; font-size:.78rem; white-space:nowrap;}
        .badge-bad  {background: var(--status-bad-bg);  color: var(--status-bad); border-radius:999px; padding:.25rem .65rem; font-weight:600; font-size:.78rem; white-space:nowrap;}
        .badge-ok-text  {color: var(--status-ok);  font-size:1.15rem; font-weight:700;}
        .badge-bad-text {color: var(--status-bad); font-size:1.15rem; font-weight:700;}

        /* ============================================================
           PAGE LABEL
        ============================================================ */
        .page-label {
            color: var(--text-label);
            font-size: .95rem;
            margin: -.5rem 0 1.25rem 0;
            font-weight: 500;
        }

        /* ============================================================
           POPOVER / MENU BUTTON
        ============================================================ */
        div[data-testid="stPopover"] {
            margin-top: 0.5rem !important;
            position: relative !important;
        }
        @media (max-width: 760px) {
            div[data-testid="stPopover"] {
                margin-top: 1rem !important;
            }
        }
        @media (max-width: 768px) {
            div[data-testid="stPopoverBody"] {
                position: absolute !important;
                top: calc(100% + 6px) !important;
                right: 0 !important;
                left: auto !important;
                bottom: auto !important;
                width: 280px !important;
                max-width: calc(100vw - 2rem) !important;
                height: auto !important;
                min-height: auto !important;
                max-height: 80vh !important;
                box-shadow: 0 12px 36px rgba(0,0,0,0.15) !important;
                border-radius: 16px !important;
                border: 1px solid var(--card-border) !important;
                background-color: var(--card-bg) !important;
                transform: none !important;
                z-index: 999999 !important;
                overflow-y: auto !important;
                padding: 1rem !important;
            }
        }
        div[data-testid="stPopover"] > button {
            border-radius: 999px !important;
            border: 1px solid var(--border-input) !important;
            background-color: var(--card-bg) !important;
            color: var(--text-primary) !important;
            font-weight: 600 !important;
            min-height: 2.6rem !important;
            padding: 0.4rem 1rem !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.03) !important;
            transition: all 0.2s ease !important;
        }
        div[data-testid="stPopover"] > button:hover {
            border-color: var(--accent) !important;
            background-color: var(--accent-hover-bg) !important;
            color: var(--accent) !important;
            box-shadow: 0 6px 16px rgba(0, 122, 255, 0.1) !important;
        }

        /* ============================================================
           MENU NAVIGATION LIST (Grouped List Style)
        ============================================================ */
        div[data-testid="stPopover"] div[data-testid="stVerticalBlock"] {
            padding: 0.25rem 0 !important;
            gap: 2px !important;
        }
        
        div[data-testid="stPopover"] .stCaption {
            font-size: 0.78rem !important;
            font-weight: 600 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.05em !important;
            color: var(--text-secondary) !important;
            margin-top: 0.8rem !important;
            margin-bottom: 0.3rem !important;
            padding-left: 0.8rem !important;
        }

        /* Navigation buttons inside popover list */
        div[data-testid="stPopover"] div[data-testid="stVerticalBlock"] div[data-testid="stButton"] button {
            width: 100% !important;
            border: none !important;
            border-radius: 8px !important;
            background: transparent !important;
            color: var(--text-primary) !important;
            padding: 0.6rem 0.8rem !important;
            min-height: 2.4rem !important;
            font-weight: 500 !important;
            box-shadow: none !important;
            text-align: left !important;
            justify-content: flex-start !important;
            transition: background-color 0.15s ease, color 0.15s ease !important;
        }
        div[data-testid="stPopover"] div[data-testid="stVerticalBlock"] div[data-testid="stButton"] button:hover {
            background-color: var(--sys-bg-tertiary) !important;
            color: var(--accent) !important;
        }
        /* Active button in the popover list */
        div[data-testid="stPopover"] div[data-testid="stVerticalBlock"] div[data-testid="stButton"] button[data-testid="baseButton-primary"] {
            background-color: var(--accent-bg) !important;
            color: var(--accent) !important;
            font-weight: 600 !important;
        }
        /* Logout button style in popover */
        div[data-testid="stPopover"] div[data-testid="stVerticalBlock"] > div[data-testid="stButton"]:last-child button {
            border-top: 1px solid var(--border-light) !important;
            border-radius: 0 !important;
            margin-top: 0.5rem !important;
            padding-top: 0.8rem !important;
            color: var(--status-bad) !important;
        }
        div[data-testid="stPopover"] div[data-testid="stVerticalBlock"] > div[data-testid="stButton"]:last-child button:hover {
            background-color: var(--status-bad-bg) !important;
            color: var(--status-bad) !important;
        }

        /* Language flags selector */
        div[data-testid="stPopover"] div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button {
            font-size: 1.2rem !important;
            min-height: 2.2rem !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            border-radius: 8px !important;
            border: 1px solid var(--border-light) !important;
            background-color: var(--sys-bg-primary) !important;
        }
        div[data-testid="stPopover"] div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button[data-testid="baseButton-primary"] {
            border-color: var(--accent) !important;
            background-color: var(--accent-bg) !important;
        }

        /* ============================================================
           RADIO GROUPS
        ============================================================ */
        div[role="radiogroup"] {
            gap: 0.5rem !important;
            padding: 4px 0 !important;
        }
        div[role="radiogroup"] label {
            border: 1px solid var(--border-input) !important;
            border-radius: 10px !important;
            padding: 0.45rem 0.85rem !important;
            margin: 0 !important;
            background: var(--card-bg) !important;
            color: var(--text-secondary) !important;
            font-weight: 550 !important;
            font-size: 0.9rem !important;
            transition: all 0.15s ease !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
        }
        div[role="radiogroup"] label:hover {
            border-color: var(--accent) !important;
            color: var(--text-primary) !important;
        }
        div[role="radiogroup"] label:has(input:checked) {
            border-color: var(--accent) !important;
            background-color: var(--accent-bg) !important;
            color: var(--accent) !important;
            font-weight: 600 !important;
            box-shadow: 0 0 0 1px var(--accent) !important;
        }

        /* ============================================================
           PYDECK ROUTE MAP INSERT (Apple Grouped Card Style)
        ============================================================ */
        div[data-testid="stPydeckChart"] {
            border-radius: 20px !important;
            overflow: hidden !important;
            border: 1px solid var(--card-border) !important;
            box-shadow: var(--card-shadow) !important;
            margin: 1.2rem 0 !important;
        }

        /* ============================================================
           FLIGHT LIST / ROWS (iOS Grouped Style)
        ============================================================ */
        .flight-list {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 20px;
            overflow: hidden;
            margin-top: 1.2rem;
            box-shadow: 0 4px 16px rgba(0,0,0,0.02);
        }
        .flight-row {
            display: grid;
            grid-template-columns: 80px minmax(120px, 1fr) 80px minmax(120px, 1fr) 80px;
            gap: 1rem;
            align-items: center;
            padding: 1.2rem 1.4rem;
            border-bottom: 1px solid var(--border-light);
            transition: background-color 0.15s ease;
        }
        .flight-row:hover {
            background-color: var(--sys-bg-tertiary);
        }
        .flight-row:last-child {border-bottom: 0;}
        
        .flight-date {
            text-align: center;
            line-height: 1.1;
            background: var(--sys-bg-primary);
            border-radius: 12px;
            padding: 0.5rem;
            border: 1px solid var(--border-light);
        }
        .flight-day {
            font-size: 1.6rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            color: var(--text-primary);
        }
        .flight-month {
            color: var(--text-secondary);
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }
        .flight-airport {
            font-size: 1.4rem;
            font-weight: 700;
            color: var(--text-primary);
            letter-spacing: -0.01em;
        }
        .flight-time {
            color: var(--text-secondary);
            font-size: 0.9rem;
            font-weight: 500;
        }
        .flight-duration {
            text-align: center;
            font-size: 1.2rem;
            font-weight: 600;
            color: var(--text-primary);
            background: var(--accent-bg);
            color: var(--accent);
            padding: 0.35rem 0.65rem;
            border-radius: 10px;
            display: inline-block;
            margin: 0 auto;
        }
        .flight-chip-row {
            display: flex;
            gap: 0.35rem;
            margin-top: 0.4rem;
            flex-wrap: wrap;
        }
        .flight-chip {
            display: inline-flex;
            align-items: center;
            border-radius: 6px;
            padding: 0.15rem 0.4rem;
            font-size: 0.72rem;
            font-weight: 600;
            border: 1px solid var(--border-light);
            color: var(--text-secondary);
            background: var(--sys-bg-primary);
        }
        .flight-chip-primary {
            background: var(--accent-bg);
            border-color: var(--accent-border);
            color: var(--accent);
        }
        .flight-landings {
            text-align: right;
        }
        .landing-pill {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: var(--sys-bg-primary);
            border: 1px solid var(--border-light);
            border-radius: 8px;
            width: 32px;
            height: 32px;
            color: var(--text-primary);
            font-weight: 600;
            font-size: 0.95rem;
        }

        /* ============================================================
           HOME STAT CARDS
        ============================================================ */
        .home-stats {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 1.2rem;
            margin: 1rem 0 1.5rem;
        }
        .home-stat {
            border: 1px solid var(--card-border) !important;
            border-radius: 18px !important;
            padding: 1.2rem !important;
            background: var(--card-bg) !important;
            box-shadow: 0 4px 16px rgba(0,0,0,0.02) !important;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .home-stat:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.06) !important;
        }
        .home-stat-icon {
            font-size: 1.5rem;
            line-height: 1;
            margin-bottom: 0.5rem;
        }
        .home-stat-value {
            font-size: 2.2rem;
            font-weight: 700;
            letter-spacing: -0.03em;
            font-feature-settings: "tnum" 1;
            margin-top: 0.25rem;
            color: var(--text-primary);
        }
        .home-stat-label {
            color: var(--text-secondary);
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        /* ============================================================
           HOME STATUS PANELS (iOS Settings Grouped Style)
        ============================================================ */
        .home-status-panel {
            border-radius: 20px;
            padding: 1.4rem;
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            margin: 1.2rem 0;
            box-shadow: 0 4px 16px rgba(0,0,0,0.02);
        }
        .home-status-heading {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 1rem;
            margin-bottom: 1rem;
        }
        .home-status-title {
            font-size: 1.35rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            color: var(--text-primary);
        }
        .home-status-subtitle {
            color: var(--text-secondary);
            font-size: 0.9rem;
            font-weight: 500;
            margin-top: 0.15rem;
        }
        .home-status-current {
            font-size: 1.1rem;
            font-weight: 700;
        }
        .home-status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 0.8rem;
        }
        .home-status-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 0.75rem;
            border: 1px solid var(--border-light);
            border-radius: 14px;
            padding: 1rem;
            background: var(--sys-bg-primary);
            min-height: 4.8rem;
        }
        .home-status-label {
            font-weight: 600;
            font-size: 0.95rem;
            color: var(--text-primary);
        }
        .home-status-detail {
            color: var(--text-secondary);
            font-size: 0.82rem;
            font-weight: 500;
            margin-top: 0.12rem;
        }

        /* ============================================================
           INFO / DEADLINE CARDS
        ============================================================ */
        .card-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 1rem;
            margin: 1rem 0;
        }
        .info-card {
            border: 1px solid var(--card-border);
            border-radius: 18px;
            padding: 1.2rem;
            background: var(--card-bg);
            box-shadow: 0 4px 16px rgba(0,0,0,0.02);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .info-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.06);
        }
        .info-title {
            font-size: 1.15rem;
            font-weight: 700;
            color: var(--text-primary);
        }
        .info-sub {
            color: var(--text-secondary);
            font-size: 0.85rem;
            margin-top: 0.25rem;
            font-weight: 500;
        }
        .info-pill {
            display: inline-flex;
            border-radius: 8px;
            padding: 0.2rem 0.55rem;
            margin-top: 0.6rem;
            background: var(--accent-bg);
            color: var(--accent);
            font-weight: 600;
            font-size: 0.78rem;
        }

        /* ============================================================
           AIRCRAFT CARDS
        ============================================================ */
        .aircraft-card {
            display: grid;
            grid-template-columns: 100px 1fr;
            gap: 1.1rem;
            align-items: center;
        }
        .aircraft-photo {
            width: 100px;
            height: 75px;
            border-radius: 14px;
            object-fit: cover;
            background: var(--sys-bg-primary);
            border: 1px solid var(--border-light);
        }
        .aircraft-photo-placeholder {
            width: 100px;
            height: 75px;
            border-radius: 14px;
            background: var(--aircraft-ph-bg);
            border: 1px solid var(--aircraft-ph-border);
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--aircraft-ph-color);
            font-weight: 700;
            font-size: 1.8rem;
        }

        /* ============================================================
           LOGIN HERO
        ============================================================ */
        .login-hero {
            text-align: center;
            margin-top: 1.5rem;
            margin-bottom: 2rem;
        }
        .login-hero-title {
            margin-top: 0.6rem;
            margin-bottom: 0.2rem;
            font-size: 2.5rem !important;
            font-weight: 800 !important;
            letter-spacing: -0.04em !important;
            background: linear-gradient(135deg, var(--accent) 0%, var(--indigo) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .login-hero-subtitle {
            color: var(--text-secondary);
            font-size: 1.15rem;
            font-weight: 500;
            letter-spacing: -0.01em;
        }

        /* ============================================================
           DEMO INTRO BOX
        ============================================================ */
        .demo-intro-box {
            background: var(--demo-box-bg);
            border: 1px solid var(--demo-box-border);
            border-radius: 16px;
            padding: 1.5rem;
            margin-bottom: 1.2rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.01);
        }
        .demo-intro-text {
            margin: 0;
            color: var(--text-secondary);
            font-weight: 500;
            line-height: 1.5;
        }

        /* ============================================================
           ACCOUNT PROFILE CARD
        ============================================================ */
        .profile-card {
            background: var(--profile-bg);
            border: 1px solid var(--profile-border);
            border-radius: 20px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 10px 25px rgba(0,0,0,0.02);
        }
        .profile-card-inner {
            display: flex;
            align-items: center;
            gap: 1.2rem;
            margin-bottom: 1.5rem;
        }
        .profile-avatar {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--accent) 0%, var(--indigo) 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 1.8rem;
            font-weight: 700;
            box-shadow: 0 8px 16px rgba(10, 132, 255, 0.15);
        }
        .profile-username {
            margin: 0;
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text-primary);
        }
        .profile-email {
            margin: 0.1rem 0 0 0;
            color: var(--text-secondary);
            font-weight: 500;
            font-size: 0.95rem;
        }

        /* ============================================================
           RESPONSIVE
        ============================================================ */
        @media (max-width: 760px) {
            .block-container {padding-left: .8rem !important; padding-right: .8rem !important;}
            div[data-testid="column"] {width: 100% !important; flex: 1 1 100% !important;}
            .flight-row {
                grid-template-columns: 56px 1fr;
                gap: .55rem;
            }
            .flight-duration, .flight-landings {text-align: left;}
            .home-stats {grid-template-columns: repeat(2, minmax(0, 1fr));}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_navigation() -> str:
    st.session_state.setdefault("language", "en")
    st.session_state.setdefault("current_page", "home")
    

    requested_page = st.query_params.get("page")
    if isinstance(requested_page, list):
        requested_page = requested_page[0] if requested_page else None
    if requested_page in PAGE_KEYS:
        st.session_state.current_page = requested_page
    old_page_names = {
        "Home": "home",
        "Logbook": "logbook",
        "In flight": "logbook",
        "Statistics": "statistics",
        "Currency": "currency",
        "Map": "map",
        "Deadlines": "deadlines",
        "Data": "data",
    }
    if st.session_state.current_page in old_page_names:
        st.session_state.current_page = old_page_names[st.session_state.current_page]
    if st.session_state.current_page in {"statistics", "map"}:
        st.session_state.current_page = "home"
    if st.session_state.current_page == "deadlines":
        st.session_state.current_page = "currency"
    if st.session_state.current_page == "in_flight":
        st.session_state.current_page = "logbook"
    if st.session_state.current_page not in PAGE_KEYS:
        st.session_state.current_page = "home"
    language = st.session_state.language

    title_col, button_col = st.columns([4.2, 1.8])
    title_col.title(tr(language, "app_title"))
    with button_col.popover(tr(language, "menu"), key=f"menu_popover_{st.session_state.current_page}", use_container_width=True):
        st.caption(tr(language, "language"))
        lang_row1 = st.columns(3)
        if lang_row1[0].button("🇬🇧", key="lang_en", use_container_width=True, type="primary" if language == "en" else "secondary"):
            st.session_state.language = "en"
            st.rerun()
        if lang_row1[1].button("🇫🇷", key="lang_fr", use_container_width=True, type="primary" if language == "fr" else "secondary"):
            st.session_state.language = "fr"
            st.rerun()
        if lang_row1[2].button("🇩🇪", key="lang_de", use_container_width=True, type="primary" if language == "de" else "secondary"):
            st.session_state.language = "de"
            st.rerun()
        lang_row2 = st.columns(3)
        if lang_row2[0].button("🇮🇹", key="lang_it", use_container_width=True, type="primary" if language == "it" else "secondary"):
            st.session_state.language = "it"
            st.rerun()
        if lang_row2[1].button("🇪🇸", key="lang_es", use_container_width=True, type="primary" if language == "es" else "secondary"):
            st.session_state.language = "es"
            st.rerun()
        language = st.session_state.language
        st.caption(tr(language, "select_page"))

        for page_key in PAGE_KEYS:
            page_label = tr(language, page_key)
            is_current_page = page_key == st.session_state.current_page
            label_prefix = "✓ " if is_current_page else ""
            if st.button(
                label_prefix + page_label,
                key=f"nav_{page_key}",
                use_container_width=True,
                type="primary" if is_current_page else "secondary"
            ):
                st.session_state.current_page = page_key
                st.query_params["page"] = page_key
                st.rerun()
        st.write("")
        if st.button(tr(language, "logout"), key="menu_logout", use_container_width=True):
            logout()
            st.rerun()

    return st.session_state.current_page


def save_new_aircraft_if_needed(data: dict, registration: str, profile: dict, image) -> None:
    if registration in data["aircraft_profiles"]:
        return
    profile["image_path"] = save_aircraft_image(registration, image)
    data["aircraft_profiles"][registration] = profile


def parsed_route_datetimes(flight_date: date, route_times: list[str]) -> list[datetime] | None:
    if not route_times or any(not time for time in route_times):
        return None
    values = []
    current_date = flight_date
    previous = None
    for route_time in route_times:
        normalized = normalize_utc_time(route_time)
        try:
            hours, minutes = [int(part) for part in normalized.split(":", 1)]
            current = datetime.combine(current_date, datetime.min.time()).replace(hour=hours, minute=minutes)
        except ValueError:
            return None
        if previous and current <= previous:
            current += timedelta(days=1)
            current_date = current.date()
        values.append(current)
        previous = current
    return values


def route_times_to_boundaries(flight_date: date, route_times: list[str]) -> list[str] | None:
    values = parsed_route_datetimes(flight_date, route_times)
    if not values:
        return None
    return [f"{value:%Y-%m-%d %H:%M} UTC" for value in values]


def route_time_minutes(flight_date: date, route_times: list[str]) -> int | None:
    values = parsed_route_datetimes(flight_date, route_times)
    if not values or len(values) < 2:
        return None
    return max(0, int((values[-1] - values[0]).total_seconds() // 60))


def compact_duration(minutes: int) -> str:
    hours, remainder = divmod(int(minutes), 60)
    return f"{hours}:{remainder:02d}"


def recent_experience_status(flights: list[dict]) -> dict:
    today = date.today()
    start = today - timedelta(days=365)
    relevant = []
    for flight in flights:
        try:
            flight_date = datetime.strptime(flight.get("date", ""), "%Y-%m-%d").date()
        except ValueError:
            continue
        if start <= flight_date <= today:
            relevant.append(flight)

    total_minutes = sum(int(flight.get("pic_minutes", 0)) + int(flight.get("dual_minutes", 0)) for flight in relevant)
    takeoffs = len(relevant)
    landings = sum(int(flight.get("landings", 0)) for flight in relevant)
    required_minutes = 12 * 60
    required_takeoffs = 12
    required_landings = 12
    return {
        "total_minutes": total_minutes,
        "required_minutes": required_minutes,
        "takeoffs": takeoffs,
        "required_takeoffs": required_takeoffs,
        "landings": landings,
        "required_landings": required_landings,
        "ok": total_minutes >= required_minutes and takeoffs >= required_takeoffs and landings >= required_landings,
    }


def display_time(value: str | None) -> str:
    if not value:
        return "--:--"
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M UTC").strftime("%H:%M")
    except ValueError:
        return value.replace(" UTC", "")


def flight_day_month(value: str) -> tuple[str, str]:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
        return parsed.strftime("%d"), parsed.strftime("%b").upper()
    except ValueError:
        return "--", ""


def flight_role(flight: dict) -> str:
    if int(flight.get("pic_minutes", 0)) > 0:
        return "PIC"
    if int(flight.get("dual_minutes", 0)) > 0:
        return "DC"
    return "TIME"


def render_single_flight_map(flight: dict) -> None:
    routes = route_rows([flight])
    points = airport_rows([flight])

    if routes and not points.empty:
        segments = []
        for r in routes:
            path = r["path"]
            for i in range(len(path) - 1):
                segments.append({
                    "from": r["from"],
                    "to": r["to"],
                    "date": r["date"],
                    "source": path[i],
                    "target": path[i+1]
                })

        line_layer = pdk.Layer(
            "GreatCircleLayer",
            segments,
            get_source_position="source",
            get_target_position="target",
            get_color=[0, 122, 255, 160],
            get_width=2.5,
            width_min_pixels=2.5,
            pickable=True
        )

        point_layer = pdk.Layer(
            "ScatterplotLayer",
            points,
            get_position="[lon, lat]",
            filled=True,
            stroked=True,
            get_fill_color=[255, 255, 255],
            get_line_color=[0, 122, 255],
            get_line_width=2,
            line_width_min_pixels=1.5,
            get_radius=5.5,
            radius_units="'pixels'",
            pickable=True
        )

        label_layer = pdk.Layer(
            "TextLayer",
            points,
            get_position="[lon, lat]",
            get_text="code",
            get_size=12,
            get_color=[0, 122, 255],
            font_family="'SF Pro Text', '-apple-system', sans-serif",
            font_weight=700,
            get_pixel_offset=[0, -10],
            get_alignment_baseline="'bottom'",
            outline_width=2.5,
            outline_color=[255, 255, 255],
            pickable=False
        )

        min_lat = float(points["lat"].min())
        max_lat = float(points["lat"].max())
        min_lon = float(points["lon"].min())
        max_lon = float(points["lon"].max())

        center_lat = (min_lat + max_lat) / 2.0
        center_lon = (min_lon + max_lon) / 2.0

        lat_span = max_lat - min_lat
        lon_span = max_lon - min_lon
        max_span = max(lat_span, lon_span)

        if max_span < 0.001:
            zoom = 11.0
        else:
            import math
            zoom = float(max(1.0, min(14.0, 8.5 - math.log2(max_span))))

        deck = pdk.Deck(
            layers=[line_layer, point_layer, label_layer],
            initial_view_state=pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=zoom, pitch=0),
            tooltip={"text": "{from} → {to}\n{date}"},
        )
        st.pydeck_chart(deck, width="stretch")
    else:
        language = st.session_state.language
        st.info(tr(language, "add_known_airports_map"))


def render_flight_detail_card(flight: dict, profiles: dict) -> None:
    language = st.session_state.language
    
    st.markdown(
        """
        <style>
        .detail-card-container {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 20px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 4px 16px rgba(0,0,0,0.02);
        }
        .detail-route {
            font-size: 1.8rem;
            font-weight: 700;
            color: var(--text-primary);
            letter-spacing: -0.03em;
        }
        .detail-date {
            font-size: 1rem;
            color: var(--text-secondary);
            font-weight: 500;
        }
        .detail-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            margin-bottom: 1rem;
        }
        .detail-item {
            background: var(--sys-bg-primary);
            padding: 0.8rem 1rem;
            border-radius: 12px;
            border: 1px solid var(--border-light);
        }
        .detail-label {
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.25rem;
        }
        .detail-value {
            font-size: 1.1rem;
            font-weight: 700;
            color: var(--text-primary);
        }
        .detail-remarks {
            background: var(--sys-bg-primary);
            padding: 1rem;
            border-radius: 12px;
            border: 1px solid var(--border-light);
            margin-top: 1rem;
            font-style: italic;
            color: var(--text-primary);
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    reg = flight.get("aircraft_registration", "Unknown")
    profile = profiles.get(reg, {}) if profiles else {}
    ac_type = profile.get("type", "Unknown")
    
    pic_min = int(flight.get("pic_minutes", 0))
    dual_min = int(flight.get("dual_minutes", 0))
    night_min = int(flight.get("night_minutes", 0))
    total_min = pic_min + dual_min
    
    f_date = flight.get("date", "")
    
    st.markdown('<div class="detail-card-container">', unsafe_allow_html=True)
    
    col_title, col_close = st.columns([5, 1.2])
    with col_title:
        st.markdown(
            f"""
            <div class="detail-route">
                {html.escape(flight.get('departure', ''))} ➔ {html.escape(flight.get('arrival', ''))}
            </div>
            <div class="detail-date">{html.escape(f_date)}</div>
            """,
            unsafe_allow_html=True
        )
    with col_close:
        if st.button("✕ " + tr(language, "close"), key="close_detail_card", use_container_width=True):
            st.session_state.selected_flight_index = None
            st.rerun()
            
    st.markdown('<div style="margin-top: 1rem;"></div>', unsafe_allow_html=True)
    
    col_details, col_map = st.columns([3, 3])
    
    with col_details:
        st.markdown(
            f"""
            <div class="detail-grid">
                <div class="detail-item">
                    <div class="detail-label">{html.escape(tr(language, "aircraft"))}</div>
                    <div class="detail-value">{html.escape(reg)}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">{html.escape(tr(language, "aircraft_profile"))}</div>
                    <div class="detail-value">{html.escape(ac_type)}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">{html.escape(tr(language, "total_time"))}</div>
                    <div class="detail-value">{html.escape(format_duration(total_min))}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">{html.escape(tr(language, "time_role"))}</div>
                    <div class="detail-value">{"PIC" if pic_min > 0 else "Dual (DC)"}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">{html.escape(tr(language, "landings"))}</div>
                    <div class="detail-value">{int(flight.get("landings", 0))}</div>
                </div>
                {"".join(f'''<div class="detail-item">
                    <div class="detail-label">{html.escape(tr(language, "night_time"))}</div>
                    <div class="detail-value">{html.escape(format_duration(night_min))}</div>
                </div>''' if night_min > 0 else "")}
            </div>
            """,
            unsafe_allow_html=True
        )
        
        dep_utc = flight.get("departure_utc", "")
        arr_utc = flight.get("arrival_utc", "")
        if dep_utc or arr_utc:
            st.markdown(
                f"""
                <div style="font-size: 0.9rem; color: var(--text-secondary); margin-top: 0.5rem; font-weight: 500;">
                    ⏱ {html.escape(tr(language, "utc_time"))}: {html.escape(dep_utc or "--:--")} UTC ➔ {html.escape(arr_utc or "--:--")} UTC
                </div>
                """,
                unsafe_allow_html=True
            )
            
        remarks = flight.get("remarks", "").strip()
        if remarks:
            st.markdown(
                f"""
                <div class="detail-remarks">
                    <strong>{html.escape(tr(language, "remarks"))}:</strong> "{html.escape(remarks)}"
                </div>
                """,
                unsafe_allow_html=True
            )
            
    with col_map:
        render_single_flight_map(flight)
        
    st.markdown('</div>', unsafe_allow_html=True)


def render_flight_cards(flights: list[dict], profiles: dict = None) -> None:
    if not flights:
        language = st.session_state.language
        st.info(tr(language, "no_flights"))
        return

    # Check if a flight is selected
    selected_idx = st.session_state.get("selected_flight_index")
    if selected_idx is not None and 0 <= selected_idx < len(flights):
        render_flight_detail_card(flights[selected_idx], profiles)

    indexed_flights = sorted(enumerate(flights), key=lambda x: x[1].get("date", ""), reverse=True)
    
    for index, flight in indexed_flights:
        day, month = flight_day_month(flight.get("date", ""))
        total_minutes = int(flight.get("pic_minutes", 0)) + int(flight.get("dual_minutes", 0))
        departure = html.escape(flight.get("departure", ""))
        arrival = html.escape(flight.get("arrival", ""))
        role = html.escape(flight_role(flight))
        sector = html.escape(flight.get("sector_index") and f"{flight.get('sector_index')}/{flight.get('sector_count')}" or "")
        xc_chip = '<span class="flight-chip">XC</span>' if departure != arrival else ""
        sector_chip = f'<span class="flight-chip">S{sector}</span>' if sector else ""
        
        # Create individual card HTML wrapping it in a single list card wrapper
        row_html = f"""
        <div class="flight-list" style="margin-top: 0; margin-bottom: 0.5rem; border-radius: 12px;">
            <div class="flight-row" style="border-bottom: 0;">
                <div class="flight-date">
                    <div class="flight-day">{html.escape(day)}</div>
                    <div class="flight-month">{html.escape(month)}</div>
                </div>
                <div>
                    <div class="flight-airport">{departure}</div>
                    <div class="flight-time">{html.escape(display_time(flight.get("departure_utc")))}</div>
                    <div class="flight-chip-row">
                        <span class="flight-chip flight-chip-primary">{role}</span>{xc_chip}{sector_chip}
                    </div>
                </div>
                <div class="flight-duration">- {html.escape(compact_duration(total_minutes))} -</div>
                <div>
                    <div class="flight-airport">{arrival}</div>
                    <div class="flight-time">{html.escape(display_time(flight.get("arrival_utc")))}</div>
                </div>
                <div class="flight-landings">
                    <span class="landing-pill">{int(flight.get("landings", 0))}</span>
                </div>
            </div>
        </div>
        """
        
        col_card, col_btn = st.columns([5.2, 0.8])
        with col_card:
            st.html(row_html)
        with col_btn:
            st.markdown('<div style="margin-top: 1.15rem;"></div>', unsafe_allow_html=True)
            if st.button("🗺️", key=f"view_flight_btn_{index}", use_container_width=True):
                st.session_state.selected_flight_index = index
                st.rerun()


def render_deadline_cards(deadlines: list[dict]) -> None:
    if not deadlines:
        language = st.session_state.language
        st.info(tr(language, "no_deadlines"))
        return
    cards = []
    for deadline in sorted(deadlines, key=lambda item: deadline_status(item)[0]):
        days_left, status = deadline_status(deadline)
        if status == "OK":
            badge_class = "badge-ok"
        elif days_left >= 0:
            badge_class = "badge-warn"
        else:
            badge_class = "badge-bad"
        cards.append(
            f"""
            <div class="info-card">
                <div class="info-title">{html.escape(deadline.get("name", ""))}</div>
                <div class="info-sub">{html.escape(deadline.get("category", ""))} · {html.escape(deadline.get("expires", ""))}</div>
                <span class="{badge_class}" style="display:inline-flex;margin-top:.45rem;">{html.escape(status)} · {days_left} days</span>
                <div class="info-sub">{html.escape(deadline.get("notes", ""))}</div>
            </div>
            """
        )
    st.html('<div class="card-grid">' + "".join(cards) + "</div>")


def image_data_url(image_path: str) -> str:
    if not image_path:
        return ""
    path = Path(image_path)
    if not path.exists() or not path.is_file():
        return ""
    suffix = path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def render_aircraft_cards(profiles: dict) -> None:
    if not profiles:
        language = st.session_state.language
        st.info(tr(language, "no_aircraft"))
        return
    cards = []
    for profile in sorted(profiles.values(), key=lambda item: item.get("registration", "")):
        details = " · ".join(
            value for value in [profile.get("manufacturer", ""), profile.get("type", ""), profile.get("category", "")] if value
        )
        image_url = image_data_url(profile.get("image_path", ""))
        image_html = (
            f'<img class="aircraft-photo" src="{image_url}" alt="{html.escape(profile.get("registration", ""))}">'
            if image_url
            else '<div class="aircraft-photo-placeholder">✈</div>'
        )
        cards.append(
            f"""
            <div class="info-card">
                <div class="aircraft-card">
                    {image_html}
                    <div>
                        <div class="info-title">{html.escape(profile.get("registration", ""))}</div>
                        <div class="info-sub">{html.escape(details or tr(st.session_state.language, "aircraft_profile"))}</div>
                        <span class="info-pill">{html.escape(profile.get("type", tr(st.session_state.language, "unknown")))}</span>
                        <div class="info-sub">{html.escape(profile.get("notes", ""))}</div>
                    </div>
                </div>
            </div>
            """
        )
    st.html('<div class="card-grid">' + "".join(cards) + "</div>")


def render_home_stat_cards(language: str, flights: list[dict], total_minutes: int, landings: int) -> None:
    airports = len({flight.get("departure") for flight in flights} | {flight.get("arrival") for flight in flights}) if flights else 0
    html_block = f"""
    <div class="home-stats">
        <div class="home-stat">
            <div class="home-stat-icon">🛬</div>
            <div class="home-stat-value">{landings}</div>
            <div class="home-stat-label">{html.escape(tr(language, "landings"))}</div>
        </div>
        <div class="home-stat">
            <div class="home-stat-icon">⏱️</div>
            <div class="home-stat-value">{html.escape(compact_duration(total_minutes))}</div>
            <div class="home-stat-label">{html.escape(tr(language, "total_time"))}</div>
        </div>
        <div class="home-stat">
            <div class="home-stat-icon">📍</div>
            <div class="home-stat-value">{airports}</div>
            <div class="home-stat-label">{html.escape(tr(language, "airports"))}</div>
        </div>
        <div class="home-stat">
            <div class="home-stat-icon">📖</div>
            <div class="home-stat-value">{len(flights)}</div>
            <div class="home-stat-label">{html.escape(tr(language, "total_flights"))}</div>
        </div>
    </div>
    """
    st.html(html_block)


def status_row(language: str, label_key: str, value: str, ok: bool) -> str:
    badge_class = "badge-ok" if ok else "badge-bad"
    symbol = "OK" if ok else "!"
    return f"""
        <div class="home-status-row">
            <div>
                <div class="home-status-label">{html.escape(tr(language, label_key))}</div>
                <div class="home-status-detail">{html.escape(value)}</div>
            </div>
            <span class="home-status-badge {badge_class}">{symbol}</span>
        </div>
    """


def render_home_status(language: str, flights: list[dict], currency_rules: list[dict]) -> None:
    experience = recent_experience_status(flights)
    status_label = tr(language, "current") if experience["ok"] else tr(language, "not_current")
    current_class = "badge-ok-text" if experience["ok"] else "badge-bad-text"
    experience_rows = [
        status_row(
            language,
            "recent_time",
            f"{format_duration(experience['total_minutes'])} / {format_duration(experience['required_minutes'])}",
            experience["total_minutes"] >= experience["required_minutes"],
        ),
        status_row(
            language,
            "takeoffs",
            f"{experience['takeoffs']} / {experience['required_takeoffs']}",
            experience["takeoffs"] >= experience["required_takeoffs"],
        ),
        status_row(
            language,
            "landings",
            f"{experience['landings']} / {experience['required_landings']}",
            experience["landings"] >= experience["required_landings"],
        ),
    ]
    st.html(
        f"""
        <div class="home-status-panel">
            <div class="home-status-heading">
                <div>
                    <div class="home-status-title">{html.escape(tr(language, "status"))}</div>
                    <div class="home-status-subtitle">{html.escape(tr(language, "last_12_months"))}</div>
                </div>
                <div class="home-status-current {current_class}">{html.escape(status_label)}</div>
            </div>
            <div class="home-status-grid">{chr(10).join(experience_rows)}</div>
        </div>
        """
    )

    statuses = [pax_currency(flights, rule) for rule in currency_rules]
    if not statuses:
        return
    passenger_cards = []
    for status in statuses:
        ok = bool(status["ok"])
        badge_class = "badge-ok" if ok else "badge-bad"
        label = tr(language, "can_carry_pax") if ok else tr(language, "not_current")
        missing = ""
        if not ok:
            missing = f'<div class="home-status-detail">{html.escape(tr(language, "missing_landings", count=status["missing"]))}</div>'
        passenger_cards.append(
            f"""
            <div class="home-status-row">
                <div>
                    <div class="home-status-label">{html.escape(status["rule"])}</div>
                    <div class="home-status-detail">{html.escape(str(status["airport"]))} · {html.escape(tr(language, "last_days", days=status["lookback_days"]))}</div>
                    <div class="home-status-detail">{status["landings"]} / {status["required_landings"]} {html.escape(tr(language, "landings").lower())}</div>
                    {missing}
                </div>
                <span class="home-status-badge {badge_class}">{html.escape(label)}</span>
            </div>
            """
        )
    st.html(
        f"""
        <div class="home-status-panel home-status-panel-passenger">
            <div class="home-status-heading">
                <div>
                    <div class="home-status-title">{html.escape(tr(language, "passenger_carry_status"))}</div>
                    <div class="home-status-subtitle">{html.escape(tr(language, "passenger_carry_subtitle"))}</div>
                </div>
            </div>
            <div class="home-status-grid">{"".join(passenger_cards)}</div>
        </div>
        """
    )


def render_route_map(data: dict, title: str | None = None) -> None:
    if title:
        st.subheader(title)
    routes = route_rows(data["flights"])
    points = airport_rows(data["flights"])

    if routes and not points.empty:
        segments = []
        for r in routes:
            path = r["path"]
            for i in range(len(path) - 1):
                segments.append({
                    "from": r["from"],
                    "to": r["to"],
                    "date": r["date"],
                    "source": path[i],
                    "target": path[i+1]
                })

        line_layer = pdk.Layer(
            "GreatCircleLayer",
            segments,
            get_source_position="source",
            get_target_position="target",
            get_color=[0, 122, 255, 160],
            get_width=2.5,
            width_min_pixels=2.5,
            pickable=True
        )

        point_layer = pdk.Layer(
            "ScatterplotLayer",
            points,
            get_position="[lon, lat]",
            filled=True,
            stroked=True,
            get_fill_color=[255, 255, 255],
            get_line_color=[0, 122, 255],
            get_line_width=2,
            line_width_min_pixels=1.5,
            get_radius=5.5,
            radius_units="'pixels'",
            pickable=True
        )

        label_layer = pdk.Layer(
            "TextLayer",
            points,
            get_position="[lon, lat]",
            get_text="code",
            get_size=12,
            get_color=[0, 122, 255],
            font_family="'SF Pro Text', '-apple-system', sans-serif",
            font_weight=700,
            get_pixel_offset=[0, -10],
            get_alignment_baseline="'bottom'",
            outline_width=2.5,
            outline_color=[255, 255, 255],
            pickable=False
        )

        min_lat = float(points["lat"].min())
        max_lat = float(points["lat"].max())
        min_lon = float(points["lon"].min())
        max_lon = float(points["lon"].max())

        center_lat = (min_lat + max_lat) / 2.0
        center_lon = (min_lon + max_lon) / 2.0

        lat_span = max_lat - min_lat
        lon_span = max_lon - min_lon
        max_span = max(lat_span, lon_span)

        if max_span < 0.001:
            zoom = 11.0
        else:
            import math
            zoom = float(max(1.0, min(14.0, 8.5 - math.log2(max_span))))

        deck = pdk.Deck(
            layers=[line_layer, point_layer, label_layer],
            initial_view_state=pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=zoom, pitch=0),
            tooltip={"text": "{from} → {to}\n{date}"},
        )
        st.pydeck_chart(deck, width="stretch")
    else:
        language = st.session_state.language
        st.info(tr(language, "add_known_airports_map"))


def render_home(data: dict) -> None:
    language = st.session_state.language
    flights = data["flights"]
    flight_df = pd.DataFrame(flights)
    total_minutes = int(flight_df[["pic_minutes", "dual_minutes"]].sum().sum()) if not flight_df.empty else 0
    pic_minutes = int(flight_df["pic_minutes"].sum()) if not flight_df.empty else 0
    dual_minutes = int(flight_df["dual_minutes"].sum()) if not flight_df.empty else 0
    night_minutes = int(flight_df["night_minutes"].sum()) if not flight_df.empty else 0
    landings = int(flight_df["landings"].sum()) if not flight_df.empty else 0

    render_home_stat_cards(language, flights, total_minutes, landings)
    render_home_status(language, flights, data["currency_rules"])
    detail_a, detail_b, detail_c = st.columns(3)
    detail_a.metric(tr(language, "pic_time_stat"), format_duration(pic_minutes))
    detail_b.metric(tr(language, "dual_time_stat"), format_duration(dual_minutes))
    detail_c.metric(tr(language, "night_time_stat"), format_duration(night_minutes))
    render_route_map(data, tr(language, "route_map"))
    st.subheader(tr(language, "recent"))
    render_flight_cards(flights, data.get("aircraft_profiles", {}))


def render_logbook(data: dict) -> None:
    language = st.session_state.language
    mode_options = {
        "manual": tr(language, "manual_entry"),
        "in_flight": tr(language, "in_flight"),
    }
    selected_mode = st.segmented_control(
        tr(language, "logbook_mode"),
        options=list(mode_options),
        format_func=lambda key: mode_options[key],
        default="manual",
        key="logbook_mode",
    )
    if selected_mode == "in_flight":
        render_in_flight(data)
        return
    flights = data["flights"]
    profiles = data["aircraft_profiles"]
    route_labels = {
        "route": tr(language, "route"),
        "airport_n": tr(language, "airport_n", number="{number}"),
        "event": tr(language, "event"),
        "count": tr(language, "count"),
        "touch_and_go": tr(language, "touch_and_go"),
        "full_stop": tr(language, "full_stop"),
        "utc_time": tr(language, "utc_time"),
        "time_role": tr(language, "time_role"),
        "pic": tr(language, "pic"),
        "dc": tr(language, "dc"),
        "add_airport": tr(language, "add_airport"),
        "remove_airport": tr(language, "remove_airport"),
    }

    st.subheader(tr(language, "add_flight"))
    flight_date = st.date_input(tr(language, "date"), value=date.today())

    selected_aircraft = aircraft_selectbox(flights, profiles, "log_aircraft")
    new_registration = ""
    new_profile = {}
    new_image = None
    if selected_aircraft == NEW_AIRCRAFT:
        new_registration, new_profile, new_image = aircraft_form("log_new_aircraft")
        selected_registration = new_registration
    else:
        selected_registration = selected_aircraft
        show_aircraft_image(profiles.get(selected_registration, {}))

    departure, arrival, route_events, route_times = route_chain_inputs(flights, "log_route", route_labels)
    minimum_landings = route_event_landing_count(route_events) + 1
    suggested_minutes = route_time_minutes(flight_date, route_times)
    route_time_signature = "|".join(route_times)

    col_time_1, col_time_2, col_landings = st.columns(3)
    time_role = col_time_1.segmented_control(
        tr(language, "time_role"),
        [tr(language, "pic"), tr(language, "dc")],
        default=tr(language, "pic"),
        key="log_time_role",
    )
    with col_time_2:
        if suggested_minutes is None:
            flight_minutes = duration_input(tr(language, "flight_time"), "log_flight_time", show_label=True)
        else:
            st.caption(tr(language, "flight_time"))
            st.metric(tr(language, "calculated_total"), format_duration(suggested_minutes))
            override_total = st.checkbox(tr(language, "override_total_time"), key="log_override_total_time")
            if override_total:
                flight_minutes = duration_input(
                    tr(language, "flight_time"),
                    "log_flight_time",
                    default_minutes=suggested_minutes,
                    default_signature=f"{flight_date.isoformat()}|{route_time_signature}",
                )
            else:
                flight_minutes = suggested_minutes
    landings = col_landings.number_input(tr(language, "landings"), min_value=minimum_landings, step=1, value=minimum_landings)
    remarks = st.text_area(tr(language, "remarks"), height=80)

    if st.button(tr(language, "save_flight"), width="stretch", type="primary"):
        if selected_aircraft == NEW_AIRCRAFT and (not new_registration or not new_profile.get("type")):
            st.error(tr(language, "add_registration_type_before_save_new"))
        else:
            if selected_aircraft == NEW_AIRCRAFT:
                save_new_aircraft_if_needed(data, new_registration, new_profile, new_image)
            is_pic = time_role == tr(language, "pic")
            base_flight = {
                "date": flight_date.isoformat(),
                "aircraft_registration": selected_registration,
                "departure": departure,
                "arrival": arrival,
                "pic_minutes": flight_minutes if is_pic else 0,
                "dual_minutes": 0 if is_pic else flight_minutes,
                "night_minutes": 0,
                "landings": int(landings),
                "route_events": route_events,
                "remarks": remarks.strip(),
            }
            boundary_times = route_times_to_boundaries(flight_date, route_times)
            if boundary_times:
                base_flight["departure_utc"] = boundary_times[0]
                base_flight["arrival_utc"] = boundary_times[-1]
            else:
                base_flight["departure_utc"] = route_times[0] if route_times else ""
                base_flight["arrival_utc"] = route_times[-1] if route_times else ""
            flights.extend(build_sector_flights(base_flight, route_events, boundary_times))
            save_data(all_data)
            st.success(tr(language, "flight_saved"))
            st.rerun()

    st.subheader(tr(language, "flights"))
    if not flights:
        st.info(tr(language, "no_flights"))
    else:
        render_flight_cards(flights, profiles)
        with st.expander(tr(language, "delete_logbook_entries")):
            delete_options = list(range(len(flights)))
            selected_for_delete = st.multiselect(
                tr(language, "select_entries_delete"),
                delete_options,
                format_func=lambda index: flight_delete_label(index, flights, profiles),
            )
            if st.button(tr(language, "delete_selected_entries"), disabled=not selected_for_delete, width="stretch"):
                data["flights"] = [
                    flight
                    for index, flight in enumerate(flights)
                    if index not in set(selected_for_delete)
                ]
                save_data(all_data)
                st.success(tr(language, "selected_entries_deleted"))
                st.rerun()


def flight_delete_label(index: int, flights: list[dict], profiles: dict) -> str:
    flight = flights[index]
    profile = profiles.get(flight.get("aircraft_registration", ""), {})
    sector = ""
    if flight.get("sector_count"):
        sector = f" sector {flight['sector_index']}/{flight['sector_count']}"
    return (
        f"{flight.get('date', '')} · {flight.get('aircraft_registration', '')} "
        f"{profile.get('type', '')} · {flight.get('departure', '')} → {flight.get('arrival', '')}{sector}"
    )


def render_in_flight(data: dict) -> None:
    language = st.session_state.language
    flights = data["flights"]
    profiles = data["aircraft_profiles"]
    route_labels = {
        "route": tr(language, "route"),
        "airport_n": tr(language, "airport_n", number="{number}"),
        "event": tr(language, "event"),
        "count": tr(language, "count"),
        "touch_and_go": tr(language, "touch_and_go"),
        "full_stop": tr(language, "full_stop"),
        "utc_time": tr(language, "utc_time"),
        "time_role": tr(language, "time_role"),
        "pic": tr(language, "pic"),
        "dc": tr(language, "dc"),
        "add_airport": tr(language, "add_airport"),
        "remove_airport": tr(language, "remove_airport"),
    }
    st.subheader(tr(language, "in_flight_logger"))

    active = st.session_state.get("active_flight")
    if not active:
        st.caption(tr(language, "setup_flight"))
        selected_aircraft = aircraft_selectbox(flights, profiles, "if_aircraft")
        new_registration = ""
        new_profile = {}
        new_image = None
        if selected_aircraft == NEW_AIRCRAFT:
            new_registration, new_profile, new_image = aircraft_form("if_new_aircraft")
            selected_registration = new_registration
        else:
            selected_registration = selected_aircraft
            show_aircraft_image(profiles.get(selected_registration, {}))

        departure, arrival, route_events, route_times = route_chain_inputs(flights, "if_route", route_labels)
        time_role = st.segmented_control(
            tr(language, "time_role"),
            [tr(language, "pic"), tr(language, "dc")],
            default=tr(language, "pic"),
            key="if_time_role",
        )
        minimum_landings = route_event_landing_count(route_events) + 1
        planned_landings = st.number_input(
            tr(language, "planned_landings"),
            min_value=minimum_landings,
            step=1,
            value=minimum_landings,
        )
        remarks = st.text_area(tr(language, "plan_remarks"), height=80)

        if st.button(tr(language, "log_off_blocks"), width="stretch", type="primary"):
            if selected_aircraft == NEW_AIRCRAFT and (not new_registration or not new_profile.get("type")):
                st.error(tr(language, "add_registration_type_before_start"))
            else:
                if selected_aircraft == NEW_AIRCRAFT:
                    save_new_aircraft_if_needed(data, new_registration, new_profile, new_image)
                    save_data(all_data)
                st.session_state.active_flight = {
                    "aircraft_registration": selected_registration,
                    "departure": departure,
                    "arrival": arrival,
                    "route_events": route_events,
                    "route_times": route_times,
                    "time_role": "pic" if time_role == tr(language, "pic") else "dc",
                    "planned_landings": int(planned_landings),
                    "remarks": remarks.strip(),
                    "off_blocks_utc": rounded_utc_now(),
                    "takeoff_utc": "",
                    "landing_times_utc": [],
                    "on_blocks_utc": "",
                }
                st.rerun()
        return
    st.metric(tr(language, "aircraft"), aircraft_label(active["aircraft_registration"], profiles))
    col_a, col_b, col_c = st.columns(3)
    col_a.metric(tr(language, "route"), f"{active['departure']} → {active['arrival']}")
    logged_route_landings = sum(
        int(event.get("landing_count", 1))
        for event in active.get("route_events", [])
        if event.get("count_as_landing") and event.get("logged_utc")
    )
    total_logged_landings = len(active["landing_times_utc"]) + logged_route_landings
    col_b.metric("Landings", f"{total_logged_landings}/{active['planned_landings']}")
    col_c.metric("Off-blocks", active["off_blocks_utc"])

    if not active["takeoff_utc"]:
        if st.button(tr(language, "log_takeoff"), width="stretch", type="primary"):
            active["takeoff_utc"] = rounded_utc_now()
            st.rerun()
    else:
        st.success(f"Takeoff: {active['takeoff_utc']}")
        if active.get("route_events"):
            st.write(tr(language, "planned_route_events"))
            for index, event in enumerate(active["route_events"]):
                label = "T&G" if event["type"] == "touch_and_go" else "Full stop"
                count_label = f" x{int(event.get('landing_count', 1))}"
                current = event.get("logged_utc")
                cols = st.columns([2, 1])
                cols[0].caption(f"{label}{count_label} at {event['airport']}" + (f" · planned {event['planned_utc']}" if event.get("planned_utc") else ""))
                if current:
                    cols[1].success(current)
                elif cols[1].button(f"Log {label} now", key=f"log_route_event_{index}", width="stretch"):
                    event["logged_utc"] = rounded_utc_now()
                    st.rerun()
        col1, col2 = st.columns(2)
        if col1.button(tr(language, "add_landing"), width="stretch"):
            active["landing_times_utc"].append(rounded_utc_now())
            st.rerun()
        if col2.button(tr(language, "save_in_flight"), width="stretch", type="primary"):
            active["on_blocks_utc"] = rounded_utc_now()
            block_minutes = minutes_between(active["off_blocks_utc"], active["on_blocks_utc"])
            route_events = active.get("route_events", [])
            boundary_times = None
            if route_events and all(event.get("logged_utc") for event in route_events):
                boundary_times = [active["off_blocks_utc"]]
                boundary_times.extend(event["logged_utc"] for event in route_events)
                boundary_times.append(active["on_blocks_utc"])
            is_pic = active.get("time_role", "pic") == "pic"
            base_flight = {
                "date": active["off_blocks_utc"][:10],
                "aircraft_registration": active["aircraft_registration"],
                "departure": active["departure"],
                "arrival": active["arrival"],
                "pic_minutes": block_minutes if is_pic else 0,
                "dual_minutes": 0 if is_pic else block_minutes,
                "night_minutes": 0,
                "landings": total_logged_landings,
                "route_events": route_events,
                "remarks": active["remarks"],
                "off_blocks_utc": active["off_blocks_utc"],
                "takeoff_utc": active["takeoff_utc"],
                "landing_times_utc": active["landing_times_utc"],
                "on_blocks_utc": active["on_blocks_utc"],
            }
            flights.extend(build_sector_flights(base_flight, route_events, boundary_times))
            save_data(all_data)
            del st.session_state.active_flight
            st.success("Flight saved from in-flight logger.")
            st.rerun()

    if active["landing_times_utc"]:
        st.write(tr(language, "landing_times"))
        st.html(
            '<div class="card-grid">'
            + "".join(
                f'<div class="info-card"><div class="info-title">{html.escape(value)}</div><div class="info-sub">{html.escape(tr(language, "utc_landing"))}</div></div>'
                for value in active["landing_times_utc"]
            )
            + "</div>"
        )
    if st.button(tr(language, "discard_active"), width="stretch"):
        del st.session_state.active_flight
        st.rerun()


def render_currency(data: dict) -> None:
    st.subheader("Currency & Deadlines")

    st.markdown("### Passenger Currency")
    statuses = [pax_currency(data["flights"], rule) for rule in data["currency_rules"]]
    cols = st.columns(max(1, min(3, len(statuses))))
    for idx, status in enumerate(statuses):
        with cols[idx % len(cols)]:
            label = "Can carry pax" if status["ok"] else "Not current"
            st.metric(status["rule"], label, f"{status['landings']}/{status['required_landings']} landings")
            st.caption(f"{status['airport']} · last {status['lookback_days']} days")

    with st.expander("Add custom currency criterion"):
        with st.form("currency_rule_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            name = col1.text_input("Rule name", placeholder="LFLI pax currency")
            with col2:
                airport = uppercase_text_input("Specific airport, optional", "LFLI", "currency_airport")
            col3, col4 = st.columns(2)
            days = col3.number_input("Lookback days", min_value=1, value=90, step=1)
            landings = col4.number_input("Required landings", min_value=1, value=3, step=1)
            notes = st.text_area("Notes", height=70)
            if st.form_submit_button("Save criterion", width="stretch"):
                data["currency_rules"].append(
                    {
                        "name": name.strip() or f"{airport or 'Custom'} pax currency",
                        "airport": airport,
                        "lookback_days": int(days),
                        "required_landings": int(landings),
                        "notes": notes.strip(),
                    }
                )
                save_data(all_data)
                st.rerun()

    st.divider()
    st.markdown("### Deadlines")
    urgent = [item for item in data["deadlines"] if deadline_status(item)[1] != "OK"]
    st.metric("Needs attention", len(urgent))

    quick_cols = st.columns(3)
    if quick_cols[0].button("Add licence expiry", width="stretch"):
        st.session_state.deadline_template = ("Licence", "Licence / rating", 90)
    if quick_cols[1].button("Add medical expiry", width="stretch"):
        st.session_state.deadline_template = ("Medical", "Medical", 60)
    if quick_cols[2].button("Add rating expiry", width="stretch"):
        st.session_state.deadline_template = ("Rating", "Licence / rating", 90)

    render_deadline_cards(data["deadlines"])

    template = st.session_state.get("deadline_template", ("", "Medical", 60))
    category_options = ["Medical", "Licence / rating", "Currency", "Insurance", "Other"]
    template_category = template[1] if template[1] in category_options else "Medical"

    with st.form("deadline_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        name = col1.text_input("Item", value=template[0], placeholder="Language proficiency")
        category = col2.selectbox(
            "Category",
            category_options,
            index=category_options.index(template_category),
        )
        col3, col4 = st.columns(2)
        expires = col3.date_input("Expiry date", value=date.today())
        remind_days = col4.number_input("Remind me days before", min_value=1, value=int(template[2]), step=1)
        notes = st.text_area("Notes", height=80)

        if st.form_submit_button("Save deadline", width="stretch"):
            data["deadlines"].append(
                {
                    "name": name.strip() or category,
                    "category": category,
                    "expires": expires.isoformat(),
                    "remind_days": int(remind_days),
                    "notes": notes.strip(),
                }
            )
            st.session_state.deadline_template = ("", "Medical", 60)
            save_data(all_data)
            st.rerun()


def render_deadlines(data: dict) -> None:
    st.subheader("Deadlines")
    urgent = [item for item in data["deadlines"] if deadline_status(item)[1] != "OK"]
    st.metric("Needs attention", len(urgent))

    quick_cols = st.columns(3)
    if quick_cols[0].button("Add licence expiry", width="stretch"):
        st.session_state.deadline_template = ("Licence", "Licence / rating", 90)
    if quick_cols[1].button("Add medical expiry", width="stretch"):
        st.session_state.deadline_template = ("Medical", "Medical", 60)
    if quick_cols[2].button("Add rating expiry", width="stretch"):
        st.session_state.deadline_template = ("Rating", "Licence / rating", 90)

    render_deadline_cards(data["deadlines"])

    template = st.session_state.get("deadline_template", ("", "Medical", 60))
    with st.form("deadline_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        name = col1.text_input("Item", value=template[0], placeholder="Language proficiency")
        category = col2.selectbox("Category", ["Medical", "Licence / rating", "Currency", "Insurance", "Other"], index=["Medical", "Licence / rating", "Currency", "Insurance", "Other"].index(template[1]))
        col3, col4 = st.columns(2)
        expires = col3.date_input("Expiry date", value=date.today())
        remind_days = col4.number_input("Remind me days before", min_value=1, value=int(template[2]), step=1)
        notes = st.text_area("Notes", height=80)

        if st.form_submit_button("Save deadline", width="stretch"):
            data["deadlines"].append(
                {
                    "name": name.strip() or category,
                    "category": category,
                    "expires": expires.isoformat(),
                    "remind_days": int(remind_days),
                    "notes": notes.strip(),
                }
            )
            st.session_state.deadline_template = ("", "Medical", 60)
            save_data(all_data)
            st.rerun()


def render_data(data: dict) -> None:
    st.subheader("Data")
    current_user_id = get_current_user_id()
    st.caption(f"Current account: {current_account_label(all_data, current_user_id)}")
    st.info(f"Airport database: {len(AIRPORTS):,} France and Switzerland airport entries from OurAirports.")
    with st.expander("Add aircraft to database"):
        registration, profile, image = aircraft_form("data_new_aircraft")
        if st.button("Save aircraft", width="stretch", type="primary"):
            if not registration or not profile.get("type"):
                st.error("Add registration and aircraft type before saving.")
            elif registration in data["aircraft_profiles"]:
                st.error("That aircraft already exists in the database.")
            else:
                profile["image_path"] = save_aircraft_image(registration, image)
                data["aircraft_profiles"][registration] = profile
                save_data(all_data)
                st.success("Aircraft saved.")
                st.rerun()
    if data["aircraft_profiles"]:
        st.subheader("Aircraft")
        render_aircraft_cards(data["aircraft_profiles"])
        with st.expander("Edit aircraft in database"):
            options = sorted(data["aircraft_profiles"])
            selected_edit_aircraft = st.selectbox(
                "Aircraft to edit",
                options,
                format_func=lambda registration: aircraft_label(registration, data["aircraft_profiles"]),
                key="edit_aircraft_select",
            )
            profile = data["aircraft_profiles"][selected_edit_aircraft]
            edit_key = selected_edit_aircraft.replace("-", "_")
            if profile.get("image_path"):
                show_aircraft_image(profile)
            with st.form("edit_aircraft_form"):
                edit_col_1, edit_col_2 = st.columns(2)
                updated_registration = edit_col_1.text_input(
                    "Registration",
                    value=profile.get("registration", selected_edit_aircraft),
                    key=f"edit_aircraft_registration_{edit_key}",
                ).upper().strip()
                updated_type = edit_col_2.text_input(
                    "Aircraft type",
                    value=profile.get("type", ""),
                    key=f"edit_aircraft_type_{edit_key}",
                ).upper().strip()
                edit_col_3, edit_col_4 = st.columns(2)
                updated_manufacturer = edit_col_3.text_input(
                    "Manufacturer",
                    value=profile.get("manufacturer", ""),
                    key=f"edit_aircraft_manufacturer_{edit_key}",
                ).strip()
                updated_category = edit_col_4.text_input(
                    "Category / class",
                    value=profile.get("category", ""),
                    key=f"edit_aircraft_category_{edit_key}",
                ).upper().strip()
                updated_image = st.file_uploader(
                    "Aircraft picture",
                    type=["jpg", "jpeg", "png"],
                    key=f"edit_aircraft_image_{edit_key}",
                )
                remove_image = st.checkbox(
                    "Remove current picture",
                    disabled=not bool(profile.get("image_path")),
                    key=f"edit_aircraft_remove_image_{edit_key}",
                )
                updated_notes = st.text_area(
                    "Aircraft notes",
                    value=profile.get("notes", ""),
                    height=80,
                    key=f"edit_aircraft_notes_{edit_key}",
                ).strip()
                if st.form_submit_button("Save aircraft changes", width="stretch", type="primary"):
                    if not updated_registration or not updated_type:
                        st.error("Add registration and aircraft type before saving.")
                    elif updated_registration != selected_edit_aircraft and updated_registration in data["aircraft_profiles"]:
                        st.error("That aircraft already exists in the database.")
                    else:
                        image_path = profile.get("image_path", "")
                        if updated_image is not None:
                            image_path = save_aircraft_image(updated_registration, updated_image)
                        elif remove_image:
                            image_path = ""
                        updated_profile = {
                            "registration": updated_registration,
                            "type": updated_type,
                            "manufacturer": updated_manufacturer,
                            "category": updated_category,
                            "notes": updated_notes,
                            "image_path": image_path,
                        }
                        if updated_registration != selected_edit_aircraft:
                            data["aircraft_profiles"].pop(selected_edit_aircraft, None)
                            for flight in data["flights"]:
                                if flight.get("aircraft_registration") == selected_edit_aircraft:
                                    flight["aircraft_registration"] = updated_registration
                        data["aircraft_profiles"][updated_registration] = updated_profile
                        save_data(all_data)
                        st.success("Aircraft updated.")
                        st.rerun()
        with st.expander("Delete aircraft from database"):
            used_aircraft = {flight.get("aircraft_registration") for flight in data["flights"]}
            options = sorted(data["aircraft_profiles"])
            selected_aircraft = st.multiselect(
                "Select aircraft to delete",
                options,
                format_func=lambda registration: aircraft_label(registration, data["aircraft_profiles"]),
            )
            blocked = [registration for registration in selected_aircraft if registration in used_aircraft]
            if blocked:
                st.warning(
                    "These aircraft still have logbook entries and cannot be deleted yet: "
                    + ", ".join(blocked)
                    + ". Delete their flights first."
                )
            deletable = [registration for registration in selected_aircraft if registration not in used_aircraft]
            if st.button("Delete selected aircraft", disabled=not deletable, width="stretch"):
                for registration in deletable:
                    profile = data["aircraft_profiles"].pop(registration, {})
                    delete_aircraft_image(profile)
                save_data(all_data)
                st.success("Selected aircraft deleted.")
                st.rerun()
    st.download_button(
        "Download my logbook backup",
        data=json.dumps(data, indent=2),
        file_name=f"pilot_logbook_backup_{current_user_id.replace('@', '_at_')}.json",
        mime="application/json",
        width="stretch",
    )
    uploaded = st.file_uploader("Restore my account from JSON backup", type=["json"])
    if uploaded is not None:
        restored = json.loads(uploaded.getvalue().decode("utf-8"))
        if "flights" in restored and "deadlines" in restored:
            data.clear()
            data.update(restored)
            save_data(all_data)
            st.success("Your account backup was restored.")
            st.rerun()
        else:
            st.error("That backup does not look like a pilot logbook file.")


def render_account(data: dict, all_data: dict) -> None:
    current_user_id = get_current_user_id()
    account = all_data.get("accounts", {}).get(current_user_id, {})
    username = account.get("username", current_user_id)
    email = account.get("email", current_user_id)
    language = st.session_state.language

    st.subheader(tr(language, "account"))

    st.html(
        f"""
        <div class="profile-card">
            <div class="profile-card-inner">
                <div class="profile-avatar">
                    {username[0].upper() if username else "P"}
                </div>
                <div>
                    <h2 class="profile-username">{html.escape(username)}</h2>
                    <p class="profile-email">{html.escape(email)}</p>
                </div>
            </div>
        </div>
        """
    )

    col1, col2 = st.columns(2)
    with col1:
        st.metric(tr(language, "total_flights"), len(data.get("flights", [])))
    with col2:
        st.metric(tr(language, "aircraft"), len(data.get("aircraft_profiles", {})))

    st.divider()

    if st.button(tr(language, "logout"), key="account_page_logout", type="primary", use_container_width=True):
        logout()
        st.rerun()

    st.divider()
    st.write(tr(language, "account_backup"))
    st.download_button(
        tr(language, "download_account_backup"),
        data=json.dumps(data, indent=2),
        file_name=f"pilot_logbook_backup_{current_user_id.replace('@', '_at_')}.json",
        mime="application/json",
        use_container_width=True,
    )

    uploaded = st.file_uploader(tr(language, "restore_account_backup"), type=["json"], key="account_restore")
    if uploaded is not None:
        try:
            restored = json.loads(uploaded.getvalue().decode("utf-8"))
            if "flights" in restored and "deadlines" in restored:
                data.clear()
                data.update(restored)
                from storage import migrate_data
                migrate_data(data)
                save_data(all_data)
                st.success(tr(language, "account_backup_restored_short"))
                st.rerun()
            else:
                st.error(tr(language, "invalid_backup"))
        except Exception:
            st.error(tr(language, "invalid_backup"))

    st.divider()
    st.write(tr(language, "switch_account"))
    
    account_rows = []
    for saved_account in sorted(all_data.get("accounts", {}).values(), key=lambda item: item.get("username", "")):
        saved_user_id = saved_account.get("user_id", "")
        if saved_user_id == current_user_id:
            continue
        account_rows.append(
            {
                "Username": saved_account.get("username", saved_user_id),
                "Email": saved_account.get("email", saved_user_id),
                "Flights": len(all_data.get("users", {}).get(saved_user_id, {}).get("flights", [])),
            }
        )
    if account_rows:
        st.dataframe(pd.DataFrame(account_rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No other accounts registered on this machine.")

    legacy_account = find_account(all_data, "legacy@local")
    if legacy_account and legacy_account["user_id"] != current_user_id:
        if st.button(tr(language, "use_legacy_account"), use_container_width=True):
            set_active_account(legacy_account["user_id"])
            get_user_data(all_data, legacy_account["user_id"])
            save_data(all_data)
            st.rerun()



page_setup()
all_data = load_data()
initialize_session(all_data)

current_user_id = get_current_user_id()
if current_user_id is None:
    render_login_page(all_data)
else:
    data = get_user_data(all_data, current_user_id)
    current_page = render_navigation()

    if current_page == "home":
        render_home(data)
    elif current_page == "logbook":
        render_logbook(data)
    elif current_page == "currency":
        render_currency(data)
    elif current_page == "data":
        render_data(data)
    elif current_page == "account":
        render_account(data, all_data)
