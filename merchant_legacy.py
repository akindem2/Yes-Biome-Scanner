"""
merchant_legacy.py

Primary detection: log file asset ID scanning (adapted from J.JARAM).
  - Looks for rbxassetid:// lines with known merchant asset IDs.
  - Cheap string prefilter before regex, runs on already-open log files.

Fallback detection: OCR on Roblox window chat region.
"""

import io
import os
import re
import threading
import time
import colorsys
import ctypes
from datetime import datetime, timezone
from typing import Dict, Optional

from PIL import Image
import win32gui
import win32ui
import numpy as np
from rapidfuzz import fuzz

import window_utils
from settings_manager import load_settings
from webhook import send_merchant_detected_message

signals = None
merchant_detector_running = False

_rapid_ocr_engine = None
_ocr_backend_name = None

DEFAULT_MERCHANTS = []

WINDOW_COOLDOWN        = 600    
_window_cooldowns: Dict[int, Dict[str, float]] = {}

CHAT_REGION = {"left": 0.02, "top": 0.10, "right": 0.46, "bottom": 0.58}
FUZZ_THRESHOLD = 70

# ── OCR color matching ────────────────────────────────────────────────────────
# Authoritative RGB values for each merchant's chat text color.
# Used instead of the user-configurable hex string so color is always precise.
MERCHANT_KNOWN_COLORS = {
    "mari":   (243, 243, 244),
    "jester": (154,  77, 241),
    "rin":    (246, 132,  66),
}

# Maximum Euclidean RGB distance for a color to be accepted.
# Color is a hard requirement — no match means no detection.
COLOR_MAX_EUCLIDEAN = 45

def _capture_window(hwnd):
    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width  = right - left
        height = bottom - top

        hwindc = win32gui.GetWindowDC(hwnd)
        srcdc  = win32ui.CreateDCFromHandle(hwindc)
        memdc  = srcdc.CreateCompatibleDC()

        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(srcdc, width, height)
        memdc.SelectObject(bmp)

        result = ctypes.windll.user32.PrintWindow(hwnd, memdc.GetSafeHdc(), 0x00000002)

        bmpinfo = bmp.GetInfo()
        bmpstr  = bmp.GetBitmapBits(True)

        img = Image.frombuffer(
            "RGB",
            (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
            bmpstr, "raw", "BGRX", 0, 1
        )

        win32gui.DeleteObject(bmp.GetHandle())
        memdc.DeleteDC()
        srcdc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwindc)

        return img if result == 1 else None
    except Exception as e:
        if signals:
            signals.log_message.emit(f"[MERCHANT] PrintWindow failed: {e}")
        return None

def _normalize_merchants(raw_merchants):
    merchants = []
    for merchant in raw_merchants or[]:
        if not isinstance(merchant, dict):
            continue
        name    = str(merchant.get("name",    "")).strip()
        message = str(merchant.get("message", "")).strip()
        color   = str(merchant.get("color",   "")).strip()
        role_id = str(merchant.get("role_id", "")).strip()
        if not name or not message:
            continue
        merchants.append({"name": name, "message": message, "color": color, "role_id": role_id})
    return merchants or list(DEFAULT_MERCHANTS)

def _load_runtime_settings():
    settings = load_settings()
    merchant_settings = settings.get("merchant_detection", {})
    return {
        "scan_interval":   max(1, int(merchant_settings.get("scan_interval", 2))),
        "merchants":       _normalize_merchants(merchant_settings.get("merchants",[])),
        "tracked_players": list(settings.get("players", {}).keys()),
    }

def _parse_expected_color(color_str):
    if not color_str:
        return None
    color_str = color_str.strip().lstrip("#")
    if len(color_str) != 6:
        return None
    try:
        return tuple(int(color_str[i:i+2], 16) for i in (0, 2, 4))
    except ValueError:
        return None

def _rgb_to_hsv(rgb):
    r, g, b = (x / 255.0 for x in rgb)
    return colorsys.rgb_to_hsv(r, g, b)

def _hsv_distance(hsv_a, hsv_b):
    dh = abs(hsv_a[0] - hsv_b[0])
    if dh > 0.5:
        dh = 1.0 - dh
    dh *= 360.0
    return dh, abs(hsv_a[1] - hsv_b[1]), abs(hsv_a[2] - hsv_b[2])

def _rgb_euclidean(a, b):
    return (sum((x - y) ** 2 for x, y in zip(a, b))) ** 0.5

def _extract_text_color(line_image, expected_rgb):
    """
    Returns (match: bool, best_rgb: tuple|None).

    Color is a hard requirement:
      - Returns (False, None) immediately if expected_rgb is None.
      - Extracts dominant colors from the OCR line's bounding-box image.
      - Accepts only if the closest color is within COLOR_MAX_EUCLIDEAN of
        expected_rgb in RGB Euclidean space.
      - Fails closed on any extraction error (no color → no detection).
    """
    if expected_rgb is None:
        return False, None
    if line_image.width <= 0 or line_image.height <= 0:
        return False, None
    try:
        import extcolors
        extracted, _ = extcolors.extract_from_image(line_image, tolerance=12, limit=6)
    except Exception as exc:
        if signals:
            signals.log_message.emit(f"[MERCHANT] Color detection failed: {exc}")
        return False, None  # fail closed — color is mandatory

    if not extracted:
        return False, None

    candidate_colors = [rgb for rgb, _count in extracted if max(rgb) > 35]
    if not candidate_colors:
        return False, None

    best_color = min(candidate_colors, key=lambda rgb: _rgb_euclidean(rgb, expected_rgb))
    dist = _rgb_euclidean(best_color, expected_rgb)
    if dist <= COLOR_MAX_EUCLIDEAN:
        return True, best_color
    return False, best_color

def _matches_merchant(line_text, merchant):
    if not line_text:
        return False
    text = line_text.lower().strip()
    msg  = merchant.get("message", "").lower().strip()
    if len(text) < 6:
        return False
    if msg in text:
        return True
    return fuzz.ratio(msg, text) >= FUZZ_THRESHOLD

def _clamp_box(box, image):
    if not box:
        return None
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]
    left, top     = max(0, int(min(xs))), max(0, int(min(ys)))
    right, bottom = min(image.width, int(max(xs))), min(image.height, int(max(ys)))
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom

def _ensure_ocr_backend():
    global _rapid_ocr_engine, _ocr_backend_name
    if _rapid_ocr_engine is not None:
        return
    from rapidocr_onnxruntime import RapidOCR
    _rapid_ocr_engine = RapidOCR()
    _ocr_backend_name = "rapidocr"

def _run_ocr(image):
    if _rapid_ocr_engine is None:
        return[]
    arr    = np.asarray(image.convert("RGB"))
    result = _rapid_ocr_engine(arr)
    lines  = []
    if result and result[0]:
        for item in result[0]:
            box, text, *_ = item
            if text:
                lines.append({"text": text, "box": box})
    return lines

def _scan_window_ocr(hwnd, merchants, account_name=None):
    full_img = _capture_window(hwnd)
    if full_img is None:
        return

    width, height = full_img.size
    crop_box = (
        int(width  * CHAT_REGION["left"]),
        int(height * CHAT_REGION["top"]),
        int(width  * CHAT_REGION["right"]),
        int(height * CHAT_REGION["bottom"]),
    )
    if crop_box[2] <= crop_box[0] or crop_box[3] <= crop_box[1]:
        return

    chat_image = full_img.crop(crop_box)

    try:
        w, h = chat_image.size
        if max(w, h) > 800:
            scale      = 800.0 / float(max(w, h))
            chat_image = chat_image.resize(
                (max(1, int(w * scale)), max(1, int(h * scale))), Image.BILINEAR
            )
    except Exception:
        pass

    try:
        chat_ocr_lines = _run_ocr(chat_image)
    except Exception as exc:
        if signals:
            signals.log_message.emit(f"[MERCHANT] OCR failed: {exc}")
        return

    for line in chat_ocr_lines:
        line_text = line["text"]
        clamped   = _clamp_box(line["box"], chat_image)
        if not clamped:
            continue
        line_image = chat_image.crop(clamped)

        for merchant in merchants:
            # Use the hardcoded known color for this merchant — not the config hex.
            # Color is a hard requirement: both text AND color must match.
            expected_rgb = MERCHANT_KNOWN_COLORS.get(merchant["name"].lower())
            color_matches, detected_color = _extract_text_color(line_image, expected_rgb)
            if not color_matches:
                continue
            if not _matches_merchant(line_text, merchant):
                continue

            merchant_key = merchant["name"].lower()
            now          = time.time()
            _window_cooldowns.setdefault(hwnd, {})
            if now - _window_cooldowns[hwnd].get(merchant_key, 0) < WINDOW_COOLDOWN:
                continue

            for m in merchants:
                _window_cooldowns[hwnd][m["name"].lower()] = now

            account_label = account_name or "Unknown account"
            if signals:
                signals.log_message.emit(
                    f"[MERCHANT] {merchant['name']} detected (OCR) for {account_label}: {line_text}"
                )

            img_bytes = io.BytesIO()
            chat_image.save(img_bytes, format="PNG")

            send_merchant_detected_message(
                merchant["name"],
                merchant["message"],
                merchant.get("color", ""),
                merchant.get("role_id", ""),
                account_name,
                line_text,
                detected_color,
                img_bytes.getvalue(),
            )

def merchant_detector_loop():
    global merchant_detector_running

    runtime = _load_runtime_settings()
    if signals:
        signals.log_message.emit(
            f"[START] OCR Merchant detector running — interval: {runtime['scan_interval']}s"
        )

    while merchant_detector_running:
        runtime         = _load_runtime_settings()
        merchants       = runtime["merchants"]
        tracked_players = runtime["tracked_players"]

        if not merchants:
            time.sleep(runtime["scan_interval"])
            continue

        for hwnd in window_utils.get_roblox_windows():
            account_name = window_utils.resolve_account_for_window(hwnd, tracked_players)
            _scan_window_ocr(hwnd, merchants, account_name)

        time.sleep(runtime["scan_interval"])

    if signals:
        signals.log_message.emit("[STOP] Merchant detector stopped")

def init(sig):
    global signals
    signals = sig
    signals.start_merchant_detector.connect(start_merchant_detector)
    signals.stop_merchant_detector.connect(stop_merchant_detector)

def start_merchant_detector(mode=""):
    global merchant_detector_running
    if mode != "OCR":
        return
    if merchant_detector_running:
        return

    try:
        _ensure_ocr_backend()
    except Exception as exc:
        if signals:
            signals.log_message.emit(f"[ERROR] Merchant detector could not start: {exc}")
        return

    merchant_detector_running = True
    threading.Thread(target=merchant_detector_loop, daemon=True).start()

def stop_merchant_detector():
    global merchant_detector_running
    merchant_detector_running = False
