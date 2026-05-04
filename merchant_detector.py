"""
merchant_detector.py

Structured as a near-exact copy of scanner.py, adapted for merchant detection.

Shared with scanner.py (copy-for-copy):
  - is_log_active()            — identical
  - _list_detection_logs()     — identical
  - find_merchant_logs()       — mirrors find_player_logs()
  - read_merchant_lines()      — mirrors read_new_lines()
  - merchant_detector_loop()   — mirrors scanner_loop()

Merchant-specific additions:
  - Animation asset-ID matching (18247165978=Mari, 18247420806=Jester, 97148159887178=Rin)
  - Timestamp required — lines with no parseable timestamp are skipped entirely
  - 60 s grace period after a log is first assigned (suppresses Roblox's startup
    animation preload failures).  pos is still advanced during the grace period so
    startup content is consumed silently and never re-read once the period expires.
  - 300 s per-player per-merchant dedup window (merchants despawn in ~3 min)
  - scan_interval read from merchant_detection.scan_interval (default 2 s)
"""

import os
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Optional

from settings_manager import load_settings
from webhook import send_merchant_detected_message

import perf_log
from account_runtime import runtime as _runtime

import config_snapshot

# ── THREADING NOTES (Phase 1.4 concurrency audit) ──────────────────────────
# Single worker thread: merchant_detector_loop.
# All three module globals below are written and read by that thread only:
#   _merchant_player_logs — single-thread, SAFE
#   _log_track_start      — single-thread, SAFE
#   _last_merchant_ts     — single-thread, SAFE
# Do NOT add cross-thread reads of these globals. Phase 3 migrates them.
# ─────────────────────────────────────────────────────────────────────────────

signals = None
merchant_detector_running = False

DEFAULT_MERCHANTS = []

# Per-player log tracking — now stored in runtime._log_map under
# key prefix "merchant:" to avoid colliding with scanner's entries.
# Grace period and dedup window stay as module constants.
WINDOW_GRACE_PERIOD   = 60.0
MERCHANT_DEDUPE_WINDOW = 1200.0

# These two dicts are private to the merchant thread — not in runtime.
_log_track_start: Dict[str, float] = {}
_last_merchant_ts: Dict[str, Dict[str, float]] = {}


MERCHANT_ANIMATION_IDS: dict[str, str] = {
    "18247165978":    "Mari",
    "18247420806":    "Jester",
    "97148159887178": "Rin",
}
_ID_STRINGS = set(MERCHANT_ANIMATION_IDS.keys())


# ── Identical to scanner.py ───────────────────────────────────────────────────

def is_log_active(filepath, max_age_seconds=120):
    """Check if a log file is from an active Roblox session."""
    try:
        mtime = os.path.getmtime(filepath)
        age = time.time() - mtime
        if age < max_age_seconds:
            return True
        # Optimization: Don't check file lock if older than 2 hours to save I/O
        if age > 7200:
            return False
    except OSError:
        return False

    # Legacy fallback: check if file is locked
    try:
        with open(filepath, 'a'):
            pass
        return False
    except PermissionError:
        return True
    except Exception:
        return False


def _list_detection_logs(log_path):
    """Return candidate log files for player detection."""
    try:
        entries = []
        for entry in os.scandir(log_path):
            if entry.is_file() and entry.name.endswith((".log", ".logs")):
                try:
                    entries.append((entry.path, entry.stat().st_mtime))
                except OSError:
                    pass
        entries.sort(key=lambda x: x[1], reverse=True)
        return [path for path, _ in entries[:50]]
    except FileNotFoundError:
        return []


# ── Mirrors find_player_logs() from scanner.py ───────────────────────────────

def find_merchant_logs(tracked_players: list, log_path: str) -> None:
    """Find which log file each player is using, preferring the newest active one."""
    if not tracked_players:
        return

    # OPTIMIZATION: Only sweep the log folder if a player is MISSING a log
    needs_search = False
    for name in tracked_players:
        _minfo = _runtime.get_log_info(f"merchant:{name}")
        current_file = _minfo.get("file") if _minfo else None
        if not current_file or not is_log_active(current_file):
            needs_search = True
            break

    if not needs_search:
        return

    log_files = _list_detection_logs(log_path)
    if not log_files:
        return

    active_logs = [path for path in log_files if is_log_active(path)]

    # Sort newest to oldest based on creation time
    try:
        active_logs.sort(key=lambda x: os.path.getctime(x), reverse=True)
    except Exception:
        pass

    for name in tracked_players:
        _minfo = _runtime.get_log_info(f"merchant:{name}")
        current_file = _minfo.get("file") if _minfo else None

        for path in active_logs:
            # If we hit our currently linked file there are no newer files
            if path == current_file:
                break

            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    data = f.read()
            except Exception:
                continue

            if name in data:
                if signals:
                    signals.log_message.emit(
                        f"[MERCHANT] {name} linked to log: {os.path.basename(path)}"
                    )
                # Set pos to END of file so we only process lines appended
                # after this moment — never re-read historical content.
                try:
                    end_pos = os.path.getsize(path)
                except OSError:
                    end_pos = 0
                _runtime.update_log_map(f"merchant:{name}", file=path, pos=end_pos)
                _log_track_start[name] = time.monotonic()
                break


# ── Mirrors read_new_lines() from scanner.py ─────────────────────────────────

def read_merchant_lines(
    player_name: str, info: dict, merchants: list, settings: dict
) -> None:
    """Read new log content and fire webhooks for any merchant matches found."""
    path     = info["file"]
    last_pos = info["pos"]

    try:
        size = os.path.getsize(path)
    except FileNotFoundError:
        return

    if size <= last_pos:
        return

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(last_pos)
            new_data = f.read()
    except Exception:
        return

    info["pos"] = size
    _runtime.update_log_map(f"merchant:{player_name}", pos=size)

    if not new_data:
        return

    # Fast pre-filter
    if not any(id_str in new_data for id_str in _ID_STRINGS):
        return

    now              = datetime.now(timezone.utc)
    last_parsed_time: Optional[datetime] = None
    player_ts        = _last_merchant_ts.setdefault(player_name, {})

    for line in new_data.splitlines():
        # ── Timestamp parsing — identical to scanner.py ───────────────────────
        if len(line) > 20 and line.startswith("202"):
            ts_part = line.split(",", 1)[0].split(" ")[0]
            if "T" in ts_part:
                try:
                    last_parsed_time = datetime.fromisoformat(
                        ts_part.replace("Z", "+00:00")
                    ).astimezone(timezone.utc)
                except Exception:
                    pass

        # ── 1200 s cutoff — identical to scanner.py ───────────────────────────
        if (
            last_parsed_time is not None
            and (now - last_parsed_time).total_seconds() > 1200
        ):
            break

        # ── Animation ID check ────────────────────────────────────────────────
        for id_str in _ID_STRINGS:
            if id_str not in line:
                continue

            # No timestamp → unknown age → never fire
            if last_parsed_time is None:
                break

            # Stale line → skip (same 30 s threshold as scanner.py)
            if (now - last_parsed_time).total_seconds() > 30:
                break

            merchant_name = MERCHANT_ANIMATION_IDS[id_str]
            ts_epoch      = last_parsed_time.timestamp()

            last_seen = player_ts.get(merchant_name, 0.0)
            if abs(ts_epoch - last_seen) < MERCHANT_DEDUPE_WINDOW:
                break

            player_ts[merchant_name] = ts_epoch

            if signals:
                signals.log_message.emit(
                    f"[MERCHANT] {merchant_name} detected (log) for {player_name}"
                )

            cfg = next(
                (m for m in merchants if m["name"].lower() == merchant_name.lower()),
                {"name": merchant_name, "message": "", "color": "#ffffff", "role_id": ""}
            )

            # Read pslink from the settings dict already in scope — no extra load.
            _player_data = settings.get("players", {}).get(player_name, {})
            _ps_link = _player_data.get("pslink", "") if isinstance(_player_data, dict) else ""

            send_merchant_detected_message(
                merchant_name,
                cfg.get("message", ""),
                cfg.get("color", "#ffffff"),
                cfg.get("role_id", ""),
                player_name,
                line,
                None,
                None,
                show_image=False,
                ps_link=_ps_link,
            )
            break  # one ID per line


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize_merchants(raw_merchants):
    merchants = []
    for m in raw_merchants or []:
        if not isinstance(m, dict):
            continue
        name    = str(m.get("name",    "")).strip()
        message = str(m.get("message", "")).strip()
        color   = str(m.get("color",   "#ffffff")).strip()
        role_id = str(m.get("role_id", "")).strip()
        if not name or not message:
            continue
        merchants.append({"name": name, "message": message, "color": color, "role_id": role_id})
    return merchants or list(DEFAULT_MERCHANTS)


# ── Mirrors scanner_loop() from scanner.py ───────────────────────────────────

def merchant_detector_loop():
    """Main merchant detector thread — mirrors scanner_loop() from scanner.py."""
    global merchant_detector_running

    if signals:
        signals.log_message.emit("[START] Merchant detector running")
    try:
        settings = load_settings()

        while merchant_detector_running:
            _t0 = time.perf_counter()

            # Read config from snapshot — no disk read on the hot path.
            settings        = config_snapshot.current
            md              = settings.get("merchant_detection", {})
            scan_interval   = max(1, int(md.get("scan_interval", 2)))
            merchants       = _normalize_merchants(md.get("merchants", []))
            tracked_players = list(settings.get("players", {}).keys())
            log_path        = settings.get("general", {}).get("log_path", "")

            time.sleep(scan_interval)

            if log_path and merchants:
                with perf_log.timed("find_merchant_logs"):
                    find_merchant_logs(tracked_players, log_path)



            # Iterate the merchant: prefixed entries from runtime
            for key, info in list(_runtime.all_log_entries().items()):
                if not key.startswith("merchant:"):
                    continue
                name = key[len("merchant:"):]
                with perf_log.timed(f"read_merchant_lines[{name}]"):
                    read_merchant_lines(name, info, merchants, settings)

            _elapsed_ms = (time.perf_counter() - _t0) * 1000
            _runtime.update_health("merchant_detector", _elapsed_ms, slow_threshold_ms=500)
            
            # Refresh settings once per cycle, after all work is done.
            # Workers read the snapshot for this cycle; next cycle gets fresh settings.
            # Refresh once per cycle at end (kept for bootstrap cycle only)
        if signals:
            signals.log_message.emit("[STOP] Merchant detector stopped")
    except Exception:
        import traceback
        traceback.print_exc()
        if signals:
            signals.log_message.emit("[ERROR] Merchant detector crashed")
            signals.merchant_crashed.emit()

    finally:
        merchant_detector_running = False


# ── Public API ────────────────────────────────────────────────────────────────

def init(sig):
    global signals
    signals = sig
    signals.start_merchant_detector.connect(start_merchant_detector)
    signals.stop_merchant_detector.connect(stop_merchant_detector)


def start_merchant_detector(mode: str = ""):
    global merchant_detector_running
    if mode != "Log-Based":
        return
    if merchant_detector_running:
        return
    merchant_detector_running = True
    threading.Thread(
        target=merchant_detector_loop, daemon=True, name="MerchantDetector"
    ).start()


def stop_merchant_detector():
    global merchant_detector_running
    merchant_detector_running = False


def handle_merchant_event(player_name: str, payload: dict) -> None:
    """Called by log_indexer in the indexer thread. Must be fast."""
    merchant_name = payload.get("merchant", "")
    line          = payload.get("line", "")
    if not merchant_name or not signals:
        return
    signals.log_message.emit(
        f"[MERCHANT] {merchant_name} detected (indexer) for {player_name}"
    )
    # Webhook send is delegated to existing function — settings read happens here.
    from settings_manager import load_settings as _ls
    _s = _ls()
    merchants = _normalize_merchants(_s.get("merchant_detection", {}).get("merchants", []))
    _player_data = _s.get("players", {}).get(player_name, {})
    _ps_link = _player_data.get("pslink", "") if isinstance(_player_data, dict) else ""
    cfg = next(
        (m for m in merchants if m["name"].lower() == merchant_name.lower()),
        {"name": merchant_name, "message": "", "color": "#ffffff", "role_id": ""}
    )
    send_merchant_detected_message(
        merchant_name, cfg.get("message",""), cfg.get("color","#ffffff"),
        cfg.get("role_id",""), player_name, line, None, None,
        show_image=False, ps_link=_ps_link,
    )
