"""
cookie_checker.py

Runs once on startup in a background thread.
Pings the Roblox auth endpoint for every account that has a cookie and
marks invalid ones so the auto-launcher skips them.
"""

import threading
import requests
from settings_manager import load_settings, mark_cookie_invalid

signals = None


def init(sig):
    global signals
    signals = sig


def _log(msg: str):
    try:
        if signals:
            signals.log_message.emit(msg)
    except Exception:
        pass


def _check_all_cookies():
    settings = load_settings(force=True)
    players  = settings.get("players", {})

    for name, data in players.items():
        if not isinstance(data, dict):
            continue

        cookie = data.get("cookie", "").strip()
        if not cookie:
            continue

        try:
            resp = requests.get(
                "https://users.roblox.com/v1/users/authenticated",
                cookies={".ROBLOSECURITY": cookie},
                timeout=10,
            )
            if resp.status_code == 200:
                mark_cookie_invalid(name, invalid=False)
                _log(f"[COOKIE] {name} ✓ valid")
            else:
                mark_cookie_invalid(name, invalid=True)
                _log(f"[COOKIE] {name} ✗ invalid (HTTP {resp.status_code}) — marked as bad")
        except Exception as e:
            _log(f"[COOKIE] {name} check failed: {e}")


def run_startup_check():
    """Kick off the background cookie check. Call once after signals are ready."""
    _log("[COOKIE] Checking all account cookies...")
    threading.Thread(target=_check_all_cookies, daemon=True).start()