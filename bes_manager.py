"""
bes_manager.py — High-level wrapper around BESMultiProcessController for Roblox windows.

- Global CPU limit for all non-exempt Roblox instances.
- Uses BES-style per-thread duty-cycling from bes_limiter.BESMultiProcessController.
- Integrates with existing PyQt signals: start_bes, stop_bes, log_message.
"""

import threading
import time

import win32gui
import win32process

import window_utils
from settings_manager import load_settings
from bes_limiter import BESMultiProcessController

signals = None
bes_running = False
_controller: BESMultiProcessController | None = None


# ----------------------------------------------------------------
# Window / PID helpers
# ----------------------------------------------------------------
def _get_roblox_pid_map() -> dict[int, int]:
    """Return {pid: hwnd} for every visible Roblox window."""
    result: dict[int, int] = {}

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


def _get_exempt_pids(exempt_accounts, pid_hwnd_map, name_cache):
    """Return the set of PIDs whose account name is in exempt_accounts.

    Uses the pre-built name_cache {pid: name} instead of calling
    resolve_account_for_window per PID.
    """
    if not exempt_accounts:
        return set()

    exempt_set = set(exempt_accounts)
    return {pid for pid, name in name_cache.items() if name and name in exempt_set}


# ----------------------------------------------------------------
# Internal BES loop (drives the controller)
# ----------------------------------------------------------------
# How often (seconds) to re-resolve which account owns each window.
# This is expensive (reads log files) so we do it infrequently.
_NAME_RESOLVE_INTERVAL = 10.0


def _bes_loop():
    global bes_running, _controller

    if _controller is None:
        return

    signals.log_message.emit("[BES] CPU throttler started")
    _controller.set_enabled(True)

    # Track when each PID was first seen so we can apply a startup grace period.
    # New Roblox instances need time to connect before being throttled — suspending
    # threads during the join/loading phase causes disconnects.
    _pid_first_seen: dict[int, float] = {}

    # Cached name resolution: {pid: account_name_or_None}
    # Re-populated every _NAME_RESOLVE_INTERVAL seconds using the efficient
    # batch function instead of per-PID resolve_account_for_window calls.
    _name_cache: dict[int, str | None] = {}
    _last_name_resolve: float = 0.0

    try:
        while bes_running:
            settings = load_settings()
            cfg = settings.get("bes", {})

            # Global "CPU limit" (1–99) -> convert to reduction percent for BES
            cpu_limit = max(1, min(99, int(cfg.get("cpu_limit", 50))))
            reduce_pct = max(0, min(99, 100 - cpu_limit))

            # Grace period (seconds) before throttling a newly launched Roblox instance.
            # Keeps BES from suspending threads while the game is still connecting.
            grace_seconds = max(0, int(cfg.get("new_window_grace_seconds", 30)))

            # Base cycle for the controller (it will auto-scale as needed)
            cycle_ms = max(10, int(cfg.get("cycle_ms", 20)))
            _controller.set_cycle_ms(cycle_ms)

            exempt_accts = cfg.get("exempt_accounts", []) or []

            pid_map = _get_roblox_pid_map()

            now = time.time()

            # Record first-seen time for any new PIDs.
            for pid in pid_map:
                if pid not in _pid_first_seen:
                    _pid_first_seen[pid] = now

            # Drop stale entries for PIDs that no longer exist.
            for pid in list(_pid_first_seen):
                if pid not in pid_map:
                    _pid_first_seen.pop(pid, None)

            # ── Name resolution (expensive, so batched + cached) ──────────
            # Only re-resolve when the timer expires OR new PIDs appeared
            # that aren't in the cache yet.
            new_pids_unseen = any(pid not in _name_cache for pid in pid_map)
            if new_pids_unseen or (now - _last_name_resolve >= _NAME_RESOLVE_INTERVAL):
                try:
                    tracked = list(settings.get("players", {}).keys())
                    hwnds = list(pid_map.values())
                    if hwnds and tracked:
                        hwnd_names = window_utils.resolve_accounts_for_windows(hwnds, tracked)
                        # Rebuild cache as {pid: name}
                        _name_cache.clear()
                        for pid, hwnd in pid_map.items():
                            _name_cache[pid] = hwnd_names.get(hwnd)
                    else:
                        _name_cache.clear()
                except Exception:
                    pass
                _last_name_resolve = now

            # Purge cache entries for PIDs that are gone.
            for pid in list(_name_cache):
                if pid not in pid_map:
                    _name_cache.pop(pid, None)

            exempt_pids = _get_exempt_pids(exempt_accts, pid_map, _name_cache)

            # Build PID -> reduction percent map (global limit, per-process application)
            target_pcts: dict[int, int] = {}
            names: dict[int, str] = {}

            if reduce_pct > 0:
                for pid, hwnd in pid_map.items():
                    if pid in exempt_pids:
                        continue

                    # Skip PIDs that are still within the startup grace period.
                    age = now - _pid_first_seen.get(pid, now)
                    if age < grace_seconds:
                        _controller.hold_unthrottled(pid, grace_seconds - age)
                        continue

                    target_pcts[pid] = reduce_pct
                    names[pid] = _name_cache.get(pid) or f"PID {pid}"

            _controller.apply(target_pcts, names=names)

            # Polling interval for settings / window changes
            time.sleep(0.5)

    finally:
        # Ensure everything is fully resumed and controller is shut down
        _controller.set_enabled(False)
        signals.log_message.emit("[BES] CPU throttler stopped")


# ----------------------------------------------------------------
# Public API
# ----------------------------------------------------------------
def init(sig):
    """Wire up PyQt signals and create the BES controller."""
    global signals, _controller
    signals = sig

    # Log callback from BESMultiProcessController -> PyQt log_message signal
    def _log_cb(msg: str):
        try:
            signals.log_message.emit(str(msg))
        except Exception:
            pass

    _controller = BESMultiProcessController(
        cycle_ms=50,
        log=_log_cb,
        auto_scale_cycle=True,
        stagger_phases=True,
        refresh_interval_s=1.0,
        max_cycle_ms=400,
        min_cycle_ms_per_pid=2,
    )

    signals.start_bes.connect(start_bes)
    signals.stop_bes.connect(stop_bes)


def start_bes():
    """Start the global BES-style throttler loop."""
    global bes_running
    if bes_running:
        return
    bes_running = True
    t = threading.Thread(target=_bes_loop, name="BES-Manager", daemon=True)
    t.start()


def stop_bes():
    """Stop the global BES-style throttler loop."""
    global bes_running
    bes_running = False
