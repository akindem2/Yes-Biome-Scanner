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

signals = None
merchant_detector_running = False

DEFAULT_MERCHANTS = []

# Mirrors scanner.py's player_logs: {player_name: {"file": path, "pos": int}}
_merchant_player_logs: Dict[str, dict] = {}

# Wall-clock (monotonic) time when each player's log was first assigned.
# Detections are suppressed for WINDOW_GRACE_PERIOD seconds after assignment.
_log_track_start: Dict[str, float] = {}
WINDOW_GRACE_PERIOD = 60.0  # seconds

_last_merchant_ts: Dict[str, Dict[str, float]] = {}
MERCHANT_DEDUPE_WINDOW = 1200.0  # 20 minutes — prevents same merchant firing multiple times

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
        current_file = _merchant_player_logs.get(name, {}).get("file")
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
        current_file = _merchant_player_logs.get(name, {}).get("file")

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
                _merchant_player_logs[name] = {"file": path, "pos": end_pos}
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

    while merchant_detector_running:
        settings        = load_settings()
        md              = settings.get("merchant_detection", {})
        scan_interval   = max(1, int(md.get("scan_interval", 2)))
        merchants       = _normalize_merchants(md.get("merchants", []))
        tracked_players = list(settings.get("players", {}).keys())
        log_path        = settings.get("general", {}).get("log_path", "")

        time.sleep(scan_interval)

        if log_path and merchants:
            find_merchant_logs(tracked_players, log_path)

            for name, info in list(_merchant_player_logs.items()):
                read_merchant_lines(name, info, merchants, settings)

    if signals:
        signals.log_message.emit("[STOP] Merchant detector stopped")


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
