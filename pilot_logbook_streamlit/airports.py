from __future__ import annotations

import json
from dataclasses import dataclass

from storage import AIRPORTS_FILE


@dataclass(frozen=True)
class Airport:
    code: str
    name: str
    municipality: str
    country: str
    kind: str
    lat: float
    lon: float


def load_airports() -> dict[str, Airport]:
    if AIRPORTS_FILE.exists():
        rows = json.loads(AIRPORTS_FILE.read_text())
        return {
            row["code"]: Airport(
                row["code"],
                row["name"],
                row.get("municipality", ""),
                row.get("country", ""),
                row.get("type", ""),
                float(row["lat"]),
                float(row["lon"]),
            )
            for row in rows
        }
    return {}


AIRPORTS = load_airports()


def airport_label(code: str) -> str:
    airport = AIRPORTS.get(code)
    if not airport:
        return code
    place = f"{airport.municipality}, {airport.country}" if airport.municipality else airport.country
    return f"{airport.code} - {airport.name} ({place})"


def recent_codes(flights: list[dict], field: str, limit: int = 8) -> list[str]:
    seen = []
    for flight in sorted(flights, key=lambda item: item.get("date", ""), reverse=True):
        code = flight.get(field)
        if code in AIRPORTS and code not in seen:
            seen.append(code)
    return seen[:limit]


def airport_options_with_recent(flights: list[dict], field: str) -> list[tuple[str, str]]:
    recent = recent_codes(flights, field)
    options = [(code, "Recent") for code in recent]
    options.extend((code, "All") for code in sorted(AIRPORTS) if code not in recent)
    return options


def option_code(option: tuple[str, str]) -> str:
    return option[0]


def option_label(option: tuple[str, str]) -> str:
    code, group = option
    return f"{group} | {airport_label(code)}"
