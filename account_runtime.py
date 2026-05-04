"""
account_runtime.py

Thread-safe central store for all runtime account state.
All subsystems read from and write to this singleton.
No module-level globals anywhere else.
"""

from __future__ import annotations

import threading
import time
from typing import Dict, Optional


class AccountRuntime:
    """
    Single, RLock-guarded store for all runtime account state.

    Internal dicts (all keyed on player name string):
      log_map    : name -> {file, pos, linked_at}
      biome_state: name -> {current, previous}
      window_cache: name -> {pid, hwnd, last_seen}
      health     : subsystem -> {last_beat, slow_cycles, status}

    RLock is used (not Lock) because some accessor methods call each
    other internally.  Never hold the lock across a sleep() or I/O call.
    """

    def __init__(self) -> None:
        self._lock          = threading.RLock()
        self._log_map:      Dict[str, dict] = {}
        self._biome_state:  Dict[str, dict] = {}
        self._window_cache: Dict[str, dict] = {}
        self._health:       Dict[str, dict] = {}

    # ── log map ──────────────────────────────────────────────────────

    def update_log_map(self, name: str, **kwargs) -> None:
        """Set/update fields on the log entry for *name*."""
        with self._lock:
            entry = self._log_map.setdefault(name, {})
            entry.update(kwargs)

    def get_log_info(self, name: str) -> Optional[dict]:
        """Return a shallow copy of the log entry for *name*, or None."""
        with self._lock:
            entry = self._log_map.get(name)
            return dict(entry) if entry else None

    def all_log_entries(self) -> Dict[str, dict]:
        """Return a shallow copy of the full log map."""
        with self._lock:
            return {k: dict(v) for k, v in self._log_map.items()}

    def clear_log_map(self) -> None:
        with self._lock:
            self._log_map.clear()

    # ── biome state ──────────────────────────────────────────────────

    def update_biome(self, name: str, biome: str) -> str:
        """
        Set the current biome for *name*.  Returns the previous biome
        (empty string if none).  The caller uses the return value to
        decide whether to fire webhook/ended events.
        """
        with self._lock:
            entry    = self._biome_state.setdefault(name, {})
            previous = entry.get("current", "")
            entry["previous"] = previous
            entry["current"]  = biome
            return previous

    def get_biome(self, name: str) -> str:
        with self._lock:
            return self._biome_state.get(name, {}).get("current", "")

    def clear_biome_state(self) -> None:
        with self._lock:
            self._biome_state.clear()

    # ── window cache ─────────────────────────────────────────────────

    def update_window(self, name: str, pid: int, hwnd: int) -> None:
        with self._lock:
            self._window_cache[name] = {
                "pid":       pid,
                "hwnd":      hwnd,
                "last_seen": time.monotonic(),
            }

    def get_window(self, name: str) -> Optional[dict]:
        with self._lock:
            entry = self._window_cache.get(name)
            return dict(entry) if entry else None

    def all_windows(self) -> Dict[str, dict]:
        with self._lock:
            return {k: dict(v) for k, v in self._window_cache.items()}

    def replace_window_cache(self, new_cache: Dict[str, dict]) -> None:
        """Atomically replace the full window cache (used by window_poller)."""
        with self._lock:
            self._window_cache = {k: dict(v) for k, v in new_cache.items()}

    # ── health ───────────────────────────────────────────────────────

    def update_health(self, subsystem: str, elapsed_ms: float,
                      slow_threshold_ms: float = 500.0) -> None:
        with self._lock:
            entry = self._health.setdefault(subsystem, {"slow_cycles": 0, "status": "OK"})
            entry["last_beat"] = time.monotonic()
            if elapsed_ms >= slow_threshold_ms:
                entry["slow_cycles"] = entry.get("slow_cycles", 0) + 1
                entry["status"] = "SLOW"
            else:
                entry["status"] = "OK"

    # ── snapshot (UI-safe read) ───────────────────────────────────────

    def snapshot(self) -> dict:
        """
        Return a plain dict of dicts safe to hand to the UI thread.
        Acquires the lock for the full copy duration to prevent torn reads.
        The UI must only ever receive snapshots, never live internal objects.
        """
        with self._lock:
            return {
                "log_map":      {k: dict(v) for k, v in self._log_map.items()},
                "biome_state":  {k: dict(v) for k, v in self._biome_state.items()},
                "window_cache": {k: dict(v) for k, v in self._window_cache.items()},
                "health":       {k: dict(v) for k, v in self._health.items()},
            }


# Module-level singleton — import this everywhere.
# Never instantiate AccountRuntime() directly in any other module.
runtime: AccountRuntime = AccountRuntime()