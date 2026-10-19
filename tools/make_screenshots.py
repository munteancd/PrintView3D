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
    from printview3d.ui import theme
    import make_demo

    theme.apply_theme(app, "dark")
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
    for _ in range(5):
        app.processEvents()

    # 8) The same G-code in the Gray, Graphite and Light themes, plus a 2 x 2 overview
    w.load_sync(os.path.join(EX, "demo_vase.gcode"))
    w.set_layer(int(w.gcode.n_layers * 0.6))
    w._redraw_gcode()
    camera(-20, -8, 1.25)
    for name in ("gray", "graphite", "light"):
        w.apply_theme(name)
        for _ in range(5):
            app.processEvents()
        shot(f"screenshot-theme-{name}.png")
    w.apply_theme("dark")
    from PIL import Image
    tiles = [Image.open(os.path.join(DOCS, f)) for f in
             ("screenshot-gcode.png", "screenshot-theme-gray.png",
              "screenshot-theme-graphite.png", "screenshot-theme-light.png")]
    tw = 720
    tiles = [t.resize((tw, int(t.height * tw / t.width))) for t in tiles]
    th = tiles[0].height
    grid = Image.new("RGB", (tw * 2 + 10, th * 2 + 10), "#888888")
    for i, t in enumerate(tiles):
        grid.paste(t, ((i % 2) * (tw + 10), (i // 2) * (th + 10)))
    grid.save(os.path.join(DOCS, "screenshot-themes.png"))

    # 9) The theme menu (toolbar icon)
    w.theme_menu.popup(w.theme_btn.mapToGlobal(QPoint(0, w.theme_btn.height())))
    for _ in range(5):
        app.processEvents()
    r = w.theme_menu.geometry()
    b = w.theme_btn.mapToGlobal(QPoint(0, 0))
    screen = app.primaryScreen().grabWindow(0)
    left = max(0, r.left() - 420)
    right = max(r.right(), b.x() + w.theme_btn.width()) + 10
    screen.copy(left, max(0, b.y() - 8), right - left,
                r.bottom() - b.y() + 20).save(os.path.join(DOCS, "screenshot-theme-menu.png"))
    print("saved screenshot-theme-menu.png")
    w.theme_menu.close()
    print("saved screenshot-themes.png")
    w.close()


if __name__ == "__main__":
    main()
