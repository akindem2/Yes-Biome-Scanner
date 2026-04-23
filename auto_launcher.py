import os
import re
import time
import threading
import subprocess
import win32process
from settings_manager import load_settings, mark_cookie_invalid
import roblox_launcher
import window_utils

signals = None
auto_launch_running = False

# ── Disconnect detection patterns (from J.JARAM log_utils.py) ────────────────
# These only match real network disconnects inside [FLog::Network] lines,
# avoiding false positives from roblox::datamodel::close which fires on every
# clean shutdown and was causing infinite relaunch loops.
_R_DISC_REASON  = re.compile(r"\[FLog::Network\]\s+Disconnect reason received:\s*(\d+)", re.I)
_R_DISC_NOTIFY  = re.compile(r"\[FLog::Network\]\s+Disconnection Notification\.\s*Reason:\s*(\d+)", re.I)
_R_DISC_SENDING = re.compile(r"\[FLog::Network\]\s+Sending disconnect with reason:\s*(\d+)", re.I)
_R_CONN_LOST    = re.compile(r"\[FLog::Network\]\s+Connection lost", re.I)

# How many bytes to read from the end of the log for disconnect scanning
_DISCONNECT_READ_BYTES = 32_768  # 32 KB — enough for recent log tail, fast to read


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


def _is_log_active(log_path, max_age_seconds=90):
    """Thin wrapper — delegates to window_utils for consistency."""
    return window_utils.is_log_active(log_path, max_age_seconds=max_age_seconds)


def _is_pid_alive(pid):
    """Return True if the given PID corresponds to a running process."""
    if pid is None:
        return False
    try:
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x0400, False, pid)  # PROCESS_QUERY_INFORMATION
        if not handle:
            return False
        exit_code = ctypes.c_ulong(0)
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return exit_code.value == 259  # STILL_ACTIVE
    except Exception:
        return False


def _find_running_accounts(tracked_players):
    """
    Return a dict of { account_name -> pid } for accounts that are
    currently in a live Roblox session.

    All three conditions must be true for an account to be considered running:
      1. A Roblox window for that account exists.
      2. The process for that window (PID) is still alive.
      3. The account's log file was updated within the last 10 seconds.

    If any condition fails, the account is NOT considered running and will
    be eligible for launch.
    """
    settings = load_settings()
    log_dir  = settings.get("general", {}).get("log_path", "")

    # Build hwnd -> pid map for all visible Roblox windows
    hwnd_pid: dict = {}
    for hwnd in window_utils.get_roblox_windows():
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            hwnd_pid[hwnd] = pid
        except Exception:
            continue

    running: dict = {}
    for name in tracked_players:
        # Condition 1: find the window that belongs to this account
        matched_hwnd = None
        matched_pid  = None
        for hwnd, pid in hwnd_pid.items():
            acct = window_utils.resolve_account_for_window(hwnd, [name])
            if acct == name:
                matched_hwnd = hwnd
                matched_pid  = pid
                break

        if matched_hwnd is None:
            continue  # no window → not running

        # Condition 2: PID is alive
        if not _is_pid_alive(matched_pid):
            continue

        # Condition 3: log file updated within the last 10 seconds
        log_path = window_utils.find_log_for_player(name, log_dir) if log_dir else None
        if not window_utils.is_log_active(log_path, max_age_seconds=10):
            continue

        running[name] = matched_pid

    return running


def auto_launch_loop():
    global auto_launch_running
    recently_launched = {}

    signals.log_message.emit("[START] Auto-Launcher running in background")

    while auto_launch_running:
        settings = load_settings()
        players = settings.get("players", {})
        delay_seconds = int(settings.get("general", {}).get("auto_launch_delay", 5))
        tracked_players = list(players.keys())

        # 1. Find running accounts
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
                # Account is running — check if it has disconnected
                settings = load_settings()
                log_dir  = settings.get("general", {}).get("log_path", "")
                log_path = window_utils.find_log_for_player(name, log_dir) if log_dir else None

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
                # Account not running — check cooldown before launching
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
                            f"[ERROR] {name} cookie is invalid or expired — marked as bad."
                        )
                    else:
                        signals.log_message.emit(f"[ERROR] Auto-Launch {name} failed: {msg}")

        time.sleep(5)

    signals.log_message.emit("[STOP] Auto-Launcher stopped")


def start_auto_launch():
    global auto_launch_running
    if auto_launch_running:
        return
    auto_launch_running = True
    threading.Thread(target=auto_launch_loop, daemon=True).start()


def stop_auto_launch():
    global auto_launch_running
    auto_launch_running = False