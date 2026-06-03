from __future__ import annotations

import hashlib
import json
from copy import deepcopy
import re
from pathlib import Path


APP_DIR = Path(__file__).parent
DATA_FILE = APP_DIR / "logbook_data.json"
AIRPORTS_FILE = APP_DIR / "airports_fr_ch.json"
AIRCRAFT_IMAGE_DIR = APP_DIR / "aircraft_images"

ACTIVE_SESSIONS: dict[str, str] = {}


def default_aircraft_image_path(registration: str) -> str:
    image_path = AIRCRAFT_IMAGE_DIR / f"{registration}.jpg"
    return str(image_path) if image_path.exists() else ""


DEFAULT_AIRCRAFT_PROFILES = {
    registration: {
        "registration": registration,
        "type": "DR400-120",
        "manufacturer": "Robin",
        "category": "SEP",
        "notes": "Robin DR400 400-120 variant.",
        "image_path": default_aircraft_image_path(registration),
    }
    for registration in ("F-HFLL", "F-HMSA", "F-HFBB", "F-HTMY")
}


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

DEMO_USER_ID = "demo"
DEMO_PASSWORD_HASH = hashlib.sha256("demo".encode("utf-8")).hexdigest()


def demo_user_data() -> dict:
    return {
        "flights": [
            {
                "date": "2026-05-28",
                "aircraft_registration": "HB-DEMO",
                "departure": "LSGG",
                "arrival": "LFLI",
                "pic_minutes": 42,
                "dual_minutes": 0,
                "night_minutes": 0,
                "landings": 2,
                "route_events": [{"airport": "LFLP", "type": "touch_and_go", "landing_count": 1, "count_as_landing": True}],
                "remarks": "Geneva local currency warm-up.",
            },
            {
                "date": "2026-05-22",
                "aircraft_registration": "HB-DEMO",
                "departure": "LFLI",
                "arrival": "LSGS",
                "pic_minutes": 74,
                "dual_minutes": 0,
                "night_minutes": 0,
                "landings": 1,
                "route_events": [],
                "remarks": "Alpine valley navigation to Sion.",
            },
            {
                "date": "2026-05-14",
                "aircraft_registration": "HB-DEMO",
                "departure": "LSGS",
                "arrival": "LSZA",
                "pic_minutes": 88,
                "dual_minutes": 0,
                "night_minutes": 0,
                "landings": 1,
                "route_events": [],
                "remarks": "Mountain route via Ticino.",
            },
            {
                "date": "2026-05-05",
                "aircraft_registration": "HB-DEMO",
                "departure": "LSZA",
                "arrival": "LSZH",
                "pic_minutes": 66,
                "dual_minutes": 0,
                "night_minutes": 0,
                "landings": 1,
                "route_events": [],
                "remarks": "Lugano to Zurich.",
            },
            {
                "date": "2026-04-27",
                "aircraft_registration": "HB-DEMO",
                "departure": "LSZH",
                "arrival": "LFSB",
                "pic_minutes": 58,
                "dual_minutes": 0,
                "night_minutes": 0,
                "landings": 1,
                "route_events": [],
                "remarks": "Zurich to Basel.",
            },
            {
                "date": "2026-04-16",
                "aircraft_registration": "F-HDEM",
                "departure": "LFSB",
                "arrival": "LFST",
                "pic_minutes": 52,
                "dual_minutes": 0,
                "night_minutes": 0,
                "landings": 1,
                "route_events": [],
                "remarks": "Alsace hop.",
            },
            {
                "date": "2026-04-07",
                "aircraft_registration": "F-HDEM",
                "departure": "LFST",
                "arrival": "LFGJ",
                "pic_minutes": 70,
                "dual_minutes": 0,
                "night_minutes": 0,
                "landings": 1,
                "route_events": [],
                "remarks": "Strasbourg to Jura.",
            },
            {
                "date": "2026-03-29",
                "aircraft_registration": "F-HDEM",
                "departure": "LFGJ",
                "arrival": "LFLL",
                "pic_minutes": 76,
                "dual_minutes": 0,
                "night_minutes": 0,
                "landings": 1,
                "route_events": [],
                "remarks": "Dole to Lyon.",
            },
            {
                "date": "2026-03-18",
                "aircraft_registration": "F-HDEM",
                "departure": "LFLL",
                "arrival": "LFLB",
                "pic_minutes": 44,
                "dual_minutes": 0,
                "night_minutes": 0,
                "landings": 1,
                "route_events": [],
                "remarks": "Lyon to Chambery.",
            },
            {
                "date": "2026-03-08",
                "aircraft_registration": "F-HDEM",
                "departure": "LFLB",
                "arrival": "LFLS",
                "pic_minutes": 46,
                "dual_minutes": 0,
                "night_minutes": 0,
                "landings": 1,
                "route_events": [],
                "remarks": "Chambery to Grenoble.",
            },
            {
                "date": "2026-02-25",
                "aircraft_registration": "F-HDEM",
                "departure": "LFLS",
                "arrival": "LFMN",
                "pic_minutes": 82,
                "dual_minutes": 0,
                "night_minutes": 0,
                "landings": 1,
                "route_events": [],
                "remarks": "Alps to the Riviera.",
            },
            {
                "date": "2026-02-14",
                "aircraft_registration": "F-HDEM",
                "departure": "LFMN",
                "arrival": "LFMD",
                "pic_minutes": 36,
                "dual_minutes": 0,
                "night_minutes": 0,
                "landings": 2,
                "route_events": [],
                "remarks": "Cote d'Azur landing practice.",
            },
        ],
        "aircraft_profiles": {
            "HB-DEMO": {
                "registration": "HB-DEMO",
                "type": "DA40",
                "manufacturer": "Diamond",
                "category": "SEP",
                "notes": "Demo Swiss touring aircraft.",
                "image_path": "",
            },
            "F-HDEM": {
                "registration": "F-HDEM",
                "type": "DR400",
                "manufacturer": "Robin",
                "category": "SEP",
                "notes": "Demo French touring aircraft.",
                "image_path": "",
            },
        },
        "deadlines": [
            {
                "name": "Class 2 medical",
                "category": "Medical",
                "expires": "2026-09-30",
                "remind_days": 60,
                "notes": "Demo reminder: book the AME appointment early.",
            },
            {
                "name": "SEP rating",
                "category": "Licence / rating",
                "expires": "2027-03-31",
                "remind_days": 90,
                "notes": "Demo reminder: plan refresher training.",
            },
            {
                "name": "Club checkout",
                "category": "Currency",
                "expires": "2026-06-20",
                "remind_days": 30,
                "notes": "Demo club deadline.",
            },
        ],
        "currency_rules": deepcopy(DEFAULT_DATA["currency_rules"]),
    }


def decimal_hours_to_minutes(value: float) -> int:
    return int(round(value * 60))


def load_data() -> dict:
    """Load the full application data store.

    The current storage format is multi-user:
    {
        "users": {
            "user@example.com": {
                "flights": [...],
                "aircraft_profiles": {...},
                "deadlines": [...],
                "currency_rules": [...]
            }
        }
    }

    Older single-user JSON files are migrated automatically into a
    temporary legacy account so existing data is not lost.
    """
    if not DATA_FILE.exists():
        save_data({"users": {}})

    data = json.loads(DATA_FILE.read_text())
    changed = migrate_to_multi_user(data)
    if ensure_accounts(data):
        changed = True
    if ensure_demo_account(data):
        changed = True

    for user_data in data.get("users", {}).values():
        if migrate_data(user_data):
            changed = True

    if changed:
        save_data(data)

    return data


def save_data(data: dict) -> None:
    DATA_FILE.write_text(json.dumps(data, indent=2))


def empty_user_data() -> dict:
    """Return a clean empty logbook for a newly created user account."""
    return {
        "flights": [],
        "aircraft_profiles": deepcopy(DEFAULT_AIRCRAFT_PROFILES),
        "deadlines": deepcopy(DEFAULT_DATA["deadlines"]),
        "currency_rules": deepcopy(DEFAULT_DATA["currency_rules"]),
    }


def password_hash(password: str) -> str:
    return hashlib.sha256(str(password or "").encode("utf-8")).hexdigest()


def account_record(user_id: str, username: str | None = None, email: str | None = None, password: str = "") -> dict:
    normalized_user_id = normalize_user_id(user_id)
    return {
        "user_id": normalized_user_id,
        "username": normalize_user_id(username or normalized_user_id.split("@")[0]),
        "email": normalize_user_id(email or normalized_user_id),
        "password_hash": password_hash(password),
    }


def ensure_accounts(data: dict) -> bool:
    changed = False
    data.setdefault("users", {})
    accounts = data.setdefault("accounts", {})
    for user_id in list(data["users"]):
        normalized_user_id = normalize_user_id(user_id)
        if normalized_user_id != user_id:
            data["users"][normalized_user_id] = data["users"].pop(user_id)
            changed = True
        if normalized_user_id not in accounts:
            accounts[normalized_user_id] = account_record(normalized_user_id)
            accounts[normalized_user_id]["password_hash"] = ""
            changed = True
    return changed


def ensure_demo_account(data: dict) -> bool:
    changed = False
    data.setdefault("users", {})
    data.setdefault("accounts", {})
    account = data["accounts"].get(DEMO_USER_ID)
    if not account or account.get("password_hash") != DEMO_PASSWORD_HASH:
        data["accounts"][DEMO_USER_ID] = {
            "user_id": DEMO_USER_ID,
            "username": "demo",
            "email": "demo",
            "password_hash": DEMO_PASSWORD_HASH,
        }
        changed = True
    if DEMO_USER_ID not in data["users"]:
        data["users"][DEMO_USER_ID] = demo_user_data()
        changed = True
    return changed


def migrate_to_multi_user(data: dict) -> bool:
    """Migrate an old single-user data file to the multi-user format."""
    if "users" in data:
        return False

    data["users"] = {
        "legacy@local": {
            "flights": data.get("flights", []),
            "aircraft_profiles": data.get("aircraft_profiles", {}),
            "deadlines": data.get("deadlines", deepcopy(DEFAULT_DATA["deadlines"])),
            "currency_rules": data.get(
                "currency_rules",
                deepcopy(DEFAULT_DATA["currency_rules"]),
            ),
        }
    }

    for key in ("flights", "aircraft_profiles", "deadlines", "currency_rules"):
        data.pop(key, None)

    return True


def get_user_data(data: dict, user_id: str) -> dict:
    """Return the private logbook data for one user, creating it if needed."""
    normalized_user_id = normalize_user_id(user_id)
    data.setdefault("users", {})

    if normalized_user_id not in data["users"]:
        data["users"][normalized_user_id] = empty_user_data()
    data.setdefault("accounts", {})
    if normalized_user_id not in data["accounts"]:
        data["accounts"][normalized_user_id] = account_record(normalized_user_id)
        data["accounts"][normalized_user_id]["password_hash"] = ""

    user_data = data["users"][normalized_user_id]
    migrate_data(user_data)
    return user_data


def find_account(data: dict, login: str) -> dict | None:
    cleaned = normalize_user_id(login)
    for account in data.get("accounts", {}).values():
        if cleaned in {normalize_user_id(account.get("user_id", "")), normalize_user_id(account.get("username", "")), normalize_user_id(account.get("email", ""))}:
            return account
    return None


def authenticate_account(data: dict, login: str, password: str) -> dict | None:
    account = find_account(data, login)
    if not account:
        return None
    stored_hash = account.get("password_hash", "")
    if stored_hash and stored_hash == password_hash(password):
        return account
    return None


def create_account(data: dict, email: str, username: str, password: str) -> tuple[bool, str, str | None]:
    if not str(email or "").strip() or not str(username or "").strip() or not str(password or ""):
        return False, "Add an email, username, and password.", None
    email = normalize_user_id(email)
    username = normalize_user_id(username)
    if find_account(data, email) or find_account(data, username):
        return False, "That email or username already exists.", None

    user_id = email
    data.setdefault("users", {})[user_id] = empty_user_data()
    data.setdefault("accounts", {})[user_id] = account_record(user_id, username=username, email=email, password=password)
    return True, f"Created account {username}.", user_id


def normalize_user_id(user_id: str) -> str:
    """Normalize user identifiers so one account always maps to one key."""
    cleaned = str(user_id or "").strip().lower()
    return cleaned or "anonymous@local"


def migrate_data(data: dict) -> bool:
    changed = False
    data.setdefault("flights", [])
    data.setdefault("deadlines", [])
    data.setdefault("currency_rules", deepcopy(DEFAULT_DATA["currency_rules"]))
    profiles = data.setdefault("aircraft_profiles", {})

    for registration, default_profile in DEFAULT_AIRCRAFT_PROFILES.items():
        if registration not in profiles:
            profiles[registration] = deepcopy(default_profile)
            changed = True
            continue
        profile = profiles[registration]
        for field in ("registration", "type", "manufacturer", "category", "notes"):
            if not profile.get(field):
                profile[field] = default_profile[field]
                changed = True
        if not profile.get("image_path") and default_profile.get("image_path"):
            profile["image_path"] = default_profile["image_path"]
            changed = True

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


def save_new_aircraft_if_needed(data: dict, registration: str, profile: dict, image) -> None:
    if registration in data["aircraft_profiles"]:
        return
    profile["image_path"] = save_aircraft_image(registration, image)
    data["aircraft_profiles"][registration] = profile


def get_current_user_id() -> str | None:
    """Return the active local account id for this session, if set."""
    import streamlit as st
    return st.session_state.get("current_user_id")


def current_account_label(all_data: dict, user_id: str) -> str:
    account = all_data.get("accounts", {}).get(user_id, {})
    username = account.get("username") or user_id
    email = account.get("email") or user_id
    return f"{username} · {email}" if username != email else username


def set_active_account(user_id: str) -> None:
    import streamlit as st
    st.session_state.current_user_id = user_id
    st.query_params["account"] = user_id



