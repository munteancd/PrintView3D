"""File associations: "Open with" and default app for .stl / .3mf / .gcode.

The work is done per platform:
  Windows -> assoc_windows (registry, current user only; Windows asks the
             user to confirm the default app in Settings)
  Linux   -> assoc_linux   (freedesktop menu entry + MIME types; the default
             can be set directly)
Other systems report is_supported() == False and the Settings page says so.
"""

from __future__ import annotations

import sys

EXTENSIONS = {
    ".stl": "STL 3D Model",
    ".3mf": "3MF 3D Project",
    ".gcode": "G-code Print File",
    ".gco": "G-code Print File",
}
# Also registered, but only under "Open with" (never made the default automatically):
# people usually have a 3D editor for these.
OPEN_WITH_EXTENSIONS = (".obj", ".ply", ".off", ".glb", ".gltf", ".step", ".stp")

if sys.platform == "win32":
    from . import assoc_windows as _impl
elif sys.platform.startswith("linux"):
    from . import assoc_linux as _impl
else:
    _impl = None


def is_supported() -> bool:
    return _impl is not None


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def needs_confirmation() -> bool:
    """True when the OS makes the user confirm the default app themselves (Windows)."""
    return sys.platform == "win32"


def register() -> None:
    _impl.register()


def make_default() -> None:
    """Register and make PrintView3D the default app.

    On Windows this opens the Settings page where the user confirms it.
    On Linux the default is set directly.
    """
    _impl.register()
    if sys.platform == "win32":
        _impl.open_default_apps_settings()
    else:
        _impl.set_default()


def unregister() -> None:
    if _impl is not None:
        _impl.unregister()


def is_registered() -> bool:
    return _impl.is_registered() if _impl is not None else False


def registered_command() -> str:
    return _impl.registered_command() if _impl is not None else ""


def this_program() -> str:
    """Path of the running program, as it appears in the registered command."""
    if sys.platform.startswith("linux"):
        return _impl.program_path()
    return sys.executable


def status() -> dict[str, str]:
    if _impl is None:
        return {ext: "Not available on this system" for ext in EXTENSIONS}
    st = _impl.status()
    return {ext: st.get(ext, "-") for ext in EXTENSIONS}
