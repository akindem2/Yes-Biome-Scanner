import multiprocessing
import sys
from PyQt6.QtWidgets import QApplication, QSplashScreen, QLabel
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont

from ui import BiomeScannerUI, UISignals
import scanner
import anti_afk

import log_indexer
import window_poller
import config_snapshot

import merchant_detector
import merchant_legacy
import auto_launcher
import bes_manager
import cookie_checker
import auto_item_manager
from settings_manager import ensure_settings, load_settings

def _make_splash_pixmap() -> QPixmap:
    """Draw a minimal branded splash screen entirely in code — no image file needed."""
    W, H = 420, 220
    px = QPixmap(W, H)
    px.fill(QColor("#0c0e14"))

    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Subtle border
    p.setPen(QColor("#272d3d"))
    p.drawRect(0, 0, W - 1, H - 1)

    # Title
    title_font = QFont("Consolas", 18, QFont.Weight.Bold)
    p.setFont(title_font)
    p.setPen(QColor("#3ec6e0"))
    p.drawText(0, 60, W, 40, Qt.AlignmentFlag.AlignHCenter, "◈  YES BIOME SCANNER")

    # Subtitle
    sub_font = QFont("Consolas", 10)
    p.setFont(sub_font)
    p.setPen(QColor("#7c8499"))
    p.drawText(0, 105, W, 24, Qt.AlignmentFlag.AlignHCenter, "Starting up, please wait…")

    # Loading bar background
    bar_x, bar_y, bar_w, bar_h = 60, 148, W - 120, 6
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#1a1e2a"))
    p.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 3, 3)

    # Animated-looking filled portion (static — just a visual cue)
    p.setBrush(QColor("#3ec6e0"))
    p.drawRoundedRect(bar_x, bar_y, int(bar_w * 0.55), bar_h, 3, 3)

    # Version hint
    ver_font = QFont("Consolas", 8)
    p.setFont(ver_font)
    p.setPen(QColor("#3a4258"))
    p.drawText(0, H - 20, W, 16, Qt.AlignmentFlag.AlignHCenter, "v1.1")

    p.end()
    return px


def main():
    multiprocessing.freeze_support()  # Must be first — prevents infinite process spawning in built exe

    ensure_settings()
    settings = load_settings()

    app = QApplication(sys.argv)

    # ── Splash screen ─────────────────────────────────────────────
    splash = QSplashScreen(_make_splash_pixmap(), Qt.WindowType.WindowStaysOnTopHint)
    splash.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    splash.show()
    app.processEvents()  # Make sure it paints before the heavy imports block the thread

    # Step 1 — populate config snapshot FIRST, before any init().
    # Workers read config_snapshot.current from the moment they start.
    config_snapshot._bootstrap()

    # Step 2 — create signals object.
    signals = UISignals()

    # Step 3 — init all subsystems.  scanner.init() calls update_players()
    # which emits players_updated — cards are populated before window.show().
    scanner.init(signals)
    anti_afk.init(signals)
    merchant_detector.init(signals)
    merchant_legacy.init(signals)
    auto_launcher.init(signals)
    bes_manager.init(signals)
    cookie_checker.init(signals)
    auto_item_manager.init(signals)

    # Step 4 — create window (connects signals → slots).
    window = BiomeScannerUI(signals)
    window.show()
    splash.finish(window)   # Fade out splash once the main window is ready

    # Step 5 — start background threads.
    # ── Log indexer ───────────────────────────────────────────────────
    # The on_event handler is called inside the indexer thread.
    # It must be fast and must not acquire the runtime RLock directly.
    def _on_log_event(event_type, player, payload):
        if event_type == log_indexer.EVENT_BIOME_FOUND:
            scanner.handle_biome_event(player, payload)
        elif event_type == log_indexer.EVENT_MERCHANT_FOUND:
            merchant_detector.handle_merchant_event(player, payload)

    log_indexer.register_handler(_on_log_event)

    def _get_indexer_config():
        from settings_manager import load_settings as _ls
        s = _ls()
        return {
            "log_dir":        s.get("general", {}).get("log_path", ""),
            "scan_interval":  s.get("general", {}).get("scan_interval", 2),
            "tracked_players": list(s.get("players", {}).keys()),
        }

    log_indexer.start(_get_indexer_config)

    def _on_settings_change(new_settings: dict) -> None:
        """Called on the UI thread whenever settings are saved."""
        new_log_dir = new_settings.get("general", {}).get("log_path", "")
        old_log_dir = config_snapshot.current.get("general", {}).get("log_path", "")
        if new_log_dir != old_log_dir:
            # Log directory changed — clear offset table so indexer rescans.
            import log_indexer as _li
            _li._offsets.clear()
            _li._log_paths.clear()
            _li._track_start.clear()
            signals.log_message.emit(
                f"[INFO] Log path changed — indexer will rescan {new_log_dir}"
            )

    config_snapshot.on_change(_on_settings_change)

    # ── Window poller ─────────────────────────────────────────────────
    def _get_poller_config():
        from settings_manager import load_settings as _ls
        s = _ls()
        return {
            "log_dir":             s.get("general", {}).get("log_path", ""),
            "tracked_players":     list(s.get("players", {}).keys()),
            "window_poll_interval": 3,
        }

    window_poller.start(_get_poller_config)

    # Run cookie check after the window is visible so log messages appear
    cookie_checker.run_startup_check()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
