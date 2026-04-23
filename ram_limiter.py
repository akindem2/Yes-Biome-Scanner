# ram_limiter.py

from typing import List, Optional, Callable
import traceback

try:
    import ram_limiter_native
    _NATIVE = True
except Exception:
    ram_limiter_native = None
    _NATIVE = False


def is_native_available() -> bool:
    return _NATIVE and ram_limiter_native is not None


def trim_all_roblox(threshold_mb: Optional[float], log_cb: Optional[Callable] = None) -> List[str]:
    """
    Calls the native C++ trim_targets() function.
    """
    if not is_native_available():
        msg = "[WARN] Native RAM limiter not available."
        if log_cb:
            log_cb(msg)
        return [msg]

    try:
        logs = ram_limiter_native.trim_targets("RobloxPlayerBeta.exe", threshold_mb)
        if log_cb:
            for line in logs:
                log_cb(line)
        return logs

    except Exception:
        traceback.print_exc()
        msg = "[ERROR] Exception while trimming RAM."
        if log_cb:
            log_cb(msg)
        return [msg]
