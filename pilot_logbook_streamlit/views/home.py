from __future__ import annotations

import html
import math
from datetime import date, datetime
import pandas as pd
import pydeck as pdk
import streamlit as st

from airports import AIRPORTS
from i18n import tr
from rules import route_rows, airport_rows, format_duration, pax_currency
from helpers import (
    get_flag_emoji,
    get_airport_flag,
    flight_day_month,
    flight_role,
    display_time,
    compact_duration,
    image_data_url,
    recent_experience_status,
)


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
            get_color=[0, 122, 255, 180],
            get_width=3.5,
            width_min_pixels=3.5,
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
            get_line_width=2.5,
            line_width_min_pixels=2.0,
            get_radius=7.0,
            radius_units="'pixels'",
            pickable=True
        )

        label_layer = pdk.Layer(
            "TextLayer",
            points,
            get_position="[lon, lat]",
            get_text="code",
            get_size=13,
            get_color=[0, 122, 255],
            font_family="'SF Pro Text', '-apple-system', sans-serif",
            font_weight=700,
            get_pixel_offset=[0, -12],
            get_alignment_baseline="'bottom'",
            outline_width=3.0,
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
    
    st.html(
        """
        <style>
        .detail-card-container {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 20px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            box-shadow: var(--card-shadow);
        }
        .detail-route {
            font-size: 1.6rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            color: var(--text-primary);
            margin: 0;
            line-height: 1.2;
        }
        .detail-date {
            color: var(--text-secondary);
            font-size: 0.9rem;
            font-weight: 550;
            margin-top: 0.25rem;
        }
        .detail-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
            gap: 1.2rem;
            margin-top: 1rem;
        }
        .detail-item {
            background: var(--sys-bg-primary);
            border: 1px solid var(--border-light);
            border-radius: 12px;
            padding: 0.65rem 0.85rem;
        }
        .detail-label {
            font-size: 0.72rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            margin-bottom: 0.15rem;
        }
        .detail-value {
            font-size: 1.15rem;
            font-weight: 700;
            color: var(--text-primary);
        }
        .detail-remarks {
            background: var(--sys-bg-primary);
            border: 1px solid var(--border-light);
            border-radius: 12px;
            padding: 1rem;
            margin-top: 1rem;
            font-size: 0.95rem;
            line-height: 1.4;
            color: var(--text-primary);
        }
        </style>
        """
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
            if "selected_flight_index" in st.query_params:
                del st.query_params["selected_flight_index"]
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

    user_id = st.session_state.get("current_user_id", "")
    current_page = st.session_state.get("current_page", "home")
    indexed_flights = sorted(enumerate(flights), key=lambda x: x[1].get("date", ""), reverse=True)
    
    rows_html = []
    for index, flight in indexed_flights:
        day, month = flight_day_month(flight.get("date", ""))
        total_minutes = int(flight.get("pic_minutes", 0)) + int(flight.get("dual_minutes", 0))
        departure = html.escape(flight.get("departure", ""))
        arrival = html.escape(flight.get("arrival", ""))
        role = html.escape(flight_role(flight))
        sector = html.escape(flight.get("sector_index") and f"{flight.get('sector_index')}/{flight.get('sector_count')}" or "")
        xc_chip = '<span class="flight-chip">XC</span>' if departure != arrival else ""
        sector_chip = f'<span class="flight-chip">S{sector}</span>' if sector else ""
        
        # Aircraft Thumbnail logic
        reg = flight.get("aircraft_registration", "")
        profile = profiles.get(reg, {}) if profiles else {}
        image_path = profile.get("image_path", "")
        image_url = image_data_url(image_path) if image_path else ""
        
        if image_url:
            col1_html = f'<img src="{image_url}" class="flight-aircraft-thumb" alt="{html.escape(reg)}">'
        else:
            col1_html = f"""
            <div class="flight-date">
                <div class="flight-day">{html.escape(day)}</div>
                <div class="flight-month">{html.escape(month)}</div>
            </div>
            """
            
        # Departure and Arrival Flags
        dep_flag = get_airport_flag(flight.get("departure", ""))
        arr_flag = get_airport_flag(flight.get("arrival", ""))
        
        dep_display = f"{departure} {dep_flag}".strip()
        arr_display = f"{arr_flag} {arrival}".strip()
        
        # Landings
        landings = int(flight.get("landings", 0))
        landings_badge = f'<span class="flight-chip" style="margin-top: 0.4rem;">☀️ {landings}</span>' if landings > 0 else ""
        
        # Selection link (toggle selection if already selected)
        token = st.session_state.get("session_token", "")
        token_param = f"&session_token={token}" if token else ""
        if selected_idx == index:
            link_href = f"?page={current_page}&account={user_id}{token_param}"
        else:
            link_href = f"?page={current_page}&selected_flight_index={index}&account={user_id}{token_param}"
            
        row_html = f"""
        <a href="{link_href}" target="_self" class="flight-row-link">
            <div class="flight-row">
                <div style="display: flex; align-items: center; justify-content: center;">
                    {col1_html}
                </div>
                <div>
                    <div class="flight-airport">{html.escape(dep_display)}</div>
                    <div class="flight-time">{html.escape(display_time(flight.get("departure_utc")))}</div>
                    <div class="flight-chip-row">
                        <span class="flight-chip flight-chip-primary">{role}</span>{xc_chip}{sector_chip}
                    </div>
                </div>
                <div style="text-align: center;">
                    <div class="flight-duration">— {html.escape(compact_duration(total_minutes))} —</div>
                </div>
                <div>
                    <div class="flight-airport">{html.escape(arr_display)}</div>
                    <div class="flight-time">{html.escape(display_time(flight.get("arrival_utc")))}</div>
                    {landings_badge}
                </div>
                <div class="flight-chevron">
                    ⟩
                </div>
            </div>
        </a>
        """
        rows_html.append(row_html)
        
    st.html(
        f"""
        <div class="flight-list">
            {"".join(rows_html)}
        </div>
        """
    )


def render_home_stat_cards(language: str, flights: list[dict], total_minutes: int, landings: int) -> None:
    airports = len({flight.get("departure") for flight in flights} | {flight.get("arrival") for flight in flights}) if flights else 0
    
    hours = total_minutes // 60
    mins = total_minutes % 60
    totals_formatted = f"{hours}:{mins:02d}"
    
    user_id = st.session_state.get("current_user_id", "")
    token = st.session_state.get("session_token", "")
    token_param = f"&session_token={token}" if token else ""
    
    landings_link = f"?page=home&account={user_id}{token_param}&show_stat=landings"
    hours_link = f"?page=home&account={user_id}{token_param}&show_stat=hours"
    airports_link = f"?page=home&account={user_id}{token_param}&show_stat=airports"
    
    html_block = f"""
    <div class="mockup-stats-row">
        <a href="{landings_link}" target="_self" class="mockup-stat-item">
            <div class="mockup-stat-icon red-bg-icon">✈️</div>
            <div class="mockup-stat-value">{landings}</div>
            <div class="mockup-stat-label">
                {html.escape(tr(language, "landings"))} <span class="mockup-stat-chevron">⟩</span>
            </div>
        </a>
        <a href="{hours_link}" target="_self" class="mockup-stat-item">
            <div class="mockup-stat-icon blue-bg-icon">⏱️</div>
            <div class="mockup-stat-value">{totals_formatted}</div>
            <div class="mockup-stat-label">
                {html.escape(tr(language, "total_time"))} <span class="mockup-stat-chevron">⟩</span>
            </div>
        </a>
        <a href="{airports_link}" target="_self" class="mockup-stat-item">
            <div class="mockup-stat-icon orange-bg-icon">🌐</div>
            <div class="mockup-stat-value">{airports}</div>
            <div class="mockup-stat-label">
                {html.escape(tr(language, "airports"))} <span class="mockup-stat-chevron">⟩</span>
            </div>
        </a>
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
    is_current = experience["ok"]
    
    current_text = tr(language, "current") if is_current else tr(language, "not_current")
    right_class = "status-right-current" if is_current else "status-right-bad"
    badge_circle_class = "status-check-circle" if is_current else "status-warn-circle"
    badge_symbol = "✓" if is_current else "!"
    
    user_id = st.session_state.get("current_user_id", "")
    token = st.session_state.get("session_token", "")
    token_param = f"&session_token={token}" if token else ""
    href = f"?page=currency&account={user_id}{token_param}"
    
    html_block = f"""
    <a href="{href}" target="_self" style="text-decoration: none;">
        <div class="mockup-status-card">
            <div class="status-left">
                <span class="status-pulse-icon">📈</span>
                <span class="status-title">{html.escape(tr(language, "status"))}</span>
            </div>
            <div class="status-right {right_class}">
                <span>{html.escape(current_text)}</span>
                <span class="{badge_circle_class}">{badge_symbol}</span>
                <span class="mockup-stat-chevron">⟩</span>
            </div>
        </div>
    </a>
    """
    st.html(html_block)

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


def render_landings_detail_card(flights: list[dict]) -> None:
    language = st.session_state.language
    st.markdown("### ✈️ " + tr(language, "landings_detail", default="Landings Detail"))
    
    from collections import Counter
    landing_counts = Counter()
    for f in flights:
        arr = f.get("arrival", "").upper().strip()
        lnd = int(f.get("landings", 0))
        if arr and lnd > 0:
            landing_counts[arr] += lnd
            
    if not landing_counts:
        st.info(tr(language, "no_landings", default="No landings logged yet."))
        return
        
    sorted_landings = landing_counts.most_common()
    
    col_close, _ = st.columns([1.5, 4.5])
    if col_close.button("✕ " + tr(language, "close"), key="close_landings_detail", use_container_width=True):
        if "show_stat" in st.query_params:
            del st.query_params["show_stat"]
        st.rerun()
        
    rows = []
    for airport, count in sorted_landings:
        flag = get_airport_flag(airport)
        airport_info = AIRPORTS.get(airport)
        name = airport_info.name if airport_info else ""
        rows.append(
            f"""
            <div style="margin-bottom: 0.75rem; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-light); padding-bottom: 0.5rem;">
                <div>
                    <span style="font-size: 1.1rem; font-weight: 700;">{flag} {html.escape(airport)}</span>
                    <span style="color: var(--text-secondary); margin-left: 0.5rem; font-size: 0.9rem;">{html.escape(name)}</span>
                </div>
                <span class="badge-ok" style="font-size: 0.85rem; font-weight: 700;">{count} landings</span>
            </div>
            """
        )
        
    st.html(
        f"""
        <div class="detail-card-container" style="background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 20px; padding: 1.5rem; margin-bottom: 2rem; box-shadow: var(--card-shadow);">
            <div style="max-height: 300px; overflow-y: auto;">
                {"".join(rows)}
            </div>
        </div>
        """
    )


def render_hours_detail_card(flights: list[dict]) -> None:
    language = st.session_state.language
    st.markdown("### ⏱️ " + tr(language, "hours_detail", default="Flight Hours over Months"))
    
    from collections import Counter
    monthly_minutes = Counter()
    for f in flights:
        f_date = f.get("date", "")
        try:
            year_month = datetime.strptime(f_date, "%Y-%m-%d").strftime("%Y-%m")
        except ValueError:
            continue
        minutes = int(f.get("pic_minutes", 0)) + int(f.get("dual_minutes", 0))
        monthly_minutes[year_month] += minutes
        
    if not monthly_minutes:
        st.info(tr(language, "no_hours", default="No flight hours logged yet."))
        return
        
    col_close, _ = st.columns([1.5, 4.5])
    if col_close.button("✕ " + tr(language, "close"), key="close_hours_detail", use_container_width=True):
        if "show_stat" in st.query_params:
            del st.query_params["show_stat"]
        st.rerun()
        
    # Bar chart
    chart_data = []
    for month, minutes in sorted(monthly_minutes.items()):
        chart_data.append({
            "Month": month,
            "Hours": round(minutes / 60.0, 1)
        })
        
    df = pd.DataFrame(chart_data)
    st.bar_chart(df, x="Month", y="Hours", color="#007aff", use_container_width=True)
    
    rows = []
    for month, minutes in sorted(monthly_minutes.items(), reverse=True):
        hours, mins = divmod(minutes, 60)
        rows.append(
            f"""
            <div style="margin-bottom: 0.75rem; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-light); padding-bottom: 0.5rem;">
                <span style="font-weight: 600;">{html.escape(month)}</span>
                <span style="font-weight: 700; color: var(--accent);">{hours}:{mins:02d} h</span>
            </div>
            """
        )
        
    st.html(
        f"""
        <div class="detail-card-container" style="background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 20px; padding: 1.5rem; margin-top: 1rem; box-shadow: var(--card-shadow);">
            <div style="max-height: 250px; overflow-y: auto;">
                {"".join(rows)}
            </div>
        </div>
        """
    )


def render_airports_detail_card(flights: list[dict]) -> None:
    language = st.session_state.language
    st.markdown("### 🌐 " + tr(language, "airports_visited", default="Airports Visited"))
    
    from collections import Counter
    airport_visits = Counter()
    for f in flights:
        dep = f.get("departure", "").upper().strip()
        arr = f.get("arrival", "").upper().strip()
        if dep:
            airport_visits[dep] += 1
        if arr:
            airport_visits[arr] += 1
            
    if not airport_visits:
        st.info(tr(language, "no_airports", default="No airports visited yet."))
        return
        
    col_close, _ = st.columns([1.5, 4.5])
    if col_close.button("✕ " + tr(language, "close"), key="close_airports_detail", use_container_width=True):
        if "show_stat" in st.query_params:
            del st.query_params["show_stat"]
        st.rerun()
        
    sorted_airports = airport_visits.most_common()
    rows = []
    for airport, count in sorted_airports:
        flag = get_airport_flag(airport)
        airport_info = AIRPORTS.get(airport)
        name = airport_info.name if airport_info else ""
        rows.append(
            f"""
            <div style="margin-bottom: 0.75rem; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-light); padding-bottom: 0.5rem;">
                <div>
                    <span style="font-size: 1.1rem; font-weight: 700;">{flag} {html.escape(airport)}</span>
                    <span style="color: var(--text-secondary); margin-left: 0.5rem; font-size: 0.9rem;">{html.escape(name)}</span>
                </div>
                <span class="badge-ok" style="font-size: 0.85rem; font-weight: 700; background: var(--accent-bg); color: var(--accent); border-color: var(--accent-border);">{count} visits</span>
            </div>
            """
        )
        
    st.html(
        f"""
        <div class="detail-card-container" style="background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 20px; padding: 1.5rem; margin-bottom: 2rem; box-shadow: var(--card-shadow);">
            <div style="max-height: 300px; overflow-y: auto;">
                {"".join(rows)}
            </div>
        </div>
        """
    )


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

    show_stat = st.query_params.get("show_stat")
    if isinstance(show_stat, list):
        show_stat = show_stat[0] if show_stat else None
    if show_stat == "landings":
        render_landings_detail_card(flights)
    elif show_stat == "hours":
        render_hours_detail_card(flights)
    elif show_stat == "airports":
        render_airports_detail_card(flights)

    render_home_status(language, flights, data["currency_rules"])
    detail_a, detail_b, detail_c = st.columns(3)
    detail_a.metric(tr(language, "pic_time_stat"), format_duration(pic_minutes))
    detail_b.metric(tr(language, "dual_time_stat"), format_duration(dual_minutes))
    detail_c.metric(tr(language, "night_time_stat"), format_duration(night_minutes))
    render_route_map(data, tr(language, "route_map"))
    st.subheader(tr(language, "recent"))
    render_flight_cards(flights, data.get("aircraft_profiles", {}))
