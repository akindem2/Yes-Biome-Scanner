import os
import re
import time
import threading
import subprocess
import ctypes
from settings_manager import load_settings, mark_cookie_invalid
import roblox_launcher
import window_utils
import win32gui

import perf_log
from account_runtime import runtime

signals = None
auto_launch_running = False

# Disconnect detection patterns (from J.JARAM log_utils.py)
# These only match real network disconnects inside [FLog::Network] lines,
# avoiding false positives from roblox::datamodel::close which fires on every
# clean shutdown and was causing infinite relaunch loops.
_R_DISC_REASON  = re.compile(r"\[FLog::Network\]\s+Disconnect reason received:\s*(\d+)", re.I)
_R_DISC_NOTIFY  = re.compile(r"\[FLog::Network\]\s+Disconnection Notification\.\s*Reason:\s*(\d+)", re.I)
_R_DISC_SENDING = re.compile(r"\[FLog::Network\]\s+Sending disconnect with reason:\s*(\d+)", re.I)
_R_CONN_LOST    = re.compile(r"\[FLog::Network\]\s+Connection lost", re.I)

# How many bytes to read from the end of the log for disconnect scanning
_DISCONNECT_READ_BYTES = 32_768  # 32 KB - enough for recent log tail, fast to read

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_WINDOW_CACHE_STALE_SECONDS = 15.0


def _is_pid_alive(pid) -> bool:
    """Return True when pid refers to a currently running process."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False

    handle = ctypes.windll.kernel32.OpenProcess(
        _PROCESS_QUERY_LIMITED_INFORMATION,
        False,
        pid,
    )
    if not handle:
        return False

    try:
        exit_code = ctypes.c_ulong()
        if not ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == 259  # STILL_ACTIVE
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def init(sig):
    global signals
    signals = sig
    signals.start_auto_launch.connect(start_auto_launch)
    signals.stop_auto_launch.connect(stop_auto_launch)


def is_disconnected(log_path):
    """
    Check the tail of a Roblox log for network disconnect signals.
    Uses [FLog::Network] regex patterns (J.JARAM approach) to avoid
    false positives from roblox::datamodel::close on clean shutdowns.
    """
    if not log_path or not os.path.exists(log_path):
        return False
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - _DISCONNECT_READ_BYTES))
            tail = f.read()

        return bool(
            _R_DISC_REASON.search(tail)
            or _R_DISC_NOTIFY.search(tail)
            or _R_DISC_SENDING.search(tail)
            or _R_CONN_LOST.search(tail)
        )
    except Exception:
        return False


def _find_running_accounts(tracked_players):
    # Read the window cache the poller maintains — no live enumeration needed.
    window_cache = runtime.all_windows()
    running: dict = {}
 
    for name in tracked_players:
        entry = window_cache.get(name)
        if not entry:
            continue   # not in cache → no window → not running
 
        pid       = entry.get("pid")
        hwnd      = entry.get("hwnd")
        last_seen = float(entry.get("last_seen") or 0.0)

        try:
            hwnd = int(hwnd)
        except (TypeError, ValueError):
            continue
        if hwnd <= 0 or not win32gui.IsWindow(hwnd):
            continue
        if last_seen and (time.monotonic() - last_seen) > _WINDOW_CACHE_STALE_SECONDS:
            continue

        # Condition 2: PID is alive
        if not _is_pid_alive(pid):
            continue

        running[name] = pid

    return running


def auto_launch_loop():
    global auto_launch_running
    recently_launched = {}

    signals.log_message.emit("[START] Auto-Launcher running in background")
    try:
        while auto_launch_running:
            settings = load_settings()
            players = settings.get("players", {})
            delay_seconds = int(settings.get("general", {}).get("auto_launch_delay", 5))
            tracked_players = list(players.keys())

            # 1. Find active accounts using the same logic shown in the UI
            with perf_log.timed("_find_running_accounts", threshold_ms=300):
                running_accounts = _find_running_accounts(tracked_players)

            # 2. Check each desired account
            for name, data in players.items():
                if not isinstance(data, dict):
                    continue
                if data.get("auto_launch", True) is False:
                    continue
                if data.get("cookie_invalid", False):
                    continue

                cookie = data.get("cookie")
                pslink = data.get("pslink")
                if not cookie or not pslink:
                    continue

                if name in running_accounts:
                    # Account is active - check if it has disconnected
                    _log_info = runtime.get_log_info(name)
                    log_path  = _log_info.get("file") if _log_info else None

                    if is_disconnected(log_path):
                        # Kill-loop guard: skip if we launched within the last 120s
                        if time.time() - recently_launched.get(name, 0) < 120:
                            continue

                        signals.log_message.emit(
                            f"[AUTO-LAUNCH] {name} disconnected. Terminating to relaunch..."
                        )
                        pid = running_accounts[name]
                        if pid:
                            try:
                                subprocess.call(
                                    ["taskkill", "/F", "/PID", str(pid)],
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL,
                                )
                            except Exception as e:
                                signals.log_message.emit(f"[ERROR] Could not kill {name}: {e}")

                        # Clear any cached log position so other modules rescan fresh
                        window_utils._log_instance_cache.clear()
                        time.sleep(2)
                else:
                    # Account not active - check cooldown before launching
                    if time.time() - recently_launched.get(name, 0) < 60:
                        continue

                    signals.log_message.emit(f"[AUTO-LAUNCH] Launching {name}...")
                    recently_launched[name] = time.time()

                    success, msg = roblox_launcher.launch_private_server(cookie, pslink)

                    if success:
                        mark_cookie_invalid(name, invalid=False)
                        signals.log_message.emit(
                            f"[AUTO-LAUNCH] Launched {name}! "
                            f"Waiting {delay_seconds}s before next check."
                        )
                        time.sleep(delay_seconds)
                    else:
                        if "AUTH_FAILED" in msg:
                            mark_cookie_invalid(name, invalid=True)
                            signals.log_message.emit(
                                f"[ERROR] {name} cookie is invalid or expired - marked as bad."
                            )
                        else:
                            signals.log_message.emit(f"[ERROR] Auto-Launch {name} failed: {msg}")

            time.sleep(5)

        signals.log_message.emit("[STOP] Auto-Launcher stopped")
    except Exception:
        import traceback
        traceback.print_exc()
        signals.log_message.emit("[ERROR] Auto-Launcher crashed")
        signals.auto_launcher_crashed.emit()

    finally:
        auto_launch_running = False



def start_auto_launch():
    global auto_launch_running
    if auto_launch_running:
        return
    auto_launch_running = True
    threading.Thread(target=auto_launch_loop, daemon=True).start()


def stop_auto_launch():
    global auto_launch_running
    auto_launch_running = False
