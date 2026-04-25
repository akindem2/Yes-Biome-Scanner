import os
import time
import threading
from datetime import datetime, timezone
from settings_manager import load_settings
from webhook import send_webhook_found_message, send_webhook_ended_message, send_start_webhook, send_stop_webhook

signals = None

# Runtime state
player_logs = {}
current_biome = {}
active_players =[]
player_pslinks = {}
scanner_running = False

def is_log_active(filepath, max_age_seconds=120):
    """Check if a log file is from an active Roblox session.
    
    Roblox no longer locks log files, so we use a recency-based approach:
    if the file was modified within max_age_seconds, it's likely active.
    We also try the legacy lock check as a fallback.
    """
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
        with open(filepath, 'a') as f:
            pass
        return False
    except PermissionError:
        return True
    except Exception:
        return False

def _list_detection_logs(log_path):
    """Return the most recent candidate log files for player and biome detection."""
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

def _list_cleanup_logs(log_path):
    """Return log files that cleanup is still allowed to delete."""
    all_logs = []
    try:
        for entry in os.scandir(log_path):
            if entry.is_file() and entry.name.endswith((".log", ".logs")):
                all_logs.append(entry.path)
    except FileNotFoundError:
        pass
    return [path for path in all_logs if path not in _failed_deletions]

# Tracks log files that have already failed to delete — never retried for cleanup again
_failed_deletions = set()

def init(sig):
    """Initialize scanner and connect signals."""
    global signals
    signals = sig

    signals.start_scanner.connect(start_scanner)
    signals.stop_scanner.connect(stop_scanner)
    signals.players_updated.connect(update_players)

    # Load initial players from settings
    settings = load_settings()
    update_players(settings.get("players", {}))


def load_runtime_settings():
    """Load settings.json values used during scanning."""
    settings = load_settings()
    general = settings.get("general", {})

    return {
        "log_path": general.get("log_path"),
        "scan_interval": general.get("scan_interval", 1),
        "auto_cleanup": general.get("auto_cleanup", True)
    }


def find_player_logs(log_path):
    """Find which log file each player is using, preferring the newest active one."""
    if not active_players:
        return

    # OPTIMIZATION: Only sweep the massive Roblox logs folder if a player is MISSING a log
    needs_search = False
    for name in active_players:
        current_file = player_logs.get(name, {}).get("file")
        if not current_file or not is_log_active(current_file):
            needs_search = True
            break
            
    if not needs_search:
        return # Skip finding logs if everyone is already happily connected!

    log_files = _list_detection_logs(log_path)
    if not log_files:
        return

    # Find logs from active Roblox sessions (recently modified or file-locked)
    active_logs =[path for path in log_files if is_log_active(path)]

    # Sort newest to oldest based on Creation Time
    try:
        active_logs.sort(key=lambda x: os.path.getctime(x), reverse=True)
    except Exception:
        pass

    for name in active_players:
        current_file = player_logs.get(name, {}).get("file")

        for path in active_logs:
            # If we hit our currently linked file, it means there are no newer files
            if path == current_file:
                break

            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    data = f.read()
            except Exception:
                continue

            if name in data:
                signals.log_message.emit(f"[INFO] {name} is using log: {path}")
                # Setting pos to 0 forces it to read the entire file history immediately
                # to catch biomes printed while the game was still loading.
                player_logs[name] = {"file": path, "pos": 0}
                break


def read_new_lines(player_name, info):
    """Read new log lines and detect biome changes."""
    path = info["file"]
    last_pos = info["pos"]

    try:
        size = os.path.getsize(path)
    except FileNotFoundError:
        return

    if size <= last_pos:
        return

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        f.seek(last_pos)
        new_data = f.read()

    info["pos"] = size

    found_biome = None

    # Each entry: (hoverText as it appears in the log, internal biome name)
    BIOME_DEFINITIONS = [
        ("SNOWY",       "snowy"),
        ("RAINY",       "rainy"),
        ("EGGLAND",     "eggland"),
        ("WINDY",       "windy"),
        ("CORRUPTION",  "corruption"),
        ("HEAVEN",      "heaven"),
        ("HELL",        "hell"),
        ("NULL",        "null"),
        ("GLITCHED",    "glitched"),
        ("DREAMSPACE",  "dreamspace"),
        ("SAND STORM",  "sand storm"),
        ("STARFALL",    "starfall"),
        ("CYBERSPACE",  "cyberspace"),
        ("SINGULARITY", "singularity"),
    ]

    # Format matches the log line: {"hoverText":"[name]",
    biome_map = {
        f'{{"hoverText":"{hover}",': internal
        for hover, internal in BIOME_DEFINITIONS
    }

    lines = new_data.splitlines()
    last_parsed_time = None
    now = datetime.now(timezone.utc)
    is_old = False

    # Scan backwards for biome
    for line in reversed(lines):
        # Attempt to parse time from the beginning of the Roblox log line
        if len(line) > 20 and line.startswith("202"):
            ts_part = line.split(",", 1)[0].split(" ")[0]
            if "T" in ts_part:
                try:
                    ts_str = ts_part.replace("Z", "+00:00")
                    log_time = datetime.fromisoformat(ts_str)
                    log_time = log_time.astimezone(timezone.utc)
                    last_parsed_time = log_time
                except Exception:
                    pass

        line_lower = line
        for search_str, true_biome in biome_map.items():
            if search_str in line_lower:
                found_biome = true_biome
                break
        
        if found_biome:
            # Mark if the found biome is from an old log line
            if last_parsed_time and (now - last_parsed_time).total_seconds() > 30:
                is_old = True
            break
            
        # To prevent scanning massive log files indefinitely if no biome exists,
        # we can break if we go way too far back (e.g., 20 minutes)
        if last_parsed_time and (now - last_parsed_time).total_seconds() > 1200:
            break

    if not found_biome:
        return

    previous = current_biome.get(player_name)

    if previous == found_biome:
        return

    current_biome[player_name] = found_biome

    if is_old:
        # We found the biome for auto-item state, but it's too old to trigger alerts
        signals.log_message.emit(f"[BIOME] {player_name} resumed in biome: {found_biome} (silenced alert)")
        signals.biome_update.emit(player_name, found_biome)
        return

    # Biome ended
    if previous:
        signals.log_message.emit(f"[BIOME] {player_name} biome ended: {previous}")
        send_webhook_ended_message(previous, player_name)

    # Biome started
    signals.log_message.emit(f"[BIOME] {player_name} biome started: {found_biome}")
    signals.biome_update.emit(player_name, found_biome)

    ps_link = player_pslinks.get(player_name)
    send_webhook_found_message(found_biome, player_name, ps_link)


def cleanup_unlinked_logs(log_path):
    """Delete logs not linked to any player."""
    all_logs = _list_cleanup_logs(log_path)
    if not all_logs:
        return

    linked_logs = {info["file"] for info in player_logs.values()}
    current_time = time.time()

    for log in all_logs:
        if log not in linked_logs:
            try:
                # 60 Second Grace Period
                if current_time - os.path.getctime(log) < 60:
                    continue
            except OSError:
                continue

            try:
                os.remove(log)
                signals.log_message.emit(f"[CLEANUP] Deleted unlinked log: {log}")
            except Exception as e:
                # Fails naturally if the log is locked by Roblox, which is good
                pass


def scanner_loop():
    """Main scanner thread."""
    global scanner_running

    settings = load_runtime_settings()
    log_path = settings["log_path"]
    scan_interval = settings["scan_interval"]
    auto_cleanup = settings["auto_cleanup"]

    try:
        signals.log_message.emit("[START] Scanner thread running")
        send_start_webhook(len(active_players))
        
        while scanner_running:
            time.sleep(scan_interval)

            find_player_logs(log_path)

            if auto_cleanup:
                cleanup_unlinked_logs(log_path)

            for name, info in list(player_logs.items()):
                read_new_lines(name, info)

        signals.log_message.emit("[STOP] Scanner stopped")
        send_stop_webhook()

    except Exception as e:
        import traceback
        traceback.print_exc()


def start_scanner():
    """Start scanner thread."""
    global scanner_running
    if scanner_running:
        return

    scanner_running = True
    threading.Thread(target=scanner_loop, daemon=True).start()


def stop_scanner():
    """Stop scanner thread."""
    global scanner_running
    scanner_running = False


def update_players(player_dict):
    """Update active players + PS links."""
    global active_players, player_logs, current_biome, player_pslinks

    active_players = list(player_dict.keys())
    player_pslinks = player_dict

    # Reset logs + biome state
    player_logs = {}
    current_biome = {}

    signals.log_message.emit(f"[INFO] Updated players: {active_players}")
