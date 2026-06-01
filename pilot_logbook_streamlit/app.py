from __future__ import annotations

import base64
import html
import json
from datetime import date, datetime
from pathlib import Path

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
from storage import delete_aircraft_image, save_aircraft_image, load_data, save_data
from ui_components import (
    NEW_AIRCRAFT,
    aircraft_form,
    aircraft_label,
    aircraft_selectbox,
    duration_input,
    route_chain_inputs,
    show_aircraft_image,
    uppercase_text_input,
)


def page_setup() -> None:
    st.set_page_config(page_title="Pilot Logbook", page_icon="✈️", layout="wide", initial_sidebar_state="collapsed")
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
        .home-status {
            border-radius: 18px;
            padding: 1rem;
            background: #ffffff;
            border: 1px solid #e2e8f0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 1rem 0 1.2rem;
            box-shadow: 0 10px 24px rgba(15, 23, 42, .055);
        }
        .home-status-title {font-size: 1.25rem; font-weight: 800;}
        .home-status-current {color: #22c55e; font-size: 1.35rem; font-weight: 850;}
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
    old_page_names = {
        "Home": "home",
        "Logbook": "logbook",
        "In flight": "in_flight",
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
    if st.session_state.current_page not in PAGE_KEYS:
        st.session_state.current_page = "home"
    language = st.session_state.language

    button_col, title_col = st.columns([2, 4])
    with button_col.expander(tr(language, "menu")):
        st.selectbox(
            tr(language, "language"),
            list(LANGUAGES),
            index=list(LANGUAGES).index(language),
            format_func=lambda code: LANGUAGES[code],
            key="language",
        )
        language = st.session_state.language
        page = st.radio(
            tr(language, "select_page"),
            PAGE_KEYS,
            index=PAGE_KEYS.index(st.session_state.current_page),
            key="menu_page_select_v2",
            format_func=lambda key: tr(language, key),
            horizontal=False,
        )
        if page != st.session_state.current_page:
            st.session_state.current_page = page
            st.rerun()
    title_col.title(tr(language, "app_title"))

    return st.session_state.current_page


def save_new_aircraft_if_needed(data: dict, registration: str, profile: dict, image) -> None:
    if registration in data["aircraft_profiles"]:
        return
    profile["image_path"] = save_aircraft_image(registration, image)
    data["aircraft_profiles"][registration] = profile


def route_times_to_boundaries(flight_date: date, route_times: list[str]) -> list[str] | None:
    if not route_times or any(not time for time in route_times):
        return None
    return [f"{flight_date.isoformat()} {time} UTC" for time in route_times]


def compact_duration(minutes: int) -> str:
    hours, remainder = divmod(int(minutes), 60)
    return f"{hours}:{remainder:02d}"


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
        st.info("No flights yet.")
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
        st.info("No deadlines yet.")
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
        st.info("No aircraft saved yet.")
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
                        <div class="info-sub">{html.escape(details or "Aircraft profile")}</div>
                        <span class="info-pill">{html.escape(profile.get("type", "Unknown"))}</span>
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
    <div class="home-status">
        <div class="home-status-title">{html.escape(tr(language, "status"))}</div>
        <div class="home-status-current">{html.escape(tr(language, "current"))} ✓</div>
    </div>
    """
    st.html(html_block)


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
        st.info("Add a flight with known airports to see routes on the map.")


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
    detail_a, detail_b, detail_c = st.columns(3)
    detail_a.metric(tr(language, "pic_time_stat"), format_duration(pic_minutes))
    detail_b.metric(tr(language, "dual_time_stat"), format_duration(dual_minutes))
    detail_c.metric(tr(language, "night_time_stat"), format_duration(night_minutes))
    render_route_map(data, tr(language, "route_map"))
    st.subheader(tr(language, "recent"))
    render_flight_cards(flights)


def render_logbook(data: dict) -> None:
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

    col_time_1, col_time_2, col_landings = st.columns(3)
    time_role = col_time_1.segmented_control(
        tr(language, "time_role"),
        [tr(language, "pic"), tr(language, "dc")],
        default=tr(language, "pic"),
        key="log_time_role",
    )
    with col_time_2:
        flight_minutes = duration_input(tr(language, "flight_time"), "log_flight_time")
    landings = col_landings.number_input(tr(language, "landings"), min_value=minimum_landings, step=1, value=minimum_landings)
    remarks = st.text_area(tr(language, "remarks"), height=80)

    if st.button(tr(language, "save_flight"), width="stretch", type="primary"):
        if selected_aircraft == NEW_AIRCRAFT and (not new_registration or not new_profile.get("type")):
            st.error("Add registration and aircraft type before saving a new aircraft.")
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
                "departure_utc": route_times[0] if route_times else "",
                "arrival_utc": route_times[-1] if route_times else "",
            }
            boundary_times = route_times_to_boundaries(flight_date, route_times)
            flights.extend(build_sector_flights(base_flight, route_events, boundary_times))
            save_data(data)
            st.success("Flight saved.")
            st.rerun()

    st.subheader(tr(language, "flights"))
    if not flights:
        st.info("No flights yet.")
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
                save_data(data)
                st.success("Selected entries deleted.")
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
                st.error("Add registration and aircraft type before starting.")
            else:
                if selected_aircraft == NEW_AIRCRAFT:
                    save_new_aircraft_if_needed(data, new_registration, new_profile, new_image)
                    save_data(data)
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

    st.metric("Aircraft", aircraft_label(active["aircraft_registration"], profiles))
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Route", f"{active['departure']} → {active['arrival']}")
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
            save_data(data)
            del st.session_state.active_flight
            st.success("Flight saved from in-flight logger.")
            st.rerun()

    if active["landing_times_utc"]:
        st.write("Landing times")
        st.html(
            '<div class="card-grid">'
            + "".join(
                f'<div class="info-card"><div class="info-title">{html.escape(value)}</div><div class="info-sub">UTC landing</div></div>'
                for value in active["landing_times_utc"]
            )
            + "</div>"
        )
    if st.button(tr(language, "discard_active"), width="stretch"):
        del st.session_state.active_flight
        st.rerun()


def render_currency(data: dict) -> None:
    st.subheader("Passenger Currency")
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
                save_data(data)
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
            save_data(data)
            st.rerun()


def render_data(data: dict) -> None:
    st.subheader("Data")
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
                save_data(data)
                st.success("Aircraft saved.")
                st.rerun()
    if data["aircraft_profiles"]:
        st.subheader("Aircraft")
        render_aircraft_cards(data["aircraft_profiles"])
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
                save_data(data)
                st.success("Selected aircraft deleted.")
                st.rerun()
    st.download_button("Download logbook backup", data=json.dumps(data, indent=2), file_name="pilot_logbook_backup.json", mime="application/json", width="stretch")
    uploaded = st.file_uploader("Restore from JSON backup", type=["json"])
    if uploaded is not None:
        restored = json.loads(uploaded.getvalue().decode("utf-8"))
        if "flights" in restored and "deadlines" in restored:
            save_data(restored)
            st.success("Backup restored.")
            st.rerun()
        else:
            st.error("That backup does not look like a pilot logbook file.")


page_setup()
data = load_data()
current_page = render_navigation()

if current_page == "home":
    render_home(data)
elif current_page == "logbook":
    render_logbook(data)
elif current_page == "in_flight":
    render_in_flight(data)
elif current_page == "currency":
    render_currency(data)
elif current_page == "deadlines":
    render_deadlines(data)
elif current_page == "data":
    render_data(data)
