"""
config_snapshot.py

In-memory config snapshot.  Written to disk only on user save.
Workers read config_snapshot.current — never load_settings() at runtime.

Push flow:
  1. App starts: _bootstrap() loads from disk once, sets current.
  2. User saves settings: settings_manager.save_settings() calls push().
  3. Workers that need a restart register via on_change().

Thread safety:
  current is a plain dict replaced atomically (Python object assignment
  is atomic under the GIL).  Readers see either the old or new snapshot,
  never a torn partial state.  No explicit lock needed for reading.
"""

from __future__ import annotations

import threading
from typing import Callable, List

# The live snapshot.  Replace this reference atomically on push().
# Workers read this directly: config_snapshot.current
current: dict = {}

_callbacks: List[Callable[[dict], None]] = []
_cb_lock   = threading.Lock()


def push(new_settings: dict) -> None:
    """
    Atomically replace the current snapshot and notify all registered
    callbacks.  Called by settings_manager.save_settings() after every save.
    Callbacks run on the calling thread (UI thread) — keep them fast.
    """
    global current
    current = new_settings          # atomic under GIL
    with _cb_lock:
        cbs = list(_callbacks)
    for fn in cbs:
        try:
            fn(new_settings)
        except Exception:
            import traceback; traceback.print_exc()


def on_change(fn: Callable[[dict], None]) -> None:
    """
    Register a callback to be called with the new settings dict
    whenever push() is called.
    Use this to restart subsystems that depend on settings that require
    a restart to take effect (e.g. log_dir change for the log indexer).
    """
    with _cb_lock:
        _callbacks.append(fn)


def _bootstrap() -> None:
    """
    Load settings from disk once at startup.
    Called from main.py before any subsystem starts.
    """
    from settings_manager import load_settings
    push(load_settings())