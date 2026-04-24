import time
import threading
import ctypes
import win32gui
import win32process
from settings_manager import load_settings

VK_SPACE         = 0x20
KEYEVENTF_KEYUP  = 0x0002
KEYEVENTF_SCANCODE = 0x0008
SPACE_SCAN       = 0x39          # hardware scan code for Space

anti_afk_running = False
signals = None


def init(sig):
    global signals
    signals = sig
    signals.start_anti_afk.connect(start_anti_afk)
    signals.stop_anti_afk.connect(stop_anti_afk)


def get_roblox_windows():
    hwnds = []
    def _cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd) == "Roblox":
            hwnds.append(hwnd)
        return True
    win32gui.EnumWindows(_cb, None)
    return hwnds


def _get_pid_for_hwnd(hwnd: int) -> int | None:
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return int(pid)
    except Exception:
        return None


# ── SendInput structures ──────────────────────────────────────────────────────

class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk",         ctypes.c_ushort),
        ("wScan",       ctypes.c_ushort),
        ("dwFlags",     ctypes.c_ulong),
        ("time",        ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

class _INPUT(ctypes.Structure):
    _fields_ = [
        ("type",    ctypes.c_ulong),
        ("ki",      _KEYBDINPUT),
        ("padding", ctypes.c_ubyte * 8),
    ]

_INPUT_KEYBOARD = 1
user32 = ctypes.windll.user32


def _force_foreground(hwnd: int) -> bool:
    """Attempt to bring hwnd to the foreground. Returns True if successful."""
    import win32api, win32con

    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.1)

    cur_tid    = win32api.GetCurrentThreadId()
    target_tid, _ = win32process.GetWindowThreadProcessId(hwnd)

    user32.AttachThreadInput(cur_tid, target_tid, True)
    try:
        win32gui.BringWindowToTop(hwnd)
        win32gui.SetForegroundWindow(hwnd)
        # SwitchToThisWindow bypasses the Windows foreground lock
        user32.SwitchToThisWindow(hwnd, True)
    except Exception:
        pass
    finally:
        user32.AttachThreadInput(cur_tid, target_tid, False)

    # Poll up to 600 ms to confirm focus actually transferred
    deadline = time.time() + 0.6
    while time.time() < deadline:
        if win32gui.GetForegroundWindow() == hwnd:
            return True
        time.sleep(0.05)

    return False


def _send_space(hwnd: int) -> bool:
    """Bring hwnd to foreground, inject Space as a scan-code keystroke, restore focus.

    Using KEYEVENTF_SCANCODE makes the event indistinguishable from a physical
    keypress at the hardware level, which is what Roblox's Raw Input pipeline reads.
    """
    import win32api

    try:
        prev_hwnd = win32gui.GetForegroundWindow()

        if not _force_foreground(hwnd):
            if signals:
                signals.log_message.emit(f"[ANTI-AFK] Could not foreground window {hwnd}, skipping")
            return False

        # Extra settle time after confirmed focus
        time.sleep(0.15)

        # Key down — scan-code mode
        key_down            = _INPUT()
        key_down.type       = _INPUT_KEYBOARD
        key_down.ki.wVk     = 0  # Should be 0 when using SCANCODE
        key_down.ki.wScan   = SPACE_SCAN
        key_down.ki.dwFlags = KEYEVENTF_SCANCODE
        user32.SendInput(1, ctypes.byref(key_down), ctypes.sizeof(_INPUT))

        # Hold the key for 50ms so the game's engine has time to see the "Down" state
        time.sleep(0.05)

        # Key up — scan-code mode
        key_up              = _INPUT()
        key_up.type         = _INPUT_KEYBOARD
        key_up.ki.wVk       = 0
        key_up.ki.wScan     = SPACE_SCAN
        key_up.ki.dwFlags   = KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP
        user32.SendInput(1, ctypes.byref(key_up), ctypes.sizeof(_INPUT))

        # Let Roblox process the key before we leave
        time.sleep(0.2)

        # Restore previous foreground window
        if prev_hwnd and prev_hwnd != hwnd:
            try:
                cur_tid2   = win32api.GetCurrentThreadId()
                prev_tid, _ = win32process.GetWindowThreadProcessId(prev_hwnd)
                user32.AttachThreadInput(cur_tid2, prev_tid, True)
                try:
                    win32gui.SetForegroundWindow(prev_hwnd)
                finally:
                    user32.AttachThreadInput(cur_tid2, prev_tid, False)
            except Exception:
                pass

        return True
    except Exception:
        return False


def perform_anti_afk():
    roblox_hwnds = get_roblox_windows()
    if not roblox_hwnds:
        return

    signals.log_message.emit(f"[ANTI-AFK] Triggering for {len(roblox_hwnds)} Roblox windows...")

    try:
        import bes_manager as _bes
        _bes_available = _bes._controller is not None and _bes.bes_running
    except Exception:
        _bes = None
        _bes_available = False

    # Hold long enough for focus switch + keypress + restore per window
    _HOLD_SECONDS = 2.0 + len(roblox_hwnds) * 1.5

    held_pids: list[int] = []
    for hwnd in roblox_hwnds:
        pid = _get_pid_for_hwnd(hwnd)
        if pid is not None and _bes_available:
            try:
                _bes._controller.hold_unthrottled(pid, _HOLD_SECONDS)
                held_pids.append(pid)
            except Exception:
                pass

    # Give BES scheduler time to actually resume the Roblox threads
    if _bes_available and held_pids:
        time.sleep(0.15)

    for hwnd in roblox_hwnds:
        try:
            if not _send_space(hwnd):
                signals.log_message.emit(f"[ANTI-AFK] Failed to send Space to window {hwnd}")
        except Exception as e:
            signals.log_message.emit(f"[ANTI-AFK] Error on window {hwnd}: {e}")

    if _bes_available and held_pids:
        for pid in held_pids:
            try:
                _bes._controller.release_hold(pid)
            except Exception:
                pass


def anti_afk_loop():
    global anti_afk_running

    settings = load_settings()
    interval = int(settings.get("general", {}).get("anti_afk_interval", 600))
    last_trigger_time = time.time()

    while anti_afk_running:
        if time.time() - last_trigger_time >= interval:
            perform_anti_afk()
            settings = load_settings()
            interval = int(settings.get("general", {}).get("anti_afk_interval", 600))
            last_trigger_time = time.time()
        time.sleep(1)


def start_anti_afk():
    global anti_afk_running
    if anti_afk_running:
        return
    anti_afk_running = True
    signals.log_message.emit("[START] Anti-AFK running in background")
    threading.Thread(target=anti_afk_loop, daemon=True).start()


def stop_anti_afk():
    global anti_afk_running
    anti_afk_running = False
    signals.log_message.emit("[STOP] Anti-AFK stopped")