"""
window_poller.py

Single daemon thread that owns all HWND/PID enumeration and account
resolution.  Writes results to AccountRuntime.replace_window_cache().
All other modules read from runtime.get_window() / runtime.all_windows().

Runs on a configurable interval (default 3 s).
"""

from __future__ import annotations

import threading
import time
from typing import Dict, List, Optional

import win32gui
import win32process

import perf_log
import window_utils
from account_runtime import runtime

_poller_running = False


def _poll(tracked_players: List[str], log_dir: str) -> None:
    """
    One polling cycle: enumerate windows, resolve accounts, write cache.
    All I/O happens BEFORE the lock is acquired.
    """
    # Step 1 — enumerate HWNDs (no lock held)
    hwnd_pid: Dict[int, int] = {}
    for hwnd in window_utils.get_roblox_windows():
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            hwnd_pid[hwnd] = pid
        except Exception:
            continue

    if not hwnd_pid:
        runtime.replace_window_cache({})
        return

    # Step 2 — batch-resolve account names from log headers (no lock held)
    hwnd_to_name = window_utils.resolve_accounts_for_windows(
        list(hwnd_pid.keys()), tracked_players, log_dir
    )

    # Step 3 — evict stale log-instance cache entries
    window_utils._evict_stale_log_cache()

    # Step 4 — build new cache dict (no lock held)
    new_cache: Dict[str, dict] = {}
    pid_to_hwnd = {pid: hwnd for hwnd, pid in hwnd_pid.items()}
    for hwnd, name in hwnd_to_name.items():
        if not name:
            continue
        pid = hwnd_pid.get(hwnd)
        if pid is None:
            continue
        new_cache[name] = {
            "pid":       pid,
            "hwnd":      hwnd,
            "last_seen": time.monotonic(),
        }

    # Step 5 — single locked write
    runtime.replace_window_cache(new_cache)


def _poller_loop(get_config) -> None:
    global _poller_running
    _poller_running = True

    try:
        while _poller_running:
            t0  = time.perf_counter()
            cfg = get_config()

            tracked = cfg.get("tracked_players", [])
            log_dir = cfg.get("log_dir", "")
            interval = max(1, cfg.get("window_poll_interval", 3))

            with perf_log.timed("window_poller.poll", threshold_ms=200):
                _poll(tracked, log_dir)

            elapsed_ms = (time.perf_counter() - t0) * 1000
            runtime.update_health("window_poller", elapsed_ms, slow_threshold_ms=200)
            time.sleep(interval)

    except Exception:
        import traceback; traceback.print_exc()
    finally:
        _poller_running = False


def start(get_config) -> None:
    threading.Thread(
        target=_poller_loop,
        args=(get_config,),
        daemon=True,
        name="WindowPoller",
    ).start()


def stop() -> None:
    global _poller_running
    _poller_running = False