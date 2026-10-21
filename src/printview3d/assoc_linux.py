"""Linux desktop integration (per-user, no root needed). Used via file_assoc.

register()     - adds a PrintView3D menu entry, teaches the desktop the
                 .stl / .3mf / .gcode file types, and puts PrintView3D in
                 "Open With" for them.
set_default()  - makes PrintView3D the default app for those types
                 (Linux allows this directly; no confirmation step).
unregister()   - removes everything above, including the default choice.

Everything follows the freedesktop.org standards that GNOME, KDE, Xfce,
Cinnamon and others use, and lives in the user's home folder:
  ~/.local/share/applications/printview3d.desktop
  ~/.local/share/mime/packages/printview3d.xml
  ~/.local/share/icons/hicolor/256x256/apps/printview3d.png
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

from . import APP_NAME

DESKTOP_ID = "printview3d.desktop"

# Our own MIME definitions, so the file types are known even on systems whose
# shared-mime-info database is old. Existing definitions are merged, not replaced.
MIME_TYPES = {
    "model/stl": ("STL 3D model", ["*.stl"]),
    "model/3mf": ("3MF 3D project", ["*.3mf"]),
    "text/x.gcode": ("G-code print file", ["*.gcode", "*.gco"]),
}
# Older/alternative names used by some distributions; listed so "Open With" works there too.
EXTRA_MIME_TYPES = ["application/sla", "model/x.stl-binary", "model/x.stl-ascii",
                    "application/vnd.ms-3mfdocument", "text/x-gcode"]
# General 3D formats: PrintView3D is offered under "Open With", but "Set as default" leaves
# them alone (people usually have a 3D editor for these). OBJ and glTF are known to
# shared-mime-info; PLY, OFF and STEP are not, so we define those ourselves.
OPEN_WITH_MIME_TYPES = {
    "model/x.ply": ("PLY 3D model", ["*.ply"]),
    "model/x.off": ("OFF 3D model", ["*.off"]),
    "model/step": ("STEP CAD model", ["*.step", "*.stp"]),
}
OPEN_WITH_EXTRA = ["model/obj", "model/gltf-binary", "model/gltf+json", "application/step",
                   "application/x-step"]
EXT_TO_MIME = {".stl": "model/stl", ".3mf": "model/3mf", ".gcode": "text/x.gcode", ".gco": "text/x.gcode"}


def _data_home() -> str:
    return os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")


def _config_home() -> str:
    return os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")


def desktop_path() -> str:
    return os.path.join(_data_home(), "applications", DESKTOP_ID)


def mime_package_path() -> str:
    return os.path.join(_data_home(), "mime", "packages", "printview3d.xml")


def icon_install_path() -> str:
    return os.path.join(_data_home(), "icons", "hicolor", "256x256", "apps", "printview3d.png")


def is_supported() -> bool:
    return sys.platform.startswith("linux")


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def program_path() -> str:
    """The file a menu entry should start.

    Inside an AppImage, sys.executable points into a temporary mount that
    disappears when the app closes; the AppImage itself is in $APPIMAGE.
    """
    if os.environ.get("APPIMAGE"):
        return os.environ["APPIMAGE"]
    return sys.executable


def exec_line() -> str:
    def q(x):
        return '"' + x.replace('"', '\\"') + '"'

    if is_frozen() or os.environ.get("APPIMAGE"):
        return f"{q(program_path())} %f"
    src = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return f"env PYTHONPATH={q(src)} {q(sys.executable)} -m printview3d %f"


def _run(*args) -> str:
    """Run a desktop helper tool if it is installed; never fail if it is not."""
    if not shutil.which(args[0]):
        return ""
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=20).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def desktop_entry() -> str:
    mimes = ";".join(list(MIME_TYPES) + EXTRA_MIME_TYPES + list(OPEN_WITH_MIME_TYPES) + OPEN_WITH_EXTRA) + ";"
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        "GenericName=3D File Viewer\n"
        "Comment=View 3D models and G-code files and open them in your slicer\n"
        f"Exec={exec_line()}\n"
        "Icon=printview3d\n"
        "Terminal=false\n"
        "Categories=Graphics;3DGraphics;Viewer;Engineering;\n"
        "Keywords=3D;print;STL;3MF;OBJ;PLY;glTF;GLB;G-code;gcode;slicer;viewer;\n"
        f"MimeType={mimes}\n"
        "StartupWMClass=PrintView3D\n"
        # Ask the desktop to start us on the dedicated GPU on dual-GPU laptops.
        "PrefersNonDefaultGPU=true\n"
        "X-KDE-RunOnDiscreteGpu=true\n"
    )


def mime_package() -> str:
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">']
    for mime, (comment, globs) in {**MIME_TYPES, **OPEN_WITH_MIME_TYPES}.items():
        parts.append(f'  <mime-type type="{mime}">')
        parts.append(f"    <comment>{comment}</comment>")
        if mime.startswith("text/"):
            parts.append('    <sub-class-of type="text/plain"/>')
        for g in globs:
            parts.append(f'    <glob pattern="{g}"/>')
        parts.append("  </mime-type>")
    parts.append("</mime-info>")
    return "\n".join(parts) + "\n"


def _icon_source() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "icon.png")


def register() -> None:
    """Menu entry + file types + "Open With". Safe to run again (updates paths)."""
    for path, content in ((desktop_path(), desktop_entry()), (mime_package_path(), mime_package())):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    os.chmod(desktop_path(), 0o755)
    os.makedirs(os.path.dirname(icon_install_path()), exist_ok=True)
    shutil.copyfile(_icon_source(), icon_install_path())
    _refresh_databases()


def set_default() -> None:
    """Make PrintView3D the default app for STL, 3MF and G-code."""
    if not shutil.which("xdg-mime"):
        _write_mimeapps_defaults()      # fall back to editing mimeapps.list ourselves
        return
    _run("xdg-mime", "default", DESKTOP_ID, *MIME_TYPES, *EXTRA_MIME_TYPES)


def _mimeapps_files() -> list[str]:
    return [os.path.join(_config_home(), "mimeapps.list"),
            os.path.join(_data_home(), "applications", "mimeapps.list")]


def _write_mimeapps_defaults() -> None:
    path = _mimeapps_files()[0]
    lines = []
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        pass
    wanted = {m: DESKTOP_ID for m in list(MIME_TYPES) + EXTRA_MIME_TYPES}
    out, section, done = [], "", set()
    for line in lines:
        s = line.strip()
        if s.startswith("["):
            if section == "[Default Applications]":
                out.extend(f"{m}={d}" for m, d in wanted.items() if m not in done)
                done.update(wanted)
            section = s
        elif section == "[Default Applications]" and "=" in s and s.split("=", 1)[0] in wanted:
            m = s.split("=", 1)[0]
            out.append(f"{m}={wanted[m]}")
            done.add(m)
            continue
        out.append(line)
    if section == "[Default Applications]":
        out.extend(f"{m}={d}" for m, d in wanted.items() if m not in done)
        done.update(wanted)
    if len(done) < len(wanted):
        out += ["", "[Default Applications]"] + [f"{m}={d}" for m, d in wanted.items()]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out).strip("\n") + "\n")


def _remove_from_mimeapps() -> None:
    """Drop PrintView3D from every default / added-association line."""
    for path in _mimeapps_files():
        try:
            with open(path, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except OSError:
            continue
        out = []
        for line in lines:
            if "=" in line and not line.lstrip().startswith(("[", "#")):
                key, val = line.split("=", 1)
                apps = [a for a in val.split(";") if a and a != DESKTOP_ID]
                if not apps:
                    continue
                line = f"{key}={';'.join(apps)};"
            out.append(line)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")


def unregister() -> None:
    for p in (desktop_path(), mime_package_path(), icon_install_path()):
        try:
            os.remove(p)
        except OSError:
            pass
    _remove_from_mimeapps()
    _refresh_databases()


def _refresh_databases() -> None:
    _run("update-mime-database", os.path.join(_data_home(), "mime"))
    _run("update-desktop-database", os.path.join(_data_home(), "applications"))
    _run("gtk-update-icon-cache", "-q", "-t", os.path.join(_data_home(), "icons", "hicolor"))


def is_registered() -> bool:
    return os.path.isfile(desktop_path())


def registered_command() -> str:
    try:
        with open(desktop_path(), encoding="utf-8") as f:
            for line in f:
                if line.startswith("Exec="):
                    return line[5:].strip()
    except OSError:
        pass
    return ""


def current_default(ext: str) -> str:
    mime = EXT_TO_MIME.get(ext, "")
    if not mime:
        return ""
    found = _run("xdg-mime", "query", "default", mime)
    if found:
        return found
    for path in _mimeapps_files():
        try:
            with open(path, encoding="utf-8") as f:
                section = ""
                for line in f:
                    s = line.strip()
                    if s.startswith("["):
                        section = s
                    elif section == "[Default Applications]" and s.startswith(mime + "="):
                        return s.split("=", 1)[1].split(";")[0]
        except OSError:
            continue
    return ""


def is_default(ext: str) -> bool:
    return current_default(ext) == DESKTOP_ID


def status() -> dict[str, str]:
    reg = is_registered()
    out = {}
    for ext in EXT_TO_MIME:
        if reg and is_default(ext):
            out[ext] = "Default app"
        elif reg:
            out[ext] = "In \"Open With\" (not default)"
        else:
            out[ext] = "Not registered"
    return out
