"""Windows file associations (per-user, no admin rights needed). Used via file_assoc.

register()   - adds PrintView3D to "Open with" for .stl/.3mf/.gcode and
               lists it under Settings > Apps > Default apps.
open_default_apps_settings() - opens that Settings page so the user can
               confirm PrintView3D as the default (Windows 10/11 require
               the user to confirm this themselves).
unregister() - removes everything register() added.

Everything is written under HKEY_CURRENT_USER, so it only affects the
current Windows user and is fully reversible.
"""

from __future__ import annotations

import os
import subprocess
import sys

from . import APP_ID, APP_NAME

EXTENSIONS = {
    ".stl": "STL 3D Model",
    ".3mf": "3MF 3D Project",
    ".gcode": "G-code Print File",
    ".gco": "G-code Print File",
    ".obj": "OBJ 3D Model",
    ".ply": "PLY 3D Model",
    ".off": "OFF 3D Model",
    ".glb": "glTF 3D Model",
    ".gltf": "glTF 3D Model",
    ".step": "STEP CAD Model",
    ".stp": "STEP CAD Model",
}

CAPS_KEY = rf"Software\{APP_ID}\Capabilities"


def is_supported() -> bool:
    return sys.platform == "win32"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def open_command() -> str:
    """Command Windows runs when a file is opened with this app."""
    if is_frozen():
        return f'"{sys.executable}" "%1"'
    # Development mode: run through pythonw so no console window appears.
    py = sys.executable
    pyw = os.path.join(os.path.dirname(py), "pythonw.exe")
    if os.path.isfile(pyw):
        py = pyw
    src = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return f'"{py}" -c "import sys; sys.path.insert(0, r\'{src}\'); from printview3d.app import main; main()" "%1"'


def icon_path() -> str:
    if is_frozen():
        return f'"{sys.executable}",0'
    ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "icon.ico")
    return f'"{ico}",0'


def _prog_id(ext: str) -> str:
    return f"{APP_ID}{ext}"            # e.g. PrintView3D.stl


def register() -> None:
    import winreg

    cmd = open_command()
    icon = icon_path()
    exe_name = os.path.basename(sys.executable) if is_frozen() else f"{APP_ID}.exe"

    def setval(root, path, name, value, kind=winreg.REG_SZ):
        with winreg.CreateKeyEx(root, path, 0, winreg.KEY_WRITE) as k:
            winreg.SetValueEx(k, name, 0, kind, value)

    hkcu = winreg.HKEY_CURRENT_USER
    for ext, desc in EXTENSIONS.items():
        pid = _prog_id(ext)
        base = rf"Software\Classes\{pid}"
        setval(hkcu, base, "", f"{desc} ({APP_NAME})")
        setval(hkcu, base + r"\DefaultIcon", "", icon)
        setval(hkcu, base + r"\shell\open", "FriendlyAppName", APP_NAME)
        setval(hkcu, base + r"\shell\open\command", "", cmd)
        # Show in the "Open with" list for this extension
        setval(hkcu, rf"Software\Classes\{ext}\OpenWithProgids", pid, b"", winreg.REG_NONE)
        # Registered-application capabilities (for Settings > Default apps)
        setval(hkcu, CAPS_KEY + r"\FileAssociations", ext, pid)

    setval(hkcu, CAPS_KEY, "ApplicationName", APP_NAME)
    setval(hkcu, CAPS_KEY, "ApplicationDescription", "Viewer for 3D models and G-code files")
    setval(hkcu, r"Software\RegisteredApplications", APP_ID, CAPS_KEY)

    app_key = rf"Software\Classes\Applications\{exe_name}"
    setval(hkcu, app_key, "FriendlyAppName", APP_NAME)
    setval(hkcu, app_key + r"\shell\open\command", "", cmd)
    for ext in EXTENSIONS:
        setval(hkcu, app_key + r"\SupportedTypes", ext, "")

    _notify_shell()


def _delete_tree(root, path: str) -> None:
    import winreg
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_ALL_ACCESS) as k:
            while True:
                try:
                    sub = winreg.EnumKey(k, 0)
                except OSError:
                    break
                _delete_tree(root, path + "\\" + sub)
        winreg.DeleteKey(root, path)
    except FileNotFoundError:
        pass
    except OSError:
        pass


def _delete_value(root, path: str, name: str) -> None:
    import winreg
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, name)
    except OSError:
        pass


def unregister() -> None:
    import winreg
    hkcu = winreg.HKEY_CURRENT_USER
    for ext in EXTENSIONS:
        _delete_tree(hkcu, rf"Software\Classes\{_prog_id(ext)}")
        _delete_value(hkcu, rf"Software\Classes\{ext}\OpenWithProgids", _prog_id(ext))
    _delete_value(hkcu, r"Software\RegisteredApplications", APP_ID)
    _delete_tree(hkcu, rf"Software\{APP_ID}")
    exe_name = os.path.basename(sys.executable) if is_frozen() else f"{APP_ID}.exe"
    _delete_tree(hkcu, rf"Software\Classes\Applications\{exe_name}")
    _notify_shell()


def is_registered() -> bool:
    if not is_supported():
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\RegisteredApplications") as k:
            winreg.QueryValueEx(k, APP_ID)
        return True
    except OSError:
        return False


def registered_command() -> str:
    """The open command currently stored in the registry ('' if none)."""
    if not is_supported():
        return ""
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            rf"Software\Classes\{_prog_id('.stl')}\shell\open\command") as k:
            return str(winreg.QueryValueEx(k, "")[0])
    except OSError:
        return ""


def current_default(ext: str) -> str:
    """ProgId Windows currently uses for this extension ('' if unknown)."""
    if not is_supported():
        return ""
    import winreg
    path = rf"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\{ext}\UserChoice"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as k:
            return str(winreg.QueryValueEx(k, "ProgId")[0])
    except OSError:
        return ""


def is_default(ext: str) -> bool:
    return current_default(ext).lower() == _prog_id(ext).lower()


def status() -> dict[str, str]:
    """Human-readable status per extension."""
    reg = is_registered()
    out = {}
    for ext in EXTENSIONS:
        if is_default(ext):
            out[ext] = "Default app"
        elif reg:
            out[ext] = "In \"Open with\" (not default)"
        else:
            out[ext] = "Not registered"
    return out


def open_default_apps_settings() -> None:
    """Open Windows Settings on PrintView3D's default-apps page."""
    for uri in (f"ms-settings:defaultapps?registeredAppUser={APP_ID}", "ms-settings:defaultapps"):
        try:
            os.startfile(uri)       # type: ignore[attr-defined]
            return
        except OSError:
            continue
    subprocess.Popen(["control", "/name", "Microsoft.DefaultPrograms"])


def _notify_shell() -> None:
    try:
        import ctypes
        SHCNE_ASSOCCHANGED = 0x08000000
        ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, 0, None, None)  # type: ignore[attr-defined]
    except Exception:
        pass
