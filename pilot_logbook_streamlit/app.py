from __future__ import annotations

import base64
import html
import json
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
    authenticate_account,
    create_account,
    delete_aircraft_image,
    find_account,
    get_user_data,
    load_data,
    save_aircraft_image,
    save_data,
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



DEFAULT_USER_ID = "arthur@local"


def get_current_user_id() -> str:
    """Return the active local account id for this session."""
    requested_account = st.query_params.get("account")
    if isinstance(requested_account, list):
        requested_account = requested_account[0] if requested_account else None
    if requested_account:
        st.session_state.current_user_id = str(requested_account).strip().lower()
    st.session_state.setdefault("current_user_id", DEFAULT_USER_ID)
    return str(st.session_state.current_user_id).strip().lower() or DEFAULT_USER_ID


def current_account_label(all_data: dict, user_id: str) -> str:
    account = all_data.get("accounts", {}).get(user_id, {})
    username = account.get("username") or user_id
    email = account.get("email") or user_id
    return f"{username} · {email}" if username != email else username


def set_active_account(user_id: str) -> None:
    st.session_state.current_user_id = user_id
    st.query_params["account"] = user_id


def page_setup() -> None:
    language = st.session_state.get("language", "en")
    st.set_page_config(page_title=tr(language, "app_title"), page_icon="✈️", layout="wide", initial_sidebar_state="collapsed")
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1180px;}
        div[data-testid="stMetric"] {border: 1px solid #e6e8eb; border-radius: 8px; padding: .8rem;}
        .status-ok {color: #116329; font-weight: 700;}
        .status-warn {color: #9a5b00; font-weight: 700;}
        .status-bad {color: #b42318; font-weight: 700;}
        .page-label {
            color: #536171;
            font-size: .95rem;
            margin: -.5rem 0 1.25rem 0;
        }
        div[data-testid="stPopover"] {
            margin-top: 1.8rem;
        }
        div[data-testid="stPopover"] > button {
            border-radius: 999px;
            border: 1px solid #d5dce5;
            background: linear-gradient(180deg, #ffffff 0%, #f7faff 100%);
            box-shadow: 0 8px 18px rgba(15, 23, 42, .08);
            font-weight: 800;
            min-height: 2.7rem;
        }
        div[data-testid="stPopover"] > button:hover {
            border-color: #1f6feb;
            box-shadow: 0 10px 22px rgba(31, 111, 235, .14);
        }
        .menu-tab-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: .35rem;
            margin-top: .4rem;
        }
        .menu-tab-link {
            display: block;
            text-decoration: none !important;
            color: #1f2937 !important;
            border-radius: 13px;
            min-height: 2.65rem;
            line-height: 2.65rem;
            padding: 0 .85rem;
            border: 1px solid #d9e0ea;
            background: #ffffff;
            font-weight: 780;
            box-shadow: 0 4px 12px rgba(15, 23, 42, .04);
            margin-bottom: .35rem;
        }
        .menu-tab-link:hover {
            border-color: #1f6feb;
            background: #f4f8ff;
            color: #1d4ed8 !important;
        }
        .menu-tab-link-active {
            background: #eef5ff;
            border-color: #1f6feb;
            color: #1d4ed8 !important;
            box-shadow: inset 0 0 0 1px #1f6feb;
        }
        div[data-testid="stPopover"] div[data-testid="stHorizontalBlock"] {
            gap: .45rem;
        }
        div[data-testid="stPopover"] div[data-testid="stButton"] > button {
            justify-content: flex-start;
            border-radius: 13px;
            min-height: 2.65rem;
            border: 1px solid #d9e0ea;
            background: #ffffff;
            font-weight: 780;
            box-shadow: 0 4px 12px rgba(15, 23, 42, .04);
        }
        div[data-testid="stPopover"] div[data-testid="stButton"] > button:hover {
            border-color: #1f6feb;
            background: #f4f8ff;
            color: #1d4ed8;
        }
        input[placeholder="HB-KDA"],
        input[placeholder="DA40"],
        input[placeholder="SEP"],
        input[placeholder="LFLI"],
        input[placeholder="HH:MM"] {
            text-transform: uppercase;
        }
        div[role="radiogroup"] label {
            border: 1px solid #cfd6df;
            border-radius: 8px;
            padding: .35rem .65rem;
            margin: .16rem .12rem;
            white-space: nowrap;
            background: #f8fafc;
            min-width: max-content;
        }
        div[role="radiogroup"] label:has(input:checked) {
            border-color: #1f6feb;
            background: #eef5ff;
            box-shadow: inset 0 0 0 1px #1f6feb;
        }
        div[role="radiogroup"] {
            gap: .25rem;
        }
        .flight-list {
            background: #ffffff;
            border: 1px solid #e4e8ee;
            border-radius: 18px;
            overflow: hidden;
            margin-top: 1rem;
            box-shadow: 0 10px 30px rgba(15, 23, 42, .06);
        }
        .flight-row {
            display: grid;
            grid-template-columns: 74px minmax(120px, 1fr) 90px minmax(120px, 1fr) 86px;
            gap: .8rem;
            align-items: center;
            padding: 1rem 1.1rem;
            border-bottom: 1px solid #edf0f4;
        }
        .flight-row:last-child {border-bottom: 0;}
        .flight-date {text-align: center; line-height: 1;}
        .flight-day {font-size: 1.9rem; font-weight: 800;}
        .flight-month {color: #7a8491; font-weight: 700; letter-spacing: .04em;}
        .flight-airport {font-size: 1.35rem; font-weight: 800;}
        .flight-time {color: #202938; font-size: 1.05rem;}
        .flight-duration {text-align: center; font-size: 1.25rem; color: #202938;}
        .flight-chip-row {display: flex; gap: .35rem; margin-top: .35rem; flex-wrap: wrap;}
        .flight-chip {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: .12rem .45rem;
            font-size: .78rem;
            font-weight: 700;
            border: 1px solid #d2d8e0;
            color: #5d6673;
        }
        .flight-chip-primary {
            background: #5946e8;
            border-color: #5946e8;
            color: #fff;
        }
        .flight-landings {text-align: right;}
        .landing-pill {
            display: inline-flex;
            border: 1px solid #cfd6df;
            border-radius: 999px;
            padding: .15rem .5rem;
            color: #5d6673;
            font-weight: 700;
        }
        .home-stats {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: .9rem;
            margin: .7rem 0 1rem;
        }
        .home-stat {
            border: 1px solid #e2e8f0;
            border-radius: 18px;
            padding: 1rem;
            background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
            box-shadow: 0 10px 24px rgba(15, 23, 42, .055);
        }
        .home-stat-icon {font-size: 1.35rem; line-height: 1;}
        .home-stat-value {font-size: 2rem; font-weight: 850; margin-top: .35rem; color: #111827;}
        .home-stat-label {color: #5f6b7a; font-weight: 700;}
        .home-status-panel {
            border-radius: 8px;
            padding: 1rem;
            background: #ffffff;
            border: 1px solid #e2e8f0;
            margin: 1rem 0 1.2rem;
            box-shadow: 0 10px 24px rgba(15, 23, 42, .055);
        }
        .home-status-panel-passenger {margin-top: -.45rem;}
        .home-status-heading {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 1rem;
            margin-bottom: .8rem;
        }
        .home-status-title {font-size: 1.25rem; font-weight: 800;}
        .home-status-subtitle {color: #64748b; font-weight: 650; margin-top: .1rem;}
        .home-status-current {font-size: 1.15rem; font-weight: 850;}
        .home-status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
            gap: .65rem;
        }
        .home-status-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: .75rem;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: .8rem;
            background: #f8fafc;
            min-height: 5rem;
        }
        .home-status-label {font-weight: 820; color: #111827;}
        .home-status-detail {color: #64748b; font-weight: 650; margin-top: .12rem;}
        .home-status-badge {
            border-radius: 999px;
            padding: .22rem .55rem;
            font-weight: 850;
            font-size: .78rem;
            white-space: nowrap;
        }
        .card-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
            gap: .75rem;
            margin: .8rem 0 1rem;
        }
        .info-card {
            border: 1px solid #e2e8f0;
            border-radius: 16px;
            padding: .95rem;
            background: #ffffff;
            box-shadow: 0 8px 20px rgba(15, 23, 42, .045);
        }
        .info-title {font-size: 1.1rem; font-weight: 850; color: #111827;}
        .info-sub {color: #64748b; margin-top: .15rem;}
        .info-pill {
            display: inline-flex;
            border-radius: 999px;
            padding: .16rem .55rem;
            margin-top: .45rem;
            background: #eef5ff;
            color: #1d4ed8;
            font-weight: 800;
            font-size: .78rem;
        }
        .aircraft-card {
            display: grid;
            grid-template-columns: 96px 1fr;
            gap: .9rem;
            align-items: center;
        }
        .aircraft-photo {
            width: 96px;
            height: 72px;
            border-radius: 12px;
            object-fit: cover;
            background: #eef2f7;
            border: 1px solid #dbe3ec;
        }
        .aircraft-photo-placeholder {
            width: 96px;
            height: 72px;
            border-radius: 12px;
            background: linear-gradient(135deg, #e0f2fe, #eef2ff);
            border: 1px solid #dbe3ec;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #2563eb;
            font-weight: 900;
            font-size: 1.7rem;
        }
        @media (max-width: 760px) {
            .block-container {padding-left: .8rem; padding-right: .8rem;}
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
    st.session_state.setdefault("current_page", "logbook")
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

    spacer_col, button_col, title_col = st.columns([0.15, 1.55, 4])
    with button_col.popover(tr(language, "menu")):
        st.caption(tr(language, "language"))
        lang_col_1, lang_col_2 = st.columns(2)
        if lang_col_1.button("🇬🇧", key="lang_en", width="stretch", type="primary" if language == "en" else "secondary"):
            st.session_state.language = "en"
            st.rerun()
        if lang_col_2.button("🇫🇷", key="lang_fr", width="stretch", type="primary" if language == "fr" else "secondary"):
            st.session_state.language = "fr"
            st.rerun()
        language = st.session_state.language
        st.caption(tr(language, "select_page"))

        menu_links = []
        current_account = get_current_user_id()
        for page_key in PAGE_KEYS:
            page_label = tr(language, page_key)
            is_current_page = page_key == st.session_state.current_page
            css_class = "menu-tab-link menu-tab-link-active" if is_current_page else "menu-tab-link"
            label_prefix = "✓ " if is_current_page else ""
            href = "?" + urlencode({"page": page_key, "account": current_account})
            menu_links.append(
                f'<a class="{css_class}" href="{html.escape(href)}" target="_self">'
                f'{html.escape(label_prefix + page_label)}</a>'
            )
        st.markdown("".join(menu_links), unsafe_allow_html=True)
    title_col.title(tr(language, "app_title"))

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


def render_flight_cards(flights: list[dict]) -> None:
    if not flights:
        language = st.session_state.language
        st.info(tr(language, "no_flights"))
        return

    rows = []
    for flight in sorted(flights, key=lambda item: item.get("date", ""), reverse=True):
        day, month = flight_day_month(flight.get("date", ""))
        total_minutes = int(flight.get("pic_minutes", 0)) + int(flight.get("dual_minutes", 0))
        departure = html.escape(flight.get("departure", ""))
        arrival = html.escape(flight.get("arrival", ""))
        role = html.escape(flight_role(flight))
        sector = html.escape(flight.get("sector_index") and f"{flight.get('sector_index')}/{flight.get('sector_count')}" or "")
        xc_chip = '<span class="flight-chip">XC</span>' if departure != arrival else ""
        sector_chip = f'<span class="flight-chip">S{sector}</span>' if sector else ""
        rows.append(
            f"""
            <div class="flight-row">
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
            """
        )
    st.html('<div class="flight-list">' + "".join(rows) + "</div>")


def render_deadline_cards(deadlines: list[dict]) -> None:
    if not deadlines:
        language = st.session_state.language
        st.info(tr(language, "no_deadlines"))
        return
    cards = []
    for deadline in sorted(deadlines, key=lambda item: deadline_status(item)[0]):
        days_left, status = deadline_status(deadline)
        color = "#22c55e" if status == "OK" else "#f59e0b" if days_left >= 0 else "#ef4444"
        cards.append(
            f"""
            <div class="info-card">
                <div class="info-title">{html.escape(deadline.get("name", ""))}</div>
                <div class="info-sub">{html.escape(deadline.get("category", ""))} · {html.escape(deadline.get("expires", ""))}</div>
                <span class="info-pill" style="background:{color}1f;color:{color};">{html.escape(status)} · {days_left} days</span>
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
            <div class="home-stat-icon">↘</div>
            <div class="home-stat-value">{landings}</div>
            <div class="home-stat-label">{html.escape(tr(language, "landings"))}</div>
        </div>
        <div class="home-stat">
            <div class="home-stat-icon">◴</div>
            <div class="home-stat-value">{html.escape(compact_duration(total_minutes))}</div>
            <div class="home-stat-label">{html.escape(tr(language, "total_time"))}</div>
        </div>
        <div class="home-stat">
            <div class="home-stat-icon">◎</div>
            <div class="home-stat-value">{airports}</div>
            <div class="home-stat-label">{html.escape(tr(language, "airports"))}</div>
        </div>
        <div class="home-stat">
            <div class="home-stat-icon">✈</div>
            <div class="home-stat-value">{len(flights)}</div>
            <div class="home-stat-label">{html.escape(tr(language, "total_flights"))}</div>
        </div>
    </div>
    """
    st.html(html_block)


def status_row(language: str, label_key: str, value: str, ok: bool) -> str:
    color = "#16a34a" if ok else "#dc2626"
    symbol = "OK" if ok else "!"
    return f"""
        <div class="home-status-row">
            <div>
                <div class="home-status-label">{html.escape(tr(language, label_key))}</div>
                <div class="home-status-detail">{html.escape(value)}</div>
            </div>
            <span class="home-status-badge" style="background:{color}1f;color:{color};">{symbol}</span>
        </div>
    """


def render_home_status(language: str, flights: list[dict], currency_rules: list[dict]) -> None:
    experience = recent_experience_status(flights)
    status_label = tr(language, "current") if experience["ok"] else tr(language, "not_current")
    status_color = "#16a34a" if experience["ok"] else "#dc2626"
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
                <div class="home-status-current" style="color:{status_color};">{html.escape(status_label)}</div>
            </div>
            <div class="home-status-grid">{"".join(experience_rows)}</div>
        </div>
        """
    )

    statuses = [pax_currency(flights, rule) for rule in currency_rules]
    if not statuses:
        return
    passenger_cards = []
    for status in statuses:
        ok = bool(status["ok"])
        color = "#16a34a" if ok else "#dc2626"
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
                <span class="home-status-badge" style="background:{color}1f;color:{color};">{html.escape(label)}</span>
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
        line_layer = pdk.Layer("PathLayer", routes, get_path="path", get_color=[32, 112, 186], width_min_pixels=4, pickable=True)
        point_layer = pdk.Layer("ScatterplotLayer", points, get_position="[lon, lat]", get_fill_color=[241, 91, 76], get_radius=4500, pickable=True)
        label_layer = pdk.Layer("TextLayer", points, get_position="[lon, lat]", get_text="code", get_size=14, get_color=[20, 24, 31], get_alignment_baseline="'bottom'")
        midpoint = points[["lat", "lon"]].mean()
        deck = pdk.Deck(
            layers=[line_layer, point_layer, label_layer],
            initial_view_state=pdk.ViewState(latitude=float(midpoint["lat"]), longitude=float(midpoint["lon"]), zoom=5.3, pitch=0),
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
    render_flight_cards(flights)


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
        render_flight_cards(flights)
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

    st.subheader("Account")
    st.caption("Local login for this prototype. Passwords are only for separating local demo accounts on this machine.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Current user", username)
    col2.metric("Flights", len(data.get("flights", [])))
    col3.metric("Aircraft", len(data.get("aircraft_profiles", {})))
    st.caption(f"Email: {email}")

    st.divider()
    st.write("Log in")
    with st.form("account_login_form"):
        login = st.text_input("Email or username", placeholder="demo")
        password = st.text_input("Password", type="password", placeholder="demo")
        login_col, demo_col = st.columns(2)
        submitted = login_col.form_submit_button("Log in", type="primary", width="stretch")
        demo_submitted = demo_col.form_submit_button("Use demo account", width="stretch")
        if submitted or demo_submitted:
            login_value = "demo" if demo_submitted else login
            password_value = "demo" if demo_submitted else password
            logged_in = authenticate_account(all_data, login_value, password_value)
            if logged_in:
                set_active_account(logged_in["user_id"])
                get_user_data(all_data, logged_in["user_id"])
                save_data(all_data)
                st.success(f"Logged in as {logged_in.get('username', logged_in['user_id'])}.")
                st.rerun()
            else:
                st.error("Email/username and password do not match.")

    st.divider()
    st.write("Create account")
    with st.form("account_create_form"):
        new_col_1, new_col_2 = st.columns(2)
        new_email = new_col_1.text_input("Email", placeholder="arthur@example.com")
        new_username = new_col_2.text_input("Username", placeholder="arthur")
        new_password = st.text_input("Password", type="password")
        if st.form_submit_button("Create account", width="stretch"):
            ok, message, user_id = create_account(all_data, new_email, new_username, new_password)
            if ok and user_id:
                set_active_account(user_id)
                save_data(all_data)
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    st.divider()
    st.write("Known local accounts")
    account_rows = []
    for saved_account in sorted(all_data.get("accounts", {}).values(), key=lambda item: item.get("username", "")):
        saved_user_id = saved_account.get("user_id", "")
        account_rows.append(
            {
                "Username": saved_account.get("username", saved_user_id),
                "Email": saved_account.get("email", saved_user_id),
                "Flights": len(all_data.get("users", {}).get(saved_user_id, {}).get("flights", [])),
            }
        )
    if account_rows:
        st.dataframe(pd.DataFrame(account_rows), width="stretch", hide_index=True)

    legacy_account = find_account(all_data, "legacy@local")
    if legacy_account and st.button("Use legacy account", width="stretch"):
        set_active_account(legacy_account["user_id"])
        get_user_data(all_data, legacy_account["user_id"])
        save_data(all_data)
        st.rerun()

    if account and not account.get("password_hash"):
        st.info("This migrated account does not have a password yet. Create a new account when you want a password-protected local profile.")

    st.divider()
    st.write("Account backup")
    st.download_button(
        "Download this account backup",
        data=json.dumps(data, indent=2),
        file_name=f"pilot_logbook_backup_{current_user_id.replace('@', '_at_')}.json",
        mime="application/json",
        width="stretch",
    )

    uploaded = st.file_uploader("Restore this account from JSON backup", type=["json"], key="account_restore")
    if uploaded is not None:
        restored = json.loads(uploaded.getvalue().decode("utf-8"))
        if "flights" in restored and "deadlines" in restored:
            data.clear()
            data.update(restored)
            save_data(all_data)
            st.success("This account backup was restored.")
            st.rerun()
        else:
            st.error("That backup does not look like a pilot logbook file.")



page_setup()
all_data = load_data()
current_user_id = get_current_user_id()
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
