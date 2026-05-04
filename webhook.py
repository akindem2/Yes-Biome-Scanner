import requests
import json
import time
from datetime import datetime, timezone
from settings_manager import load_settings, BIOME_ALL_KEYS, MERCHANT_ROLE_ID_KEYS

import webhook_queue
from webhook_queue import WebhookTask

version      = "1.3.0"
discord_link = "https://discord.gg/fGTNj2sAfA"

BIOMES = {
    "sand storm":  {"color": 0x9e7951, "icon": "https://raw.githubusercontent.com/akindem2/Yes-Biome-Scanner/refs/heads/main/sand%20storm.png", "type": "rare",     "length": 650},
    "hell":        {"color": 0x4a0f0f, "icon": "https://raw.githubusercontent.com/akindem2/Yes-Biome-Scanner/refs/heads/main/hell.png", "type": "rare",     "length": 666},
    "starfall":    {"color": 0x3896d9, "icon": "https://raw.githubusercontent.com/akindem2/Yes-Biome-Scanner/refs/heads/main/starfall.png", "type": "rare",     "length": 600},
    "heaven":      {"color": 0xc4a73d, "icon": "https://raw.githubusercontent.com/akindem2/Yes-Biome-Scanner/refs/heads/main/heaven.png", "type": "rare",     "length": 240},
    "corruption":  {"color": 0x4b1896, "icon": "https://raw.githubusercontent.com/akindem2/Yes-Biome-Scanner/refs/heads/main/corruption.png", "type": "rare",     "length": 650},
    "null":        {"color": 0x4a4a4a, "icon": "https://raw.githubusercontent.com/akindem2/Yes-Biome-Scanner/refs/heads/main/null.png", "type": "rare",     "length": 99},
    "dreamspace":  {"color": 0xe32ddd, "icon": "https://raw.githubusercontent.com/akindem2/Yes-Biome-Scanner/refs/heads/main/dreamspace.png", "type": "everyone", "length": 192},
    "glitched":    {"color": 0x00ff33, "icon": "https://raw.githubusercontent.com/akindem2/Yes-Biome-Scanner/refs/heads/main/glitched.png", "type": "everyone", "length": 164},
    "cyberspace":  {"color": 0x023db3, "icon": "https://raw.githubusercontent.com/akindem2/Yes-Biome-Scanner/refs/heads/main/cyberspace.png", "type": "everyone", "length": 720},
    "snowy":       {"color": 0x99ccff, "icon": "https://raw.githubusercontent.com/akindem2/Yes-Biome-Scanner/refs/heads/main/snowy.png", "type": "common",   "length": 120},
    "windy":       {"color": 0x66ccff, "icon": "https://raw.githubusercontent.com/akindem2/Yes-Biome-Scanner/refs/heads/main/windy.png", "type": "common",   "length": 120},
    "rainy":       {"color": 0x3366ff, "icon": "https://raw.githubusercontent.com/akindem2/Yes-Biome-Scanner/refs/heads/main/rainy.png", "type": "common",   "length": 120},
    "eggland":     {"color": 0xeefc4f, "icon": "https://raw.githubusercontent.com/akindem2/Yes-Biome-Scanner/refs/heads/main/eggland.png", "type": "common"},
    "singularity": {"color": 0x000000, "icon": "https://raw.githubusercontent.com/akindem2/Yes-Biome-Scanner/refs/heads/main/singularity.png", "type": "rare", "length": 1200},
}

MERCHANTS = {
    "mari":   {"icon": "https://raw.githubusercontent.com/akindem2/Yes-Biome-Scanner/refs/heads/main/mari.png"},
    "jester": {"icon": "https://raw.githubusercontent.com/akindem2/Yes-Biome-Scanner/refs/heads/main/jester.png"},
    "rin":    {"icon": "https://raw.githubusercontent.com/akindem2/Yes-Biome-Scanner/refs/heads/main/rin.png"},
}

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

    # Non-blocking enqueue - caller returns immediately.
    # The per-URL worker thread handles delay, send, and retry.
    webhook_queue.enqueue(WebhookTask(
        url=webhook_url,
        embed=embed,
        content=content,
        image_bytes=image_bytes,
        delay_ms=delay_ms,
    ))



# -------------------------------------------------------------------
# BIOME FOUND / ENDED
# -------------------------------------------------------------------
def send_webhook_found_message(biome_name, account_name, ps_link: str = ""):
    if biome_name not in BIOMES:
        return

    biome = BIOMES[biome_name]
    timestamp = (
        f"<t:{int(time.time() + biome['length'])}:R>"
        if "length" in biome else "whenever"
    )

    # ps_link is passed in directly by the caller (scanner.py reads it from
    # player_pslinks which is already in memory).  No settings disk read needed.
    actual_ps = ps_link or ""

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
    ps_link: str = "",
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
    # ps_link supplied by caller — no load_settings() needed here

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
