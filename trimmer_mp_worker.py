# trimmer_mp_worker.py
#
# Runs inside a SEPARATE PROCESS spawned by TrimmerWorker.
# Imports are intentionally kept minimal — only what the subprocess actually needs.

import time


def run_trimmer_worker(config_queue, log_queue, stop_event):
    """
    Entry point for the trimmer subprocess.

    Args:
        config_queue : multiprocessing.Queue  – receives config dicts from the main process.
        log_queue    : multiprocessing.Queue  – sends log strings back to the main process.
        stop_event   : multiprocessing.Event  – set externally to request a clean shutdown.
    """
    enabled      = False
    interval_s   = 15.0
    threshold_mb = None   # None = trim all regardless of current RAM usage
    last_trim    = 0.0

    def _log(msg: str):
        try:
            log_queue.put_nowait(str(msg))
        except Exception:
            pass

    _log("[INFO] Trimmer subprocess ready.")

    while not stop_event.is_set():
        # ── Drain any pending config updates ──────────────────────────
        while True:
            try:
                msg = config_queue.get_nowait()
            except Exception:
                break   # queue is empty or closed — move on

            if msg is None:
                # Explicit stop sentinel
                _log("[INFO] Trimmer subprocess received stop sentinel.")
                return

            if isinstance(msg, dict) and msg.get("type") == "config":
                enabled      = bool(msg.get("enabled",      enabled))
                interval_s   = float(msg.get("interval_s",  interval_s))
                threshold_mb = msg.get("threshold_mb",       threshold_mb)

        # ── Trim if due ────────────────────────────────────────────────
        if enabled and (time.time() - last_trim) >= interval_s:
            try:
                from ram_limiter_native import trim_targets  # type: ignore
                logs = trim_targets("RobloxPlayerBeta.exe", threshold_mb) or []
                for line in logs:
                    _log(line)
            except ImportError:
                _log("[ERROR] ram_limiter_native not found inside subprocess — stopping trimmer.")
                stop_event.set()
                return
            except Exception as e:
                _log(f"[ERROR] Trim cycle failed: {e}")

            last_trim = time.time()

        time.sleep(0.25)   # short sleep keeps the config queue responsive