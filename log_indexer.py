"""
log_indexer.py

Single daemon thread that owns all log file scanning.
Replaces the independent scan loops in scanner.py and merchant_detector.py.

Consumers register handlers via register_handler().  Each handler is called
synchronously inside the indexer thread — keep handlers fast and non-blocking.
Handlers must NOT call runtime accessors that acquire the RLock (deadlock risk).
"""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

import perf_log
from account_runtime import runtime


# ── Biome detection — canonical rule ────────────────────────────────
# Copy BIOME_DEFINITIONS from scanner.py when migrating.
# assetId values must be the real IDs confirmed from Roblox logs.
# Format: (hoverText, assetId, internal_name)
BIOME_DEFINITIONS: List[tuple] = [
    ("SNOWY",      109912975653138, "snowy"),
    ("RAINY",      137992545432987, "rainy"),
    ("EGGLAND",    107114559110957, "eggland"),
    ("WINDY",      138169499467564, "windy"),
    ("CORRUPTION", 137622939436355, "corruption"),
    ("HEAVEN",     100160513248702, "heaven"),
    ("HELL",       89721298978404, "hell"),
    ("NULL",       120277135407020, "null"),
    ("GLITCHED",   92180140049616, "glitched"),
    ("DREAMSPACE", 124768988619166, "dreamspace"),
    ("SAND STORM", 102180669654341, "sand storm"),
    ("STARFALL",   110087292131274, "starfall"),
    ("CYBERSPACE", 89000537898277, "cyberspace"),
    ("SINGULARITY", 107114559110957, "singularity"),
]

# NOTE: "line_lower" variable in scanner.py is a misnomer — lines are NOT
# lowercased.  Matching is case-sensitive by design: BIOME_DEFINITIONS uses
# the exact title-case from the Roblox log.  Do NOT add .lower() here.
_BIOME_MAP: Dict[str, str] = {
    f'{{"hoverText":"{hover}","assetId":{asset_id}}}': internal
    for hover, asset_id, internal in BIOME_DEFINITIONS
}


def _detect_biome(line: str) -> Optional[str]:
    """
    Return internal biome name if line contains the exact structured
    substring {"hoverText":"NAME","assetId":ID}.  Otherwise None.
    """
    for search_str, internal in _BIOME_MAP.items():
        if search_str in line:
            return internal
    return None


# ── Merchant animation IDs (mirrors merchant_detector.py) ────────────
MERCHANT_ANIMATION_IDS: Dict[str, str] = {
    "18247165978":    "Mari",
    "18247420806":    "Jester",
    "97148159887178": "Rin",
}
_ID_STRINGS = set(MERCHANT_ANIMATION_IDS.keys())


# ── Event types ──────────────────────────────────────────────────────
# Handlers receive (event_type, player_name, payload_dict).
EVENT_BIOME_FOUND    = "biome_found"
EVENT_MERCHANT_FOUND = "merchant_found"
EVENT_DISCONNECT     = "disconnect"

Handler = Callable[[str, str, dict], None]
_handlers: List[Handler] = []
_handlers_lock = threading.Lock()


def register_handler(fn: Handler) -> None:
    """Register a callable to receive all parsed events."""
    with _handlers_lock:
        _handlers.append(fn)


def _emit(event_type: str, player: str, payload: dict) -> None:
    with _handlers_lock:
        handlers = list(_handlers)
    for fn in handlers:
        try:
            fn(event_type, player, payload)
        except Exception:
            import traceback; traceback.print_exc()


# ── Internal state (private to indexer thread) ───────────────────────
# Offsets are written here so the indexer thread never has to acquire
# the RLock on the hot path.  runtime.update_log_map() is called once
# per cycle to sync the canonical store.
_offsets:      Dict[str, int]   = {}   # player_name -> file offset
_log_paths:    Dict[str, str]   = {}   # player_name -> log path
_track_start:  Dict[str, float] = {}   # player_name -> monotonic time
_last_merch_ts: Dict[str, Dict[str, float]] = {}
_stale_cycles: Dict[str, int]   = {}   # player_name -> consecutive cycles with no new bytes

# ── Log indexer loop ─────────────────────────────────────────────────
_indexer_running = False


def _list_logs(log_dir: str) -> List[str]:
    try:
        return [
            os.path.join(log_dir, f)
            for f in os.listdir(log_dir)
            if f.endswith((".log", ".logs"))
        ]
    except FileNotFoundError:
        return []


def _is_active(path: str, max_age: int = 120) -> bool:
    try:
        return time.time() - os.path.getmtime(path) < max_age
    except OSError:
        return False


def _username_in_log(path: str, name: str) -> bool:
    """
    Return True if the log file at path belongs to the given player.
    Reads the entire file and checks for the username both
    case-sensitively and case-insensitively, since Roblox log headers
    vary in casing across versions and username may appear at any point.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            data = f.read()
    except Exception:
        return False
    name_lower = name.lower()
    return name in data or name_lower in data.lower()


# Number of consecutive no-growth cycles before a log is considered stale
# and re-linking is forced.  At a 2 s interval this is 60 s of silence.
_STALE_CYCLE_LIMIT = 30


# Tracks the last log path before unlinking, so _link_players() can
# skip it and avoid immediately re-linking to the same dead log.
_last_unlinked: Dict[str, str] = {}  # player_name -> path that was unlinked


def _unlink_player(name: str) -> None:
    """Clear a player's log assignment so _link_players() will rescan for them."""
    old_path = _log_paths.pop(name, None)
    if old_path:
        _last_unlinked[name] = old_path
    _offsets.pop(name, None)
    _track_start.pop(name, None)
    _stale_cycles.pop(name, None)
    runtime.update_log_map(name, file=None, pos=0)


def _link_players(tracked: List[str], log_dir: str) -> None:
    """
    For any player who lacks an active log, scan active log files and
    link the newest one that contains their username in the header.
    Updates both _log_paths/_offsets and runtime.update_log_map().
    """
    needs = [
        n for n in tracked
        if not _log_paths.get(n)
    ]
    if not needs:
        return

    active = [p for p in _list_logs(log_dir) if _is_active(p)]
    try:
        active.sort(key=lambda x: os.path.getctime(x), reverse=True)
    except Exception:
        pass

    for name in needs:
        skip_path = _last_unlinked.get(name)  # don't re-link to the log we just left
        for path in active:
            if path == skip_path:
                continue
            if not _username_in_log(path, name):
                continue
            # New log found — link from the start so we catch the current
            # biome line Roblox writes at session start, but mark all lines
            # as old so they don't trigger webhook alerts.
            _log_paths[name]    = path
            _offsets[name]      = 0
            _stale_cycles[name] = 0
            _track_start[name]  = time.monotonic()
            _last_unlinked.pop(name, None)  # clear skip guard on successful link
            runtime.update_log_map(name, file=path, pos=0)
            break


def _parse_timestamp(line: str) -> Optional[datetime]:
    if len(line) <= 20 or not line.startswith("202"):
        return None
    ts_part = line.split(",", 1)[0].split(" ")[0]
    if "T" not in ts_part:
        return None
    try:
        return datetime.fromisoformat(
            ts_part.replace("Z", "+00:00")
        ).astimezone(timezone.utc)
    except Exception:
        return None


def _process_new_lines(player: str, new_data: str) -> None:
    """Parse new log content and emit events for biome/merchant/disconnect."""
    if not new_data:
        return

    now   = datetime.now(timezone.utc)
    lines = new_data.splitlines()

    # ── Biome detection (backwards scan, mirrors scanner.py) ──────────
    last_ts: Optional[datetime] = None
    found_biome: Optional[str]  = None
    is_old = False

    for line in reversed(lines):
        ts = _parse_timestamp(line)
        if ts:
            last_ts = ts

        biome = _detect_biome(line)
        if biome:
            found_biome = biome
            if last_ts and (now - last_ts).total_seconds() > 30:
                is_old = True
            break

        if last_ts and (now - last_ts).total_seconds() > 1200:
            break

    if found_biome:
        _emit(EVENT_BIOME_FOUND, player, {
            "biome":  found_biome,
            "is_old": is_old,
        })

    # ── Merchant detection (forward scan) ────────────────────────────
    if not any(id_str in new_data for id_str in _ID_STRINGS):
        return   # fast pre-filter

    player_ts = _last_merch_ts.setdefault(player, {})
    last_ts   = None

    for line in lines:
        ts = _parse_timestamp(line)
        if ts:
            last_ts = ts

        if last_ts and (now - last_ts).total_seconds() > 1200:
            break

        for id_str in _ID_STRINGS:
            if id_str not in line:
                continue
            if last_ts is None:
                break
            if (now - last_ts).total_seconds() > 30:
                break
            merchant_name = MERCHANT_ANIMATION_IDS[id_str]
            ts_epoch      = last_ts.timestamp()
            last_seen     = player_ts.get(merchant_name, 0.0)
            if abs(ts_epoch - last_seen) < 1200.0:
                break
            player_ts[merchant_name] = ts_epoch
            _emit(EVENT_MERCHANT_FOUND, player, {
                "merchant": merchant_name,
                "line":     line,
            })
            break


def _indexer_loop(get_config) -> None:
    """
    Main indexer loop.  get_config() is called each cycle and must return
    a dict with at least: {log_dir, scan_interval, tracked_players}.
    """
    global _indexer_running
    _indexer_running = True

    try:
        while _indexer_running:
            t0  = time.perf_counter()
            cfg = get_config()

            log_dir         = cfg.get("log_dir", "")
            scan_interval   = max(1, cfg.get("scan_interval", 2))
            tracked_players = cfg.get("tracked_players", [])

            if log_dir and tracked_players:
                with perf_log.timed("log_indexer.link_players"):
                    _link_players(tracked_players, log_dir)

                for player in tracked_players:
                    path   = _log_paths.get(player)
                    offset = _offsets.get(player, 0)
                    if not path:
                        continue
                    try:
                        size = os.path.getsize(path)
                    except FileNotFoundError:
                        # Log file deleted — unlink immediately.
                        _unlink_player(player)
                        continue
                    if size <= offset:
                        # No new bytes this cycle — increment stale counter.
                        _stale_cycles[player] = _stale_cycles.get(player, 0) + 1
                        if _stale_cycles[player] >= _STALE_CYCLE_LIMIT:
                            # Log has been silent too long — player likely
                            # switched servers.  Unlink so _link_players()
                            # rescans for a newer log next cycle.
                            _unlink_player(player)
                        continue
                    # Log is growing — reset stale counter.
                    _stale_cycles[player] = 0
                    try:
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            f.seek(offset)
                            new_data = f.read()
                    except Exception:
                        continue
                    _offsets[player] = size
                    runtime.update_log_map(player, pos=size)
                    with perf_log.timed(f"log_indexer.parse[{player}]"):
                        _process_new_lines(player, new_data)

            elapsed_ms = (time.perf_counter() - t0) * 1000
            runtime.update_health("log_indexer", elapsed_ms, slow_threshold_ms=500)
            time.sleep(scan_interval)

    except Exception:
        import traceback; traceback.print_exc()
    finally:
        _indexer_running = False


def start(get_config) -> None:
    """Start the indexer daemon thread.  get_config is called each cycle."""
    threading.Thread(
        target=_indexer_loop,
        args=(get_config,),
        daemon=True,
        name="LogIndexer",
    ).start()


def stop() -> None:
    global _indexer_running
    _indexer_running = False
