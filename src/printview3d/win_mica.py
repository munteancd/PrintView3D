"""Windows 11 "Mica": the window background takes a soft tint of the desktop wallpaper.

Windows draws the effect itself (DWM, on the graphics card); PrintView3D only asks for it and
leaves the background of the toolbar, side panel and status bar transparent (see
ui.theme.apply_theme(..., mica=True)). The 3D view always stays solid.

Needs Windows 11 22H2 or newer (build 22621). Elsewhere supported() is False and nothing changes.
Windows turns Mica off by itself when "Transparency effects" is off in Windows Settings, in
battery saver, and while the window is not active (it then shows a plain colour).
"""

from __future__ import annotations

import sys

MIN_BUILD = 22621                     # Windows 11 22H2: DWMWA_SYSTEMBACKDROP_TYPE

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMSBT_MAINWINDOW = 2                 # Mica
DWMSBT_TRANSIENTWINDOW = 3            # Acrylic (blur of what lies behind the window)
DWMSBT_TABBEDWINDOW = 4               # Mica Alt (stronger wallpaper tint)
BACKDROPS = {"mica": DWMSBT_MAINWINDOW, "acrylic": DWMSBT_TRANSIENTWINDOW, "mica-alt": DWMSBT_TABBEDWINDOW}


def supported() -> bool:
    if sys.platform != "win32":
        return False
    try:
        return sys.getwindowsversion().build >= MIN_BUILD
    except Exception:  # noqa: BLE001
        return False


def _set_int(hwnd: int, attr: int, value: int) -> bool:
    import ctypes
    v = ctypes.c_int(value)
    return ctypes.windll.dwmapi.DwmSetWindowAttribute(
        ctypes.c_void_p(hwnd), ctypes.c_uint(attr), ctypes.byref(v), ctypes.sizeof(v)) == 0


def set_dark(hwnd: int, dark: bool) -> bool:
    """Dark or light Mica (and title bar), to match the theme."""
    if not supported():
        return False
    try:
        return _set_int(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 1 if dark else 0)
    except Exception:  # noqa: BLE001
        return False


def apply(hwnd: int, dark: bool, kind: str = "mica") -> bool:
    """Ask Windows for Mica (or kind: "mica-alt", "acrylic") behind the whole window.
    True when Windows accepted it."""
    if not supported():
        return False
    try:
        import ctypes

        class MARGINS(ctypes.Structure):
            _fields_ = [("l", ctypes.c_int), ("r", ctypes.c_int), ("t", ctypes.c_int), ("b", ctypes.c_int)]

        set_dark(hwnd, dark)
        # The "glass" frame covers the whole window, so the backdrop shows behind our content.
        ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(ctypes.c_void_p(hwnd), ctypes.byref(MARGINS(-1, -1, -1, -1)))
        return _set_int(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, BACKDROPS.get(kind, DWMSBT_MAINWINDOW))
    except Exception:  # noqa: BLE001 - never let a visual effect break the program
        return False


def backdrop(hwnd: int) -> int:
    """The backdrop type Windows reports for the window (for the CI self-test); -1 if unknown."""
    try:
        import ctypes
        v = ctypes.c_int(-1)
        ok = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            ctypes.c_void_p(hwnd), ctypes.c_uint(DWMWA_SYSTEMBACKDROP_TYPE), ctypes.byref(v), ctypes.sizeof(v)) == 0
        return v.value if ok else -1
    except Exception:  # noqa: BLE001
        return -1
