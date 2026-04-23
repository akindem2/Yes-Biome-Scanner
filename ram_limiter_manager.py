# ram_limiter_manager.py

import threading
import time
import ram_limiter  # wrapper around your native C++ module
from settings_manager import load_settings

_running = False
_thread = None
_signals = None


def init(signals):
    """
    Connects UI signals to start/stop the RAM limiter.
    """
    global _signals
    _signals = signals

    signals.start_ram_limiter.connect(start)
    signals.stop_ram_limiter.connect(stop)


def start():
    """
    Starts the RAM limiter thread.
    """
    global _running, _thread
    if _running:
        return

    _running = True
    _thread = threading.Thread(target=_loop, daemon=True)
    _thread.start()

    if _signals:
        _signals.log_message.emit("[RAM] Started RAM limiter.")


def stop():
    """
    Stops the RAM limiter thread.
    """
    global _running
    _running = False

    if _signals:
        _signals.log_message.emit("[RAM] Stopped RAM limiter.")


def _loop():
    global _running

    while _running:
        settings = load_settings()
        ram_cfg = settings.get("ram_limiter", {})

        THRESHOLD_MB = ram_cfg.get("threshold_mb", 800)
        INTERVAL_SEC = ram_cfg.get("interval_sec", 5)

        try:
            ram_limiter.trim_all_roblox(
                threshold_mb=THRESHOLD_MB,
                log_cb=lambda line: _signals.log_message.emit(f"[RAM] {line}")
            )
        except Exception as e:
            _signals.log_message.emit(f"[ERROR] RAM limiter exception: {e}")

        time.sleep(INTERVAL_SEC)
        