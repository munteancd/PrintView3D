# PyInstaller build recipe for PrintView3D.
# Build with:  pyinstaller --noconfirm --clean printview3d.spec
# (build_windows.bat does this for you)

import sys
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = (
    collect_submodules("pyvistaqt")
    + collect_submodules("vtkmodules.qt")
    + [
        "qtpy", "qtpy.QtCore", "qtpy.QtGui", "qtpy.QtWidgets",
        "vtkmodules.util.numpy_support",
    ]
)

a = Analysis(
    ["src/printview3d/__main__.py"],
    pathex=["src"],
    datas=[("src/printview3d/resources", "printview3d/resources")],
    hiddenimports=hiddenimports,
    excludes=[
        # Not needed and large; keeps the build smaller.
        "PyQt5", "PyQt6", "PySide2", "tkinter", "IPython", "jupyter", "trame",
        "pytest", "scipy", "pandas", "cv2", "imageio", "imageio_ffmpeg", "cryptography",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore",
        "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtMultimedia", "PySide6.QtPdf",
        "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtBluetooth",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PrintView3D",
    icon="src/printview3d/resources/icon.ico",
    console=False,
    upx=False,
    version="version_info.txt" if sys.platform == "win32" else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="PrintView3D", upx=False)
