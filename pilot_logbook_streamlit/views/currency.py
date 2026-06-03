from __future__ import annotations

from datetime import date
import html
import streamlit as st

from i18n import tr
from rules import pax_currency, deadline_status
from storage import save_data
from ui_components import uppercase_text_input


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


def render_currency(data: dict) -> None:
    language = st.session_state.language
    all_data = st.session_state.get("all_data", data)
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
    all_data = st.session_state.get("all_data", data)
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
