from __future__ import annotations

import html
import json
import streamlit as st

from airports import AIRPORTS
from helpers import image_data_url
from i18n import tr
from storage import (
    get_current_user_id,
    current_account_label,
    save_aircraft_image,
    save_data,
    delete_aircraft_image,
)
from ui_components import (
    aircraft_form,
    aircraft_label,
    show_aircraft_image,
)


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


def render_data(data: dict) -> None:
    language = st.session_state.language
    all_data = st.session_state.get("all_data", data)
    if st.button("← " + tr(language, "back_to_account"), key="back_to_account", use_container_width=True):
        st.session_state.current_page = "account"
        st.query_params["page"] = "account"
        st.rerun()

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
        use_container_width=True,
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
