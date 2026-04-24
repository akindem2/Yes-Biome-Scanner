import subprocess
import threading
import requests
import roblox_launcher
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QPushButton, QTextEdit, QListWidget,
    QListWidgetItem, QLineEdit, QFormLayout, QMessageBox, QHBoxLayout,
    QStackedWidget, QCheckBox, QFrame, QDialog, QScrollArea, QComboBox,
    QSizePolicy, QSpinBox, QApplication, QScrollArea
)
from PyQt6.QtCore import (
    pyqtSignal, QObject, Qt, QPropertyAnimation, QEasingCurve,
    QTimer, QUrl, QThread
)
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor, QPainter, QFont, QPixmap

from settings_manager import load_settings, save_settings, mark_cookie_invalid

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineScript
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False
from trimmer import TrimmerTab  

# ------------------------------------------------------------------
# COLOR THEMES
# ------------------------------------------------------------------
THEMES = {
    "Classic": {
        "bg": "#0c0e14", "surface": "#13161f", "surface_2": "#1a1e2a", "surface_3": "#222738",
        "border": "#272d3d", "border_hi": "#3a4258", "text": "#dde1ec", "text_dim": "#7c8499",
        "accent": "#3ec6e0", "accent_hi": "#65d8ef", "accent_dim": "#1a6b7a", "green": "#3edfa0",
        "red": "#e05555", "yellow": "#e0c35e", "purple": "#9c7fe0",
    },
    "Dark": {
        "bg": "#0d0d0d", "surface": "#141414", "surface_2": "#1f1f1f", "surface_3": "#2e2e2e",
        "border": "#333333", "border_hi": "#4d4d4d", "text": "#e0e0e0", "text_dim": "#888888",
        "accent": "#bb86fc", "accent_hi": "#ffffff", "accent_dim": "#3700b3", "green": "#03dac6",
        "red": "#cf6679", "yellow": "#f6c342", "purple": "#bb86fc",
    },
    "Light": {
        "bg": "#f4f5f7", "surface": "#ffffff", "surface_2": "#ebeef0", "surface_3": "#dfe1e5",
        "border": "#dcdfe4", "border_hi": "#c1c7d0", "text": "#172b4d", "text_dim": "#5e6c84",
        "accent": "#0052cc", "accent_hi": "#0065ff", "accent_dim": "#deebff", "green": "#00875a",
        "red": "#de350b", "yellow": "#ff991f", "purple": "#5243aa",
    },
    "Mocha": {
        "bg": "#1e1b18", "surface": "#2b2622", "surface_2": "#38312c", "surface_3": "#453c36",
        "border": "#524840", "border_hi": "#6f6156", "text": "#e8e0d5", "text_dim": "#a39586",
        "accent": "#d2b48c", "accent_hi": "#e6cda3", "accent_dim": "#8c6b4a", "green": "#8fbc8f",
        "red": "#cd5c5c", "yellow": "#f4a460", "purple": "#9370db",
    },
    "Cherry": {
        "bg": "#1a0f14", "surface": "#26151d", "surface_2": "#331c27", "surface_3": "#402230",
        "border": "#4d293a", "border_hi": "#66364d", "text": "#f0d9e5", "text_dim": "#ad7a96",
        "accent": "#ff4d6d", "accent_hi": "#ff758f", "accent_dim": "#a32a42", "green": "#52b788",
        "red": "#ef233c", "yellow": "#ffd166", "purple": "#b56576",
    },

    "Galaxy": {
        "bg": "#0b0a14", "surface": "#151225", "surface_2": "#1f1a33", "surface_3": "#2a2245",
        "border": "#3a2f5c", "border_hi": "#56458a",
        "text": "#e8e3ff", "text_dim": "#9a8fc2",
        "accent": "#b45cff", "accent_hi": "#d28aff", "accent_dim": "#6a2ca3",
        "green": "#5de6c1", "red": "#ff4f81", "yellow": "#ffd479", "purple": "#c77dff",
    },

    "Eclipse": {
        "bg": "#140b00", "surface": "#1f1200", "surface_2": "#2b1800", "surface_3": "#3a2100",
        "border": "#4a2a00", "border_hi": "#6a3c00",
        "text": "#ffe8c7", "text_dim": "#b08a63",
        "accent": "#ff8c00", "accent_hi": "#ffb347", "accent_dim": "#a65a00",
        "green": "#7fd37f", "red": "#ff4d3d", "yellow": "#ffc857", "purple": "#c77dff",
    },

    "Black//White": {  # black with white accents + text
        "bg": "#000000", "surface": "#0a0a0a", "surface_2": "#141414", "surface_3": "#1f1f1f",
        "border": "#2a2a2a", "border_hi": "#3d3d3d",
        "text": "#ffffff", "text_dim": "#bfbfbf",
        "accent": "#ffffff", "accent_hi": "#e6e6e6", "accent_dim": "#808080",
        "green": "#7fffd4", "red": "#ff6b6b", "yellow": "#ffe066", "purple": "#c8a2ff",
    },

    "Mint": {
        "bg": "#0f1a17", "surface": "#152420", "surface_2": "#1d2f2a", "surface_3": "#263a34",
        "border": "#2f4740", "border_hi": "#42675a",
        "text": "#e6fff7", "text_dim": "#9ac7b8",
        "accent": "#6ff2c4", "accent_hi": "#9fffe0", "accent_dim": "#3aa685",
        "green": "#7fffd4", "red": "#ff6b6b", "yellow": "#ffe066", "purple": "#b39fff",
    },

    "Cotton Candy": {
        "bg": "#1a1420", "surface": "#241a2c", "surface_2": "#2f2138", "surface_3": "#3b2a45",
        "border": "#4a3658", "border_hi": "#6a4c7d",
        "text": "#ffeaff", "text_dim": "#c7a6c7",
        "accent": "#ff8ad6", "accent_hi": "#ffb3e6", "accent_dim": "#b34f8f",
        "green": "#8fffcf", "red": "#ff6b9c", "yellow": "#ffd6a5", "purple": "#d6a2ff",
    },

    "Electric": {
        "bg": "#041014", "surface": "#071a20", "surface_2": "#0c242c", "surface_3": "#12303a",
        "border": "#1a3f4a", "border_hi": "#2a5f6a",
        "text": "#d9faff", "text_dim": "#8ab3ba",
        "accent": "#00e5ff", "accent_hi": "#66f3ff", "accent_dim": "#008a99",
        "green": "#00ffcc", "red": "#ff4d6d", "yellow": "#ffe066", "purple": "#9d4dff",
    },

    "Ultraviolet": {
        "bg": "#0a0010", "surface": "#14001f", "surface_2": "#1f0030", "surface_3": "#2a0040",
        "border": "#3a005c", "border_hi": "#5c0090",
        "text": "#ffd9ff", "text_dim": "#b38ab3",
        "accent": "#ff2bd6", "accent_hi": "#ff6ae6", "accent_dim": "#a6008f",
        "green": "#00ffcc", "red": "#ff4d6d", "yellow": "#ffe066", "purple": "#d28aff",
    },

    "Forest": {
        "bg": "#0d140f", "surface": "#162018", "surface_2": "#1f2b22", "surface_3": "#29362c",
        "border": "#334238", "border_hi": "#4a5f52",
        "text": "#e6f2e9", "text_dim": "#9bb3a3",
        "accent": "#4caf50", "accent_hi": "#7cd67f", "accent_dim": "#2f6e32",
        "green": "#7fffd4", "red": "#e85d5d", "yellow": "#e6c76b", "purple": "#a8a2ff",
    },

    "Ocean": {
        "bg": "#07141a", "surface": "#0b1f29", "surface_2": "#102a35", "surface_3": "#163544",
        "border": "#1d4454", "border_hi": "#2d6275",
        "text": "#d9f3ff", "text_dim": "#8ab3c7",
        "accent": "#3ec6e0", "accent_hi": "#65d8ef", "accent_dim": "#1a6b7a",
        "green": "#52e6b5", "red": "#ff6b6b", "yellow": "#ffd479", "purple": "#9d8cff",
    },

    "Moss": {
        "bg": "#12140d", "surface": "#1a1f12", "surface_2": "#232a18", "surface_3": "#2d351f",
        "border": "#374027", "border_hi": "#4f5a39",
        "text": "#f0f5e6", "text_dim": "#aeb8a0",
        "accent": "#b4d455", "accent_hi": "#d4f27a", "accent_dim": "#7a8f33",
        "green": "#9fe870", "red": "#d96b6b", "yellow": "#e6d96b", "purple": "#b8a2ff",
    },

    "Slate": {
        "bg": "#0f1114", "surface": "#171a1f", "surface_2": "#20242a", "surface_3": "#2a2f36",
        "border": "#343a43", "border_hi": "#4a525e",
        "text": "#e3e7ec", "text_dim": "#9aa1ac",
        "accent": "#5c7cfa", "accent_hi": "#8da2ff", "accent_dim": "#2f3f8f",
        "green": "#6fe6b5", "red": "#e66f6f", "yellow": "#e6c76b", "purple": "#9d8cff",
    },

    "Graphite": {
        "bg": "#111213", "surface": "#1a1b1d", "surface_2": "#232528", "surface_3": "#2d2f33",
        "border": "#383b40", "border_hi": "#4d5157",
        "text": "#e5e7ea", "text_dim": "#9da2a8",
        "accent": "#9aa0a6", "accent_hi": "#c3c7cc", "accent_dim": "#5a5f63",
        "green": "#7fd3a0", "red": "#e06b6b", "yellow": "#e6c76b", "purple": "#a8a2ff",
    }
}

COLORS    = {}
LOG_COLORS = {}

def apply_global_theme(theme_name):
    if theme_name not in THEMES:
        theme_name = "Classic"

    COLORS.update(THEMES[theme_name])

    LOG_COLORS.clear()
    LOG_COLORS.update({
        "[START]":        COLORS["green"],
        "[STOP]":         COLORS["red"],
        "[BIOME]":        COLORS["accent"],
        "[INFO]":         COLORS["text_dim"],
        "[CLEANUP]":      COLORS["yellow"],
        "[ANTI-AFK]":     COLORS["purple"],
        "[MERCHANT]":     COLORS["yellow"],
        "[AUTO-LAUNCH]":  COLORS["accent_hi"],
        "[BES]":          COLORS["purple"],
        "[ERROR]":        COLORS["red"],
        "[AUTO-ITEM]":    COLORS["green"],
    })

_init_settings = load_settings()
apply_global_theme(_init_settings.get("general", {}).get("theme", "Classic"))


def _hex_to_rgba(color: str, alpha: float) -> str:
    color = color.lstrip("#")
    r = int(color[0:2], 16)
    g = int(color[2:4], 16)
    b = int(color[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha:.2f})"


def _is_merchant_fix_applied() -> bool:
    """Return True if the hosts-file merchant fix is currently active."""
    import os
    windir = os.environ.get("WINDIR", "C:\\Windows")
    hosts_path = os.path.join(windir, "System32", "drivers", "etc", "hosts")
    try:
        with open(hosts_path, "r", encoding="utf-8") as f:
            return "255.255.255.0 assetdelivery.roblox.com" in f.read()
    except Exception:
        return False


# ------------------------------------------------------------------
# STYLESHEET
# ------------------------------------------------------------------
def get_stylesheet():
    return f"""
    QWidget {{
        background-color: {COLORS["bg"]};
        color: {COLORS["text"]};
        font-family: "Consolas", "Courier New", monospace;
        font-size: 13px;
        selection-background-color: {COLORS["accent_dim"]};
        selection-color: {COLORS["text"]};
    }}

    QFrame[frameShape="4"],
    QFrame[frameShape="5"] {{
        color: {COLORS["border"]};
        background: {COLORS["border"]};
        border: none;
        max-height: 1px;
    }}

    QLabel {{
        background: transparent;
        color: {COLORS["text"]};
    }}

    QLabel#title {{
        font-size: 18px;
        font-weight: bold;
        letter-spacing: 2px;
        color: {COLORS["accent"]};
    }}

    QLabel#section_header {{
        font-size: 11px;
        font-weight: bold;
        letter-spacing: 2px;
        color: {COLORS["text_dim"]};
        text-transform: uppercase;
        padding: 4px 0 2px 0;
    }}

    QLabel#hint {{
        font-size: 11px;
        color: {COLORS["text_dim"]};
        font-style: italic;
    }}

    QPushButton {{
        background-color: {COLORS["surface_2"]};
        color: {COLORS["text"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 6px;
        padding: 7px 18px;
        font-family: "Consolas", "Courier New", monospace;
        font-size: 13px;
        font-weight: bold;
        letter-spacing: 0.5px;
    }}

    QPushButton:hover {{
        background-color: {COLORS["surface_3"]};
        border-color: {COLORS["accent_dim"]};
        color: {COLORS["accent"]};
    }}

    QPushButton:pressed, QPushButton:checked {{
        background-color: {COLORS["accent_dim"]};
        border-color: {COLORS["accent"]};
        color: {COLORS["accent_hi"]};
    }}

    QPushButton#danger {{
        border-color: {COLORS["red"]};
        color: {COLORS["red"]};
    }}

    QPushButton#danger:hover {{
        background-color: {COLORS["red"]};
        color: {COLORS["bg"]};
    }}

    QPushButton#action {{
        background-color: {COLORS["accent_dim"]};
        border-color: {COLORS["accent"]};
        color: {COLORS["accent_hi"]};
    }}

    QPushButton#action:hover {{
        background-color: {COLORS["accent"]};
        border-color: {COLORS["accent_hi"]};
        color: {COLORS["bg"]};
    }}

    QPushButton#save {{
        background-color: {COLORS["surface_2"]};
        border-color: {COLORS["green"]};
        color: {COLORS["green"]};
    }}

    QPushButton#save:hover {{
        background-color: {COLORS["green"]};
        color: {COLORS["bg"]};
    }}

    QLineEdit {{
        background-color: {COLORS["surface_2"]};
        color: {COLORS["text"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 5px;
        padding: 6px 10px;
        font-family: "Consolas", "Courier New", monospace;
        font-size: 13px;
    }}

    QLineEdit:focus {{
        border-color: {COLORS["accent"]};
        background-color: {COLORS["surface_3"]};
    }}

    QLineEdit:hover {{
        border-color: {COLORS["border_hi"]};
    }}

    QSpinBox {{
        background-color: {COLORS["surface_2"]};
        color: {COLORS["text"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 5px;
        padding: 5px 8px;
        font-family: "Consolas", "Courier New", monospace;
        font-size: 13px;
    }}

    QSpinBox:focus {{
        border-color: {COLORS["accent"]};
    }}

    QComboBox {{
        background-color: {COLORS["surface_2"]};
        color: {COLORS["text"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 5px;
        padding: 6px 10px;
        font-family: "Consolas", "Courier New", monospace;
        font-size: 13px;
    }}

    QComboBox::drop-down {{ border: 0px; }}

    QComboBox QAbstractItemView {{
        background-color: {COLORS["surface_3"]};
        color: {COLORS["text"]};
        selection-background-color: {COLORS["accent_dim"]};
        selection-color: {COLORS["accent_hi"]};
        border: 1px solid {COLORS["border"]};
        outline: none;
    }}

    QListWidget {{
        background-color: {COLORS["surface"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 6px;
        outline: none;
        padding: 4px;
    }}

    QListWidget::item {{
        padding: 7px 10px;
        border-radius: 4px;
        color: {COLORS["text"]};
        border: none;
    }}

    QListWidget::item:hover {{
        background-color: {COLORS["surface_2"]};
        color: {COLORS["accent"]};
    }}

    QListWidget::item:selected {{
        background-color: {COLORS["accent_dim"]};
        color: {COLORS["accent_hi"]};
    }}

    QTextEdit {{
        background-color: {COLORS["surface"]};
        color: {COLORS["text"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 6px;
        padding: 8px;
        font-family: "Consolas", "Courier New", monospace;
        font-size: 12px;
        selection-background-color: {COLORS["accent_dim"]};
    }}

    QTextEdit:focus {{ border-color: {COLORS["border_hi"]}; }}

    QScrollBar:vertical {{
        background: {COLORS["surface"]};
        width: 8px;
        border-radius: 4px;
        border: none;
    }}
    QScrollBar::handle:vertical {{
        background: {COLORS["border_hi"]};
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {COLORS["accent_dim"]}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical,  QScrollBar::sub-page:vertical {{
        background: none; border: none; height: 0;
    }}
    QScrollBar:horizontal {{
        background: {COLORS["surface"]};
        height: 8px;
        border-radius: 4px;
        border: none;
    }}
    QScrollBar::handle:horizontal {{
        background: {COLORS["border_hi"]};
        border-radius: 4px;
        min-width: 24px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {COLORS["accent_dim"]}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        background: none; border: none; width: 0;
    }}

    QCheckBox {{
        spacing: 8px;
        color: {COLORS["text"]};
    }}
    QCheckBox::indicator {{
        width: 16px; height: 16px;
        border-radius: 4px;
        border: 1px solid {COLORS["border_hi"]};
        background: {COLORS["surface_2"]};
    }}
    QCheckBox::indicator:checked {{
        background: {COLORS["accent_dim"]};
        border-color: {COLORS["accent"]};
    }}
    QCheckBox::indicator:hover {{ border-color: {COLORS["accent"]}; }}

    QFormLayout QLabel {{
        color: {COLORS["text_dim"]};
        font-size: 12px;
        letter-spacing: 0.5px;
    }}

    QMessageBox {{ background-color: {COLORS["surface"]}; }}
    QMessageBox QLabel {{ color: {COLORS["text"]}; }}
    QMessageBox QPushButton {{ min-width: 80px; }}
    """


# ------------------------------------------------------------------
# COOKIE BROWSER DIALOG
# ------------------------------------------------------------------
class CookieBrowserDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cookie_value = None
        self.setWindowTitle("Log in to Roblox to Extract Cookie")
        self.resize(800, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if not WEBENGINE_AVAILABLE:
            return

        self.webview      = QWebEngineView(self)
        self.profile      = self.webview.page().profile()

        script = QWebEngineScript()
        script.setName("DisableWebAuthn")
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        script.setRunsOnSubFrames(True)
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        script.setSourceCode("""
            Object.defineProperty(navigator, 'credentials', {
                get: function() { return undefined; }
            });
        """)
        self.profile.scripts().insert(script)

        self.cookie_store = self.profile.cookieStore()
        self.cookie_store.deleteAllCookies()
        self.cookie_store.cookieAdded.connect(self.on_cookie_added)

        layout.addWidget(self.webview)
        self.webview.setUrl(QUrl("https://www.roblox.com/login"))

    def on_cookie_added(self, cookie):
        name = bytes(cookie.name()).decode("utf-8")
        if name == ".ROBLOSECURITY":
            self.cookie_value = bytes(cookie.value()).decode("utf-8")
            self.accept()


# ------------------------------------------------------------------
# ANIMATED BUTTON
# ------------------------------------------------------------------
class AnimatedButton(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


# ------------------------------------------------------------------
# STATUS DOT
# ------------------------------------------------------------------
class StatusDot(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(10, 10)
        self._active    = False
        self._pulse_on  = False
        self._timer     = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._render()

    def _render(self):
        color = COLORS["green"] if self._active else COLORS["text_dim"]
        self.setStyleSheet(
            f"border-radius: 5px; background-color: {_hex_to_rgba(color, 1.0 if self._active else 0.4)};"
        )

    def set_active(self, active: bool):
        self._active = active
        self._render()
        if active:
            self._timer.start(600)
        else:
            self._timer.stop()
            self._pulse_on = False
            self._render()

    def _tick(self):
        self._pulse_on = not self._pulse_on
        color = COLORS["green"]
        alpha = 1.0 if self._pulse_on else 0.4
        self.setStyleSheet(f"border-radius: 5px; background-color: {_hex_to_rgba(color, alpha)};")


# ------------------------------------------------------------------
# SIGNALS
# ------------------------------------------------------------------
class UISignals(QObject):
    start_scanner            = pyqtSignal()
    stop_scanner             = pyqtSignal()
    start_anti_afk           = pyqtSignal()
    stop_anti_afk            = pyqtSignal()
    start_merchant_detector  = pyqtSignal(str)
    stop_merchant_detector   = pyqtSignal()
    start_auto_launch        = pyqtSignal()
    stop_auto_launch         = pyqtSignal()
    start_bes                = pyqtSignal()
    stop_bes                 = pyqtSignal()
    start_auto_item          = pyqtSignal()
    stop_auto_item           = pyqtSignal()
    auto_item_config_updated = pyqtSignal()
    biome_update             = pyqtSignal(str, str)
    log_message              = pyqtSignal(str)
    players_updated          = pyqtSignal(dict)


# ------------------------------------------------------------------
# ACCOUNT OVERVIEW PANEL
# ------------------------------------------------------------------
_avatar_cache: dict = {}  # username -> QPixmap or None


class _AvatarLoader(QThread):
    """Fetches a Roblox headshot for one username in a background thread.
    Emits raw image bytes so the QPixmap is constructed on the main thread.
    """
    loaded = pyqtSignal(str, bytes)  # username, raw PNG bytes (empty on failure)

    def __init__(self, username: str):
        super().__init__()
        self._username = username

    def run(self):
        try:
            # Step 1: username -> user ID
            resp = requests.post(
                "https://users.roblox.com/v1/usernames/users",
                json={"usernames": [self._username], "excludeBannedUsers": False},
                timeout=5,
            )

            data = resp.json().get("data", [])
            if not data:
                self.loaded.emit(self._username, b"")
                return
            user_id = data[0]["id"]

            # Step 2: user ID -> headshot URL
            resp2 = requests.get(
                "https://thumbnails.roblox.com/v1/users/avatar-headshot",
                params={
                    "userIds":    str(user_id),
                    "size":       "150x150",
                    "format":     "Png",
                    "isCircular": "false",
                },
                timeout=5,
            )
            thumb_data = resp2.json().get("data", [])
            if not thumb_data:
                self.loaded.emit(self._username, b"")
                return
            img_url = thumb_data[0].get("imageUrl", "")
            print(img_url)
            if not img_url:
                self.loaded.emit(self._username, b"")
                return

            # Step 3: download raw image bytes only — QPixmap is built on main thread
            img_resp = requests.get(img_url, timeout=5)
            img_resp.raise_for_status()
            self.loaded.emit(self._username, img_resp.content)
        except Exception:
            self.loaded.emit(self._username, b"")


class AccountCard(QFrame):
    """Single read-only account row: avatar | name | biome | status outline."""

    clicked = pyqtSignal(str)  # emits username when card is clicked

    def __init__(self, username: str, parent=None):
        super().__init__(parent)
        self._username = username
        self._active   = False
        self._selected = False

        self.setFixedHeight(62)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_outline(active=False)

        row = QHBoxLayout(self)
        row.setContentsMargins(6, 5, 6, 5)
        row.setSpacing(6)

        # Avatar — 32x32 so 3 cards fit side-by-side
        self._avatar_lbl = QLabel()
        self._avatar_lbl.setFixedSize(32, 32)
        self._avatar_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._avatar_lbl.setStyleSheet(
            f"border-radius: 4px; background: {COLORS['surface_3']};"
        )
        row.addWidget(self._avatar_lbl)

        # Text column — Ignored horizontal policy lets grid column bound the width
        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        text_col.setContentsMargins(0, 0, 0, 0)
        self._name_lbl  = QLabel(username)
        self._name_lbl.setStyleSheet(f"color: {COLORS['text']}; font-weight: bold; font-size: 12px;")
        self._name_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._biome_lbl = QLabel("\u2014")
        self._biome_lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")
        self._biome_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        text_col.addWidget(self._name_lbl)
        text_col.addWidget(self._biome_lbl)
        row.addLayout(text_col, 1)

        # Status dot (right side)
        self._dot = StatusDot()
        row.addWidget(self._dot)

    def _apply_outline(self, active: bool):
        if self._selected:
            border_color = COLORS["accent"]
        else:
            border_color = COLORS["green"] if active else COLORS["red"]
        self.setStyleSheet(
            f"AccountCard {{"
            f"  background: {COLORS['surface_2'] if self._selected else COLORS['surface']};"
            f"  border: 2px solid {border_color};"
            f"  border-radius: 8px;"
            f"}}"
        )

    def set_selected(self, selected: bool):
        self._selected = selected
        self._apply_outline(self._active)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._username)
        super().mousePressEvent(event)

    def set_avatar(self, pixmap):
        if pixmap and not pixmap.isNull():
            self._avatar_lbl.setPixmap(
                pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
            )
        else:
            self._avatar_lbl.setText("?")

    def set_active(self, active: bool):
        if active == self._active:
            return
        self._active = active
        self._apply_outline(active)
        self._dot.set_active(active)

    def set_biome(self, biome: str):
        self._biome_lbl.setText(biome.upper() if biome else "\u2014")

    def refresh_theme(self):
        self._apply_outline(self._active)
        self._name_lbl.setStyleSheet(f"color: {COLORS['text']}; font-weight: bold; font-size: 12px;")
        self._biome_lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")
        self._avatar_lbl.setStyleSheet(
            f"border-radius: 4px; background: {COLORS['surface_3']};"
        )
        self._dot._render()


class AccountOverviewPanel(QWidget):
    """
    Read-only scrollable panel showing every configured account with
    live status (red/green outline), current biome, and profile picture.
    Refreshes on a QTimer and responds to biome_update signals.
    """

    account_selected = pyqtSignal(str)  # emits username when a card is clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards:    dict = {}   # username -> AccountCard
        self._loaders:  list = []   # keep QThread refs alive
        self._selected: str  = ""   # currently selected username

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._container = QWidget()
        self._layout    = QGridLayout(self._container)
        self._layout.setSpacing(6)
        self._layout.setContentsMargins(0, 0, 4, 0)
        # Three equal columns that stretch to fill available width
        for _c in range(3):
            self._layout.setColumnStretch(_c, 1)
        scroll.setWidget(self._container)
        outer.addWidget(scroll)

        # Refresh active/inactive status every 5 seconds
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_status)
        self._status_timer.start(5000)

    def rebuild(self, players: dict):
        """Rebuild cards whenever the player list changes."""
        # Remove cards for deleted players
        for name in list(self._cards.keys()):
            if name not in players:
                card = self._cards.pop(name)
                self._layout.removeWidget(card)
                card.deleteLater()

        # Add cards for new players
        for name in players:
            if name not in self._cards:
                card = AccountCard(name)
                card.clicked.connect(self._on_card_clicked)
                self._cards[name] = card
                self._load_avatar(name)

        # Re-place all cards in 3-column grid order
        self._relayout()
        self._refresh_status()

    def _relayout(self):
        """Re-place every card into the 3-column grid, preserving dict order."""
        for card in self._cards.values():
            self._layout.removeWidget(card)
        for i, card in enumerate(self._cards.values()):
            row, col = divmod(i, 3)
            self._layout.addWidget(card, row, col)

    def on_biome_update(self, player: str, biome: str):
        card = self._cards.get(player)
        if card:
            card.set_biome(biome)

    def _on_card_clicked(self, username: str):
        """Toggle selection: clicking the same card again deselects it."""
        if self._selected == username:
            # Deselect
            card = self._cards.get(username)
            if card:
                card.set_selected(False)
            self._selected = ""
        else:
            # Deselect previous
            prev = self._cards.get(self._selected)
            if prev:
                prev.set_selected(False)
            # Select new
            self._selected = username
            card = self._cards.get(username)
            if card:
                card.set_selected(True)
        self.account_selected.emit(self._selected)

    def _refresh_status(self):
        """Check which accounts have an active Roblox window and update outlines."""
        try:
            import window_utils
            active_names = set()
            for hwnd in window_utils.get_roblox_windows():
                name = window_utils.resolve_account_for_window(hwnd, list(self._cards.keys()))
                if name:
                    active_names.add(name)
        except Exception:
            active_names = set()

        for name, card in self._cards.items():
            card.set_active(name in active_names)

        # Sync biomes from scanner state
        try:
            import scanner
            for name, card in self._cards.items():
                biome = scanner.current_biome.get(name, "")
                card.set_biome(biome)
        except Exception:
            pass

    def _load_avatar(self, username: str):
        if username in _avatar_cache:
            card = self._cards.get(username)
            if card:
                card.set_avatar(_avatar_cache[username])
            return

        loader = _AvatarLoader(username)
        loader.loaded.connect(self._on_avatar_loaded)
        self._loaders.append(loader)
        loader.start()

    def _on_avatar_loaded(self, username: str, img_bytes: bytes):
        # QPixmap must be constructed on the main thread — never in the worker.
        if img_bytes:
            pixmap = QPixmap()
            pixmap.loadFromData(img_bytes)
            pixmap = pixmap if not pixmap.isNull() else None
        else:
            pixmap = None
        _avatar_cache[username] = pixmap
        card = self._cards.get(username)
        if card:
            card.set_avatar(pixmap)
        # Clean up finished loaders
        self._loaders = [l for l in self._loaders if l.isRunning()]

    def refresh_theme(self):
        for card in self._cards.values():
            card.refresh_theme()


# ------------------------------------------------------------------
# MAIN WINDOW
# ------------------------------------------------------------------
class BiomeScannerUI(QWidget):
    def __init__(self, signals):
        super().__init__()

        self.signals  = signals
        self.settings = load_settings()
        self.players  = self.settings.get("players", {})
        self.bes_is_running = False
        self.auto_item_is_running = False

        self.setWindowTitle("Yes Biome Scanner")
        self.setMinimumSize(980, 620)

        self.setWindowOpacity(0.0)
        self._fade_in = QPropertyAnimation(self, b"windowOpacity")
        self._fade_in.setDuration(350)
        self._fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        # ── Header row ───────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(10)

        title_lbl = QLabel("\u25c8  YES BIOME SCANNER")
        title_lbl.setObjectName("title")
        header.addWidget(title_lbl)
        header.addStretch()

        self._scan_dot   = StatusDot()
        self.toggle_btn  = AnimatedButton("\u25b6 Scanner")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setObjectName("action")
        self.toggle_btn.clicked.connect(self.toggle_scanner)
        header.addWidget(self._scan_dot)
        header.addWidget(self.toggle_btn)

        self._afk_dot        = StatusDot()
        self.afk_toggle_btn  = AnimatedButton("\u25b6 Anti-AFK")
        self.afk_toggle_btn.setCheckable(True)
        self.afk_toggle_btn.clicked.connect(self.toggle_anti_afk)
        header.addWidget(self._afk_dot)
        header.addWidget(self.afk_toggle_btn)

        self._merchant_dot       = StatusDot()
        self.merchant_toggle_btn = AnimatedButton("\u25b6 Merchant")
        self.merchant_toggle_btn.setCheckable(True)
        self.merchant_toggle_btn.clicked.connect(self.toggle_merchant_detector)

        self.merchant_mode_combo = QComboBox()
        self.merchant_mode_combo.addItems(["Log-Based", "OCR"])
        self.merchant_mode_combo.setToolTip("Log-Based: Fast log scanning via blocked assets.\nOCR: Relies on chat logs and OCR.")
        # Restore last saved selection
        saved_mode = self.settings.get("general", {}).get("merchant_mode", "Log-Based")
        idx = self.merchant_mode_combo.findText(saved_mode)
        if idx >= 0:
            self.merchant_mode_combo.setCurrentIndex(idx)
        # Save selection whenever it changes
        self.merchant_mode_combo.currentTextChanged.connect(self._save_merchant_mode)

        header.addWidget(self._merchant_dot)
        header.addWidget(self.merchant_toggle_btn)
        header.addWidget(self.merchant_mode_combo)

        self._auto_dot       = StatusDot()
        self.auto_toggle_btn = AnimatedButton("\u25b6 Auto Launch")
        self.auto_toggle_btn.setCheckable(True)
        self.auto_toggle_btn.clicked.connect(self.toggle_auto_launch)
        header.addWidget(self._auto_dot)
        header.addWidget(self.auto_toggle_btn)

        self.toggle_all_btn = AnimatedButton("\u23ef Toggle All")
        self.toggle_all_btn.setObjectName("action")
        self.toggle_all_btn.clicked.connect(self.toggle_all)
        header.addWidget(self.toggle_all_btn)

        settings_btn = AnimatedButton("\u2699 Settings")
        settings_btn.clicked.connect(self.open_settings)
        header.addWidget(settings_btn)

        root.addLayout(header)
        root.addWidget(self._divider())

        # ── Account overview panel ───────────────────────────────
        overview_lbl = QLabel("ACCOUNTS")
        overview_lbl.setObjectName("section_header")
        root.addWidget(overview_lbl)

        self.overview_panel = AccountOverviewPanel()
        self.overview_panel.setMinimumHeight(140)
        self.overview_panel.setMaximumHeight(280)
        self.overview_panel.rebuild(self.players)
        root.addWidget(self.overview_panel)

        root.addWidget(self._divider())

        # ── Log box ───────────────────────────────────────────────
        log_header = QHBoxLayout()
        log_lbl = QLabel("SCANNER LOG")
        log_lbl.setObjectName("section_header")
        log_header.addWidget(log_lbl)
        log_header.addStretch()

        self._selected_player_label = QLabel("no account selected")
        self._selected_player_label.setObjectName("hint")
        log_header.addWidget(self._selected_player_label)

        launch_ps_btn = AnimatedButton("▶ Launch PS")
        launch_ps_btn.setObjectName("action")
        launch_ps_btn.setFixedHeight(28)
        launch_ps_btn.setToolTip("Click an account card to select, then launch their private server")
        launch_ps_btn.clicked.connect(self._launch_selected_player)
        log_header.addWidget(launch_ps_btn)

        kill_all_btn = AnimatedButton("Kill All")
        kill_all_btn.setObjectName("danger")
        kill_all_btn.setFixedHeight(28)
        kill_all_btn.clicked.connect(self.kill_all_roblox)
        log_header.addWidget(kill_all_btn)

        clear_btn = AnimatedButton("Clear")
        clear_btn.setObjectName("danger")
        clear_btn.setFixedHeight(28)
        clear_btn.clicked.connect(self.log_box_clear)
        log_header.addWidget(clear_btn)
        root.addLayout(log_header)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.document().setMaximumBlockCount(500)
        root.addWidget(self.log_box, 1)

        from trimmer import TrimmerTab
        self.trimmer_tab = TrimmerTab(parent=self)

        self.signals.biome_update.connect(self.update_biome)
        self.signals.biome_update.connect(self.overview_panel.on_biome_update)
        self.signals.players_updated.connect(self._on_players_updated)
        self.signals.log_message.connect(self.append_log)
        self.overview_panel.account_selected.connect(self._on_account_selected)

        self.apply_theme()

    # ── Theme ────────────────────────────────────────────────────
    def apply_theme(self):
        self.setStyleSheet(get_stylesheet())
        for dot in (self._scan_dot, self._afk_dot, self._merchant_dot,
                    self._auto_dot):
            dot._render()
        if hasattr(self, 'overview_panel'):
            self.overview_panel.refresh_theme()

    def _on_players_updated(self, players: dict):
        """Called when the players dict changes (add/remove in Settings)."""
        self.players = players
        self.overview_panel.rebuild(players)

    def _refresh_list(self):
        """No-op stub — player list lives in Settings > Players tab."""
        pass

    def _save_merchant_mode(self, mode: str):
        """Persist the merchant mode dropdown selection to settings."""
        settings = load_settings()
        settings.setdefault("general", {})["merchant_mode"] = mode
        save_settings(settings)
        self.settings = settings

    def _on_account_selected(self, username: str):
        """Called when the user clicks an account card in the overview panel."""
        self._selected_player = username
        if username:
            self._selected_player_label.setText(f"▶ {username}")
        else:
            self._selected_player_label.setText("no account selected")

    def _launch_selected_player(self):
        """Launch the private server for whichever account card is selected."""
        username = getattr(self, '_selected_player', '')
        if not username:
            QMessageBox.warning(self, "No Account Selected",
                "Click an account card above to select it, then press Launch PS.")
            return

        player_data = self.players.get(username)
        if not isinstance(player_data, dict):
            QMessageBox.warning(self, "Error", "Player data is missing or invalid.")
            return

        cookie = player_data.get("cookie", "")
        pslink = player_data.get("pslink", "")

        if not cookie:
            QMessageBox.warning(self, "No Cookie",
                f"No cookie is linked for {username}.\n"
                "Go to Settings → Players to extract and save a cookie.")
            return
        if not pslink:
            QMessageBox.warning(self, "No PS Link",
                f"No private server link is set for {username}.\n"
                "Go to Settings → Players to add one.")
            return

        success, msg = roblox_launcher.launch_private_server(cookie, pslink)
        if success:
            self.append_log(f"[INFO] Launching Roblox for {username}…")
        else:
            QMessageBox.warning(self, "Launch Error",
                f"Failed to launch Roblox for {username}:\n\n{msg}")

    @staticmethod
    def _divider():
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        return line

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._fade_in.start)

    # ── Toggle handlers ──────────────────────────────────────────
    def toggle_scanner(self):
        on = self.toggle_btn.isChecked()
        self.toggle_btn.setText("\u25a0 Scanner" if on else "\u25b6 Scanner")
        self._scan_dot.set_active(on)
        self.signals.start_scanner.emit() if on else self.signals.stop_scanner.emit()

    def toggle_anti_afk(self):
        on = self.afk_toggle_btn.isChecked()
        self.afk_toggle_btn.setText("\u25a0 Anti-AFK" if on else "\u25b6 Anti-AFK")
        self._afk_dot.set_active(on)
        self.signals.start_anti_afk.emit() if on else self.signals.stop_anti_afk.emit()

    def toggle_merchant_detector(self):
        on = self.merchant_toggle_btn.isChecked()

        # Guard: Log-Based requires the hosts fix to be active
        if on and self.merchant_mode_combo.currentText() == "Log-Based":
            if not _is_merchant_fix_applied():
                self.merchant_toggle_btn.setChecked(False)
                QMessageBox.warning(
                    self,
                    "Fix Not Applied",
                    "The Log-Based merchant detection fix is not applied.\n\n"
                    "Go to Settings \u2192 Merchants and apply the fix before "
                    "starting Log-Based detection."
                )
                return

        self.merchant_toggle_btn.setText("\u25a0 Merchant" if on else "\u25b6 Merchant")
        self._merchant_dot.set_active(on)
        self.merchant_mode_combo.setEnabled(not on)

        if on:
            self.signals.start_merchant_detector.emit(self.merchant_mode_combo.currentText())
        else:
            self.signals.stop_merchant_detector.emit()

    def toggle_auto_launch(self):
        on = self.auto_toggle_btn.isChecked()
        self.auto_toggle_btn.setText("\u25a0 Auto Launch" if on else "\u25b6 Auto Launch")
        self._auto_dot.set_active(on)
        self.signals.start_auto_launch.emit() if on else self.signals.stop_auto_launch.emit()

    def toggle_all(self):
        any_on = any(btn.isChecked() for btn in (
            self.toggle_btn, self.afk_toggle_btn,
            self.merchant_toggle_btn, self.auto_toggle_btn
        ))
        target = not any_on
        for btn, handler in [
            (self.toggle_btn,          self.toggle_scanner),
            (self.afk_toggle_btn,      self.toggle_anti_afk),
            (self.merchant_toggle_btn, self.toggle_merchant_detector),
            (self.auto_toggle_btn,     self.toggle_auto_launch),
        ]:
            if btn.isChecked() != target:
                btn.setChecked(target)
                handler()

    def closeEvent(self, event):
        try:
            self.trimmer_tab.shutdown()
        except Exception:
            pass
        super().closeEvent(event)

    def kill_all_roblox(self):
        try:
            result = subprocess.run(["taskkill", "/F", "/IM", "RobloxPlayerBeta.exe"],
                capture_output=True, text=True
            )
            msg = "[INFO] Killed all Roblox instances." if result.returncode == 0 \
                  else "[INFO] No Roblox instances found to kill."
            self.append_log(msg)
        except Exception as e:
            self.append_log(f"[ERROR] Failed to kill Roblox: {e}")

    def log_box_clear(self):
        self.log_box.clear()

    def update_biome(self, player, biome):
        self.append_log(f"[BIOME] {player} \u2192 {biome.upper()}")

    def append_log(self, text: str):
        cursor = self.log_box.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(COLORS["text_dim"]))
        for tag, color in LOG_COLORS.items():
            if tag in text:
                fmt.setForeground(QColor(color))
                break
        cursor.insertText(text + "\n", fmt)
        self.log_box.setTextCursor(cursor)
        self.log_box.ensureCursorVisible()

    def open_settings(self):
        self.settings_window = SettingsWindow(self)
        self.settings_window.show()


# ------------------------------------------------------------------
# CALIBRATE OVERLAY
# ------------------------------------------------------------------
class CalibrateOverlay(QWidget):
    """
    Full-screen semi-transparent overlay that captures one left-click from the user,
    resolves the Roblox window under that point, and emits relative (x, y) coords
    as fractions of the client area (0.0-1.0).
    """

    captured  = pyqtSignal(float, float)
    cancelled = pyqtSignal()

    def __init__(self, label: str = "", parent=None):
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self._label = label
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setCursor(Qt.CursorShape.CrossCursor)

        full = QApplication.primaryScreen().virtualGeometry()
        for screen in QApplication.screens():
            full = full.united(screen.geometry())
        self.setGeometry(full)

    def showEvent(self, event):
        super().showEvent(event)
        self.activateWindow()
        self.raise_()
        QTimer.singleShot(50, self.grabMouse)

    def closeEvent(self, event):
        self.releaseMouse()
        super().closeEvent(event)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 150))

        name_line = f"\u2192  {self._label}" if self._label else ""
        body = "\n".join(filter(None, [
            name_line,
            "",
            "Click the target location inside Roblox",
            "",
            "Press  ESC  to cancel",
        ]))

        font = QFont("Consolas", 15)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(255, 255, 255, 230))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, body)
        p.end()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.close()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.globalPosition().toPoint()
        ax, ay = pos.x(), pos.y()
        self.close()
        self._resolve_and_emit(ax, ay)

    def _resolve_and_emit(self, ax: int, ay: int) -> None:
        try:
            import win32gui
            import window_utils

            hwnd = win32gui.WindowFromPoint((ax, ay))
            roblox_hwnd = None
            candidate = hwnd
            while candidate:
                try:
                    if win32gui.GetWindowText(candidate) == "Roblox":
                        roblox_hwnd = candidate
                        break
                except Exception:
                    pass
                parent = win32gui.GetParent(candidate)
                if not parent or parent == candidate:
                    break
                candidate = parent

            if not roblox_hwnd:
                windows = window_utils.get_roblox_windows()
                if windows:
                    roblox_hwnd = windows[0]

            if not roblox_hwnd:
                QMessageBox.warning(
                    None,
                    "No Roblox Window",
                    "Could not find a Roblox window.\n"
                    "Make sure Roblox is running and try again.",
                )
                self.cancelled.emit()
                return

            left, top = win32gui.ClientToScreen(roblox_hwnd, (0, 0))
            _cl, _ct, cr, cb = win32gui.GetClientRect(roblox_hwnd)
            width  = int(cr - _cl)
            height = int(cb - _ct)
            if width <= 0 or height <= 0:
                self.cancelled.emit()
                return

            rel_x = max(0.0, min(1.0, (ax - left)  / width))
            rel_y = max(0.0, min(1.0, (ay - top) / height))
            self.captured.emit(rel_x, rel_y)

        except Exception as exc:
            QMessageBox.warning(None, "Calibration Error", str(exc))
            self.cancelled.emit()


# ------------------------------------------------------------------
# SETTINGS WINDOW
# ------------------------------------------------------------------
class SettingsWindow(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent            = parent
        self.settings          = load_settings()
        self.merchant_settings = self.settings.get("merchant_detection", {})
        self.players           = self.settings.get("players", {})
        self.webhooks_data     = list(self.settings.get("webhooks", []))

        self.setWindowTitle("Settings")
        self.setMinimumSize(800, 660)

        self.setWindowOpacity(0.0)
        self._open_anim = QPropertyAnimation(self, b"windowOpacity")
        self._open_anim.setDuration(280)
        self._open_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._open_anim.setStartValue(0.0)
        self._open_anim.setEndValue(1.0)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(148)
        for label in ("GENERAL", "MERCHANTS", "PLAYERS", "WEBHOOKS", "BES", "RAM LIMITER", "AUTO ITEM", "CREDITS"):
            self.sidebar.addItem(label)
        self.sidebar.currentRowChanged.connect(self._switch_tab)
        layout.addWidget(self.sidebar)

        self.pages = QStackedWidget()
        self.pages.setContentsMargins(20, 16, 20, 16)
        layout.addWidget(self.pages)

        self.pages.addWidget(self._build_general_tab())   # 0
        self.pages.addWidget(self._build_merchants_tab()) # 1
        self.pages.addWidget(self._build_players_tab())   # 2
        self.pages.addWidget(self._build_webhooks_tab())  # 3
        self.pages.addWidget(self._build_bes_tab())       # 4


        self.trimmer_tab = self.parent.trimmer_tab
        self.trimmer_tab.setParent(self.pages)
        self.trimmer_tab.hide()
        self.pages.addWidget(self.trimmer_tab)            # 5

        self.auto_item_items_data: list = []
        self.auto_item_coord_inputs: dict = {}
        self.pages.addWidget(self._build_auto_item_tab()) # 6

        self.pages.addWidget(self._build_credits_tab())   # 7

        self.sidebar.setCurrentRow(0)
        self.apply_theme()

    # ── Theme ─────────────────────────────────────────────────────
    def apply_theme(self):
        self.setStyleSheet(get_stylesheet())
        self.sidebar.setStyleSheet(f"""
            QListWidget {{
                background: {COLORS["surface"]};
                border: none;
                border-right: 1px solid {COLORS["border"]};
                border-radius: 0;
                padding: 8px 4px;
            }}
            QListWidget::item {{
                padding: 10px 14px;
                font-size: 12px;
                font-weight: bold;
                letter-spacing: 1px;
                color: {COLORS["text_dim"]};
                border-radius: 4px;
            }}
            QListWidget::item:hover  {{ background: {COLORS["surface_2"]}; color: {COLORS["text"]}; }}
            QListWidget::item:selected {{ background: {COLORS["accent_dim"]}; color: {COLORS["accent_hi"]}; }}
        """)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._open_anim.start)

    def _switch_tab(self, index):
        self.pages.setCurrentIndex(index)

    @staticmethod
    def _divider():
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        return line

    def _flash_saved(self, message: str):
        QMessageBox.information(self, "Saved", message)

    # ══════════════════════════════════════════════════════════════
    # TAB: GENERAL
    # ══════════════════════════════════════════════════════════════
    def _build_general_tab(self):
        page    = QWidget()
        layout  = QVBoxLayout(page)
        layout.setSpacing(12)
        general = self.settings.get("general", {})

        title = QLabel("GENERAL")
        title.setObjectName("title")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self.theme_dropdown = QComboBox()
        self.theme_dropdown.addItems(list(THEMES.keys()))
        self.theme_dropdown.setCurrentText(general.get("theme", "Classic"))

        self.log_path_input          = QLineEdit(general.get("log_path", ""))
        self.scan_interval_input     = QLineEdit(str(general.get("scan_interval", 1)))
        self.afk_interval_input      = QLineEdit(str(general.get("anti_afk_interval", 600)))
        self.auto_launch_delay_input = QLineEdit(str(general.get("auto_launch_delay", 5)))
        self.cleanup_checkbox        = QCheckBox("Auto-cleanup unused logs")
        self.cleanup_checkbox.setChecked(general.get("auto_cleanup", True))

        form.addRow("Theme:",                 self.theme_dropdown)
        form.addRow("Log Path:",              self.log_path_input)
        form.addRow("Scan Interval (s):",     self.scan_interval_input)
        form.addRow("Anti-AFK Interval (s):", self.afk_interval_input)
        form.addRow("Auto Launch Delay (s):", self.auto_launch_delay_input)
        form.addRow("",                       self.cleanup_checkbox)
        layout.addLayout(form)

        save_btn = AnimatedButton("\u2713  Save General Settings")
        save_btn.setObjectName("save")
        save_btn.clicked.connect(self._save_general_settings)
        layout.addWidget(save_btn)
        layout.addStretch()
        return page

    def _save_general_settings(self):
        try:
            afk_interval = int(self.afk_interval_input.text().strip())
        except ValueError:
            afk_interval = 600
        try:
            scan_interval = int(self.scan_interval_input.text().strip())
        except ValueError:
            scan_interval = 1
        try:
            launch_delay = int(self.auto_launch_delay_input.text().strip())
        except ValueError:
            launch_delay = 5

        theme_val = self.theme_dropdown.currentText()

        self.settings["general"] = {
            "log_path":          self.log_path_input.text().strip(),
            "scan_interval":     scan_interval,
            "anti_afk_interval": afk_interval,
            "auto_launch_delay": launch_delay,
            "auto_cleanup":      self.cleanup_checkbox.isChecked(),
            "theme":             theme_val
        }

        save_settings(self.settings)
        apply_global_theme(theme_val)
        self.parent.apply_theme()
        self.apply_theme()
        self._flash_saved("General settings saved.")

    # ══════════════════════════════════════════════════════════════
    # TAB: MERCHANTS
    # ══════════════════════════════════════════════════════════════
    def _build_merchants_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        title = QLabel("MERCHANTS")
        title.setObjectName("title")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self.merchant_scan_interval_input = QLineEdit(str(self.merchant_settings.get("scan_interval", 2)))
        self.merchant_scan_interval_input.setMaximumWidth(80)
        form.addRow("Scan Interval (s):", self.merchant_scan_interval_input)
        layout.addLayout(form)

        save_btn = AnimatedButton("\u2713  Save Merchant Settings")
        save_btn.setObjectName("save")
        save_btn.clicked.connect(self._save_merchant_settings)
        layout.addWidget(save_btn)

        layout.addWidget(self._divider())

        fix_title = QLabel("LOG-BASED DETECTION FIX")
        fix_title.setObjectName("section_header")
        layout.addWidget(fix_title)

        fix_hint = QLabel(
            "In order for Log-Based merchant detection to work, Roblox must be prevented from downloading "
            "merchant assets so that they appear as errors in the log file. "
            "Applying this fix will automatically modify your system's 'hosts' file to block the asset delivery endpoint. "
            "WARNING: YOU CAN NOT ROLL WITH THIS FIX APPLIED!"
        )
        fix_hint.setWordWrap(True)
        fix_hint.setObjectName("hint")
        layout.addWidget(fix_hint)

        self.merchant_fix_btn = AnimatedButton()
        self._update_fix_btn_state()
        self.merchant_fix_btn.clicked.connect(self._toggle_merchant_fix)
        layout.addWidget(self.merchant_fix_btn)

        layout.addStretch()
        return page

    def _save_merchant_settings(self):
        try:
            interval = max(1, int(self.merchant_scan_interval_input.text().strip()))
        except ValueError:
            interval = 2
        self.settings.setdefault("merchant_detection", {})["scan_interval"] = interval
        save_settings(self.settings)
        self._flash_saved("Merchant settings saved.")

    def _get_hosts_path(self):
        import os
        windir = os.environ.get("WINDIR", "C:\\Windows")
        return os.path.join(windir, "System32", "drivers", "etc", "hosts")

    def _is_fix_applied(self):
        return _is_merchant_fix_applied()

    def _update_fix_btn_state(self):
        if self._is_fix_applied():
            self.merchant_fix_btn.setText("\u2715 Remove Fix (Requires Admin)")
            self.merchant_fix_btn.setEnabled(True)
            self.merchant_fix_btn.setObjectName("danger")
        else:
            self.merchant_fix_btn.setText("\u26a0 Apply Fix (Requires Admin)")
            self.merchant_fix_btn.setEnabled(True)
            self.merchant_fix_btn.setObjectName("action")
        self.merchant_fix_btn.style().unpolish(self.merchant_fix_btn)
        self.merchant_fix_btn.style().polish(self.merchant_fix_btn)

    def _toggle_merchant_fix(self):
        import subprocess, os, base64, re

        is_applied = self._is_fix_applied()
        hosts_path = self._get_hosts_path()

        if is_applied:
            reply = QMessageBox.question(
                self, "Remove Fix",
                "This will remove the merchant fix from your system hosts file. Proceed?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
            try:
                with open(hosts_path, "r", encoding="utf-8") as f:
                    content = f.read()
                content = re.sub(r"(?m)^\s*# YesBiomeScanner Merchant Fix.*$\n?", "", content)
                content = re.sub(r"(?m)^\s*255\.255\.255\.0 assetdelivery\.roblox\.com.*$\n?", "", content)
                content = content.rstrip() + "\n"
                with open(hosts_path, "w", encoding="utf-8") as f:
                    f.write(content)
            except PermissionError:
                ps_script = (
                    f"$path = '{hosts_path}'\n"
                    f"$text = [IO.File]::ReadAllText($path)\n"
                    f"$text = $text -replace '(?m)^\\s*# YesBiomeScanner Merchant Fix.*?\\r?\\n', ''\n"
                    f"$text = $text -replace '(?m)^\\s*255\\.255\\.255\\.0 assetdelivery\\.roblox\\.com.*?\\r?\\n', ''\n"
                    f"$text = $text.TrimEnd() + \"`r`n\"\n"
                    f"[IO.File]::WriteAllText($path, $text)"
                )
                encoded = base64.b64encode(ps_script.encode('utf-16le')).decode('utf-8')
                cmd = f"Start-Process powershell -Verb RunAs -Wait -WindowStyle Hidden -ArgumentList '-NoProfile -EncodedCommand {encoded}'"
                try:
                    subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to launch PowerShell: {e}")
                    return
                if self._is_fix_applied():
                    QMessageBox.warning(self, "Action Cancelled", "The prompt was cancelled or failed.")
                    return
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to modify hosts file: {e}")
                return
            self._update_fix_btn_state()
            QMessageBox.information(self, "Success", "Fix removed successfully!")
        else:
            reply = QMessageBox.question(
                self, "Apply Fix",
                "This will close ALL Roblox windows, clear all logs, and modify your system hosts file. "
                "YOU CAN NOT ROLL WHEN THIS FIX IS APPLIED! Proceed?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
            try:
                subprocess.run(["taskkill", "/F", "/IM", "RobloxPlayerBeta.exe"],
                    capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            except Exception:
                pass
            log_path = self.settings.get("general", {}).get("log_path", "")
            if os.path.exists(log_path):
                for f in os.listdir(log_path):
                    if f.endswith((".log", ".logs")):
                        try:
                            os.remove(os.path.join(log_path, f))
                        except Exception:
                            pass
            try:
                with open(hosts_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if content and not content.endswith("\n"):
                    content += "\n"
                content += "# YesBiomeScanner Merchant Fix\n255.255.255.0 assetdelivery.roblox.com\n"
                with open(hosts_path, "w", encoding="utf-8") as f:
                    f.write(content)
            except PermissionError:
                ps_script = (
                    f"$path = '{hosts_path}'\n"
                    f"$text = [IO.File]::ReadAllText($path)\n"
                    f"if ($text.Length -gt 0 -and -not $text.EndsWith(\"`n\")) {{ $text += \"`r`n\" }}\n"
                    f"$text += \"# YesBiomeScanner Merchant Fix`r`n255.255.255.0 assetdelivery.roblox.com`r`n\"\n"
                    f"[IO.File]::WriteAllText($path, $text)"
                )
                encoded = base64.b64encode(ps_script.encode('utf-16le')).decode('utf-8')
                cmd = f"Start-Process powershell -Verb RunAs -Wait -WindowStyle Hidden -ArgumentList '-NoProfile -EncodedCommand {encoded}'"
                try:
                    subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to launch PowerShell: {e}")
                    return
                if not self._is_fix_applied():
                    QMessageBox.warning(self, "Action Cancelled", "The prompt was cancelled or failed.")
                    return
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to modify hosts file: {e}")
                return
            self._update_fix_btn_state()
            QMessageBox.information(self, "Success", "Fix applied successfully!")

    # ══════════════════════════════════════════════════════════════
    # TAB: PLAYERS
    # ══════════════════════════════════════════════════════════════
    def _build_players_tab(self):
        page   = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        title = QLabel("PLAYERS")
        title.setObjectName("title")
        layout.addWidget(title)

        self.player_list_widget = QListWidget()
        self.player_list_widget.currentRowChanged.connect(self._load_selected_player)
        self._refresh_settings_list()
        layout.addWidget(self.player_list_widget)

        form = QFormLayout()
        form.setSpacing(8)

        self.new_username = QLineEdit()
        self.new_username.setPlaceholderText("Roblox username\u2026")
        self.new_pslink   = QLineEdit()
        self.new_pslink.setPlaceholderText("Private server link\u2026")

        form.addRow("Username:", self.new_username)
        form.addRow("PS Link:",  self.new_pslink)

        self.auto_launch_checkbox_settings = QCheckBox("Enable Auto Launch")
        self.auto_launch_checkbox_settings.setChecked(True)
        form.addRow("", self.auto_launch_checkbox_settings)
        layout.addLayout(form)

        webhook_hint = QLabel("\U0001f4a1 Webhook assignments are managed in the Webhooks tab \u2192")
        webhook_hint.setObjectName("hint")
        layout.addWidget(webhook_hint)

        btn_row = QHBoxLayout()
        add_btn   = AnimatedButton("+ Add / Update")
        add_btn.setObjectName("action")
        add_btn.clicked.connect(self._add_player)
        rm_btn    = AnimatedButton("\u2715 Remove")
        rm_btn.setObjectName("danger")
        rm_btn.clicked.connect(self._remove_player)
        login_btn = AnimatedButton("\U0001f511 Extract Cookie")
        login_btn.clicked.connect(self.extract_cookie)
        launch_btn = AnimatedButton("\U0001f680 Launch PS")
        launch_btn.clicked.connect(self.launch_player)
        save_btn  = AnimatedButton("\u2713 Save")
        save_btn.setObjectName("save")
        save_btn.clicked.connect(self._save_players)

        btn_row.addWidget(add_btn)
        btn_row.addWidget(rm_btn)
        btn_row.addWidget(login_btn)
        btn_row.addWidget(launch_btn)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)
        layout.addStretch()
        return page

    def _refresh_settings_list(self):
        self.player_list_widget.clear()
        for name, data in self.players.items():
            pslink     = data.get("pslink", "") if isinstance(data, dict) else data
            has_cookie = "\u2713" if isinstance(data, dict) and data.get("cookie") else "\u2717"
            auto       = "ON" if isinstance(data, dict) and data.get("auto_launch", True) else "OFF"
            bad_cookie = isinstance(data, dict) and data.get("cookie_invalid", False)

            label = f"[{has_cookie}|{auto}]  {name}   \u00b7   {pslink or '\u2014'}"
            if bad_cookie:
                label = f"\u26a0 [{has_cookie}|{auto}]  {name}   \u00b7   {pslink or '\u2014'}"

            item = QListWidgetItem(label)
            if bad_cookie:
                item.setForeground(QColor(COLORS["red"]))
            self.player_list_widget.addItem(item)

    def _load_selected_player(self, index):
        if index < 0 or index >= len(self.players):
            return
        name = list(self.players.keys())[index]
        data = self.players[name]
        self.new_username.setText(name)
        if isinstance(data, dict):
            self.new_pslink.setText(data.get("pslink", ""))
            self.auto_launch_checkbox_settings.setChecked(data.get("auto_launch", True))
        else:
            self.new_pslink.setText(data)
            self.auto_launch_checkbox_settings.setChecked(True)

    def _add_player(self):
        username = self.new_username.text().strip()
        pslink   = self.new_pslink.text().strip()

        if not username:
            QMessageBox.warning(self, "Error", "Username cannot be empty.")
            return

        selected   = self.player_list_widget.currentRow()
        old_cookie = ""

        if selected >= 0:
            old_name = list(self.players.keys())[selected]
            old_data = self.players.get(old_name, {})
            if isinstance(old_data, dict):
                old_cookie = old_data.get("cookie", "")
            self.players.pop(old_name, None)
        elif username in self.players:
            old_data = self.players[username]
            if isinstance(old_data, dict):
                old_cookie = old_data.get("cookie", "")

        self.players[username] = {
            "pslink":      pslink,
            "cookie":      old_cookie,
            "auto_launch": self.auto_launch_checkbox_settings.isChecked()
        }
        self._refresh_settings_list()
        self.new_username.clear()
        self.new_pslink.clear()

    def _remove_player(self):
        row = self.player_list_widget.currentRow()
        if row < 0:
            return
        username = list(self.players.keys())[row]
        self.players.pop(username, None)
        self.player_list_widget.takeItem(row)

        self.settings["players"] = self.players
        save_settings(self.settings)
        self.parent.players = self.players
        self.parent.signals.players_updated.emit(self.players)

    def _save_players(self):
        self.settings["players"] = self.players
        save_settings(self.settings)
        self.parent.players = self.players
        self.parent.signals.players_updated.emit(self.players)
        self._flash_saved("Players saved.")

    def extract_cookie(self):
        target_username = self.new_username.text().strip()
        if not target_username:
            QMessageBox.warning(self, "Error",
                "Please click a player from the list or enter their username first.")
            return

        if not WEBENGINE_AVAILABLE:
            QMessageBox.critical(self, "Error",
                "PyQt6-WebEngine is not installed. "
                "Run 'python -m pip install PyQt6-WebEngine requests' to use this feature.")
            return

        dialog = CookieBrowserDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            cookie = dialog.cookie_value
            if cookie:
                try:
                    req = requests.get("https://users.roblox.com/v1/users/authenticated",
                                       cookies={".ROBLOSECURITY": cookie})
                    if req.status_code == 200:
                        actual_username = req.json().get("name")

                        if actual_username.lower() != target_username.lower():
                            reply = QMessageBox.question(
                                self, "Mismatch",
                                f"You logged into '{actual_username}', but selected '{target_username}'.\n\n"
                                f"Assign this cookie to {target_username}?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                            )
                            if reply == QMessageBox.StandardButton.No:
                                return

                        if target_username in self.players:
                            self.players[target_username]["cookie"] = cookie
                        else:
                            pslink = self.new_pslink.text().strip()
                            self.players[target_username] = {
                                "pslink":      pslink,
                                "cookie":      cookie,
                                "auto_launch": self.auto_launch_checkbox_settings.isChecked()
                            }

                        self._save_players()
                        mark_cookie_invalid(target_username, invalid=False)
                        self._refresh_settings_list()
                        QMessageBox.information(self, "Success",
                            f"Linked cookie successfully to {target_username}!")
                    else:
                        QMessageBox.warning(self, "Error", "Failed to verify cookie via Roblox API.")
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"An error occurred: {e}")

    def launch_player(self):
        username = self.new_username.text().strip()
        if not username or username not in self.players:
            QMessageBox.warning(self, "Error", "Please select a valid player to launch.")
            return

        player_data = self.players[username]
        if not isinstance(player_data, dict):
            QMessageBox.warning(self, "Error", "Player data is invalid.")
            return

        cookie = player_data.get("cookie")
        pslink = player_data.get("pslink")

        if not cookie:
            QMessageBox.warning(self, "Error", "No cookie linked for this player.")
            return
        if not pslink:
            QMessageBox.warning(self, "Error", "No private server link for this player.")
            return

        success, msg = roblox_launcher.launch_private_server(cookie, pslink)
        if success:
            QMessageBox.information(self, "Success", f"Launching Roblox for {username}...")
        else:
            QMessageBox.warning(self, "Launch Error",
                f"Failed to launch Roblox for {username}:\n\n{msg}")

    # ══════════════════════════════════════════════════════════════
    # TAB: WEBHOOKS
    # ══════════════════════════════════════════════════════════════
    def _build_webhooks_tab(self):
        page   = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(16)
        layout.setContentsMargins(0, 0, 0, 0)

        left = QWidget()
        left.setMaximumWidth(220)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(8)

        title_wh = QLabel("WEBHOOKS")
        title_wh.setObjectName("title")
        ll.addWidget(title_wh)

        hint = QLabel(
            "Create named webhooks and configure\n"
            "accounts, enabled biomes, and role IDs\n"
            "independently per webhook."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        ll.addWidget(hint)

        self.wh_list_widget = QListWidget()
        self.wh_list_widget.currentRowChanged.connect(self._load_webhook)
        ll.addWidget(self.wh_list_widget, 1)

        wh_btn_row = QHBoxLayout()
        add_wh_btn = AnimatedButton("+ Add")
        add_wh_btn.setObjectName("action")
        add_wh_btn.clicked.connect(self._add_webhook)
        rm_wh_btn  = AnimatedButton("\u2715 Remove")
        rm_wh_btn.setObjectName("danger")
        rm_wh_btn.clicked.connect(self._remove_webhook)
        wh_btn_row.addWidget(add_wh_btn)
        wh_btn_row.addWidget(rm_wh_btn)
        ll.addLayout(wh_btn_row)

        layout.addWidget(left)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        layout.addWidget(sep)

        right = QWidget()
        rl    = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)

        editor_title = QLabel("EDIT WEBHOOK")
        editor_title.setObjectName("section_header")
        rl.addWidget(editor_title)

        form_wh = QFormLayout()
        form_wh.setSpacing(8)
        self.wh_name_input = QLineEdit()
        self.wh_name_input.setPlaceholderText("e.g. Main Server, Alt Alerts\u2026")
        self.wh_url_input  = QLineEdit()
        self.wh_url_input.setPlaceholderText("https://discord.com/api/webhooks/\u2026")
        self.wh_delay_input = QLineEdit()
        self.wh_delay_input.setPlaceholderText("0")

        form_wh.addRow("Name:", self.wh_name_input)
        form_wh.addRow("URL:",  self.wh_url_input)
        form_wh.addRow("Delay (ms):", self.wh_delay_input)
        rl.addLayout(form_wh)

        editor_scroll = QScrollArea()
        editor_scroll.setWidgetResizable(True)
        editor_scroll.setFrameShape(QFrame.Shape.NoFrame)
        editor_content = QWidget()
        editor_layout  = QVBoxLayout(editor_content)
        editor_layout.setSpacing(12)
        editor_layout.setContentsMargins(2, 4, 8, 4)
        editor_scroll.setWidget(editor_content)
        rl.addWidget(editor_scroll, 1)

        checklists_row = QHBoxLayout()
        checklists_row.setSpacing(12)

        # Biome accounts
        biome_col = QVBoxLayout()
        biome_hdr = QHBoxLayout()
        biome_acct_lbl = QLabel("BIOME ACCOUNTS")
        biome_acct_lbl.setObjectName("section_header")
        biome_hdr.addWidget(biome_acct_lbl)
        biome_all_btn = AnimatedButton("All")
        biome_all_btn.setFixedHeight(24)
        biome_all_btn.clicked.connect(self._check_all_biome_accounts)
        biome_hdr.addWidget(biome_all_btn)
        biome_col.addLayout(biome_hdr)
        biome_acct_scroll = QScrollArea()
        biome_acct_scroll.setWidgetResizable(True)
        biome_acct_scroll.setFrameShape(QFrame.Shape.NoFrame)
        biome_acct_scroll.setFixedHeight(110)
        biome_acct_content = QWidget()
        self.wh_biome_layout = QVBoxLayout(biome_acct_content)
        self.wh_biome_layout.setSpacing(4)
        self.wh_biome_layout.setContentsMargins(2, 2, 2, 2)
        biome_acct_scroll.setWidget(biome_acct_content)
        biome_col.addWidget(biome_acct_scroll)
        checklists_row.addLayout(biome_col)

        # Merchant accounts
        merchant_col = QVBoxLayout()
        merchant_hdr = QHBoxLayout()
        merchant_acct_lbl = QLabel("MERCHANT ACCOUNTS")
        merchant_acct_lbl.setObjectName("section_header")
        merchant_hdr.addWidget(merchant_acct_lbl)
        merchant_all_btn = AnimatedButton("All")
        merchant_all_btn.setFixedHeight(24)
        merchant_all_btn.clicked.connect(self._check_all_merchant_accounts)
        merchant_hdr.addWidget(merchant_all_btn)
        merchant_col.addLayout(merchant_hdr)
        merchant_acct_scroll = QScrollArea()
        merchant_acct_scroll.setWidgetResizable(True)
        merchant_acct_scroll.setFrameShape(QFrame.Shape.NoFrame)
        merchant_acct_scroll.setFixedHeight(110)
        merchant_acct_content = QWidget()
        self.wh_merchant_layout = QVBoxLayout(merchant_acct_content)
        self.wh_merchant_layout.setSpacing(4)
        self.wh_merchant_layout.setContentsMargins(2, 2, 2, 2)
        merchant_acct_scroll.setWidget(merchant_acct_content)
        merchant_col.addWidget(merchant_acct_scroll)
        checklists_row.addLayout(merchant_col)

        editor_layout.addLayout(checklists_row)

        self.wh_biome_checkboxes:    dict = {}
        self.wh_merchant_checkboxes: dict = {}

        self._wh_autosave_timer = QTimer(self)
        self._wh_autosave_timer.setSingleShot(True)
        self._wh_autosave_timer.timeout.connect(self._autosave_current_webhook)

        self._rebuild_wh_account_checkboxes()

        editor_layout.addWidget(self._divider())

        from settings_manager import BIOME_ALL_KEYS, BIOME_ROLE_ID_KEYS, MERCHANT_ROLE_ID_KEYS

        en_biome_hdr = QHBoxLayout()
        en_biome_lbl = QLabel("ENABLED BIOMES")
        en_biome_lbl.setObjectName("section_header")
        en_biome_hdr.addWidget(en_biome_lbl)
        en_biome_all_btn = AnimatedButton("All")
        en_biome_all_btn.setFixedHeight(24)
        en_biome_all_btn.clicked.connect(self._check_all_enabled_biomes)
        en_biome_hdr.addWidget(en_biome_all_btn)
        en_biome_hdr.addStretch()
        editor_layout.addLayout(en_biome_hdr)

        en_biome_hint = QLabel("Uncheck a biome to stop this webhook sending alerts for it.")
        en_biome_hint.setObjectName("hint")
        en_biome_hint.setWordWrap(True)
        editor_layout.addWidget(en_biome_hint)

        self.wh_enabled_biome_checkboxes: dict = {}
        en_biome_grid = QHBoxLayout()
        col1 = QVBoxLayout()
        col2 = QVBoxLayout()
        biome_keys = list(BIOME_ALL_KEYS)
        mid = (len(biome_keys) + 1) // 2
        for i, biome_name in enumerate(biome_keys):
            cb = QCheckBox(biome_name.title())
            cb.setChecked(True)
            cb.toggled.connect(lambda _c: self._wh_autosave_timer.start(300))
            self.wh_enabled_biome_checkboxes[biome_name] = cb
            (col1 if i < mid else col2).addWidget(cb)
        en_biome_grid.addLayout(col1)
        en_biome_grid.addLayout(col2)
        en_biome_grid.addStretch()
        editor_layout.addLayout(en_biome_grid)

        editor_layout.addWidget(self._divider())

        biome_role_lbl = QLabel("BIOME ROLE IDS")
        biome_role_lbl.setObjectName("section_header")
        editor_layout.addWidget(biome_role_lbl)

        biome_role_hint = QLabel(
            "glitched, cyberspace and dreamspace always ping @everyone \u2014 no role ID needed."
        )
        biome_role_hint.setObjectName("hint")
        biome_role_hint.setWordWrap(True)
        editor_layout.addWidget(biome_role_hint)

        biome_role_form = QFormLayout()
        biome_role_form.setSpacing(6)
        self.wh_biome_role_inputs: dict = {}
        for biome_name in BIOME_ROLE_ID_KEYS:
            inp = QLineEdit()
            inp.setPlaceholderText("Discord role ID")
            inp.setMaximumWidth(200)
            biome_role_form.addRow(f"{biome_name.title()}:", inp)
            self.wh_biome_role_inputs[biome_name] = inp
        editor_layout.addLayout(biome_role_form)

        editor_layout.addWidget(self._divider())

        merchant_role_lbl = QLabel("MERCHANT ROLE IDS")
        merchant_role_lbl.setObjectName("section_header")
        editor_layout.addWidget(merchant_role_lbl)

        merchant_role_form = QFormLayout()
        merchant_role_form.setSpacing(6)
        self.wh_merchant_role_inputs: dict = {}
        for merchant_name in MERCHANT_ROLE_ID_KEYS:
            inp = QLineEdit()
            inp.setPlaceholderText("Discord role ID")
            inp.setMaximumWidth(200)
            merchant_role_form.addRow(f"{merchant_name.title()}:", inp)
            self.wh_merchant_role_inputs[merchant_name] = inp
        editor_layout.addLayout(merchant_role_form)

        editor_layout.addStretch()

        btn_row = QHBoxLayout()
        test_wh_btn = AnimatedButton("\u2709 Send Test")
        test_wh_btn.clicked.connect(self._test_current_webhook)
        save_wh_btn = AnimatedButton("\u2713 Save Webhook")
        save_wh_btn.setObjectName("save")
        save_wh_btn.clicked.connect(self._save_current_webhook)
        btn_row.addWidget(test_wh_btn)
        btn_row.addWidget(save_wh_btn)
        btn_row.addStretch()
        rl.addLayout(btn_row)

        layout.addWidget(right, 1)

        self._refresh_webhooks_list()
        return page

    def _rebuild_wh_account_checkboxes(self):
        for cb in self.wh_biome_checkboxes.values():
            cb.setParent(None)
        self.wh_biome_checkboxes.clear()

        for cb in self.wh_merchant_checkboxes.values():
            cb.setParent(None)
        self.wh_merchant_checkboxes.clear()

        for name in self.players.keys():
            b_cb = QCheckBox(name)
            b_cb.toggled.connect(lambda _c, _n=name: self._wh_autosave_timer.start(300))
            self.wh_biome_layout.addWidget(b_cb)
            self.wh_biome_checkboxes[name] = b_cb

            m_cb = QCheckBox(name)
            m_cb.toggled.connect(lambda _c, _n=name: self._wh_autosave_timer.start(300))
            self.wh_merchant_layout.addWidget(m_cb)
            self.wh_merchant_checkboxes[name] = m_cb

        self.wh_biome_layout.addStretch()
        self.wh_merchant_layout.addStretch()

    def _check_all_biome_accounts(self):
        for cb in self.wh_biome_checkboxes.values():
            cb.setChecked(True)

    def _check_all_merchant_accounts(self):
        for cb in self.wh_merchant_checkboxes.values():
            cb.setChecked(True)

    def _check_all_enabled_biomes(self):
        for cb in self.wh_enabled_biome_checkboxes.values():
            cb.setChecked(True)

    def _refresh_webhooks_list(self):
        self.wh_list_widget.clear()
        for wh in self.webhooks_data:
            name = wh.get("name", "Unnamed")
            n_b  = len(wh.get("biome_accounts", []))
            n_m  = len(wh.get("merchant_accounts", []))
            self.wh_list_widget.addItem(f"{name} [B:{n_b} M:{n_m}]")

        has = bool(self.webhooks_data)
        self.wh_name_input.setEnabled(has)
        self.wh_url_input.setEnabled(has)
        self.wh_delay_input.setEnabled(has)
        for cb in (
            list(self.wh_biome_checkboxes.values())
            + list(self.wh_merchant_checkboxes.values())
            + list(self.wh_enabled_biome_checkboxes.values())
        ):
            cb.setEnabled(has)
        for inp in list(self.wh_biome_role_inputs.values()) + list(self.wh_merchant_role_inputs.values()):
            inp.setEnabled(has)

    def _load_webhook(self, index):
        if index < 0 or index >= len(self.webhooks_data):
            return
        from settings_manager import BIOME_ALL_KEYS

        wh = self.webhooks_data[index]
        self.wh_name_input.setText(wh.get("name", ""))
        self.wh_url_input.setText(wh.get("url", ""))
        self.wh_delay_input.setText(str(wh.get("delay_ms", 0)))

        biome_accts    = wh.get("biome_accounts", [])
        merchant_accts = wh.get("merchant_accounts", [])
        for name, cb in self.wh_biome_checkboxes.items():
            cb.blockSignals(True); cb.setChecked(name in biome_accts); cb.blockSignals(False)
        for name, cb in self.wh_merchant_checkboxes.items():
            cb.blockSignals(True); cb.setChecked(name in merchant_accts); cb.blockSignals(False)

        enabled_biomes = wh.get("enabled_biomes", list(BIOME_ALL_KEYS))
        for name, cb in self.wh_enabled_biome_checkboxes.items():
            cb.blockSignals(True); cb.setChecked(name in enabled_biomes); cb.blockSignals(False)

        biome_role_ids    = wh.get("biome_role_ids", {})
        merchant_role_ids = wh.get("merchant_role_ids", {})
        for biome_name, inp in self.wh_biome_role_inputs.items():
            inp.setText(str(biome_role_ids.get(biome_name, "") or ""))
        for merchant_name, inp in self.wh_merchant_role_inputs.items():
            inp.setText(str(merchant_role_ids.get(merchant_name, "") or ""))

    def _add_webhook(self):
        from settings_manager import BIOME_ALL_KEYS, BIOME_ROLE_ID_KEYS, MERCHANT_ROLE_ID_KEYS
        new_wh = {
            "name":              f"Webhook {len(self.webhooks_data) + 1}",
            "url":               "",
            "delay_ms":          0,
            "biome_accounts":    [],
            "merchant_accounts": [],
            "biome_role_ids":    {k: "" for k in BIOME_ROLE_ID_KEYS},
            "merchant_role_ids": {k: "" for k in MERCHANT_ROLE_ID_KEYS},
            "enabled_biomes":    list(BIOME_ALL_KEYS),
        }
        self.webhooks_data.append(new_wh)
        self._refresh_webhooks_list()
        self.wh_list_widget.setCurrentRow(len(self.webhooks_data) - 1)

    def _remove_webhook(self):
        row = self.wh_list_widget.currentRow()
        if row < 0 or row >= len(self.webhooks_data):
            return
        self.webhooks_data.pop(row)
        self._refresh_webhooks_list()
        self.settings["webhooks"] = self.webhooks_data
        save_settings(self.settings)

    def _collect_current_webhook_data(self):
        row = self.wh_list_widget.currentRow()
        if row < 0 or row >= len(self.webhooks_data):
            return None
        try:
            delay = int(self.wh_delay_input.text().strip())
        except ValueError:
            delay = 0
        return {
            "row":              row,
            "name":             self.wh_name_input.text().strip(),
            "url":              self.wh_url_input.text().strip(),
            "delay_ms":         delay,
            "biome_accounts":   [n for n, cb in self.wh_biome_checkboxes.items()         if cb.isChecked()],
            "merchant_accounts":[n for n, cb in self.wh_merchant_checkboxes.items()      if cb.isChecked()],
            "enabled_biomes":   [k for k, cb in self.wh_enabled_biome_checkboxes.items() if cb.isChecked()],
            "biome_role_ids":   {k: inp.text().strip() for k, inp in self.wh_biome_role_inputs.items()},
            "merchant_role_ids":{k: inp.text().strip() for k, inp in self.wh_merchant_role_inputs.items()},
        }

    def _build_webhook_entry(self, d: dict) -> dict:
        return {
            "name":              d["name"],
            "url":               d["url"],
            "delay_ms":          d["delay_ms"],
            "biome_accounts":    d["biome_accounts"],
            "merchant_accounts": d["merchant_accounts"],
            "enabled_biomes":    d["enabled_biomes"],
            "biome_role_ids":    d["biome_role_ids"],
            "merchant_role_ids": d["merchant_role_ids"],
        }

    def _autosave_current_webhook(self):
        d = self._collect_current_webhook_data()
        if d is None or not d["name"]:
            return
        self.webhooks_data[d["row"]] = self._build_webhook_entry(d)
        self.settings["webhooks"] = self.webhooks_data
        save_settings(self.settings)
        self._refresh_webhooks_list()
        self.wh_list_widget.setCurrentRow(d["row"])

    def _save_current_webhook(self):
        d = self._collect_current_webhook_data()
        if d is None:
            QMessageBox.warning(self, "Error",
                "Select a webhook from the list first, or click '+ Add' to create one.")
            return
        if not d["name"]:
            QMessageBox.warning(self, "Error", "Webhook name cannot be empty.")
            return
        if not d["url"]:
            QMessageBox.warning(self, "Error", "Webhook URL cannot be empty.")
            return
        self.webhooks_data[d["row"]] = self._build_webhook_entry(d)
        self.settings["webhooks"] = self.webhooks_data
        save_settings(self.settings)
        self._refresh_webhooks_list()
        self.wh_list_widget.setCurrentRow(d["row"])
        self._warn_unlinked_accounts()
        self._flash_saved(f'Webhook "{d["name"]}" saved.')

    def _test_current_webhook(self):
        url = self.wh_url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Enter a webhook URL before testing.")
            return
        from webhook import send_test_webhook
        success, msg = send_test_webhook(url)
        if success:
            QMessageBox.information(self, "Test Sent", msg)
        else:
            QMessageBox.warning(self, "Test Failed", msg)

    def _warn_unlinked_accounts(self):
        all_players = list(self.players.keys())
        if not all_players:
            return
        all_biome_covered    = set()
        all_merchant_covered = set()
        for wh in self.webhooks_data:
            if not isinstance(wh, dict):
                continue
            all_biome_covered.update(wh.get("biome_accounts", []))
            all_merchant_covered.update(wh.get("merchant_accounts", []))
        unlinked_biome    = [p for p in all_players if p not in all_biome_covered]
        unlinked_merchant = [p for p in all_players if p not in all_merchant_covered]
        if not unlinked_biome and not unlinked_merchant:
            return
        lines = ["The following accounts have no webhook assigned and will receive no notifications:\n"]
        if unlinked_biome:
            lines.append("Biomes:\n  " + "\n  ".join(unlinked_biome))
        if unlinked_merchant:
            lines.append("\nMerchants:\n  " + "\n  ".join(unlinked_merchant))
        QMessageBox.warning(self, "Unlinked Accounts", "\n".join(lines))

    # ══════════════════════════════════════════════════════════════
    # TAB: BES
    # ══════════════════════════════════════════════════════════════
    def _build_bes_tab(self):
        page   = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        bes = self.settings.get("bes", {})

        header_row = QHBoxLayout()
        title = QLabel("BES \u00b7 CPU THROTTLER")
        title.setObjectName("title")
        header_row.addWidget(title)
        header_row.addStretch()

        self.bes_toggle_btn = AnimatedButton(
            "\u25a0 Stop BES" if getattr(self.parent, 'bes_is_running', False) else "\u25b6 Start BES"
        )
        self.bes_toggle_btn.setCheckable(True)
        self.bes_toggle_btn.setChecked(getattr(self.parent, 'bes_is_running', False))
        self.bes_toggle_btn.setObjectName("action")
        self.bes_toggle_btn.clicked.connect(self._toggle_bes)
        header_row.addWidget(self.bes_toggle_btn)
        layout.addLayout(header_row)

        desc = QLabel("Limits Roblox CPU usage similarly to Battle Encoder Shirase (BES).")
        desc.setWordWrap(True)
        desc.setObjectName("hint")
        layout.addWidget(desc)

        layout.addWidget(self._divider())

        form = QFormLayout()
        form.setSpacing(10)

        cpu_row = QHBoxLayout()
        self.bes_cpu_input = QLineEdit(str(bes.get("cpu_limit", 50)))
        self.bes_cpu_input.setPlaceholderText("1 \u2013 99")
        self.bes_cpu_input.setMaximumWidth(80)
        cpu_row.addWidget(self.bes_cpu_input)
        cpu_row.addWidget(QLabel("%"))
        cpu_row.addStretch()
        form.addRow("CPU Limit:", cpu_row)

        cycle_row = QHBoxLayout()
        self.bes_cycle_input = QLineEdit(str(bes.get("cycle_ms", 1000)))
        self.bes_cycle_input.setPlaceholderText("e.g. 1000")
        self.bes_cycle_input.setMaximumWidth(80)
        cycle_row.addWidget(self.bes_cycle_input)
        cycle_row.addWidget(QLabel("ms per cycle  (lower = smoother but higher overhead)"))
        cycle_row.addStretch()
        form.addRow("Cycle Time:", cycle_row)

        layout.addLayout(form)
        layout.addWidget(self._divider())

        exempt_header = QLabel("EXEMPT ACCOUNTS")
        exempt_header.setObjectName("section_header")
        layout.addWidget(exempt_header)

        exempt_desc = QLabel("Checked accounts will NOT be throttled even while BES is running.")
        exempt_desc.setWordWrap(True)
        exempt_desc.setObjectName("hint")
        layout.addWidget(exempt_desc)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_content = QWidget()
        self.bes_exempt_layout = QVBoxLayout(scroll_content)
        self.bes_exempt_layout.setSpacing(5)
        self.bes_exempt_layout.setContentsMargins(4, 4, 4, 4)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        self.bes_exempt_checkboxes: dict = {}
        exempt_accounts = bes.get("exempt_accounts", [])
        for name in self.players.keys():
            cb = QCheckBox(name)
            cb.setChecked(name in exempt_accounts)
            self.bes_exempt_layout.addWidget(cb)
            self.bes_exempt_checkboxes[name] = cb
        self.bes_exempt_layout.addStretch()

        save_bes_btn = AnimatedButton("\u2713 Save BES Settings")
        save_bes_btn.setObjectName("save")
        save_bes_btn.clicked.connect(self._save_bes_settings)
        layout.addWidget(save_bes_btn)

        return page

    def _save_bes_settings(self):
        try:
            cpu_limit = max(1, min(99, int(self.bes_cpu_input.text().strip())))
        except ValueError:
            cpu_limit = 50
        try:
            cycle_ms = max(100, int(self.bes_cycle_input.text().strip()))
        except ValueError:
            cycle_ms = 1000

        exempt_accounts = [
            name for name, cb in self.bes_exempt_checkboxes.items()
            if cb.isChecked()
        ]
        self.settings["bes"] = {
            "cpu_limit":       cpu_limit,
            "cycle_ms":        cycle_ms,
            "exempt_accounts": exempt_accounts
        }
        save_settings(self.settings)
        self._flash_saved("BES settings saved.")

    def _toggle_bes(self):
        on = self.bes_toggle_btn.isChecked()
        self.bes_toggle_btn.setText("\u25a0 Stop BES" if on else "\u25b6 Start BES")
        self.parent.bes_is_running = on
        if on:
            self.parent.signals.start_bes.emit()
        else:
            self.parent.signals.stop_bes.emit()

# ══════════════════════════════════════════════════════════════
# TAB: AUTO ITEM
# ══════════════════════════════════════════════════════════════

    _AI_COORD_KEYS = [
        ("inv_button",   "Inventory Button"),
        ("items_tab",    "Items Tab"),
        ("search_box",   "Search Box"),
        ("query_pos",    "First Result (click)"),
        ("amount_box",   "Amount Box"),
        ("use_button",   "Use Button"),
        ("close_button", "Close Button"),
    ]

    _AI_BIOMES = [
        "sand storm", "hell", "starfall", "heaven",
        "corruption", "null", "dreamspace", "glitched",
        "cyberspace", "snowy", "windy", "rainy", "eggland",
    ]

    _AI_BIOME_NEVER = "__never__"

    def _build_auto_item_tab(self):
        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        ai        = self.settings.get("auto_item", {})
        ai_coords = ai.get("coords", {})
        ai_cond   = ai_coords.get("conditional", {})
        self.auto_item_items_data = list(ai.get("items", []))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        page   = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 8, 8)

        header_row = QHBoxLayout()
        title = QLabel("AUTO ITEM")
        title.setObjectName("title")
        header_row.addWidget(title)
        header_row.addStretch()

        self.auto_item_toggle_btn = AnimatedButton(
            "\u25a0 Stop Auto-Item" if getattr(self.parent, "auto_item_is_running", False)
            else "\u25b6 Start Auto-Item"
        )
        self.auto_item_toggle_btn.setCheckable(True)
        self.auto_item_toggle_btn.setChecked(getattr(self.parent, "auto_item_is_running", False))
        self.auto_item_toggle_btn.setObjectName("action")
        self.auto_item_toggle_btn.clicked.connect(self._toggle_auto_item)
        header_row.addWidget(self.auto_item_toggle_btn)
        layout.addLayout(header_row)

        hint = QLabel(
            "Automatically uses items in Roblox on a configurable cooldown. "
            "Coordinates are relative (0.0\u20131.0) to the Roblox window size "
            "so they work at any resolution."
        )
        hint.setWordWrap(True)
        hint.setObjectName("hint")
        layout.addWidget(hint)

        layout.addWidget(self._divider())

        acct_hdr = QLabel("ACCOUNTS")
        acct_hdr.setObjectName("section_header")
        layout.addWidget(acct_hdr)

        acct_hint = QLabel("Select which accounts Auto-Item should run on.")
        acct_hint.setObjectName("hint")
        layout.addWidget(acct_hint)

        ai_users = list(ai.get("users", []))
        self.auto_item_user_checkboxes: dict = {}
        acct_row = QHBoxLayout()
        acct_row.setSpacing(16)
        for name in self.players.keys():
            cb = QCheckBox(name)
            cb.setChecked(name in ai_users)
            acct_row.addWidget(cb)
            self.auto_item_user_checkboxes[name] = cb
        acct_row.addStretch()
        layout.addLayout(acct_row)

        layout.addWidget(self._divider())

        items_hdr = QLabel("ITEMS")
        items_hdr.setObjectName("section_header")
        layout.addWidget(items_hdr)

        self.auto_item_list = QListWidget()
        self.auto_item_list.setFixedHeight(130)
        self.auto_item_list.currentRowChanged.connect(self._load_selected_auto_item)
        layout.addWidget(self.auto_item_list)

        item_btn_row = QHBoxLayout()
        add_item_btn = AnimatedButton("+ Add Item")
        add_item_btn.setObjectName("action")
        add_item_btn.clicked.connect(self._add_auto_item_item)
        rm_item_btn  = AnimatedButton("\u2715 Remove Item")
        rm_item_btn.setObjectName("danger")
        rm_item_btn.clicked.connect(self._remove_auto_item_item)
        item_btn_row.addWidget(add_item_btn)
        item_btn_row.addWidget(rm_item_btn)
        item_btn_row.addStretch()
        layout.addLayout(item_btn_row)

        edit_hdr = QLabel("EDIT SELECTED ITEM")
        edit_hdr.setObjectName("section_header")
        layout.addWidget(edit_hdr)

        item_form = QFormLayout()
        item_form.setSpacing(8)

        self.auto_item_name_input = QLineEdit()
        self.auto_item_name_input.setPlaceholderText("e.g.  Heavenly Potion")
        item_form.addRow("Name:", self.auto_item_name_input)

        self.auto_item_amount_spin = QSpinBox()
        self.auto_item_amount_spin.setRange(1, 9999)
        self.auto_item_amount_spin.setValue(1)
        self.auto_item_amount_spin.setMaximumWidth(90)
        item_form.addRow("Amount:", self.auto_item_amount_spin)

        self.auto_item_cooldown_input = QLineEdit("60")
        self.auto_item_cooldown_input.setPlaceholderText("seconds between uses")
        self.auto_item_cooldown_input.setMaximumWidth(90)
        item_form.addRow("Cooldown (s):", self.auto_item_cooldown_input)

        self.auto_item_item_enabled_cb = QCheckBox("Enabled")
        self.auto_item_item_enabled_cb.setChecked(True)
        item_form.addRow("", self.auto_item_item_enabled_cb)

        layout.addLayout(item_form)

        # ── ACCOUNT FILTER ────────────────────────────────────────────────
        acct_filter_hdr = QLabel("ACCOUNT FILTER")
        acct_filter_hdr.setObjectName("section_header")
        layout.addWidget(acct_filter_hdr)

        acct_filter_hint = QLabel(
            "Choose which accounts this item applies to. "
            "All checked \u2192 any account. "
            "None checked \u2192 item is dormant (never triggered)."
        )
        acct_filter_hint.setWordWrap(True)
        acct_filter_hint.setObjectName("hint")
        layout.addWidget(acct_filter_hint)

        acct_filter_btn_row = QHBoxLayout()
        acct_all_btn  = AnimatedButton("All")
        acct_none_btn = AnimatedButton("None")
        acct_all_btn.setFixedHeight(26)
        acct_none_btn.setFixedHeight(26)
        acct_filter_btn_row.addWidget(acct_all_btn)
        acct_filter_btn_row.addWidget(acct_none_btn)
        acct_filter_btn_row.addStretch()
        layout.addLayout(acct_filter_btn_row)

        self.auto_item_item_accounts_checkboxes: dict = {}
        acct_cb_row = QHBoxLayout()
        acct_cb_row.setSpacing(16)
        for name in self.players.keys():
            cb = QCheckBox(name)
            cb.setChecked(True)
            acct_cb_row.addWidget(cb)
            self.auto_item_item_accounts_checkboxes[name] = cb
        acct_cb_row.addStretch()
        layout.addLayout(acct_cb_row)

        acct_all_btn.clicked.connect(
            lambda: [cb.setChecked(True) for cb in self.auto_item_item_accounts_checkboxes.values()]
        )
        acct_none_btn.clicked.connect(
            lambda: [cb.setChecked(False) for cb in self.auto_item_item_accounts_checkboxes.values()]
        )
        # ─────────────────────────────────────────────────────────────────

        biome_hdr = QLabel("BIOME FILTER")
        biome_hdr.setObjectName("section_header")
        layout.addWidget(biome_hdr)

        biome_hint = QLabel(
            "Check every biome in which this item should be used. "
            "All checked \u2192 use in any biome.  "
            "None checked \u2192 item will never be used."
        )
        biome_hint.setWordWrap(True)
        biome_hint.setObjectName("hint")
        layout.addWidget(biome_hint)

        biome_btn_row = QHBoxLayout()
        check_all_btn   = AnimatedButton("Check All")
        uncheck_all_btn = AnimatedButton("Uncheck All")
        check_all_btn.setFixedHeight(26)
        uncheck_all_btn.setFixedHeight(26)
        biome_btn_row.addWidget(check_all_btn)
        biome_btn_row.addWidget(uncheck_all_btn)
        biome_btn_row.addStretch()
        layout.addLayout(biome_btn_row)

        biome_grid_w = QWidget()
        biome_grid   = QHBoxLayout(biome_grid_w)
        biome_grid.setContentsMargins(0, 0, 0, 0)
        biome_grid.setSpacing(0)
        col1 = QVBoxLayout()
        col2 = QVBoxLayout()
        col1.setSpacing(4)
        col2.setSpacing(4)
        self.auto_item_biome_checkboxes: dict = {}
        for i, biome in enumerate(self._AI_BIOMES):
            cb = QCheckBox(biome.title())
            cb.setChecked(True)
            self.auto_item_biome_checkboxes[biome] = cb
            (col1 if i % 2 == 0 else col2).addWidget(cb)
        col1.addStretch()
        col2.addStretch()
        biome_grid.addLayout(col1)
        biome_grid.addLayout(col2)
        biome_grid.addStretch()
        layout.addWidget(biome_grid_w)

        check_all_btn.clicked.connect(
            lambda: [cb.setChecked(True) for cb in self.auto_item_biome_checkboxes.values()]
        )
        uncheck_all_btn.clicked.connect(
            lambda: [cb.setChecked(False) for cb in self.auto_item_biome_checkboxes.values()]
        )

        alert_hdr = QLabel("ITEM WEBHOOK ALERT  (optional)")
        alert_hdr.setObjectName("section_header")
        layout.addWidget(alert_hdr)

        alert_form = QFormLayout()
        alert_form.setSpacing(8)

        self.auto_item_alert_cb = QCheckBox("Send webhook alert before using this item")
        alert_form.addRow("", self.auto_item_alert_cb)

        self.auto_item_alert_webhook_input = QLineEdit()
        self.auto_item_alert_webhook_input.setPlaceholderText("Discord webhook URL")
        alert_form.addRow("Alert Webhook:", self.auto_item_alert_webhook_input)

        self.auto_item_alert_lead_input = QLineEdit("15")
        self.auto_item_alert_lead_input.setPlaceholderText("seconds before use")
        self.auto_item_alert_lead_input.setMaximumWidth(90)
        alert_form.addRow("Alert Lead (s):", self.auto_item_alert_lead_input)

        self.auto_item_alert_msg_input = QLineEdit()
        self.auto_item_alert_msg_input.setPlaceholderText("Optional message text")
        alert_form.addRow("Message:", self.auto_item_alert_msg_input)

        layout.addLayout(alert_form)

        apply_item_btn = AnimatedButton("\u2713 Apply Item Changes")
        apply_item_btn.clicked.connect(self._apply_auto_item_changes)
        layout.addWidget(apply_item_btn)

        layout.addWidget(self._divider())

        coord_hdr = QLabel("CLICK COORDINATES  (relative 0.0 \u2013 1.0)")
        coord_hdr.setObjectName("section_header")
        layout.addWidget(coord_hdr)

        coord_hint = QLabel(
            "Fraction of the Roblox window width/height. "
            "X=0 is the left edge, X=1 is the right edge. "
            "Y=0 is the top edge, Y=1 is the bottom edge."
        )
        coord_hint.setWordWrap(True)
        coord_hint.setObjectName("hint")
        layout.addWidget(coord_hint)

        coord_form = QFormLayout()
        coord_form.setSpacing(8)
        self.auto_item_coord_inputs = {}

        for key, label in self._AI_COORD_KEYS:
            saved = ai_coords.get(key, {})
            x_in  = QLineEdit(str(saved.get("x", 0.0)))
            y_in  = QLineEdit(str(saved.get("y", 0.0)))
            x_in.setMaximumWidth(80)
            y_in.setMaximumWidth(80)
            row_w = QWidget()
            row_h = QHBoxLayout(row_w)
            row_h.setContentsMargins(0, 0, 0, 0)
            row_h.setSpacing(6)
            row_h.addWidget(QLabel("X:"))
            row_h.addWidget(x_in)
            row_h.addWidget(QLabel("Y:"))
            row_h.addWidget(y_in)
            calib_btn = AnimatedButton("Calibrate")
            calib_btn.setFixedWidth(140)
            calib_btn.clicked.connect(
                lambda _checked=False, lbl=label, xi=x_in, yi=y_in:
                    self._start_calibrate(lbl, xi, yi)
            )
            row_h.addWidget(calib_btn)
            row_h.addStretch()
            coord_form.addRow(f"{label}:", row_w)
            self.auto_item_coord_inputs[key] = (x_in, y_in)

        layout.addLayout(coord_form)

        layout.addWidget(self._divider())

        cond_hdr = QLabel("CONDITIONAL CLICK  (optional gate)")
        cond_hdr.setObjectName("section_header")
        layout.addWidget(cond_hdr)

        cond_hint = QLabel(
            "When enabled, Auto-Item first checks a pixel at the gate point. "
            "It only clicks when the pixel matches the specified color within the given tolerance."
        )
        cond_hint.setWordWrap(True)
        cond_hint.setObjectName("hint")
        layout.addWidget(cond_hint)

        cond_form = QFormLayout()
        cond_form.setSpacing(8)

        self.auto_item_cond_enabled_cb = QCheckBox("Enable conditional click gate")
        self.auto_item_cond_enabled_cb.setChecked(bool(ai_cond.get("enabled", False)))
        cond_form.addRow("", self.auto_item_cond_enabled_cb)

        cond_pt = ai_cond.get("point", {})
        self.auto_item_cond_x_input = QLineEdit(str(cond_pt.get("x", 0.0)))
        self.auto_item_cond_y_input = QLineEdit(str(cond_pt.get("y", 0.0)))
        self.auto_item_cond_x_input.setMaximumWidth(80)
        self.auto_item_cond_y_input.setMaximumWidth(80)
        cond_xy_w = QWidget()
        cond_xy_h = QHBoxLayout(cond_xy_w)
        cond_xy_h.setContentsMargins(0, 0, 0, 0)
        cond_xy_h.setSpacing(6)
        cond_xy_h.addWidget(QLabel("X:"))
        cond_xy_h.addWidget(self.auto_item_cond_x_input)
        cond_xy_h.addWidget(QLabel("Y:"))
        cond_xy_h.addWidget(self.auto_item_cond_y_input)
        cond_calib_btn = AnimatedButton("Calibrate")
        cond_calib_btn.setFixedWidth(140)
        cond_calib_btn.clicked.connect(
            lambda _checked=False: self._start_calibrate(
                "Conditional Gate",
                self.auto_item_cond_x_input,
                self.auto_item_cond_y_input,
            )
        )
        cond_xy_h.addWidget(cond_calib_btn)
        cond_xy_h.addStretch()
        cond_form.addRow("Gate Point:", cond_xy_w)

        self.auto_item_cond_color_input = QLineEdit(str(ai_cond.get("color", "#FFFFFF")))
        self.auto_item_cond_color_input.setPlaceholderText("#RRGGBB")
        self.auto_item_cond_color_input.setMaximumWidth(100)
        cond_form.addRow("Color (hex):", self.auto_item_cond_color_input)

        self.auto_item_cond_tol_spin = QSpinBox()
        self.auto_item_cond_tol_spin.setRange(0, 255)
        self.auto_item_cond_tol_spin.setValue(int(ai_cond.get("tolerance", 10)))
        self.auto_item_cond_tol_spin.setMaximumWidth(90)
        cond_form.addRow("Tolerance:", self.auto_item_cond_tol_spin)

        layout.addLayout(cond_form)

        layout.addWidget(self._divider())

        auto_hdr = QLabel("AUTOMATION")
        auto_hdr.setObjectName("section_header")
        layout.addWidget(auto_hdr)

        auto_form = QFormLayout()
        auto_form.setSpacing(8)

        self.auto_item_tick_input = QLineEdit(str(ai.get("tick_interval", 60.0)))
        self.auto_item_tick_input.setPlaceholderText("seconds between checks")
        self.auto_item_tick_input.setMaximumWidth(90)
        auto_form.addRow("Tick Interval (s):", self.auto_item_tick_input)

        self.auto_item_click_delay_input = QLineEdit(str(ai.get("click_delay", 0.2)))
        self.auto_item_click_delay_input.setPlaceholderText("delay between clicks")
        self.auto_item_click_delay_input.setMaximumWidth(90)
        auto_form.addRow("Click Delay (s):", self.auto_item_click_delay_input)

        self.auto_item_block_mouse_cb = QCheckBox("Block user mouse movement during automation")
        self.auto_item_block_mouse_cb.setChecked(bool(ai.get("disable_mouse_move", False)))
        auto_form.addRow("", self.auto_item_block_mouse_cb)

        layout.addLayout(auto_form)

        layout.addWidget(self._divider())

        bottom_row = QHBoxLayout()

        save_btn = AnimatedButton("\u2713  Save Auto-Item Settings")
        save_btn.setObjectName("save")
        save_btn.clicked.connect(self._save_auto_item_settings)
        bottom_row.addWidget(save_btn)

        self.auto_item_test_combo = QComboBox()
        for name in self.players.keys():
            self.auto_item_test_combo.addItem(name)
        bottom_row.addWidget(self.auto_item_test_combo)

        test_btn = AnimatedButton("\u25b6 Test Once")
        test_btn.clicked.connect(self._test_auto_item_once)
        bottom_row.addWidget(test_btn)
        bottom_row.addStretch()

        layout.addLayout(bottom_row)
        layout.addStretch()

        scroll.setWidget(page)
        outer_layout.addWidget(scroll)

        self._refresh_auto_item_list()
        return outer

    def _refresh_auto_item_list(self):
        self.auto_item_list.clear()
        for item in self.auto_item_items_data:
            name     = item.get("name", "Unnamed")
            amount   = item.get("amount", 1)
            cooldown = item.get("cooldown", 60.0)
            biomes   = item.get("biomes", [])
            enabled  = item.get("enabled", True)
            flag     = "\u2713" if enabled else "\u2717"
            if not biomes:
                bio_str = "any biome"
            elif biomes == [self._AI_BIOME_NEVER]:
                bio_str = "never"
            else:
                bio_str = ", ".join(biomes)
            users          = item.get("users", [])
            users_explicit = bool(item.get("users_explicit", False))
            if not users and not users_explicit:
                acct_str = "all accounts"
            elif not users and users_explicit:
                acct_str = "no accounts"
            else:
                acct_str = ", ".join(str(u) for u in users)
            label = f"[{flag}]  {name}  \u00d7{amount}  every {cooldown}s  [{bio_str}]  [{acct_str}]"
            self.auto_item_list.addItem(label)

    def _load_selected_auto_item(self, index):
        if index < 0 or index >= len(self.auto_item_items_data):
            return
        item = self.auto_item_items_data[index]
        self.auto_item_name_input.setText(str(item.get("name", "")))
        self.auto_item_amount_spin.setValue(int(item.get("amount", 1)))
        self.auto_item_cooldown_input.setText(str(item.get("cooldown", 60.0)))
        self.auto_item_item_enabled_cb.setChecked(bool(item.get("enabled", True)))
        self.auto_item_alert_cb.setChecked(bool(item.get("alert_enabled", False)))
        self.auto_item_alert_webhook_input.setText(str(item.get("alert_webhook", "")))
        self.auto_item_alert_lead_input.setText(str(item.get("alert_lead_s", 15.0)))
        self.auto_item_alert_msg_input.setText(str(item.get("alert_message", "")))

        saved_biomes = item.get("biomes", [])
        if not saved_biomes:
            for cb in self.auto_item_biome_checkboxes.values():
                cb.setChecked(True)
        elif saved_biomes == [self._AI_BIOME_NEVER]:
            for cb in self.auto_item_biome_checkboxes.values():
                cb.setChecked(False)
        else:
            saved_lower = {b.strip().lower() for b in saved_biomes}
            for biome, cb in self.auto_item_biome_checkboxes.items():
                cb.setChecked(biome.lower() in saved_lower)

        # Restore per-item account filter
        saved_users    = item.get("users", [])
        users_explicit = bool(item.get("users_explicit", False))
        if not saved_users and not users_explicit:
            # Default / all accounts
            for cb in self.auto_item_item_accounts_checkboxes.values():
                cb.setChecked(True)
        elif not saved_users and users_explicit:
            # Explicitly no accounts
            for cb in self.auto_item_item_accounts_checkboxes.values():
                cb.setChecked(False)
        else:
            saved_users_set = {str(u).strip() for u in saved_users}
            for name, cb in self.auto_item_item_accounts_checkboxes.items():
                cb.setChecked(name in saved_users_set)

    def _apply_auto_item_changes(self):
        index = self.auto_item_list.currentRow()
        if index < 0 or index >= len(self.auto_item_items_data):
            QMessageBox.warning(self, "No Item Selected", "Select an item from the list first.")
            return
        name = self.auto_item_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Item name cannot be empty.")
            return
        try:
            cooldown = float(self.auto_item_cooldown_input.text().strip())
        except ValueError:
            cooldown = 60.0

        checked_biomes = [
            biome for biome, cb in self.auto_item_biome_checkboxes.items()
            if cb.isChecked()
        ]
        if len(checked_biomes) == len(self._AI_BIOMES):
            biomes = []
        elif checked_biomes:
            biomes = checked_biomes
        else:
            biomes = [self._AI_BIOME_NEVER]

        try:
            lead_s = float(self.auto_item_alert_lead_input.text().strip())
        except ValueError:
            lead_s = 15.0

        # Account filter: collect checked accounts
        checked_accounts = [
            acct for acct, cb in self.auto_item_item_accounts_checkboxes.items()
            if cb.isChecked()
        ]
        all_accounts_checked = len(checked_accounts) == len(self.auto_item_item_accounts_checkboxes)
        if all_accounts_checked:
            item_users          = []
            item_users_explicit = False   # backward-compat: empty = any
        else:
            item_users          = checked_accounts
            item_users_explicit = True    # explicit allowlist (may be empty = nobody)

        self.auto_item_items_data[index] = {
            "name":           name,
            "amount":         self.auto_item_amount_spin.value(),
            "cooldown":       max(0.0, cooldown),
            "biomes":         biomes,
            "enabled":        self.auto_item_item_enabled_cb.isChecked(),
            "users":          item_users,
            "users_explicit": item_users_explicit,
            "alert_enabled":  self.auto_item_alert_cb.isChecked(),
            "alert_webhook":  self.auto_item_alert_webhook_input.text().strip(),
            "alert_lead_s":   max(0.0, lead_s),
            "alert_message":  self.auto_item_alert_msg_input.text().strip(),
        }
        self._refresh_auto_item_list()
        self.auto_item_list.setCurrentRow(index)

    def _add_auto_item_item(self):
        self.auto_item_items_data.append({
            "name":           "New Item",
            "amount":         1,
            "cooldown":       60.0,
            "biomes":         [],
            "enabled":        True,
            "users":          [],
            "users_explicit": False,
            "alert_enabled":  False,
            "alert_webhook":  "",
            "alert_lead_s":   15.0,
            "alert_message":  "",
        })
        self._refresh_auto_item_list()
        self.auto_item_list.setCurrentRow(len(self.auto_item_items_data) - 1)

    def _remove_auto_item_item(self):
        index = self.auto_item_list.currentRow()
        if index < 0 or index >= len(self.auto_item_items_data):
            return
        self.auto_item_items_data.pop(index)
        self._refresh_auto_item_list()
        new_row = min(index, len(self.auto_item_items_data) - 1)
        if new_row >= 0:
            self.auto_item_list.setCurrentRow(new_row)

    def _start_calibrate(self, label: str, x_input: QLineEdit, y_input: QLineEdit) -> None:
        self.hide()

        import window_utils
        hwnds = window_utils.get_roblox_windows()
        if hwnds:
            try:
                import win32gui, win32con, win32process, win32api, ctypes
                hwnd = hwnds[0]
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                current_tid = win32api.GetCurrentThreadId()
                target_tid, _ = win32process.GetWindowThreadProcessId(hwnd)
                ctypes.windll.user32.AttachThreadInput(current_tid, target_tid, True)
                win32gui.BringWindowToTop(hwnd)
                win32gui.SetForegroundWindow(hwnd)
                ctypes.windll.user32.AttachThreadInput(current_tid, target_tid, False)
            except Exception:
                pass

        self._calib_overlay = CalibrateOverlay(label=label, parent=None)

        def _on_captured(rx: float, ry: float) -> None:
            x_input.setText(f"{rx:.4f}")
            y_input.setText(f"{ry:.4f}")
            self.show()
            self.activateWindow()
            self.raise_()
            self._calib_overlay = None

        def _on_cancelled() -> None:
            self.show()
            self.activateWindow()
            self.raise_()
            self._calib_overlay = None

        def _on_destroyed():
            if not self.isVisible():
                self.show()
            self._calib_overlay = None

        self._calib_overlay.captured.connect(_on_captured)
        self._calib_overlay.cancelled.connect(_on_cancelled)
        self._calib_overlay.destroyed.connect(_on_destroyed)
        self._calib_overlay.show()

    def _save_auto_item_settings(self):
        coords_out = {}
        for key, _label in self._AI_COORD_KEYS:
            x_in, y_in = self.auto_item_coord_inputs[key]
            try:
                x = float(x_in.text().strip())
            except ValueError:
                x = 0.0
            try:
                y = float(y_in.text().strip())
            except ValueError:
                y = 0.0
            coords_out[key] = {
                "x": max(0.0, min(1.0, x)),
                "y": max(0.0, min(1.0, y)),
            }
        try:
            cx = float(self.auto_item_cond_x_input.text().strip())
        except ValueError:
            cx = 0.0
        try:
            cy = float(self.auto_item_cond_y_input.text().strip())
        except ValueError:
            cy = 0.0
        coords_out["conditional"] = {
            "enabled":   self.auto_item_cond_enabled_cb.isChecked(),
            "point":     {"x": cx, "y": cy},
            "color":     self.auto_item_cond_color_input.text().strip() or "#FFFFFF",
            "tolerance": self.auto_item_cond_tol_spin.value(),
        }
        try:
            tick = float(self.auto_item_tick_input.text().strip())
        except ValueError:
            tick = 60.0
        try:
            delay = float(self.auto_item_click_delay_input.text().strip())
        except ValueError:
            delay = 0.2

        users = [
            name for name, cb in self.auto_item_user_checkboxes.items()
            if cb.isChecked()
        ]

        self.settings["auto_item"] = {
            "tick_interval":      max(1.0, tick),
            "click_delay":        max(0.05, delay),
            "disable_mouse_move": self.auto_item_block_mouse_cb.isChecked(),
            "users":              users,
            "items":              list(self.auto_item_items_data),
            "coords":             coords_out,
        }
        save_settings(self.settings)
        self.parent.signals.auto_item_config_updated.emit()
        self._flash_saved("Auto-Item settings saved.")

    def _toggle_auto_item(self):
        on = self.auto_item_toggle_btn.isChecked()
        self.auto_item_toggle_btn.setText(
            "\u25a0 Stop Auto-Item" if on else "\u25b6 Start Auto-Item"
        )
        self.parent.auto_item_is_running = on
        if on:
            self.parent.signals.start_auto_item.emit()
        else:
            self.parent.signals.stop_auto_item.emit()

    def _test_auto_item_once(self):
        import auto_item_manager
        uid = self.auto_item_test_combo.currentText().strip()
        if not uid:
            QMessageBox.warning(self, "No Account",
                                "Select an account from the dropdown first.")
            return
        self._save_auto_item_settings()
        ok = auto_item_manager.test_once(uid)
        if not ok:
            QMessageBox.information(
                self, "Test Failed",
                "Test run failed or was skipped. Check the log for details."
            )

    def closeEvent(self, event):
        if hasattr(self, 'trimmer_tab') and hasattr(self, 'pages'):
            self.pages.removeWidget(self.trimmer_tab)
            self.trimmer_tab.setParent(self.parent)
        super().closeEvent(event)

# ══════════════════════════════════════════════════════════════
# TAB: CREDITS
# ══════════════════════════════════════════════════════════════
    def _build_credits_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        # Title
        title = QLabel("CREDITS")
        title.setObjectName("title")
        layout.addWidget(title)

        # Creator section
        creator = QLabel("Created by:")
        creator.setStyleSheet("font-size: 12px; font-weight: bold;")
        layout.addWidget(creator)

        creator_info = QLabel(
            "• GitHub: akindem2\n"
            "• Discord: jamaquasdontaiviousjamaljrlll"
        )
        creator_info.setStyleSheet("font-size: 10px; color: #aaa;")
        creator_info.setWordWrap(True)
        layout.addWidget(creator_info)

        # Project section
        project = QLabel("Project:")
        project.setStyleSheet("font-size: 12px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(project)

        project_info = QLabel(
           "Yes Biome Scanner — a modular, Python powered\n"
            "automation and biome‑detection tool for Roblox Sol's RNG."
        )
        project_info.setStyleSheet("font-size: 10px; color: #aaa;")
        project_info.setWordWrap(True)
        layout.addWidget(project_info)

        # Thanks section
        thanks = QLabel("Special Thanks:")
        thanks.setStyleSheet("font-size: 12px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(thanks)

        thanks_info = QLabel(
            "• Testers\n"
            "• J.JARAM — inspiration for early models"
        )

        thanks_info.setStyleSheet("font-size: 10px; color: #aaa;")
        thanks_info.setWordWrap(True)
        layout.addWidget(thanks_info)

        # Spacer to push content up
        layout.addStretch()

        return page