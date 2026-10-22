"""CI only (temporary, for the Mica fix): open PrintView3D like app.py does and take a real
screenshot of the desktop, so the Mica backdrop Windows draws can be seen.

    python tools/ci_mica_shots.py OUT.png --theme dark --mica 1 [--settings]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--theme", default="dark")
    ap.add_argument("--mica", type=int, default=1)
    ap.add_argument("--settings", action="store_true")
    ap.add_argument("--switch-to", default="")
    a = ap.parse_args()

    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    from printview3d.ui import theme
    from printview3d.ui.main_window import MainWindow
    from printview3d.settings import Settings
    from printview3d import win_mica

    app = QApplication(sys.argv[:1])
    settings = Settings()
    settings.set("theme", a.theme)
    settings.set("mica", bool(a.mica))
    theme.apply_theme(app, a.theme)
    win = MainWindow(settings)
    use = bool(a.mica) and win_mica.supported()
    if use:
        win.prepare_mica()
    win.resize(1100, 720)
    win.move(120, 80)
    win.show()
    ok = win.enable_mica() if use else False
    win.load_sync(os.path.join(os.path.dirname(__file__), "..", "examples", "demo_plate.3mf"))
    win.raise_()
    win.activateWindow()
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.SetForegroundWindow(int(win.winId()))
    info = {"supported": win_mica.supported(), "applied": ok, "theme": a.theme}

    def open_settings():
        if a.settings:
            from printview3d.ui.settings_dialog import SettingsDialog
            from printview3d.gpu import renderer_info
            win._dlg = SettingsDialog(settings, win, renderer_info(win.plotter))
            win._dlg.move(420, 240)
            win._dlg.show()
            win._dlg.raise_()
            win._dlg.activateWindow()

    def shoot():
        app.processEvents()
        pix = app.primaryScreen().grabWindow(0)
        pix.save(a.out)
        with open(a.out + ".json", "w", encoding="utf-8") as f:
            json.dump(info, f)
        app.quit()

    if a.switch_to:
        QTimer.singleShot(2500, lambda: win.choose_theme(a.switch_to))
    QTimer.singleShot(3000, open_settings)
    QTimer.singleShot(9000, shoot)
    app.exec()
    return 0


if __name__ == "__main__":
    sys.exit(main())
