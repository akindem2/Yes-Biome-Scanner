import pydirectinput
import time
import threading
import win32gui
import win32con
import win32com.client
from settings_manager import load_settings

anti_afk_running = False
signals = None

def init(sig):
    """Initialize Anti-AFK and connect signals."""
    global signals
    signals = sig

    signals.start_anti_afk.connect(start_anti_afk)
    signals.stop_anti_afk.connect(stop_anti_afk)

def get_roblox_windows():
    hwnds =[]

    def enum_windows_proc(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd) == "Roblox":
            hwnds.append(hwnd)
        return True

    win32gui.EnumWindows(enum_windows_proc, None)
    return hwnds

def perform_anti_afk():
    """Brings each Roblox window to the front, presses Space, and restores original window."""
    roblox_hwnds = get_roblox_windows()
    if not roblox_hwnds:
        return

    original_hwnd = win32gui.GetForegroundWindow()
    shell = win32com.client.Dispatch("WScript.Shell")

    signals.log_message.emit(f"[ANTI-AFK] Triggering for {len(roblox_hwnds)} Roblox windows...")

    for hwnd in roblox_hwnds:
        try:
            placement = win32gui.GetWindowPlacement(hwnd)
            show_cmd = placement[1]

            # Only restore if minimized to prevent un-maximizing currently maximized windows
            if show_cmd == win32con.SW_SHOWMINIMIZED:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                
            shell.SendKeys('%')
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.2) 
            pydirectinput.press('space')
            time.sleep(0.2)
        except Exception as e:
            signals.log_message.emit(f"[ANTI-AFK] Error on window {hwnd}: {e}")

    try:
        if original_hwnd:
            placement = win32gui.GetWindowPlacement(original_hwnd)
            show_cmd = placement[1]

            # Only restore if minimized
            if show_cmd == win32con.SW_SHOWMINIMIZED:
                win32gui.ShowWindow(original_hwnd, win32con.SW_RESTORE)

            # Required to bypass Windows focus rules
            shell.SendKeys('%')

            win32gui.SetForegroundWindow(original_hwnd)
    except Exception as e:
        signals.log_message.emit(f"[ANTI-AFK] Could not restore original window: {e}")

def anti_afk_loop():
    """Background loop that triggers based on the custom interval."""
    global anti_afk_running
    
    # Load interval when started
    settings = load_settings()
    interval = int(settings.get("general", {}).get("anti_afk_interval", 600))
    
    last_trigger_time = time.time()

    while anti_afk_running:
        if time.time() - last_trigger_time >= interval:
            perform_anti_afk()
            
            # Reload interval just in case it was changed in settings
            settings = load_settings()
            interval = int(settings.get("general", {}).get("anti_afk_interval", 600))
            last_trigger_time = time.time()
            
        time.sleep(1) # Sleep 1 second to remain responsive to the stop button

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