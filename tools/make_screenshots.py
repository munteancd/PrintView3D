"""Regenerate the README screenshots in docs/ from the demo files.

Run (needs a display; on Linux CI use xvfb-run):
    python tools/make_demo.py
    python tools/make_screenshots.py
"""

from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.environ.setdefault("QT_API", "pyside6")

from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

DOCS = os.path.join(ROOT, "docs")
EX = os.path.join(ROOT, "examples")


def main():
    app = QApplication([])
    from printview3d.settings import Settings
    from printview3d.ui.main_window import MainWindow
    from printview3d.ui.settings_dialog import SettingsDialog
    from printview3d.ui.theme import apply_dark_theme
    import make_demo

    apply_dark_theme(app)
    import subprocess
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "i18n.py"), "compile"], check=True)
    tmp = tempfile.mkdtemp()
    # Stand-in slicer programs so the slicer menu has something to show.
    bindir = os.path.join(tmp, "bin")
    os.makedirs(bindir)
    for exe in ("CrealityPrint", "orca-slicer", "bambu-studio"):
        p = os.path.join(bindir, exe + (".exe" if sys.platform == "win32" else ""))
        with open(p, "w") as f:
            f.write("")
        os.chmod(p, 0o755)
    os.environ["PATH"] = bindir + os.pathsep + os.environ.get("PATH", "")
    settings = Settings(os.path.join(tmp, "settings.json"))
    settings.set("slicer_id", "creality_print")
    w = MainWindow(settings)
    w.resize(1440, 900)
    w.move(0, 0)
    w.show()
    app.processEvents()

    def shot(name, widget=None):
        w.statusBar().clearMessage()
        app.processEvents()
        w.plotter.render()
        app.processEvents()
        (widget or w).grab().save(os.path.join(DOCS, name))
        print("saved", name)

    def camera(azim, elev, zoom=1.0):
        w.scene.set_view("iso")
        cam = w.plotter.camera
        cam.Azimuth(azim)
        cam.Elevation(elev)
        cam.OrthogonalizeViewUp()
        w.plotter.reset_camera(bounds=w.scene.focus_bounds)
        cam.Zoom(zoom)
        w.plotter.reset_camera_clipping_range()

    os.makedirs(DOCS, exist_ok=True)

    # 1) STL model view + a thumbnail for the demo G-code / 3MF
    w.load_sync(os.path.join(EX, "demo_vase.stl"))
    camera(-25, -5, 1.15)
    shot("screenshot-model.png")
    img = w.plotter.screenshot(None, return_img=True)
    from PIL import Image
    im = Image.fromarray(img)
    h = im.height
    cx = im.width // 2
    im = im.crop((cx - h // 2, 0, cx + h // 2, h)).resize((300, 300))
    import io
    bio = io.BytesIO()
    im.save(bio, "PNG")
    make_demo.main(bio.getvalue())

    # 2) G-code, cut at 60 % height
    w.load_sync(os.path.join(EX, "demo_vase.gcode"))
    w.set_layer(int(w.gcode.n_layers * 0.6))
    w._redraw_gcode()
    camera(-20, -8, 1.25)
    shot("screenshot-gcode.png")

    # 3) Single layer from the top
    w.set_layer(int(w.gcode.n_layers * 0.35))
    w.only_layer_cb.setChecked(True)
    w._redraw_gcode()
    w.scene.set_view("top")
    w.plotter.camera.Zoom(1.6)
    shot("screenshot-layer.png")
    w.only_layer_cb.setChecked(False)

    # 4) 3MF plate with several objects
    w.load_sync(os.path.join(EX, "demo_plate.3mf"))
    camera(-15, -10, 1.1)
    shot("screenshot-3mf.png")

    # 5) Slicer menu (the arrow on the button)
    w._fill_slicer_menu()
    pos = w.slicer_btn.mapToGlobal(QPoint(0, w.slicer_btn.height()))
    w.slicer_menu.popup(pos)
    for _ in range(5):
        app.processEvents()
    screen = app.primaryScreen().grabWindow(0)
    r = w.slicer_menu.geometry()
    b = w.slicer_btn.mapToGlobal(QPoint(0, 0))
    left, top = max(0, b.x() - 160), max(0, b.y() - 8)
    screen.copy(left, top, max(r.right(), b.x() + w.slicer_btn.width()) - left + 180,
                r.bottom() - top + 16).save(os.path.join(DOCS, "screenshot-slicer-menu.png"))
    print("saved screenshot-slicer-menu.png")
    w.slicer_menu.close()

    # 6) Settings
    d = SettingsDialog(settings, w, {"GPU": "(your graphics card)"})
    d.show()
    for _ in range(5):
        app.processEvents()
    d.grab().save(os.path.join(DOCS, "screenshot-settings.png"))
    print("saved screenshot-settings.png")
    d.close()

    # 7) Arabic (right-to-left) for the Translations section
    from printview3d import i18n
    i18n.apply_language(app, "ar")
    for _ in range(5):
        app.processEvents()
    w.load_sync(os.path.join(EX, "demo_vase.gcode"))
    w.set_layer(int(w.gcode.n_layers * 0.6))
    w._redraw_gcode()
    camera(-20, -8, 1.25)
    shot("screenshot-arabic.png")
    i18n.apply_language(app, "en")
    w.close()


if __name__ == "__main__":
    main()
