from __future__ import annotations

from datetime import date
import html
import streamlit as st

from i18n import tr
from rules import (
    route_event_landing_count,
    build_sector_flights,
    rounded_utc_now,
    minutes_between,
    format_duration,
)
from helpers import (
    route_time_minutes,
    route_times_to_boundaries,
    flight_delete_label,
)
from storage import save_new_aircraft_if_needed, save_data
from ui_components import (
    NEW_AIRCRAFT,
    aircraft_selectbox,
    aircraft_form,
    show_aircraft_image,
    route_chain_inputs,
    duration_input,
    aircraft_label,
)
from views.home import render_flight_cards


def render_logbook(data: dict) -> None:
    language = st.session_state.language
    all_data = st.session_state.get("all_data", data)
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


def render_in_flight(data: dict) -> None:
    language = st.session_state.language
    all_data = st.session_state.get("all_data", data)
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
