"""Dark Fusion theme shared by all windows."""

from PySide6.QtGui import QColor, QPalette

ACCENT = "#2fa4a0"
ACCENT_HOVER = "#38bbb6"


def apply_dark_theme(app):
    app.setStyle("Fusion")
    pal = QPalette()
    c = QColor
    pal.setColor(QPalette.Window, c("#1f2328"))
    pal.setColor(QPalette.WindowText, c("#e6e8eb"))
    pal.setColor(QPalette.Base, c("#171a1e"))
    pal.setColor(QPalette.AlternateBase, c("#23272d"))
    pal.setColor(QPalette.ToolTipBase, c("#2b3038"))
    pal.setColor(QPalette.ToolTipText, c("#e6e8eb"))
    pal.setColor(QPalette.Text, c("#e6e8eb"))
    pal.setColor(QPalette.Button, c("#2a2f36"))
    pal.setColor(QPalette.ButtonText, c("#e6e8eb"))
    pal.setColor(QPalette.BrightText, c("#ffffff"))
    pal.setColor(QPalette.Highlight, c(ACCENT))
    pal.setColor(QPalette.HighlightedText, c("#ffffff"))
    pal.setColor(QPalette.Link, c(ACCENT_HOVER))
    pal.setColor(QPalette.PlaceholderText, c("#8a919a"))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, c("#6b727b"))
    app.setPalette(pal)
    app.setStyleSheet(f"""
        QToolBar {{ background: #1a1d21; border: none; border-bottom: 1px solid #2d323a; spacing: 4px; padding: 4px; }}
        QToolButton {{ padding: 5px 9px; border-radius: 5px; color: #e6e8eb; }}
        QToolButton:hover {{ background: #2d333b; }}
        QToolButton:checked {{ background: #343b45; }}
        QToolButton#slicerButton {{ background: {ACCENT}; color: white; font-weight: 600; padding: 6px 14px; }}
        QToolButton#slicerButton:hover {{ background: {ACCENT_HOVER}; }}
        QToolButton#slicerButton[popupMode="1"] {{ padding-right: 28px; }}
        QToolButton#slicerButton::menu-button {{ width: 22px; border-left: 1px solid rgba(255,255,255,0.35);
            border-top-right-radius: 5px; border-bottom-right-radius: 5px; }}
        QGroupBox {{ border: 1px solid #2f343c; border-radius: 6px; margin-top: 14px; padding: 8px 8px 6px 8px; font-weight: 600; }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #aab1ba; }}
        QLabel#fileName {{ font-size: 15px; font-weight: 600; }}
        QLabel#muted, QLabel#formKey {{ color: #9aa1aa; }}
        QPushButton {{ padding: 5px 12px; border-radius: 5px; background: #2d333b; border: 1px solid #3a414b; }}
        QPushButton:hover {{ background: #353c46; }}
        QPushButton#primary {{ background: {ACCENT}; border: none; color: white; font-weight: 600; }}
        QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
        QScrollArea {{ border: none; }}
        QSlider::groove:horizontal {{ height: 6px; background: #2d333b; border-radius: 3px; }}
        QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 3px; }}
        QSlider::handle:horizontal {{ background: #e6e8eb; width: 16px; margin: -6px 0; border-radius: 8px; }}
        QStatusBar {{ background: #1a1d21; color: #aab1ba; }}
        QListWidget {{ border: 1px solid #2f343c; border-radius: 6px; }}
    """)
