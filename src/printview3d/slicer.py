"""Find and launch slicers.

PrintView3D can hand the current file to any slicer. Known slicers are listed
in SLICERS and found automatically; any other program can be chosen as a
"Custom" slicer in Settings.

Detection for a known slicer, in order:
  1. A path the user picked manually (Settings)
  2. Windows "App Paths" registry entries
  3. Windows uninstall entries whose display name matches the slicer
  4. Common install folders (Program Files, LocalAppData)
  5. The PATH (useful on Linux/macOS and for portable installs)
The newest version wins when several copies are installed.

All slicers listed here accept a file path on the command line, which is
how Windows "Open with" starts them too.
"""

from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional

CUSTOM = "custom"


@dataclass(frozen=True)
class Slicer:
    id: str
    name: str
    exe_names: tuple[str, ...]                 # exact file names, most likely first
    keywords: tuple[str, ...]                  # fallback: exe name contains one of these
    display_name: str                          # regex for the Windows uninstall entry
    folders: tuple[str, ...] = field(default_factory=tuple)  # globs under Program Files etc.


SLICERS: list[Slicer] = [
    Slicer("creality_print", "Creality Print",
           ("CrealityPrint.exe", "Creality Print.exe", "CrealityPrint6.exe"),
           ("crealityprint", "creality print"),
           r"creality\s*print",
           (r"Creality\Creality Print*", "Creality Print*", "CrealityPrint*",
            r"Programs\Creality*", r"Programs\Creality\Creality Print*")),
    Slicer("orcaslicer", "OrcaSlicer",
           ("orca-slicer.exe", "OrcaSlicer.exe"),
           ("orca-slicer", "orcaslicer"),
           r"^orca\s*slicer",
           ("OrcaSlicer*", r"Programs\OrcaSlicer*")),
    Slicer("bambu_studio", "Bambu Studio",
           ("bambu-studio.exe", "BambuStudio.exe"),
           ("bambu-studio", "bambustudio"),
           r"bambu\s*studio",
           (r"Bambu Studio*", r"BambuStudio*", r"Bambu Lab\Bambu Studio*")),
    Slicer("prusaslicer", "PrusaSlicer",
           ("prusa-slicer.exe", "PrusaSlicer.exe"),
           ("prusa-slicer", "prusaslicer"),
           r"prusa\s*slicer",
           (r"Prusa3D\PrusaSlicer*", r"PrusaSlicer*")),
    Slicer("cura", "UltiMaker Cura",
           ("UltiMaker-Cura.exe", "Ultimaker-Cura.exe", "Cura.exe"),
           ("ultimaker-cura", "cura"),
           r"\bcura\b",
           ("UltiMaker Cura*", "Ultimaker Cura*")),
    Slicer("elegoo_slicer", "Elegoo Slicer",
           ("elegoo-slicer.exe", "ElegooSlicer.exe"),
           ("elegoo",),
           r"elegoo\s*slicer",
           ("ElegooSlicer*", r"ELEGOO\ElegooSlicer*", "Elegoo Slicer*")),
    Slicer("anycubic_slicer_next", "Anycubic Slicer Next",
           ("AnycubicSlicerNext.exe", "anycubic-slicer-next.exe"),
           ("anycubic",),
           r"anycubic\s*slicer\s*next",
           ("AnycubicSlicerNext*", r"Anycubic\AnycubicSlicerNext*", "Anycubic Slicer Next*")),
]
BY_ID = {s.id: s for s in SLICERS}

# Helper programs that live next to the real slicer and must never be launched.
_EXCLUDE = ("uninst", "update", "crash", "console", "gcodeviewer", "gcode-viewer", "engine",
            "helper", "setup", "redist", "qtwebengine", "dumper", "elevate", "repair")


def slicer_name(slicer_id: str, custom_name: str = "") -> str:
    if slicer_id == CUSTOM:
        return custom_name or "custom slicer"
    s = BY_ID.get(slicer_id)
    return s.name if s else "slicer"


# --------------------------------------------------------------------------
# Detection
# --------------------------------------------------------------------------
def _version_key(path: str):
    nums = re.findall(r"\d+", os.path.dirname(path))
    return ([int(n) for n in nums[-4:]], os.path.getmtime(path) if os.path.exists(path) else 0)


def _usable(path: str) -> bool:
    base = os.path.basename(path).lower()
    return os.path.isfile(path) and not any(x in base for x in _EXCLUDE)


def _exe_in_folder(s: Slicer, folder: str) -> list[str]:
    if not folder or not os.path.isdir(folder):
        return []
    found = [os.path.join(folder, n) for n in s.exe_names if os.path.isfile(os.path.join(folder, n))]
    if not found:
        for p in glob.glob(os.path.join(folder, "*.exe")):
            base = os.path.basename(p).lower()
            if any(k in base for k in s.keywords) and _usable(p):
                found.append(p)
    return [p for p in found if _usable(p)]


def _registry_candidates(s: Slicer) -> list[str]:
    if sys.platform != "win32":
        return []
    import winreg

    out: list[str] = []
    hives = (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE)
    for hive in hives:
        for exe in s.exe_names:
            try:
                with winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}") as k:
                    out.append(str(winreg.QueryValueEx(k, "")[0]).strip('"'))
            except OSError:
                pass

    name_re = re.compile(s.display_name, re.I)
    roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, path in roots:
        try:
            root = winreg.OpenKey(hive, path)
        except OSError:
            continue
        with root:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(root, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(root, sub) as k:
                        try:
                            name = str(winreg.QueryValueEx(k, "DisplayName")[0])
                        except OSError:
                            continue
                        if not name_re.search(name):
                            continue
                        for value in ("DisplayIcon", "InstallLocation"):
                            try:
                                v = str(winreg.QueryValueEx(k, value)[0])
                            except OSError:
                                continue
                            v = v.split(",")[0].strip().strip('"')
                            if v.lower().endswith(".exe") and _usable(v):
                                out.append(v)
                            else:
                                out.extend(_exe_in_folder(s, v if os.path.isdir(v) else os.path.dirname(v)))
                except OSError:
                    continue
    return out


def _folder_candidates(s: Slicer) -> list[str]:
    if sys.platform != "win32":
        return []
    out = []
    bases = [os.environ.get(v) for v in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "LOCALAPPDATA")]
    for b in filter(None, bases):
        for pat in s.folders:
            for folder in glob.glob(os.path.join(b, pat)):
                out.extend(_exe_in_folder(s, folder))
    return out


def _path_candidates(s: Slicer) -> list[str]:
    out = []
    for exe in s.exe_names:
        for name in (exe, os.path.splitext(exe)[0]):
            p = shutil.which(name)
            if p:
                out.append(p)
    return out


def find_slicer(slicer_id: str, manual_path: str = "") -> Optional[str]:
    """Full path of a known slicer, or None if it is not installed."""
    if manual_path and os.path.isfile(manual_path):
        return manual_path
    s = BY_ID.get(slicer_id)
    if s is None:
        return None
    seen, cands = set(), []
    for p in _registry_candidates(s) + _folder_candidates(s) + _path_candidates(s):
        key = os.path.normcase(os.path.abspath(p))
        if key not in seen and os.path.isfile(p):
            seen.add(key)
            cands.append(p)
    if not cands:
        return None
    cands.sort(key=_version_key, reverse=True)
    return cands[0]


def detect_installed(manual_paths: Optional[dict] = None) -> dict[str, str]:
    """{slicer_id: exe path} for every known slicer that is installed."""
    manual_paths = manual_paths or {}
    found = {}
    for s in SLICERS:
        p = find_slicer(s.id, manual_paths.get(s.id, ""))
        if p:
            found[s.id] = p
    return found


# Backwards compatible helper (used by older code/tests)
def find_creality_print(saved_path: str = "") -> Optional[str]:
    return find_slicer("creality_print", saved_path)


# --------------------------------------------------------------------------
# Settings helpers
# --------------------------------------------------------------------------
def migrate_settings(settings) -> None:
    """Move the single 'slicer_path' of v0.1/v0.2 into the per-slicer paths."""
    old = settings.get("slicer_path", "")
    if old:
        paths = dict(settings.get("slicer_paths") or {})
        paths.setdefault("creality_print", old)
        settings.set("slicer_paths", paths)
        settings.set("slicer_path", "")
        if not settings.get("slicer_id"):
            settings.set("slicer_id", "creality_print")


def resolve(settings, slicer_id: Optional[str] = None,
            installed: Optional[dict] = None) -> tuple[str, str, Optional[str]]:
    """Which slicer to use: (id, display name, exe path or None).

    slicer_id None = the default from Settings. If no default was chosen yet,
    the first installed slicer (in SLICERS order) is used.
    """
    paths = settings.get("slicer_paths") or {}
    custom = settings.get("custom_slicer") or {}
    sid = slicer_id or settings.get("slicer_id", "")

    if sid == CUSTOM:
        p = custom.get("path", "")
        return CUSTOM, slicer_name(CUSTOM, custom.get("name", "")), (p if os.path.isfile(p) else None)
    if sid in BY_ID:
        return sid, BY_ID[sid].name, find_slicer(sid, paths.get(sid, ""))

    # Nothing chosen yet: first slicer that is installed.
    installed = installed if installed is not None else detect_installed(paths)
    for s in SLICERS:
        if s.id in installed:
            return s.id, s.name, installed[s.id]
    return "", "slicer", None


# --------------------------------------------------------------------------
# Launch
# --------------------------------------------------------------------------
def open_in_slicer(slicer_exe: str, file_path: Optional[str] = None) -> None:
    """Start the slicer (detached), optionally opening a file in it."""
    args = [slicer_exe]
    if file_path:
        args.append(os.path.abspath(file_path))
    kwargs = {"cwd": os.path.dirname(slicer_exe) or None, "close_fds": True}
    if sys.platform == "win32":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, **kwargs)
