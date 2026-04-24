"""
window_utils.py

Standalone helpers for finding Roblox windows, their owning PIDs, and resolving
which tracked player account owns each window/log.

No imports from scanner, merchant_detector, auto_launcher, or bes_manager —
all scripts can import this module without creating circular dependencies.
"""

from __future__ import annotations

import os
import re
import time
from typing import Dict, List, Optional

import win32gui
import win32process

from settings_manager import load_settings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
LOG_INSTANCE_PATTERN = re.compile(r"^[^,]+,[^,]+,([0-9a-fA-F]+),")

# Cache: log_path -> {"instance_id": int}
_log_instance_cache: Dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Roblox window enumeration
# ---------------------------------------------------------------------------
def get_roblox_windows() -> List[int]:
    """Return a list of HWNDs for every visible Roblox window."""
    hwnds: List[int] = []

    def _cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd) == "Roblox":
            hwnds.append(hwnd)
        return True

    win32gui.EnumWindows(_cb, None)
    return hwnds


def get_roblox_pid_map() -> Dict[int, int]:
    """Return {pid: hwnd} for every visible Roblox window."""
    result: Dict[int, int] = {}

    def _cb(hwnd, _):
        try:
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd) == "Roblox":
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                result[int(pid)] = hwnd
        except Exception:
            pass
        return True

    win32gui.EnumWindows(_cb, None)
    return result


# ---------------------------------------------------------------------------
# Log file helpers
# ---------------------------------------------------------------------------
def is_log_active(log_path: Optional[str], max_age_seconds: int = 120) -> bool:
    """Return True if the log file has been written to within max_age_seconds."""
    if not log_path or not os.path.exists(log_path):
        return False
    try:
        if time.time() - os.path.getmtime(log_path) < max_age_seconds:
            return True
    except OSError:
        pass
    # Legacy fallback: check if file is locked by Roblox
    try:
        with open(log_path, "a"):
            pass
        return False
    except PermissionError:
        return True
    except Exception:
        return False


def list_candidate_logs(log_dir: str) -> List[str]:
    """Return all .log/.logs files in the Roblox log directory."""
    try:
        return [
            os.path.join(log_dir, f)
            for f in os.listdir(log_dir)
            if f.endswith((".log", ".logs"))
        ]
    except FileNotFoundError:
        return []


def find_log_for_player(player_name: str, log_dir: str) -> Optional[str]:
    """
    Scan the Roblox log directory and return the path of the newest active log
    file that contains player_name. Returns None if not found.
    """
    candidates = [p for p in list_candidate_logs(log_dir) if is_log_active(p)]
    try:
        candidates.sort(key=lambda x: os.path.getctime(x), reverse=True)
    except Exception:
        pass

    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                data = f.read()
            if player_name in data:
                return path
        except Exception:
            continue
    return None


def find_logs_for_players(player_names: List[str], log_dir: str) -> Dict[str, str]:
    """
    Return {player_name: log_path} for every player whose name appears in an
    active Roblox log file. Reads each candidate log at most once.
    """
    candidates = [p for p in list_candidate_logs(log_dir) if is_log_active(p)]
    try:
        candidates.sort(key=lambda x: os.path.getctime(x), reverse=True)
    except Exception:
        pass

    result: Dict[str, str] = {}
    remaining = set(player_names)

    for path in candidates:
        if not remaining:
            break
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                data = f.read()
        except Exception:
            continue
        for name in list(remaining):
            if name in data:
                result[name] = path
                remaining.discard(name)

    return result


# ---------------------------------------------------------------------------
# Log instance ID extraction  (maps a log file to a Roblox process/thread ID)
# ---------------------------------------------------------------------------
def extract_log_instance_id(log_path: str) -> Optional[int]:
    """
    Read the first ~25 lines of a Roblox log and extract the hex instance ID
    embedded in the CSV header. Returns None if not found.
    Results are cached indefinitely once found.
    """
    cached = _log_instance_cache.get(log_path)
    if cached:
        return cached["instance_id"]

    instance_id: Optional[int] = None
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            for _ in range(25):
                line = f.readline()
                if not line:
                    break
                m = LOG_INSTANCE_PATTERN.match(line.strip())
                if m:
                    instance_id = int(m.group(1), 16)
                    break
    except OSError:
        pass

    if instance_id is not None:
        _log_instance_cache[log_path] = {"instance_id": instance_id}

    return instance_id


# ---------------------------------------------------------------------------
# Window -> account resolution
# ---------------------------------------------------------------------------
def resolve_account_for_window(hwnd: int, tracked_players: List[str]) -> Optional[str]:
    """
    Return the tracked player name that owns the given Roblox window, or None.

    Reads settings to find the log directory, scans active logs to find each
    player, then matches the log's instance ID against the window's PID/TIDs.
    Fully standalone — no dependency on scanner.player_logs or any other module's
    runtime state.
    """
    try:
        from bes_limiter import list_thread_ids
    except Exception:
        list_thread_ids = None

    try:
        _tid, pid = win32process.GetWindowThreadProcessId(hwnd)
    except Exception:
        return None

    settings = load_settings()
    log_dir: str = settings.get("general", {}).get("log_path", "")
    if not log_dir:
        return None

    tids: Optional[set] = None

    for player_name in tracked_players:
        log_path = find_log_for_player(player_name, log_dir)
        if not log_path:
            continue

        instance_id = extract_log_instance_id(log_path)
        if instance_id is None:
            continue

        # Older logs embed the PID directly
        if instance_id == pid:
            return player_name

        # Newer logs embed a thread ID belonging to the process
        if list_thread_ids is not None:
            if tids is None:
                try:
                    tids = set(list_thread_ids(pid))
                except Exception:
                    tids = set()
            if instance_id in tids:
                return player_name

    return None


def resolve_accounts_for_windows(
    hwnds: List[int],
    tracked_players: List[str],
) -> Dict[int, Optional[str]]:
    """
    Batch version of resolve_account_for_window.
    Returns {hwnd: player_name_or_None} for every hwnd in the list.
    Reads each log file at most once across the whole batch for efficiency.
    """
    try:
        from bes_limiter import list_thread_ids
    except Exception:
        list_thread_ids = None

    settings = load_settings()
    log_dir: str = settings.get("general", {}).get("log_path", "")

    # Pre-load instance IDs for all tracked players (each log read once)
    player_instance_ids: Dict[str, Optional[int]] = {}
    for player_name in tracked_players:
        log_path = find_log_for_player(player_name, log_dir) if log_dir else None
        player_instance_ids[player_name] = (
            extract_log_instance_id(log_path) if log_path else None
        )

    result: Dict[int, Optional[str]] = {}
    for hwnd in hwnds:
        try:
            _tid, pid = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            result[hwnd] = None
            continue

        tids: Optional[set] = None
        matched: Optional[str] = None

        for player_name in tracked_players:
            instance_id = player_instance_ids.get(player_name)
            if instance_id is None:
                continue

            if instance_id == pid:
                matched = player_name
                break

            if list_thread_ids is not None:
                if tids is None:
                    try:
                        tids = set(list_thread_ids(pid))
                    except Exception:
                        tids = set()
                if instance_id in tids:
                    matched = player_name
                    break

        result[hwnd] = matched

    return result


def get_active_account_hwnds(tracked_players: List[str]) -> Dict[str, int]:
    """
    Return {player_name: hwnd} for accounts currently considered active by the UI.

    The UI defines an account as active when there is a visible Roblox window that
    can be resolved back to one of the tracked player names.
    """
    active: Dict[str, int] = {}
    for hwnd in get_roblox_windows():
        try:
            player_name = resolve_account_for_window(hwnd, tracked_players)
        except Exception:
            player_name = None
        if player_name and player_name not in active:
            active[player_name] = hwnd
    return active


def get_active_account_pids(tracked_players: List[str]) -> Dict[str, int]:
    """
    Return {player_name: pid} using the same active-account definition as the UI.
    """
    active: Dict[str, int] = {}
    for player_name, hwnd in get_active_account_hwnds(tracked_players).items():
        try:
            _tid, pid = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            continue
        active[player_name] = pid
    return active
