from __future__ import annotations

import base64
import html
from datetime import date, datetime, timedelta
from pathlib import Path

from airports import AIRPORTS
from ui_components import normalize_utc_time


def get_flag_emoji(country_code: str) -> str:
    if not country_code or len(country_code) != 2:
        return ""
    return "".join(chr(127397 + ord(c)) for c in country_code.upper())


def get_airport_flag(code: str) -> str:
    airport = AIRPORTS.get(code.upper())
    if airport and airport.country:
        return get_flag_emoji(airport.country)
    return ""


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


def display_time(value: str | None) -> str:
    if not value:
        return "--:--"
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M UTC").strftime("%H:%M")
    except ValueError:
        return value.replace(" UTC", "")


def compact_duration(minutes: int) -> str:
    hours, remainder = divmod(int(minutes), 60)
    return f"{hours}:{remainder:02d}"


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


def image_data_url(image_path: str) -> str:
    if not image_path:
        return ""
    path = Path(image_path)
    if not path.exists() or not path.is_file():
        return ""
    suffix = path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def flight_delete_label(index: int, flights: list[dict], profiles: dict) -> str:
    # Moved helper function from logbook page to keep UI cleaner
    flight = flights[index]
    reg = flight.get("aircraft_registration", "Unknown")
    profile = profiles.get(reg, {}) if profiles else {}
    ac_type = profile.get("type", "Unknown")
    return f"{flight.get('date')} | {flight.get('departure')} ➔ {flight.get('arrival')} ({reg} - {ac_type})"
