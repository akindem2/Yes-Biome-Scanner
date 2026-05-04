"""
auto_item_manager.py — Wires AutoItemEngine to Yes Biome Scanner's data sources.

Follows the same init/signal pattern as bes_manager.py.
"""

import threading
import time
from typing import Optional

import window_utils
from settings_manager import load_settings
from auto_item_automation import AutoItemEngine
from account_runtime import runtime

# ----------------------------------------------------------------
# Module-level state
# ----------------------------------------------------------------
signals = None
_engine: Optional[AutoItemEngine] = None
_auto_item_running: bool = False

# Cached {player_name: pid} map, refreshed every PID_CACHE_TTL seconds
_pid_cache: dict = {}
_pid_cache_lock = threading.Lock()
_pid_cache_ts: float = 0.0
_PID_CACHE_TTL = 5.0


# ----------------------------------------------------------------
# Providers
# ----------------------------------------------------------------

def _refresh_pid_cache() -> None:
    global _pid_cache, _pid_cache_ts
    try:
        new_cache: dict = {}

        # Prefer the authoritative runtime cache populated by window_poller.
        for name, info in runtime.all_windows().items():
            try:
                pid = int(info.get("pid", 0) or 0)
            except Exception:
                pid = 0
            if pid > 0:
                new_cache[str(name)] = pid

        # Fallback: resolve directly if the runtime cache is empty or stale.
        if not new_cache:
            settings = load_settings()
            tracked = list(settings.get("players", {}).keys())
            log_dir = str(settings.get("general", {}).get("log_path", "") or "")
            pid_hwnd = window_utils.get_roblox_pid_map()   # {pid: hwnd}
            if pid_hwnd and tracked and log_dir:
                resolved = window_utils.resolve_accounts_for_windows(
                    list(pid_hwnd.values()),
                    tracked,
                    log_dir,
                )
                for pid, hwnd in pid_hwnd.items():
                    name = resolved.get(hwnd)
                    if name:
                        new_cache[str(name)] = int(pid)

        with _pid_cache_lock:
            _pid_cache = new_cache
            # Only update timestamp if we got data, so empty cache will retry on next call
            if new_cache:
                _pid_cache_ts = time.time()
    except Exception:
        pass


def _pid_provider(uid: str) -> Optional[int]:
    uid = str(uid).strip()

    # Fast path: read the shared runtime cache directly.
    try:
        info = runtime.get_window(uid)
        if info:
            pid = int(info.get("pid", 0) or 0)
            if pid > 0:
                return pid
    except Exception:
        pass

    # Case-insensitive fallback for names that differ only by casing/spacing in UI state.
    try:
        for name, info in runtime.all_windows().items():
            if str(name).strip().casefold() != uid.casefold():
                continue
            pid = int(info.get("pid", 0) or 0)
            if pid > 0:
                return pid
    except Exception:
        pass

    now = time.time()
    with _pid_cache_lock:
        age    = now - _pid_cache_ts
        cached = dict(_pid_cache)
    if age > _PID_CACHE_TTL or not cached:
        _refresh_pid_cache()
        with _pid_cache_lock:
            cached = dict(_pid_cache)

    pid = cached.get(uid)
    if pid:
        return int(pid)

    uid_fold = uid.casefold()
    for name, pid in cached.items():
        try:
            if str(name).strip().casefold() == uid_fold:
                return int(pid)
        except Exception:
            continue
    return None


def _hwnd_provider(pid: int) -> Optional[int]:
    try:
        for info in runtime.all_windows().values():
            if int(info.get("pid", 0) or 0) == int(pid):
                hwnd = int(info.get("hwnd", 0) or 0)
                if hwnd > 0:
                    return hwnd
    except Exception:
        pass

    try:
        pid_map = window_utils.get_roblox_pid_map()
        return pid_map.get(int(pid))
    except Exception:
        return None


def _biome_provider(uid: str) -> str:
    try:
        return str(runtime.get_biome(str(uid).strip()) or "")
    except Exception:
        return ""


def _in_menu_provider(uid: str) -> bool:
    # Yes Biome Scanner does not track menu state.
    # Returning False means "user is in-game" so the engine is allowed to act.
    return False


def _log_cb(msg: str) -> None:
    try:
        if signals is not None:
            signals.log_message.emit(str(msg))
    except Exception:
        pass


# ----------------------------------------------------------------
# Public API
# ----------------------------------------------------------------

def init(sig) -> None:
    """Wire up PyQt signals and create the AutoItemEngine."""
    global signals, _engine
    signals = sig

    _engine = AutoItemEngine(
        pid_provider      = _pid_provider,
        hwnd_provider     = _hwnd_provider,
        biome_provider    = _biome_provider,
        in_menu_provider  = _in_menu_provider,
        log               = _log_cb,
    )

    sig.start_auto_item.connect(start_auto_item)
    sig.stop_auto_item.connect(stop_auto_item)
    sig.auto_item_config_updated.connect(update_config)


def update_config() -> None:
    """Push the current saved settings into the running engine."""
    if _engine is None:
        return
    settings = load_settings()
    cfg = dict(settings.get("auto_item", {}))
    # Always reflect the running state so the engine knows if it's enabled.
    cfg["enabled"] = _auto_item_running
    _engine.update_config(cfg)


def start_auto_item() -> None:
    global _auto_item_running
    if _engine is None or _auto_item_running:
        return
    _auto_item_running = True
    update_config()
    _engine.start()


def stop_auto_item() -> None:
    global _auto_item_running
    _auto_item_running = False
    if _engine is not None:
        # Push disabled config first so the engine's loop exits cleanly.
        update_config()
        _engine.stop()


def is_running() -> bool:
    return _auto_item_running and _engine is not None and _engine.is_running()


def test_once(uid: str) -> bool:
    """Run the configured automation once for a single user (ignores cooldowns)."""
    if _engine is None:
        _log_cb("[Auto-Item] Engine not initialised.")
        return False
    update_config()
    return _engine.test_once(str(uid))
