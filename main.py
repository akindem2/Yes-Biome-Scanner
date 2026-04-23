import multiprocessing
import sys
from PyQt6.QtWidgets import QApplication, QSplashScreen, QLabel
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont

from ui import BiomeScannerUI, UISignals
import scanner
import anti_afk
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

    signals = UISignals()

    scanner.init(signals)
    anti_afk.init(signals)
    merchant_detector.init(signals)
    merchant_legacy.init(signals)
    auto_launcher.init(signals)
    bes_manager.init(signals)
    cookie_checker.init(signals)
    auto_item_manager.init(signals)

    window = BiomeScannerUI(signals)
    window.show()
    splash.finish(window)   # Fade out splash once the main window is ready

    # Run cookie check after the window is visible so log messages appear
    cookie_checker.run_startup_check()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
