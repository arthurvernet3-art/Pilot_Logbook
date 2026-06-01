from __future__ import annotations

import hashlib
from pathlib import Path

import streamlit as st

from airports import airport_options_with_recent, option_code, option_label


NEW_AIRCRAFT = "__new_aircraft__"


def normalize_utc_time(value: str) -> str:
    cleaned = str(value or "").strip().upper().replace(" ", "")
    if not cleaned:
        return ""
    if ":" in cleaned:
        parts = cleaned.split(":", 1)
        if len(parts[0]) in {1, 2} and len(parts[1]) == 2 and parts[0].isdigit() and parts[1].isdigit():
            hours = int(parts[0])
            minutes = int(parts[1])
            if 0 <= hours <= 23 and 0 <= minutes <= 59:
                return f"{hours:02d}:{minutes:02d}"
        return cleaned
    if len(cleaned) in {3, 4} and cleaned.isdigit():
        hours = int(cleaned[:-2])
        minutes = int(cleaned[-2:])
        if 0 <= hours <= 23 and 0 <= minutes <= 59:
            return f"{hours:02d}:{minutes:02d}"
    return cleaned


def aircraft_label(registration: str, profiles: dict) -> str:
    profile = profiles.get(registration, {})
    aircraft_type = profile.get("type", "Unknown")
    return f"{registration} - {aircraft_type}"


def recent_aircraft(flights: list[dict], profiles: dict, limit: int = 8) -> list[str]:
    seen = []
    for flight in sorted(flights, key=lambda item: item.get("date", ""), reverse=True):
        registration = flight.get("aircraft_registration")
        if registration and registration in profiles and registration not in seen:
            seen.append(registration)
    for registration in sorted(profiles):
        if registration not in seen:
            seen.append(registration)
    return seen[:limit]


def aircraft_selectbox(flights: list[dict], profiles: dict, key: str) -> str:
    recent = recent_aircraft(flights, profiles)
    options = recent + [NEW_AIRCRAFT]
    return st.selectbox(
        "Aircraft",
        options,
        format_func=lambda value: "Create new aircraft..." if value == NEW_AIRCRAFT else f"Recent | {aircraft_label(value, profiles)}",
        key=key,
    )


def uppercase_text_input(label: str, placeholder: str, key: str) -> str:
    value = st.text_input(label, placeholder=placeholder, key=key)
    return value.upper().strip()


def aircraft_form(prefix: str) -> tuple[str, dict, object]:
    col1, col2 = st.columns(2)
    with col1:
        registration = uppercase_text_input("Registration", "HB-KDA", f"{prefix}_registration")
    with col2:
        aircraft_type = uppercase_text_input("Aircraft type", "DA40", f"{prefix}_type")
    col3, col4 = st.columns(2)
    manufacturer = col3.text_input("Manufacturer", placeholder="Diamond", key=f"{prefix}_manufacturer").strip()
    with col4:
        category = uppercase_text_input("Category / class", "SEP", f"{prefix}_category")
    image = st.file_uploader("Aircraft picture", type=["jpg", "jpeg", "png"], key=f"{prefix}_image")
    notes = st.text_area("Aircraft notes", height=70, key=f"{prefix}_notes").strip()
    return registration, {
        "registration": registration,
        "type": aircraft_type,
        "manufacturer": manufacturer,
        "category": category,
        "notes": notes,
        "image_path": "",
    }, image


def airport_selectbox(label: str, flights: list[dict], field: str, key: str, default_code: str = "LFLI") -> str:
    options = airport_options_with_recent(flights, field)
    index = next((idx for idx, option in enumerate(options) if option_code(option) == default_code), 0)
    selected = st.selectbox(label, options, index=index, format_func=option_label, key=key)
    return option_code(selected)


def route_chain_controls(prefix: str, labels: dict, max_airports: int = 8) -> None:
    count_key = f"{prefix}_airport_count"
    st.session_state.setdefault(count_key, 2)
    col1, col2 = st.columns(2)
    if col1.button(labels["add_airport"], key=f"{prefix}_add_airport", width="stretch"):
        st.session_state[count_key] = min(max_airports, st.session_state[count_key] + 1)
        st.rerun()
    if col2.button(labels["remove_airport"], key=f"{prefix}_remove_airport", width="stretch", disabled=st.session_state[count_key] <= 2):
        st.session_state[count_key] = max(2, st.session_state[count_key] - 1)
        st.rerun()


def route_chain_inputs(flights: list[dict], prefix: str, labels: dict) -> tuple[str, str, list[dict], list[str]]:
    count = st.session_state.get(f"{prefix}_airport_count", 2)
    airports = []
    airport_times = []
    events = []
    st.caption(labels["route"])
    for index in range(count):
        airport_label_text = labels["airport_n"].format(number=index + 1)
        if index == 0 or index == count - 1:
            col1, col2 = st.columns([2.4, 1])
            with col1:
                airports.append(airport_selectbox(airport_label_text, flights, "arrival", f"{prefix}_airport_{index}"))
            airport_times.append(
                normalize_utc_time(col2.text_input(labels["utc_time"], placeholder="HHMM", key=f"{prefix}_airport_time_{index}"))
            )
            continue

        col1, col2, col3, col4 = st.columns([2.1, 1.1, .7, 1])
        with col1:
            airport = airport_selectbox(airport_label_text, flights, "arrival", f"{prefix}_airport_{index}")
        event_label = col2.selectbox(
            labels["event"],
            [labels["touch_and_go"], labels["full_stop"]],
            key=f"{prefix}_event_type_{index}",
        )
        landing_count = col3.selectbox(
            labels["count"],
            list(range(1, 10)),
            key=f"{prefix}_event_count_{index}",
        )
        planned_utc = normalize_utc_time(col4.text_input(labels["utc_time"], placeholder="HHMM", key=f"{prefix}_event_time_{index}"))
        airports.append(airport)
        airport_times.append(planned_utc)
        events.append(
            {
                "type": "touch_and_go" if event_label == labels["touch_and_go"] else "full_stop",
                "airport": airport,
                "planned_utc": planned_utc,
                "logged_utc": "",
                "landing_count": int(landing_count),
                "count_as_landing": True,
            }
        )
    route_chain_controls(prefix, labels)
    return airports[0], airports[-1], events, airport_times


def route_event_inputs(flights: list[dict], prefix: str, max_events: int = 2) -> list[dict]:
    events = []
    st.caption("Intermediate stops / touch-and-goes")
    for index in range(max_events):
        col1, col2, col3 = st.columns([1.1, 2.2, 1.4])
        event_type = col1.selectbox(
            f"Event {index + 1}",
            ["None", "Touch-and-go", "Full stop"],
            key=f"{prefix}_event_type_{index}",
        )
        with col2:
            airport = airport_selectbox("Airport", flights, "arrival", f"{prefix}_event_airport_{index}")
        time_utc = normalize_utc_time(col3.text_input("UTC time", placeholder="HHMM", key=f"{prefix}_event_time_{index}"))
        if event_type != "None":
            events.append(
                {
                    "type": "touch_and_go" if event_type == "Touch-and-go" else "full_stop",
                    "airport": airport,
                    "planned_utc": time_utc,
                    "logged_utc": "",
                    "count_as_landing": True,
                }
            )
    return events


def duration_input(label: str, key: str, show_label: bool = False, default_minutes: int | None = None, default_signature: str | None = None) -> int:
    if show_label:
        st.caption(label)
    default_hours = int(default_minutes or 0) // 60
    default_remainder = int(default_minutes or 0) % 60
    if default_minutes is not None and default_signature:
        key_suffix = hashlib.sha1(default_signature.encode("utf-8")).hexdigest()[:12]
        hours_key = f"{key}_{key_suffix}_hours"
        minutes_key = f"{key}_{key_suffix}_minutes"
    else:
        hours_key = f"{key}_hours"
        minutes_key = f"{key}_minutes"
    hours_col, minutes_col = st.columns(2)
    hours = hours_col.number_input("Hours", min_value=0, step=1, value=default_hours, key=hours_key)
    minutes = minutes_col.number_input("Minutes", min_value=0, max_value=59, step=1, value=default_remainder, key=minutes_key)
    return int(hours) * 60 + int(minutes)


def show_aircraft_image(profile: dict) -> None:
    image_path = profile.get("image_path")
    if image_path and Path(image_path).exists():
        st.image(image_path, width=220)
