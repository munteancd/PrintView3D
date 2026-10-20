"""Application entry point.

Usage:
    PrintView3D.exe [file]                       open a file (double-click passes it here)
    PrintView3D.exe file --screenshot out.png    render a file to an image and exit
    PrintView3D.exe file --send-to-slicer [ID]   open file in the default (or given) slicer and exit
    PrintView3D.exe --lang ar                    start in a given language (en, ar, nl, de, fr, es)
    PrintView3D.exe --theme light                start with a colour theme (auto, dark, gray, graphite, light)
    PrintView3D.exe --register                   add to "Open with" / applications menu and exit
    PrintView3D.exe --unregister                 remove file associations and exit
"""

from __future__ import annotations

import argparse
import os
import sys

os.environ.setdefault("QT_API", "pyside6")   # pyvistaqt/qtpy: use PySide6

# Linux: the VTK 3D view does not work in native Wayland windows, so use
# X11 (XWayland, available on all mainstream Wayland desktops) unless the
# user explicitly chose a Qt platform.
if sys.platform.startswith("linux") and os.environ.get("WAYLAND_DISPLAY") \
        and "QT_QPA_PLATFORM" not in os.environ:
    os.environ["QT_QPA_PLATFORM"] = "xcb"
    os.environ["PRINTVIEW3D_SET_QPA"] = "1"      # so slicers we start don't inherit it


def _set_windows_app_id():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PrintView3D.Viewer")  # type: ignore[attr-defined]
        except Exception:
            pass


def _FileOpener(app, win):
    from PySide6.QtCore import QEvent, QObject

    class FileOpener(QObject):
        def eventFilter(self, obj, ev):
            if ev.type() == QEvent.FileOpen and ev.file():
                win.load(ev.file())
                return True
            return False

    return FileOpener(app)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="PrintView3D", add_help=True)
    parser.add_argument("file", nargs="?", help="STL, 3MF or G-code file to open")
    parser.add_argument("--screenshot", metavar="PNG", help="render FILE to an image and exit")
    parser.add_argument("--layer", type=int, help="with --screenshot: G-code layer to show (1-based)")
    parser.add_argument("--view", default="iso", choices=["iso", "top", "front", "right"],
                        help="with --screenshot: camera view")
    parser.add_argument("--unregister", action="store_true",
                        help="remove file associations (used by the uninstaller) and exit")
    parser.add_argument("--send-to-slicer", nargs="?", const="", metavar="SLICER_ID",
                        help="open FILE in the default slicer (or the given one, e.g. orcaslicer) and exit")
    parser.add_argument("--lang", metavar="CODE",
                        help="show the interface in this language for this run (en, ar, nl, de, fr, es)")
    parser.add_argument("--theme", choices=["auto", "dark", "gray", "graphite", "light"],
                        help="colour theme for this run")
    parser.add_argument("--register", action="store_true",
                        help='add PrintView3D to "Open with" (and the Linux applications menu) and exit')
    args, _unknown = parser.parse_known_args(argv if argv is not None else sys.argv[1:])

    if args.send_to_slicer is not None:
        from . import slicer as sl
        from .settings import Settings
        settings = Settings()
        sl.migrate_settings(settings)
        sid, name, exe = sl.resolve(settings, args.send_to_slicer or None)
        if not exe:
            print(f"{name} was not found. Choose it in Settings.", file=sys.stderr)
            return 1
        from .loaders import SEND_AS_STL, file_kind, load_file
        if args.file and file_kind(args.file) in SEND_AS_STL:   # slicers don't all read these: send STL
            from . import freecad as fc
            model = load_file(args.file, None, settings.get("freecad_path", ""))
            if not model.parts:
                print("Nothing to send (a FreeCAD file needs FreeCAD to convert it).", file=sys.stderr)
                return 1
            base = os.path.splitext(os.path.basename(args.file))[0]
            args.file = fc.export_stl(model.parts, os.path.join(os.path.dirname(fc.cache_dir()), "to-slicer",
                                                                base + ".stl"))
        sl.open_in_slicer(exe, args.file)
        print(f"Opening {args.file or name} in {name}")
        return 0

    if args.register:
        from . import file_assoc
        if file_assoc.is_supported():
            file_assoc.register()
            print("Registered PrintView3D.")
        return 0

    if args.unregister:
        from . import file_assoc
        if file_assoc.is_supported():
            file_assoc.unregister()
        return 0

    _set_windows_app_id()

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from . import APP_NAME
    from .ui.main_window import MainWindow
    from .ui import theme

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setDesktopFileName("printview3d")        # Linux: match the menu entry / taskbar icon
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)

    # Language must be set before the window is built.
    from . import i18n
    from .settings import Settings
    settings = Settings()
    i18n.apply_language(app, args.lang or settings.get("language", "en"))
    theme.apply_theme(app, args.theme or settings.get("theme", "auto"))

    win = MainWindow(settings)

    if args.screenshot:
        if not args.file:
            print("--screenshot needs a file", file=sys.stderr)
            return 2
        win.resize(1280, 800)
        win.show()
        app.processEvents()
        win.load_sync(args.file)
        if args.layer is not None and win.gcode is not None:
            win.set_layer(args.layer - 1)
            win._redraw_gcode()
        win.set_view(args.view)
        app.processEvents()
        win.plotter.render()
        app.processEvents()
        win.grab().save(args.screenshot)
        print(f"Saved {args.screenshot}")
        win.close()
        return 0

    win.show()
    win.start_update_checks()
    # macOS: files opened from Finder (double-click, Open With, drop on the Dock icon)
    # arrive as a FileOpen event, not on the command line.
    app.installEventFilter(_FileOpener(app, win))
    if args.file:
        QTimer.singleShot(50, lambda: win.load(args.file))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
