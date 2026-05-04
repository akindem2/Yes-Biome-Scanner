import os
import json
import time

APPDATA = os.getenv("LOCALAPPDATA")

if not APPDATA:
    APPDATA = os.path.join(os.path.expanduser("~"), "AppData", "Local")

SETTINGS_DIR  = os.path.join(APPDATA, "YesBiomeScanner")
SETTINGS_PATH = os.path.join(SETTINGS_DIR, "settings.json")

print(f"\n[SETTINGS] Currently reading/writing settings from: {SETTINGS_PATH}\n")

LOG_PATH_DEFAULT = os.path.join(APPDATA, "Roblox", "logs")

# Biomes with per-webhook role ID fields.
# glitched / cyberspace / dreamspace excluded — they always ping @everyone.
BIOME_ROLE_ID_KEYS = (
    "sand storm", "hell", "starfall", "heaven",
    "corruption", "null", "snowy", "windy", "rainy", "eggland",
    "singularity",
)

# All biomes (used for enabled_biomes default)
BIOME_ALL_KEYS = (
    "sand storm", "hell", "starfall", "heaven", "corruption", "null",
    "dreamspace", "glitched", "cyberspace", "snowy", "windy", "rainy", "eggland",
    "singularity",
)

MERCHANT_ROLE_ID_KEYS = ("mari", "jester", "rin")

DEFAULT_WEBHOOK = {
    "name":              "",
    "url":               "",
    "delay_ms":          0,
    "biome_accounts":    [],
    "merchant_accounts":[],
    "biome_role_ids":    {k: "" for k in BIOME_ROLE_ID_KEYS},
    "merchant_role_ids": {k: "" for k in MERCHANT_ROLE_ID_KEYS},
    "enabled_biomes":    list(BIOME_ALL_KEYS),
}

DEFAULT_SETTINGS = {
    "webhooks": [],
    "players":  {},
    "general": {
        "log_path":           LOG_PATH_DEFAULT,
        "scan_interval":      1,
        "auto_cleanup":       True,
        "anti_afk_interval":  300,
        "auto_launch_delay":  5,
        "theme":              "Classic",
        "merchant_mode":      "Log-Based"
    },
    "merchant_detection": {
        "scan_interval": 2,
        "merchants": [
            {"name": "Mari",   "message": "[Merchant]: Mari has arrived on the island...",    "color": "#ffffff", "role_id": ""},
            {"name": "Jester", "message": "[Merchant]: Jester has arrived on the island!!.",  "color": "#9834eb", "role_id": ""},
            {"name": "Rin",    "message": "[Merchant]: Rin has arrived on the island!!.",     "color": "#ffa569", "role_id": ""},
        ]
    },
    "bes": {
        "cpu_limit":       50,
        "cycle_ms":        20,
        "exempt_accounts": []
    },
    "auto_item": {
        "tick_interval":       60.0,
        "click_delay":         0.2,
        "disable_mouse_move":  True,
        "users":               [],
        "items":               [
            {
                "name": "Strange Controller",
                "amount": 1,
                "cooldown": 3600.0,
                "biomes": [],
                "enabled": True,
                "alert_enabled": False,
                "alert_webhook": "",
                "alert_lead_s": 15.0,
                "alert_message": ""
            },
            {
                "name": "Biome Randomizeer",
                "amount": 1,
                "cooldown": 7200.0,
                "biomes": [],
                "enabled": True,
                "alert_enabled": False,
                "alert_webhook": "",
                "alert_lead_s": 15.0,
                "alert_message": ""
            }
        ],
        "coords": {
            "inv_button":   {"x": 0.0, "y": 0.0},
            "items_tab":    {"x": 0.0, "y": 0.0},
            "search_box":   {"x": 0.0, "y": 0.0},
            "query_pos":    {"x": 0.0, "y": 0.0},
            "amount_box":   {"x": 0.0, "y": 0.0},
            "use_button":   {"x": 0.0, "y": 0.0},
            "close_button": {"x": 0.0, "y": 0.0},
            "conditional": {
                "enabled":   False,
                "point":     {"x": 0.0, "y": 0.0},
                "color":     "#FFFFFF",
                "tolerance": 10,
            },
        },
    },
}

_cached_settings = None
_last_load_time  = 0


def _normalize_players(players):
    normalized = {}
    
    # Crash-proof check: If the settings file is corrupted and players isn't a dictionary, ignore it
    if not isinstance(players, dict):
        return normalized
        
    for name, value in players.items():
        if isinstance(value, dict):
            normalized[name] = {
                "pslink":         value.get("pslink", ""),
                "cookie":         value.get("cookie", ""),
                "auto_launch":    value.get("auto_launch", True),
                "cookie_invalid": value.get("cookie_invalid", False),
            }
        else:
            normalized[name] = {
                "pslink":         value if value is not None else "",
                "cookie":         "",
                "auto_launch":    True,
                "cookie_invalid": False,
            }
    return normalized


def _normalize_webhook(wh: dict) -> dict:
    """Ensure a webhook entry has all required keys with correct defaults."""
    if not isinstance(wh, dict):
        return {
            "name": "", 
            "url": "",
            "delay_ms": 0,
            "biome_accounts": [], 
            "merchant_accounts":[],
            "biome_role_ids":    {k: "" for k in BIOME_ROLE_ID_KEYS},
            "merchant_role_ids": {k: "" for k in MERCHANT_ROLE_ID_KEYS},
            "enabled_biomes":    list(BIOME_ALL_KEYS),
        }

    biome_role_ids = dict(wh.get("biome_role_ids") or {})
    for k in BIOME_ROLE_ID_KEYS:
        biome_role_ids.setdefault(k, "")

    merchant_role_ids = dict(wh.get("merchant_role_ids") or {})
    for k in MERCHANT_ROLE_ID_KEYS:
        merchant_role_ids.setdefault(k, "")

    enabled_biomes = wh.get("enabled_biomes")
    if not isinstance(enabled_biomes, list):
        enabled_biomes = list(BIOME_ALL_KEYS)
    else:
        # Add any biomes introduced after this webhook was saved.
        existing = set(enabled_biomes)
        for k in BIOME_ALL_KEYS:
            if k not in existing:
                enabled_biomes.append(k)
        
    try:
        delay = int(wh.get("delay_ms", 0))
    except (ValueError, TypeError):
        delay = 0

    return {
        "name":              wh.get("name", ""),
        "url":               wh.get("url", ""),
        "delay_ms":          delay,
        "biome_accounts":    list(wh.get("biome_accounts") or[]),
        "merchant_accounts": list(wh.get("merchant_accounts") or[]),
        "biome_role_ids": biome_role_ids,
        "merchant_role_ids": merchant_role_ids,
        "enabled_biomes": enabled_biomes,
    }


def _migrate_webhooks(data):
    """
    Migrations applied in order:
    1. Legacy per-player webhook fields → named webhooks.
    2. Old single "accounts" key → split biome_accounts + merchant_accounts.
    3. Wipe global role_ids (now per-webhook, start blank).
    4. Remove legacy top-level webhook_url.
    5. Normalize all webhook entries.
    """
    # Step 1: per-player webhook → named webhooks
    if not data.get("webhooks"):
        players   = data.get("players", {})
        migrated: list = []
        seen_urls: set = set()

        for name, info in players.items():
            if not isinstance(info, dict):
                continue
            url = info.get("webhook", "").strip()
            if not url:
                continue
            existing = next((w for w in migrated if w["url"] == url), None)
            if existing:
                if name not in existing["biome_accounts"]:
                    existing["biome_accounts"].append(name)
                if name not in existing["merchant_accounts"]:
                    existing["merchant_accounts"].append(name)
            elif url not in seen_urls:
                migrated.append({
                    **DEFAULT_WEBHOOK,
                    "name":              f"Webhook {len(migrated) + 1}",
                    "url":               url,
                    "biome_accounts":    [name],
                    "merchant_accounts": [name],
                })
                seen_urls.add(url)

        if migrated:
            data["webhooks"] = migrated
            print(f"[SETTINGS] Migrated {len(migrated)} legacy per-player webhook(s).")

    # Step 2: old "accounts" key → split
    for wh in data.get("webhooks", []):
        if not isinstance(wh, dict):
            continue
        if "accounts" in wh and ("biome_accounts" not in wh or "merchant_accounts" not in wh):
            old = wh.pop("accounts", [])
            wh.setdefault("biome_accounts",   list(old))
            wh.setdefault("merchant_accounts", list(old))

    # Step 3: wipe global role_ids
    data.pop("role_ids", None)

    # Step 4: remove legacy top-level webhook_url
    data.pop("webhook_url", None)

    # Step 5: normalize every webhook entry
    data["webhooks"] = [_normalize_webhook(wh) for wh in data.get("webhooks", [])]

    return data


def _merge_defaults(data, defaults):
    if not isinstance(data, dict):
        return defaults
    merged = dict(data)
    for key, default_value in defaults.items():
        current_value = merged.get(key)
        if isinstance(default_value, dict):
            merged[key] = _merge_defaults(current_value or {}, default_value)
        elif key not in merged:
            merged[key] = default_value
    return merged


def ensure_settings():
    if not os.path.exists(SETTINGS_DIR):
        os.makedirs(SETTINGS_DIR)
    if not os.path.exists(SETTINGS_PATH):
        save_settings(DEFAULT_SETTINGS)


def load_settings(force=False):
    global _cached_settings, _last_load_time

    if not force and _cached_settings and (time.time() - _last_load_time < 5.0):
        return _cached_settings

    ensure_settings()
    try:
        with open(SETTINGS_PATH, "r") as f:
            loaded = json.load(f)
    except Exception:
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS

    merged = _merge_defaults(loaded, DEFAULT_SETTINGS)
    merged["players"] = _normalize_players(merged.get("players", {}))
    merged = _migrate_webhooks(merged)

    if merged != loaded:
        save_settings(merged)

    _cached_settings = merged
    _last_load_time  = time.time()

    return merged


def save_settings(data):
    global _cached_settings, _last_load_time

    if not os.path.exists(SETTINGS_DIR):
        os.makedirs(SETTINGS_DIR)

    with open(SETTINGS_PATH, "w") as f:
        json.dump(data, f, indent=4)

    _cached_settings = data
    _last_load_time  = time.time()

    # Push new snapshot to all workers immediately.
    # Import is local to avoid circular import with config_snapshot.
    try:
        import config_snapshot
        config_snapshot.push(data)
    except Exception:
        pass

def mark_cookie_invalid(player_name: str, invalid: bool = True):
    settings = load_settings(force=True)
    player = settings.get("players", {}).get(player_name)
    if isinstance(player, dict):
        player["cookie_invalid"] = invalid
        save_settings(settings)
