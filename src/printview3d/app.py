"""Application entry point.

Usage:
    PrintView3D.exe [file]                       open a file (double-click passes it here)
    PrintView3D.exe file --screenshot out.png    render a file to an image and exit
    PrintView3D.exe --unregister                 remove file associations and exit
"""

from __future__ import annotations

import argparse
import os
import sys

os.environ.setdefault("QT_API", "pyside6")   # pyvistaqt/qtpy: use PySide6


def _set_windows_app_id():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PrintView3D.Viewer")  # type: ignore[attr-defined]
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="PrintView3D", add_help=True)
    parser.add_argument("file", nargs="?", help="STL, 3MF or G-code file to open")
    parser.add_argument("--screenshot", metavar="PNG", help="render FILE to an image and exit")
    parser.add_argument("--layer", type=int, help="with --screenshot: G-code layer to show (1-based)")
    parser.add_argument("--view", default="iso", choices=["iso", "top", "front", "right"],
                        help="with --screenshot: camera view")
    parser.add_argument("--unregister", action="store_true",
                        help="remove file associations (used by the uninstaller) and exit")
    args, _unknown = parser.parse_known_args(argv if argv is not None else sys.argv[1:])

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
    from .ui.theme import apply_dark_theme

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    apply_dark_theme(app)

    win = MainWindow()

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
    if args.file:
        QTimer.singleShot(50, lambda: win.load(args.file))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
