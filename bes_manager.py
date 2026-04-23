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


def _get_exempt_pids(exempt_accounts, pid_hwnd_map):
    """Return the set of PIDs whose account name is in exempt_accounts."""
    if not exempt_accounts:
        return set()

    try:
        settings = load_settings()
        tracked = list(settings.get("players", {}).keys())
        exempt_pids = set()

        for pid, hwnd in pid_hwnd_map.items():
            name = window_utils.resolve_account_for_window(hwnd, tracked)
            if name and name in exempt_accounts:
                exempt_pids.add(pid)

        return exempt_pids
    except Exception:
        return set()


# ----------------------------------------------------------------
# Internal BES loop (drives the controller)
# ----------------------------------------------------------------
def _bes_loop():
    global bes_running, _controller

    if _controller is None:
        # Log via print as a fallback if signals not ready
        return

    signals.log_message.emit("[BES] CPU throttler started")
    _controller.set_enabled(True)

    try:
        while bes_running:
            settings = load_settings()
            cfg = settings.get("bes", {})

            # Global "CPU limit" (1–99) -> convert to reduction percent for BES
            cpu_limit = max(1, min(99, int(cfg.get("cpu_limit", 50))))
            reduce_pct = max(0, min(99, 100 - cpu_limit))

            # Base cycle for the controller (it will auto-scale as needed)
            cycle_ms = max(10, int(cfg.get("cycle_ms", 20)))
            _controller.set_cycle_ms(cycle_ms)

            exempt_accts = cfg.get("exempt_accounts", []) or []

            pid_map = _get_roblox_pid_map()
            exempt_pids = _get_exempt_pids(exempt_accts, pid_map)

            # Build PID -> reduction percent map (global limit, per-process application)
            target_pcts: dict[int, int] = {}
            names: dict[int, str] = {}

            if reduce_pct > 0:
                for pid, hwnd in pid_map.items():
                    if pid in exempt_pids:
                        continue
                    target_pcts[pid] = reduce_pct

                    # Optional: try to resolve a friendly name for logging/UI
                    try:
                        settings = load_settings()
                        tracked = list(settings.get("players", {}).keys())
                        name = window_utils.resolve_account_for_window(hwnd, tracked) or f"PID {pid}"
                    except Exception:
                        name = f"PID {pid}"
                    names[pid] = name

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
