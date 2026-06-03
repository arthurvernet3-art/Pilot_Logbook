from __future__ import annotations

import html
import json
import pandas as pd
import streamlit as st

from i18n import tr
from navigation import logout
from storage import (
    get_current_user_id,
    find_account,
    set_active_account,
    get_user_data,
    save_data,
    migrate_data,
)


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

    if st.button("✈️ " + tr(language, "manage_aircraft_data"), key="go_to_data_page", use_container_width=True):
        st.session_state.current_page = "data"
        st.query_params["page"] = "data"
        st.rerun()

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
