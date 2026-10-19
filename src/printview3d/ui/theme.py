"""Colour themes: Automatic (follows the system), Dark, Gray, Graphite and Light.

A theme sets the colours of the window (Qt palette + style sheet) and of the
3D view (background, build plate, grid). The colours of G-code features and
models never change, so they always mean the same thing as in the slicer;
the 3D backgrounds are chosen so every feature colour stays visible.

Switching is immediate: apply_theme() restyles every window, and the main
window recolours the 3D view (MainWindow.apply_theme).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPainterPath, QPalette, QPen, QPixmap

from ..i18n import tr_noop

ACCENT = "#2fa4a0"
ACCENT_HOVER = "#38bbb6"

# Setting value -> name shown in Settings.
THEME_NAMES = {
    "auto": tr_noop("Automatic (system theme)"),
    "dark": tr_noop("Dark"),
    "gray": tr_noop("Gray"),
    "graphite": tr_noop("Graphite"),
    "light": tr_noop("Light"),
}
# Order used by Ctrl+T (next theme).
CYCLE = ["dark", "gray", "graphite", "light"]

THEMES: dict[str, dict[str, str]] = {
    "dark": {
        # window
        "window": "#1f2328", "base": "#171a1e", "alt": "#23272d", "text": "#e6e8eb",
        "button": "#2a2f36", "button_hover": "#353c46", "button_border": "#3a414b",
        "tool_hover": "#2d333b", "tool_checked": "#343b45",
        "bar": "#1a1d21", "bar_border": "#2d323a", "border": "#2f343c",
        "muted": "#9aa1aa", "group_title": "#aab1ba", "disabled": "#6b727b",
        "placeholder": "#8a919a", "tooltip": "#2b3038",
        "groove": "#2d333b", "handle": "#e6e8eb", "handle_border": "#e6e8eb",
        "link": "#7cc7c4", "thumb": "#15181c",
        # 3D view
        "bg_bottom": "#16191d", "bg_top": "#2a2f37", "plate": "#22262c",
        "grid_minor": "#363b43", "grid_major": "#535a64", "plate_edge": "#7a828d",
        "axes_label": "#e6e8eb",
    },
    "gray": {
        "window": "#3b3e43", "base": "#33363a", "alt": "#404349", "text": "#eef0f2",
        "button": "#4a4e54", "button_hover": "#555a61", "button_border": "#5d626a",
        "tool_hover": "#4b4f56", "tool_checked": "#575c64",
        "bar": "#35383c", "bar_border": "#4a4e55", "border": "#52575e",
        "muted": "#b4b9bf", "group_title": "#c3c8cd", "disabled": "#80868d",
        "placeholder": "#a2a7ad", "tooltip": "#4a4e54",
        "groove": "#4f545b", "handle": "#eef0f2", "handle_border": "#eef0f2",
        "link": "#8fd6d2", "thumb": "#2f3236",
        "bg_bottom": "#45494f", "bg_top": "#6c727a", "plate": "#4f545a",
        "grid_minor": "#5f646b", "grid_major": "#7b8189", "plate_edge": "#a6acb3",
        "axes_label": "#eef0f2",
    },
    # Warm, dark coffee-brown charcoal: soft on the eyes in the evening.
    "graphite": {
        "window": "#2b2622", "base": "#231f1c", "alt": "#312b27", "text": "#ece6df",
        "button": "#3a332e", "button_hover": "#463e37", "button_border": "#5a4e44",
        "tool_hover": "#3d3530", "tool_checked": "#4a4039",
        "bar": "#26211e", "bar_border": "#3a332d", "border": "#40372f",
        "muted": "#b3a89c", "group_title": "#c2b6a9", "disabled": "#7d7268",
        "placeholder": "#9e9387", "tooltip": "#3a332e",
        "groove": "#40372f", "handle": "#ece6df", "handle_border": "#ece6df",
        "link": "#8fd6d2", "thumb": "#201c19",
        "bg_bottom": "#28221e", "bg_top": "#4d433b", "plate": "#3a322c",
        "grid_minor": "#4a4038", "grid_major": "#685b50", "plate_edge": "#9a8b7d",
        "axes_label": "#ece6df",
    },
    "light": {
        "window": "#f3f4f6", "base": "#ffffff", "alt": "#f0f1f3", "text": "#1f2328",
        "button": "#e8eaed", "button_hover": "#dde0e4", "button_border": "#c9cdd3",
        "tool_hover": "#e1e4e8", "tool_checked": "#d3d8de",
        "bar": "#e9ebee", "bar_border": "#d0d4d9", "border": "#d0d4d9",
        "muted": "#5d646d", "group_title": "#4a5059", "disabled": "#a0a6ad",
        "placeholder": "#868d96", "tooltip": "#ffffff",
        "groove": "#d0d4d9", "handle": "#ffffff", "handle_border": "#9aa1aa",
        "link": "#1f7f7b", "thumb": "#c4cad1",
        # Light-gray rather than white, so white and yellow toolpaths stay visible.
        "bg_bottom": "#c9ced5", "bg_top": "#eceef1", "plate": "#b3bac3",
        "grid_minor": "#a3abb5", "grid_major": "#858e99", "plate_edge": "#5b6470",
        "axes_label": "#1f2328",
    },
}

_setting = "auto"
_current = "dark"


def system_theme() -> str:
    """'dark' or 'light' from the operating system (Windows, GNOME, KDE, macOS)."""
    try:
        scheme = QGuiApplication.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Light:
            return "light"
        if scheme == Qt.ColorScheme.Dark:
            return "dark"
    except AttributeError:          # Qt older than 6.5
        pass
    return "dark"                   # unknown: keep the classic look


def resolve(setting: str) -> str:
    if setting in THEMES:
        return setting
    return system_theme()


def current() -> str:
    """The theme in use ('dark', 'gray' or 'light')."""
    return _current


def setting() -> str:
    return _setting


def colors(name: str | None = None) -> dict[str, str]:
    return THEMES[name or _current]


def apply_theme(app, choice: str = "auto") -> str:
    """Style the whole application. Returns the theme used."""
    global _setting, _current
    _setting = choice if choice in THEME_NAMES else "auto"
    _current = resolve(_setting)
    t = THEMES[_current]
    app.setStyle("Fusion")
    pal = QPalette()
    c = QColor
    pal.setColor(QPalette.Window, c(t["window"]))
    pal.setColor(QPalette.WindowText, c(t["text"]))
    pal.setColor(QPalette.Base, c(t["base"]))
    pal.setColor(QPalette.AlternateBase, c(t["alt"]))
    pal.setColor(QPalette.ToolTipBase, c(t["tooltip"]))
    pal.setColor(QPalette.ToolTipText, c(t["text"]))
    pal.setColor(QPalette.Text, c(t["text"]))
    pal.setColor(QPalette.Button, c(t["button"]))
    pal.setColor(QPalette.ButtonText, c(t["text"]))
    pal.setColor(QPalette.BrightText, c("#ffffff"))
    pal.setColor(QPalette.Highlight, c(ACCENT))
    pal.setColor(QPalette.HighlightedText, c("#ffffff"))
    pal.setColor(QPalette.Link, c(t["link"]))
    pal.setColor(QPalette.PlaceholderText, c(t["placeholder"]))
    # Fusion draws frames/shadows from these.
    pal.setColor(QPalette.Light, c(t["button_hover"]))
    pal.setColor(QPalette.Midlight, c(t["button"]))
    pal.setColor(QPalette.Mid, c(t["border"]))
    pal.setColor(QPalette.Dark, c(t["bar_border"]))
    pal.setColor(QPalette.Shadow, c("#000000" if _current != "light" else "#9aa1aa"))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, c(t["disabled"]))
    app.setPalette(pal)
    app.setStyleSheet(f"""
        QToolBar {{ background: {t['bar']}; border: none; border-bottom: 1px solid {t['bar_border']}; spacing: 4px; padding: 4px; }}
        QToolButton {{ padding: 5px 9px; border-radius: 5px; color: {t['text']}; }}
        QToolButton:hover {{ background: {t['tool_hover']}; }}
        QToolButton:checked {{ background: {t['tool_checked']}; }}
        QToolBar QToolButton {{ border: 1px solid {t['button_border']}; background: {t['button']};
            padding: 4px 10px; margin: 1px 2px; font-weight: 600; }}
        QToolBar QToolButton:hover {{ background: {t['button_hover']}; border-color: {t['muted']}; }}
        QToolBar QToolButton:checked {{ background: {t['tool_checked']}; border-color: {ACCENT}; }}
        QToolBar QToolButton#themeButton {{ padding: 4px 6px; }}
        QToolBar QToolButton#themeButton::menu-indicator {{ image: none; width: 0; }}
        QToolButton#slicerButton {{ background: {ACCENT}; color: white; font-weight: 600; padding: 6px 14px; }}
        QToolButton#slicerButton:hover {{ background: {ACCENT_HOVER}; }}
        QToolButton#slicerButton[popupMode="1"] {{ padding-right: 28px; }}
        QToolButton#slicerButton::menu-button {{ width: 22px; border-left: 1px solid rgba(255,255,255,0.35);
            border-top-right-radius: 5px; border-bottom-right-radius: 5px; }}
        QGroupBox {{ border: 1px solid {t['border']}; border-radius: 6px; margin-top: 14px; padding: 8px 8px 6px 8px; font-weight: 600; }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {t['group_title']}; }}
        QLabel#fileName {{ font-size: 15px; font-weight: 600; }}
        QLabel#muted, QLabel#formKey {{ color: {t['muted']}; }}
        QLabel#thumbnail {{ background: {t['thumb']}; border-radius: 6px; padding: 6px; }}
        QPushButton {{ padding: 5px 12px; border-radius: 5px; background: {t['button']}; border: 1px solid {t['button_border']}; }}
        QPushButton:hover {{ background: {t['button_hover']}; }}
        QPushButton#primary {{ background: {ACCENT}; border: none; color: white; font-weight: 600; }}
        QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
        QPushButton#link {{ color: {t['link']}; border: none; background: transparent; }}
        QPushButton#link:hover {{ text-decoration: underline; }}
        QScrollArea {{ border: none; }}
        QSlider::groove:horizontal {{ height: 6px; background: {t['groove']}; border-radius: 3px; }}
        QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 3px; }}
        QSlider::handle:horizontal {{ background: {t['handle']}; border: 1px solid {t['handle_border']};
            width: 14px; margin: -6px 0; border-radius: 8px; }}
        QStatusBar {{ background: {t['bar']}; color: {t['group_title']}; }}
        QListWidget {{ border: 1px solid {t['border']}; border-radius: 6px; }}
    """)
    return _current


def next_theme(name: str) -> str:
    """The theme after `name` for Ctrl+T."""
    i = CYCLE.index(name) if name in CYCLE else -1
    return CYCLE[(i + 1) % len(CYCLE)]


def theme_icon(name: str | None = None) -> QIcon:
    """Half-filled circle (the usual 'theme' symbol) in the theme's text colour."""
    size = 64                       # drawn large, Qt scales it down sharply
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    fg = QColor(colors(name)["text"])
    p.setPen(QPen(fg, 5))
    c, r = QPointF(size / 2, size / 2), 24
    p.drawEllipse(c, r, r)
    half = QPainterPath()
    half.moveTo(c)
    half.arcTo(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), 90, 180)
    p.fillPath(half, fg)
    p.end()
    return QIcon(pm)


def apply_dark_theme(app):
    """Kept for older scripts."""
    return apply_theme(app, "dark")
