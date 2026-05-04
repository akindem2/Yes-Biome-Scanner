# perf_log.py
import time
import threading
import logging

# Toggle via Help menu or BIOME_PERF_LOG=1 env var.
# Always False in production.
ENABLED: bool = False

_log = logging.getLogger("perf")
_lock = threading.Lock()   # guards ENABLED writes only


def set_enabled(value: bool) -> None:
    global ENABLED
    with _lock:
        ENABLED = bool(value)


class timed:
    """Context manager — wraps a block and logs if slow.

    Usage:
        with perf_log.timed("find_player_logs"):
            find_player_logs(log_path)
    """
    __slots__ = ("label", "threshold_ms", "_t0")

    def __init__(self, label: str, threshold_ms: float = 200.0) -> None:
        self.label        = label
        self.threshold_ms = threshold_ms

    def __enter__(self):
        if ENABLED:
            self._t0 = time.perf_counter()
        return self

    def __exit__(self, *_):
        if not ENABLED:
            return
        elapsed_ms = (time.perf_counter() - self._t0) * 1000
        if elapsed_ms >= self.threshold_ms:
            _log.warning("[PERF] %s took %.1f ms", self.label, elapsed_ms)