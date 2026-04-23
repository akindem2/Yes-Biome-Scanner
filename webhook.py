import requests
import json
import threading
import time
from datetime import datetime, timezone
from settings_manager import load_settings, BIOME_ALL_KEYS, MERCHANT_ROLE_ID_KEYS

version      = "1.2.0"
discord_link = "https://discord.gg/fGTNj2sAfA"

BIOMES = {
    "sand storm":  {"color": 0x9e7951, "icon": "https://i.postimg.cc/RV5j7tTV/Screenshot-2026-01-24-022828.png", "type": "rare",     "length": 650},
    "hell":        {"color": 0x4a0f0f, "icon": "https://i.postimg.cc/J7JFznW4/Screenshot-2026-01-24-022445.png", "type": "rare",     "length": 666},
    "starfall":    {"color": 0x3896d9, "icon": "https://i.postimg.cc/6pHjm4CC/Screenshot-2026-01-24-021625.png", "type": "rare",     "length": 600},
    "heaven":      {"color": 0xc4a73d, "icon": "https://i.postimg.cc/MptNJFJY/Screenshot-2026-01-24-022645.png", "type": "rare",     "length": 240},
    "corruption":  {"color": 0x4b1896, "icon": "https://i.postimg.cc/ncGwqPzd/Screenshot-2026-01-24-022047.png", "type": "rare",     "length": 650},
    "null":        {"color": 0x4a4a4a, "icon": "https://i.postimg.cc/9fK94cH6/Screenshot-2026-01-24-023128.png", "type": "rare",     "length": 99},
    "dreamspace":  {"color": 0xe32ddd, "icon": "https://i.postimg.cc/25nwjyVg/Screenshot-2026-01-25-014034.png", "type": "everyone", "length": 192},
    "glitched":    {"color": 0x00ff33, "icon": "https://i.postimg.cc/jj0Kfn2L/Screenshot-2026-01-25-001319.png", "type": "everyone", "length": 164},
    "cyberspace":  {"color": 0x023db3, "icon": "https://i.postimg.cc/28Bym3tD/Screenshot-2026-01-26-203242.png", "type": "everyone", "length": 720},
    "snowy":       {"color": 0x99ccff, "icon": "https://i.postimg.cc/g0sDYMsP/Screenshot-2026-01-24-144259.png", "type": "common",   "length": 120},
    "windy":       {"color": 0x66ccff, "icon": "https://i.postimg.cc/Y98ysrZR/Screenshot-2026-01-24-144103.png", "type": "common",   "length": 120},
    "rainy":       {"color": 0x3366ff, "icon": "https://i.postimg.cc/wv3bn8pF/Screenshot-2026-01-24-144429.png", "type": "common",   "length": 120},
    "eggland":     {"color": 0xeefc4f, "icon": "https://i.postimg.cc/66jdjhyg/Screenshot-2026-03-28-183948.png", "type": "common"},
}

MERCHANTS = {
    "mari":   {"icon": "https://i.postimg.cc/ryjLBcx5/Screenshot-2026-01-24-143823.png"},
    "jester": {"icon": "https://i.postimg.cc/rw0XRrbH/Screenshot-2026-01-24-143919.png"},
    "rin":    {"icon": "https://static.wikia.nocookie.net/sol-rng/images/0/04/RinHeadShot.png/revision/latest?cb=20260214165200"},
}

# -------------------------------------------------------------------
# THREADING & DELAY LOGIC
# -------------------------------------------------------------------
_webhook_locks = {}
_webhook_last_sent = {}
_global_webhook_lock = threading.Lock()

def _get_url_lock(url):
    with _global_webhook_lock:
        if url not in _webhook_locks:
            _webhook_locks[url] = threading.Lock()
        return _webhook_locks[url]

def _get_all_unique_webhooks() -> dict[str, int]:
    settings = load_settings()
    urls: dict[str, int] = {}
    for wh in settings.get("webhooks", []):
        if not isinstance(wh, dict):
            continue
        url = wh.get("url", "").strip()
        if url:
            urls[url] = max(urls.get(url, 0), wh.get("delay_ms", 0))
    return urls

def _get_biome_webhooks_for_player(account_name: str) -> list[tuple[str, dict]]:
    settings = load_settings()
    results: list[tuple[str, dict]] = []
    seen: set[str] = set()

    for wh in settings.get("webhooks", []):
        if not isinstance(wh, dict):
            continue
        if account_name in wh.get("biome_accounts", []):
            url = wh.get("url", "").strip()
            if url and url not in seen:
                results.append((url, wh))
                seen.add(url)

    return results

def _get_merchant_webhooks_for_player(account_name: str) -> list[tuple[str, dict]]:
    settings = load_settings()
    results: list[tuple[str, dict]] = []
    seen: set[str] = set()

    for wh in settings.get("webhooks", []):
        if not isinstance(wh, dict):
            continue
        if account_name in wh.get("merchant_accounts", []):
            url = wh.get("url", "").strip()
            if url and url not in seen:
                results.append((url, wh))
                seen.add(url)

    return results

# -------------------------------------------------------------------
# START / STOP / TEST
# -------------------------------------------------------------------
def send_start_webhook(num_accounts):
    urls_with_delays = _get_all_unique_webhooks()
    if not urls_with_delays:
        return

    embed = {
        "title":       "BIOME SCANNER STARTED",
        "description": f"Scanner successfully started! Tracking `{num_accounts}` accounts.",
        "color":       0x2ECC71,
        "footer":      {"text": f"Yes Biome Scanner v{version} | {discord_link}"}
    }
    for url, delay in urls_with_delays.items():
        send_webhook(embed, url, delay_ms=delay)


def send_stop_webhook():
    urls_with_delays = _get_all_unique_webhooks()
    if not urls_with_delays:
        return

    embed = {
        "title":  "BIOME SCANNER STOPPED",
        "color":  0xE74C3C,
        "footer": {"text": f"Yes Biome Scanner v{version} | {discord_link}"}
    }
    for url, delay in urls_with_delays.items():
        send_webhook(embed, url, delay_ms=delay)


def send_test_webhook(url: str) -> tuple[bool, str]:
    """Send a test message to a specific webhook URL."""
    if not url:
        return False, "No URL provided."

    embed = {
        "title":       "✅ Test Message",
        "description": "This is a test message from Yes Biome Scanner. Your webhook is working correctly!",
        "color":       0x2ECC71,
        "footer":      {"text": f"Yes Biome Scanner v{version} | {discord_link}"}
    }
    try:
        resp = requests.post(url, json={"embeds": [embed]}, timeout=10)
        if resp.status_code in (200, 204):
            return True, "Test message sent successfully!"
        return False, f"Discord returned HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return False, str(e)

# -------------------------------------------------------------------
# CORE SEND
# -------------------------------------------------------------------
def send_webhook(embed, webhook_url, content=None, image_bytes=None, delay_ms=0):
    if not webhook_url:
        return

    url_lock = _get_url_lock(webhook_url)
    with url_lock:
        if delay_ms > 0:
            delay_s = delay_ms / 1000.0
            now = time.time()
            last_sent = _webhook_last_sent.get(webhook_url, 0)
            elapsed = now - last_sent
            if elapsed < delay_s:
                time.sleep(delay_s - elapsed)

        try:
            payload = {"embeds": [embed]}
            if content:
                payload["content"] = content
            if image_bytes:
                requests.post(
                    webhook_url,
                    data={"payload_json": json.dumps(payload)},
                    files={"file": ("screenshot.png", image_bytes, "image/png")},
                )
            else:
                requests.post(webhook_url, json=payload)
        except Exception as e:
            print("[WEBHOOK ERROR]", e)
        finally:
            _webhook_last_sent[webhook_url] = time.time()

# -------------------------------------------------------------------
# BIOME FOUND / ENDED
# -------------------------------------------------------------------
def send_webhook_found_message(biome_name, account_name, ps_link):
    if biome_name not in BIOMES:
        return

    biome = BIOMES[biome_name]
    timestamp = (
        f"<t:{int(time.time() + biome['length'])}:R>"
        if "length" in biome else "whenever"
    )

    settings    = load_settings()
    player_data = settings.get("players", {}).get(account_name, {})
    actual_ps   = player_data.get("pslink", "") if isinstance(player_data, dict) else ""

    webhook_entries = _get_biome_webhooks_for_player(account_name)
    if not webhook_entries:
        return

    embed = {
        "title":     f"{biome_name.upper()} BIOME FOUND!",
        "color":     biome["color"],
        "thumbnail": {"url": biome["icon"]},
        "fields": [
            {"name": "ACCOUNT",     "value": account_name,             "inline": False},
            {"name": "SERVER LINK", "value": actual_ps or "Not Found", "inline": False},
            {"name": "TIME OVER",   "value": f"{timestamp} | May be Incorrect", "inline": False},
        ],
        "footer": {"text": f"Yes Biome Scanner v{version} | {discord_link}"}
    }

    for url, wh in webhook_entries:
        enabled_biomes = wh.get("enabled_biomes", list(BIOME_ALL_KEYS))
        if biome_name not in enabled_biomes:
            continue

        if biome["type"] == "everyone":
            content = "@everyone"
        else:
            role_id = str(wh.get("biome_role_ids", {}).get(biome_name, "") or "").strip()
            content = f"<@&{role_id}>" if role_id else None

        delay = wh.get("delay_ms", 0)
        send_webhook(embed, url, content=content, delay_ms=delay)

def send_webhook_ended_message(biome_name, account_name):
    if biome_name not in BIOMES:
        return

    biome     = BIOMES[biome_name]
    timestamp = datetime.now(timezone.utc).isoformat()

    embed = {
        "title":     f"{biome_name.upper()} BIOME ENDED!",
        "color":     biome["color"],
        "thumbnail": {"url": biome["icon"]},
        "timestamp": timestamp,
        "fields": [{"name": "ACCOUNT", "value": account_name, "inline": False}],
        "footer": {"text": f"Yes Biome Scanner v{version} | {discord_link}"}
    }

    webhook_entries = _get_biome_webhooks_for_player(account_name)
    for url, wh in webhook_entries:
        enabled_biomes = wh.get("enabled_biomes", list(BIOME_ALL_KEYS))
        if biome_name not in enabled_biomes:
            continue

        delay = wh.get("delay_ms", 0)
        send_webhook(embed, url, delay_ms=delay)

# -------------------------------------------------------------------
# MERCHANT DETECTED
# -------------------------------------------------------------------
def send_merchant_detected_message(
    merchant_name,
    configured_message,
    configured_color,
    configured_role_id,
    account_name,
    detected_text,
    detected_color=None,
    chat_image_bytes=None,
    show_image: bool = True,
):
    """
    Send a merchant-detected webhook embed.

    show_image=True  (default): attach chat_image_bytes if present, otherwise
                                fall back to the merchant's icon URL.
                                Used by the OCR detector.
    show_image=False:           omit image entirely.
                                Used by the log-based detector which has no
                                screenshot to share.
    """
    settings    = load_settings()
    player_data = settings.get("players", {}).get(account_name, {})
    ps_link     = player_data.get("pslink", "") if isinstance(player_data, dict) else (player_data or "")

    webhook_entries = _get_merchant_webhooks_for_player(account_name)
    if not webhook_entries:
        return

    merchant = MERCHANTS.get(merchant_name.lower(), {})
    icon_url = merchant.get("icon")

    try:
        embed_color = int(str(configured_color).lstrip("#"), 16)
    except ValueError:
        if detected_color:
            embed_color = (
                (int(detected_color[0]) << 16)
                | (int(detected_color[1]) << 8)
                | int(detected_color[2])
            )
        else:
            embed_color = 0xF1C40F

    timestamp = f"<t:{int(time.time() + 180)}:R>"

    embed = {
        "title": f"{merchant_name.upper()} DETECTED!",
        "color": embed_color,
        "fields": [
            {"name": "ACCOUNT",           "value": account_name or "Unknown account", "inline": False},
            {"name": "SERVER LINK",       "value": ps_link or "Not Found",            "inline": False},
            {"name": "TIME OF DEPARTURE", "value": timestamp,                          "inline": False},
        ],
        "footer": {"text": f"Yes Biome Scanner v{version} | {discord_link}"}
    }

    if show_image:
        if chat_image_bytes:
            embed["image"] = {"url": "attachment://screenshot.png"}
        elif icon_url:
            embed["image"] = {"url": icon_url}

    for url, wh in webhook_entries:
        role_id = str(wh.get("merchant_role_ids", {}).get(merchant_name.lower(), "") or "").strip()
        content = f"<@&{role_id}>" if role_id else None

        delay = wh.get("delay_ms", 0)
        send_webhook(
            embed, url,
            content=content,
            image_bytes=chat_image_bytes if show_image else None,
            delay_ms=delay,
        )
