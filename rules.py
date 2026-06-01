from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pandas as pd

from airports import AIRPORTS


def parse_iso(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def format_duration(minutes: int | float) -> str:
    minutes = int(minutes)
    hours, remainder = divmod(minutes, 60)
    return f"{hours}h {remainder:02d}m"


def rounded_utc_now(step_minutes: int = 5) -> str:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    discard = timedelta(minutes=now.minute % step_minutes)
    rounded = now - discard
    if discard >= timedelta(minutes=step_minutes / 2):
        rounded += timedelta(minutes=step_minutes)
    return rounded.strftime("%Y-%m-%d %H:%M UTC")


def minutes_between(start: str, end: str) -> int:
    start_dt = datetime.strptime(start, "%Y-%m-%d %H:%M UTC").replace(tzinfo=UTC)
    end_dt = datetime.strptime(end, "%Y-%m-%d %H:%M UTC").replace(tzinfo=UTC)
    return max(0, int((end_dt - start_dt).total_seconds() // 60))


def split_minutes(total: int, parts: int) -> list[int]:
    if parts <= 1:
        return [int(total)]
    base, remainder = divmod(int(total), parts)
    return [base + (1 if index < remainder else 0) for index in range(parts)]


def route_airports(departure: str, route_events: list[dict], arrival: str) -> list[str]:
    codes = [departure]
    codes.extend(event["airport"] for event in route_events if event.get("airport"))
    codes.append(arrival)
    return codes


def route_event_landing_count(route_events: list[dict]) -> int:
    return sum(int(event.get("landing_count", 1)) for event in route_events if event.get("count_as_landing", True))


def build_sector_flights(base_flight: dict, route_events: list[dict] | None = None, boundary_times: list[str] | None = None) -> list[dict]:
    route_events = route_events or []
    codes = route_airports(base_flight["departure"], route_events, base_flight["arrival"])
    sectors = max(1, len(codes) - 1)
    if sectors == 1:
        flight = dict(base_flight)
        flight["route_events"] = []
        return [flight]

    pic_minutes = sector_minutes(base_flight.get("pic_minutes", 0), sectors, boundary_times)
    dual_minutes = split_minutes(base_flight.get("dual_minutes", 0), sectors)
    night_minutes = split_minutes(base_flight.get("night_minutes", 0), sectors)
    landings = sector_landings(int(base_flight.get("landings", 0)), route_events, sectors)
    group_id = str(uuid4())

    rows = []
    for index in range(sectors):
        row = dict(base_flight)
        row["departure"] = codes[index]
        row["arrival"] = codes[index + 1]
        row["pic_minutes"] = pic_minutes[index]
        row["dual_minutes"] = dual_minutes[index]
        row["night_minutes"] = night_minutes[index]
        row["landings"] = landings[index]
        row["route_events"] = []
        row["sector_group"] = group_id
        row["sector_index"] = index + 1
        row["sector_count"] = sectors
        if boundary_times:
            row["departure_utc"] = boundary_times[index]
            row["arrival_utc"] = boundary_times[index + 1]
        if index < len(route_events):
            row["sector_event"] = route_events[index]
        rows.append(row)
    return rows


def sector_minutes(total: int, sectors: int, boundary_times: list[str] | None) -> list[int]:
    if not boundary_times or len(boundary_times) != sectors + 1:
        return split_minutes(total, sectors)
    values = [
        minutes_between(boundary_times[index], boundary_times[index + 1])
        for index in range(sectors)
    ]
    return values if sum(values) > 0 else split_minutes(total, sectors)


def sector_landings(total_landings: int, route_events: list[dict], sectors: int) -> list[int]:
    implied = route_event_landing_count(route_events) + 1
    remaining = max(total_landings, implied)
    values = []
    for index in range(sectors):
        expected = 1 if index == sectors - 1 else int(route_events[index].get("landing_count", 1))
        value = min(expected, remaining)
        values.append(value)
        remaining -= value
    if remaining > 0:
        values[-1] += remaining
    return values


def deadline_status(deadline: dict) -> tuple[int, str]:
    days_left = (parse_iso(deadline["expires"]) - date.today()).days
    if days_left < 0:
        return days_left, "Expired"
    if days_left <= int(deadline["remind_days"]):
        return days_left, "Action needed"
    return days_left, "OK"


def deadline_rows(deadlines: list[dict]) -> pd.DataFrame:
    rows = []
    for deadline in deadlines:
        days_left, status = deadline_status(deadline)
        rows.append(
            {
                "Name": deadline["name"],
                "Category": deadline["category"],
                "Expires": deadline["expires"],
                "Reminder": f"{deadline['remind_days']} days before",
                "Days left": days_left,
                "Status": status,
                "Notes": deadline["notes"],
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("Days left")


def route_rows(flights: list[dict]) -> list[dict]:
    rows = []
    for flight in flights:
        codes = route_airports(flight["departure"], flight.get("route_events", []), flight["arrival"])
        airports = [AIRPORTS.get(code) for code in codes]
        if any(airport is None for airport in airports):
            continue
        rows.append(
            {
                "from": codes[0],
                "to": codes[-1],
                "date": flight["date"],
                "path": [[airport.lon, airport.lat] for airport in airports if airport],
            }
        )
    return rows


def airport_rows(flights: list[dict]) -> pd.DataFrame:
    used_codes = {f["departure"] for f in flights} | {f["arrival"] for f in flights}
    for flight in flights:
        used_codes.update(event["airport"] for event in flight.get("route_events", []) if event.get("airport"))
    rows = [
        {"code": airport.code, "name": airport.name, "lat": airport.lat, "lon": airport.lon}
        for airport in AIRPORTS.values()
        if airport.code in used_codes
    ]
    return pd.DataFrame(rows)


def display_flights(flights: list[dict], profiles: dict) -> pd.DataFrame:
    rows = []
    for flight in flights:
        registration = flight.get("aircraft_registration", "Unknown")
        profile = profiles.get(registration, {})
        pic = int(flight.get("pic_minutes", 0))
        dual = int(flight.get("dual_minutes", 0))
        rows.append(
            {
                "Date": flight["date"],
                "Aircraft": registration,
                "Type": profile.get("type", "Unknown"),
                "Sector": sector_label(flight),
                "Departure": flight["departure"],
                "Arrival": flight["arrival"],
                "Via": route_event_summary(flight.get("route_events", [])),
                "PIC": format_duration(pic),
                "Dual": format_duration(dual),
                "Night": format_duration(flight.get("night_minutes", 0)),
                "Total": format_duration(pic + dual),
                "Landings": flight["landings"],
                "Remarks": flight["remarks"],
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("Date", ascending=False)


def sector_label(flight: dict) -> str:
    if not flight.get("sector_count"):
        return ""
    return f"{flight['sector_index']}/{flight['sector_count']}"


def route_event_summary(events: list[dict]) -> str:
    labels = []
    for event in events:
        kind = "T&G" if event.get("type") == "touch_and_go" else "Stop"
        count = int(event.get("landing_count", 1))
        count_label = f" x{count}" if count > 1 else ""
        time = event.get("logged_utc") or event.get("planned_utc") or ""
        suffix = f" {time}" if time else ""
        labels.append(f"{kind} {event.get('airport', '')}{count_label}{suffix}")
    return ", ".join(labels)


def pax_currency(flights: list[dict], rule: dict) -> dict:
    lookback_days = int(rule.get("lookback_days", 90))
    required = int(rule.get("required_landings", 3))
    airport = rule.get("airport", "").strip().upper()
    today = date.today()
    start = date.today() - timedelta(days=lookback_days)
    relevant = []
    for flight in flights:
        flight_date = parse_iso(flight["date"])
        if flight_date < start or flight_date > today:
            continue
        if airport and airport not in {flight.get("departure"), flight.get("arrival")}:
            continue
        relevant.append(flight)
    landings = sum(int(flight.get("landings", 0)) for flight in relevant)
    return {
        "rule": rule["name"],
        "airport": airport or "General",
        "lookback_days": lookback_days,
        "required_landings": required,
        "landings": landings,
        "ok": landings >= required,
        "missing": max(0, required - landings),
    }
