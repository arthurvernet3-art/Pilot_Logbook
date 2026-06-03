from __future__ import annotations

import html
import streamlit as st

from i18n import PAGE_KEYS, tr
from storage import ACTIVE_SESSIONS, find_account
from helpers import recent_experience_status


def logout() -> None:
    uid = st.session_state.get("current_user_id")
    if uid:
        normalized_uid = uid.strip().lower()
        if normalized_uid in ACTIVE_SESSIONS:
            del ACTIVE_SESSIONS[normalized_uid]
    st.session_state.current_user_id = None
    if "session_token" in st.session_state:
        del st.session_state.session_token
    if "account" in st.query_params:
        del st.query_params["account"]
    if "session_token" in st.query_params:
        del st.query_params["session_token"]


def render_navigation(data: dict) -> str:
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

    # Calculate currency status and deadlines
    from rules import deadline_status
    flights = data.get("flights", [])
    experience = recent_experience_status(flights)
    is_current = experience.get("ok", False)

    has_expired_deadline = False
    has_warning_deadline = False
    for item in data.get("deadlines", []):
        days_left, d_status = deadline_status(item)
        if d_status == "Expired":
            has_expired_deadline = True
        elif d_status == "Action needed":
            has_warning_deadline = True

    if not is_current or has_expired_deadline:
        pill_class = "status-pill-bad"
        pill_text = tr(language, "not_current")
        bg_light = "rgba(255, 59, 48, 0.18)"
        bg_dark = "rgba(255, 69, 58, 0.15)"
    elif has_warning_deadline:
        pill_class = "status-pill-warn"
        pill_text = tr(language, "needs_attention")
        bg_light = "rgba(255, 149, 0, 0.18)"
        bg_dark = "rgba(255, 214, 10, 0.15)"
    else:
        pill_class = "status-pill-ok"
        pill_text = tr(language, "current")
        bg_light = "rgba(52, 199, 89, 0.18)"
        bg_dark = "rgba(48, 209, 88, 0.15)"

    # Inject dynamic gradient override
    st.markdown(
        f"""
        <style>
        :root {{
            --sys-bg-gradient: linear-gradient(180deg, {bg_light} 0%, #f2f2f7 320px) !important;
        }}
        @media (prefers-color-scheme: dark) {{
            :root {{
                --sys-bg-gradient: linear-gradient(180deg, {bg_dark} 0%, #000000 320px) !important;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

    col_status, col_title, col_menu = st.columns([1.5, 3, 1.5])
    with col_status:
        st.markdown(
            f"""
            <div class="top-status-pill {pill_class}">
                <span class="pill-dot"></span> {html.escape(pill_text)}
            </div>
            """,
            unsafe_allow_html=True
        )

    with col_title:
        page_title_label = tr(language, st.session_state.current_page)
        st.markdown(
            f"""
            <h1 class="top-page-title">{html.escape(page_title_label)}</h1>
            """,
            unsafe_allow_html=True
        )

    with col_menu:
        with st.popover("👤", key=f"menu_popover_{st.session_state.current_page}", use_container_width=True):
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

            page_key = "account"
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
                if "selected_flight_index" in st.query_params:
                    del st.query_params["selected_flight_index"]
                st.session_state.selected_flight_index = None
                st.rerun()
            st.write("")
            if st.button(tr(language, "logout"), key="menu_logout", use_container_width=True):
                logout()
                st.rerun()

    return st.session_state.current_page


def render_bottom_nav(user_id: str) -> None:
    current_page = st.session_state.get("current_page", "home")
    token = st.session_state.get("session_token", "")
    token_param = f"&session_token={token}" if token else ""
    language = st.session_state.language

    home_active = "active" if current_page == "home" else ""
    logbook_active = "active" if current_page == "logbook" else ""
    currency_active = "active" if current_page == "currency" else ""
    account_active = "active" if current_page == "account" else ""

    html_block = f"""
    <div class="bottom-nav-container">
        <div class="bottom-nav-bar">
            <a href="?page=home&account={user_id}{token_param}" target="_self" class="bottom-nav-item {home_active}">
                <span class="bottom-nav-icon">🏠</span>
                <span class="bottom-nav-label">{html.escape(tr(language, "home"))}</span>
            </a>
            <a href="?page=logbook&account={user_id}{token_param}" target="_self" class="bottom-nav-item {logbook_active}">
                <span class="bottom-nav-icon">📖</span>
                <span class="bottom-nav-label">{html.escape(tr(language, "logbook"))}</span>
            </a>
            <a href="?page=currency&account={user_id}{token_param}" target="_self" class="bottom-nav-item {currency_active}">
                <span class="bottom-nav-icon">🧭</span>
                <span class="bottom-nav-label">{html.escape(tr(language, "currency"))}</span>
            </a>
            <a href="?page=account&account={user_id}{token_param}" target="_self" class="bottom-nav-item {account_active}">
                <span class="bottom-nav-icon">👤</span>
                <span class="bottom-nav-label">{html.escape(tr(language, "account"))}</span>
            </a>
        </div>
        <a href="?page=logbook&account={user_id}{token_param}" target="_self" class="bottom-nav-plus-btn">
            +
        </a>
    </div>
    """
    st.html(html_block)
