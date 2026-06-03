from __future__ import annotations

from pathlib import Path
import streamlit as st

from i18n import tr
from storage import (
    load_data,
    get_user_data,
    get_current_user_id,
    ACTIVE_SESSIONS,
    find_account,
)
from navigation import render_navigation, render_bottom_nav
from views import (
    render_login_page,
    render_home,
    render_logbook,
    render_currency,
    render_data,
    render_account,
)


def page_setup() -> None:
    language = st.session_state.get("language", "en")
    st.set_page_config(
        page_title=tr(language, "app_title"),
        page_icon="✈️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    css_path = Path(__file__).parent / "style.css"
    if css_path.exists():
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def initialize_session(all_data: dict) -> None:
    st.session_state.setdefault("language", "en")
    st.session_state["all_data"] = all_data
    
    requested_account = st.query_params.get("account")
    if isinstance(requested_account, list):
        requested_account = requested_account[0] if requested_account else None
    
    requested_token = st.query_params.get("session_token")
    if isinstance(requested_token, list):
        requested_token = requested_token[0] if requested_token else None
    
    current_session_user = st.session_state.get("current_user_id")
    
    # If there is a session token in query params matching active sessions, automatically restore user_id in session state
    if requested_account and requested_token:
        normalized_req = requested_account.strip().lower()
        if ACTIVE_SESSIONS.get(normalized_req) == requested_token:
            st.session_state.current_user_id = normalized_req
            st.session_state.session_token = requested_token
            st.query_params["account"] = normalized_req
            st.query_params["session_token"] = requested_token
            current_session_user = normalized_req
    
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
        if "session_token" in st.session_state:
            st.query_params["session_token"] = st.session_state.session_token

    # Synchronize selected_flight_index with query_params
    requested_flight = st.query_params.get("selected_flight_index")
    if isinstance(requested_flight, list):
        requested_flight = requested_flight[0] if requested_flight else None
    if requested_flight is not None:
        try:
            st.session_state.selected_flight_index = int(requested_flight)
        except ValueError:
            st.session_state.selected_flight_index = None
    else:
        if "selected_flight_index" not in st.session_state:
            st.session_state.selected_flight_index = None


page_setup()
all_data = load_data()
initialize_session(all_data)

current_user_id = get_current_user_id()
if current_user_id is None:
    render_login_page(all_data)
else:
    data = get_user_data(all_data, current_user_id)
    current_page = render_navigation(data)

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
    
    render_bottom_nav(current_user_id)
