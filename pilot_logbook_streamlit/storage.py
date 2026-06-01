from __future__ import annotations

import json
import re
from pathlib import Path


APP_DIR = Path(__file__).parent
DATA_FILE = APP_DIR / "logbook_data.json"
AIRPORTS_FILE = APP_DIR / "airports_fr_ch.json"
AIRCRAFT_IMAGE_DIR = APP_DIR / "aircraft_images"


DEFAULT_DATA = {
    "flights": [
        {
            "date": "2026-05-18",
            "aircraft_registration": "HB-KDA",
            "departure": "LSGG",
            "arrival": "LSZH",
            "pic_minutes": 66,
            "dual_minutes": 0,
            "night_minutes": 0,
            "landings": 1,
            "route_events": [],
            "remarks": "Cross-country flight",
        }
    ],
    "aircraft_profiles": {
        "HB-KDA": {
            "registration": "HB-KDA",
            "type": "DA40",
            "manufacturer": "Diamond",
            "category": "SEP",
            "notes": "",
            "image_path": "",
        }
    },
    "deadlines": [
        {
            "name": "Class 2 medical",
            "category": "Medical",
            "expires": "2026-09-30",
            "remind_days": 60,
            "notes": "Book AME appointment early.",
        },
        {
            "name": "SEP rating",
            "category": "Licence / rating",
            "expires": "2027-03-31",
            "remind_days": 90,
            "notes": "Check refresher requirements.",
        },
    ],
    "currency_rules": [
        {
            "name": "Default pax currency",
            "airport": "",
            "lookback_days": 90,
            "required_landings": 3,
            "notes": "Standard passenger-carrying check.",
        },
        {
            "name": "LFLI pax currency",
            "airport": "LFLI",
            "lookback_days": 45,
            "required_landings": 3,
            "notes": "Local stricter check.",
        },
    ],
}


def decimal_hours_to_minutes(value: float) -> int:
    return int(round(value * 60))


def load_data() -> dict:
    if not DATA_FILE.exists():
        save_data(DEFAULT_DATA)
    data = json.loads(DATA_FILE.read_text())
    if migrate_data(data):
        save_data(data)
    return data


def save_data(data: dict) -> None:
    DATA_FILE.write_text(json.dumps(data, indent=2))


def migrate_data(data: dict) -> bool:
    changed = False
    data.setdefault("flights", [])
    data.setdefault("deadlines", [])
    data.setdefault("currency_rules", DEFAULT_DATA["currency_rules"])
    profiles = data.setdefault("aircraft_profiles", {})

    for profile in profiles.values():
        if "image_path" not in profile:
            profile["image_path"] = ""
            changed = True

    for flight in data["flights"]:
        old_registration = flight.pop("aircraft", None)
        old_type = flight.pop("type", None)
        if old_registration and "aircraft_registration" not in flight:
            flight["aircraft_registration"] = old_registration
            changed = True
        registration = flight.get("aircraft_registration", "Unknown")
        if registration not in profiles:
            profiles[registration] = {
                "registration": registration,
                "type": old_type or "Unknown",
                "manufacturer": "",
                "category": "",
                "notes": "",
                "image_path": "",
            }
            changed = True
        elif old_type and profiles[registration].get("type") in {"", "Unknown"}:
            profiles[registration]["type"] = old_type
            changed = True
        for prefix in ("pic", "dual", "night"):
            old_key = f"{prefix}_hours"
            new_key = f"{prefix}_minutes"
            if new_key not in flight:
                flight[new_key] = decimal_hours_to_minutes(float(flight.pop(old_key, 0)))
                changed = True
            elif old_key in flight:
                flight.pop(old_key)
                changed = True
        if "route_events" not in flight:
            flight["route_events"] = []
            changed = True
    return changed


def save_aircraft_image(registration: str, uploaded_file) -> str:
    if uploaded_file is None:
        return ""
    AIRCRAFT_IMAGE_DIR.mkdir(exist_ok=True)
    suffix = Path(uploaded_file.name).suffix.lower() or ".jpg"
    safe_registration = re.sub(r"[^A-Z0-9-]+", "_", registration.upper())
    image_path = AIRCRAFT_IMAGE_DIR / f"{safe_registration}{suffix}"
    image_path.write_bytes(uploaded_file.getbuffer())
    return str(image_path)


def delete_aircraft_image(profile: dict) -> None:
    image_path = profile.get("image_path")
    if not image_path:
        return
    path = Path(image_path)
    if path.exists() and path.is_file() and AIRCRAFT_IMAGE_DIR in path.parents:
        path.unlink()
