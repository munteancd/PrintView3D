"""Finding the user's FreeCAD and using it to show FreeCAD documents and STEP files in 3D.

PrintView3D does not include FreeCAD's geometry engine. When FreeCAD is
installed, its command-line program (FreeCADCmd) is started hidden in the
background with resources/freecad_export.py, which turns the visible objects
(or the parts of a STEP file) into STL meshes. The result is cached, so opening the same file again is
instant. Without FreeCAD, only the preview picture and the object list are
shown (see loaders.freecad).
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

from .loaders.freecad import FreeCADDoc, read_fcstd
from .loaders.mesh import MeshPart, ModelData, load_stl
from .loaders.step import header_meta, read_step_header

FREECAD_EXTENSIONS = (".fcstd",)
TIMEOUT = 180


@dataclass
class FreeCADInstall:
    cmd: list[str]          # command for the headless FreeCADCmd
    gui: list[str]          # command that opens FreeCAD itself
    where: str = ""         # the path / package shown in Settings


# ------------------------------------------------------------------ finding
def _win_candidates() -> list[str]:
    roots = [os.environ.get(v, "") for v in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)")]
    roots.append(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"))
    found = []
    for r in filter(None, roots):
        for d in sorted(glob.glob(os.path.join(r, "FreeCAD*")), reverse=True):   # newest first
            found.append(os.path.join(d, "bin"))
    return found


def _from_bin_dir(bindir: str) -> Optional[FreeCADInstall]:
    exe = ".exe" if sys.platform == "win32" else ""
    cmd = next((os.path.join(bindir, n + exe) for n in ("freecadcmd", "FreeCADCmd")
                if os.path.isfile(os.path.join(bindir, n + exe))), None)
    gui = next((os.path.join(bindir, n + exe) for n in ("freecad", "FreeCAD")
                if os.path.isfile(os.path.join(bindir, n + exe))), None)
    if cmd:
        return FreeCADInstall([cmd], [gui or cmd], bindir)
    return None


def from_path(path: str) -> Optional[FreeCADInstall]:
    """An install from a program file the user picked (FreeCAD, FreeCADCmd or an AppImage)."""
    if not path or not os.path.isfile(path):
        return None
    if path.lower().endswith(".appimage"):
        return FreeCADInstall([path, "freecadcmd"], [path], path)
    found = _from_bin_dir(os.path.dirname(path))
    if found:
        return found
    return FreeCADInstall([path], [path], path)


def find_freecad(user_path: str = "") -> Optional[FreeCADInstall]:
    if user_path:
        found = from_path(user_path)
        if found:
            return found
    if sys.platform == "win32":
        for d in _win_candidates():
            found = _from_bin_dir(d)
            if found:
                return found
    elif sys.platform == "darwin":
        for app in glob.glob("/Applications/FreeCAD*.app") + glob.glob(os.path.expanduser("~/Applications/FreeCAD*.app")):
            found = _from_bin_dir(os.path.join(app, "Contents", "Resources", "bin"))
            if found:
                return found
    for name in ("freecadcmd", "FreeCADCmd", "freecadcmd-daily"):
        p = shutil.which(name)
        if p:
            gui = shutil.which("freecad") or shutil.which("FreeCAD") or p
            return FreeCADInstall([p], [gui], p)
    if sys.platform.startswith("linux"):
        if shutil.which("snap") and os.path.exists("/snap/bin/freecad.cmd"):
            return FreeCADInstall(["/snap/bin/freecad.cmd"], ["/snap/bin/freecad"], "snap: freecad")
        if shutil.which("flatpak") and _flatpak_has("org.freecad.FreeCAD"):
            return FreeCADInstall(["flatpak", "run", "--command=FreeCADCmd", "org.freecad.FreeCAD"],
                                  ["flatpak", "run", "org.freecad.FreeCAD"], "Flatpak: org.freecad.FreeCAD")
        home = os.path.expanduser("~")
        for d in (os.path.join(home, "Applications"), os.path.join(home, "Downloads"), home, "/opt"):
            for p in sorted(glob.glob(os.path.join(d, "FreeCAD*.AppImage")), reverse=True):
                return FreeCADInstall([p, "freecadcmd"], [p], p)
    return None


def _flatpak_has(app_id: str) -> bool:
    from .slicer import clean_environment
    try:
        r = subprocess.run(["flatpak", "info", app_id], capture_output=True, timeout=10,
                           env=clean_environment())
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


# ------------------------------------------------------------- conversion
def cache_dir() -> str:
    """In the user's home (not /tmp: a Flatpak FreeCAD cannot see our /tmp)."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "PrintView3D", "cache", "freecad")
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Caches", "PrintView3D", "freecad")
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "printview3d", "freecad")


def _job_dir(path: str, names: list[str], kind: str = "fcstd") -> str:
    st = os.stat(path)
    key = f"{os.path.abspath(path)}|{st.st_size}|{st.st_mtime_ns}|{','.join(names)}|{kind}|2"
    return os.path.join(cache_dir(), hashlib.sha1(key.encode("utf-8")).hexdigest()[:16])


def _script_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "resources", "freecad_export.py")


class FreeCADError(RuntimeError):
    pass


def convert(install: FreeCADInstall, path: str, names: list[str], kind: str = "fcstd",
            info: Optional[dict] = None) -> list[tuple[str, str]]:
    """Run FreeCAD hidden; returns [(object label, stl path)]. Uses the cache when possible.
    kind "fcstd": the named objects of a FreeCAD document; "step": all parts of a STEP file."""
    out = _job_dir(path, names, kind)
    result_file = os.path.join(out, "result.json")
    if not os.path.isfile(result_file):
        os.makedirs(out, exist_ok=True)
        script = os.path.join(out, "freecad_export.py")
        shutil.copyfile(_script_path(), script)
        job = os.path.join(out, "job.json")
        with open(job, "w", encoding="utf-8") as f:
            json.dump({"file": os.path.abspath(path), "objects": names, "out_dir": out, "type": kind}, f)
        from .slicer import clean_environment
        env = clean_environment()
        env["PRINTVIEW3D_FREECAD_JOB"] = job
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = 0x08000000           # CREATE_NO_WINDOW: no console flashes up
        try:
            subprocess.run(install.cmd + [script], env=env, cwd=out, timeout=TIMEOUT,
                           stdin=subprocess.DEVNULL, capture_output=True, **kwargs)
        except subprocess.TimeoutExpired:
            raise FreeCADError("FreeCAD took too long to convert this file.") from None
        except OSError as e:
            raise FreeCADError(f"Could not start FreeCAD: {e}") from None
        if not os.path.isfile(result_file):
            raise FreeCADError("FreeCAD did not convert the file.")
    with open(result_file, encoding="utf-8") as f:
        result = json.load(f)
    if info is not None:
        info.update(result)
    objs = [(o["label"], o["stl"]) for o in result.get("objects", []) if os.path.isfile(o["stl"])]
    if not objs and result.get("errors"):
        shutil.rmtree(out, ignore_errors=True)        # don't cache a failure
        raise FreeCADError(result["errors"][-1].strip().splitlines()[-1])
    return objs


# ------------------------------------------------------------------ loading
def doc_meta(doc: FreeCADDoc) -> dict:
    meta = {}
    if doc.version:
        meta["Created with"] = f"FreeCAD {doc.version}"
    if doc.label:
        meta["Title"] = doc.label
    return meta


def load_fcstd(path: str, progress=None, install: Optional[FreeCADInstall] = None) -> ModelData:
    """A FreeCAD document as a model: real 3D through FreeCAD when installed,
    otherwise no parts (the viewer then shows the preview picture and object list)."""
    doc = read_fcstd(path)
    shown = doc.shown()
    m = ModelData(parts=[], meta=doc_meta(doc), thumbnail=doc.thumbnail)
    m.freecad = {"doc": doc, "shown": shown, "status": "no_freecad", "error": "", "install": install}
    if progress:
        progress(0.1)
    if install is None or not shown:
        if not shown:
            m.freecad["status"] = "nothing_visible"
        return m
    try:
        objs = convert(install, path, [o.name for o in shown])
    except FreeCADError as e:
        m.freecad.update(status="failed", error=str(e))
        return m
    for i, (label, stl) in enumerate(objs):
        part = load_stl(stl).parts[0]
        m.parts.append(MeshPart(label, part.vertices, part.faces))
        if progress:
            progress(0.2 + 0.8 * (i + 1) / len(objs))
    m.freecad["status"] = "ok"
    return m


def load_step(path: str, progress=None, install: Optional[FreeCADInstall] = None) -> ModelData:
    """A STEP file: the header details always; the 3D model through FreeCAD when installed."""
    m = ModelData(parts=[], meta=header_meta(read_step_header(path)))
    m.freecad = {"doc": None, "shown": [], "status": "no_freecad", "error": "", "install": install,
                 "source": "step"}
    if progress:
        progress(0.1)
    if install is None:
        return m
    result: dict = {}
    try:
        objs = convert(install, path, [], "step", result)
    except FreeCADError as e:
        m.freecad.update(status="failed", error=str(e))
        return m
    for i, (label, stl) in enumerate(objs):
        part = load_stl(stl).parts[0]
        m.parts.append(MeshPart(label, part.vertices, part.faces))
        if progress:
            progress(0.2 + 0.8 * (i + 1) / len(objs))
    if not m.parts:
        m.freecad.update(status="failed", error="FreeCAD found no solid shapes in this file.")
        return m
    m.freecad["status"] = "ok"
    m.freecad["named_parts"] = not result.get("fallback", False)
    return m


def export_stl(parts: list[MeshPart], path: str) -> str:
    """Write the parts as one binary STL (for sending a model to a slicer that cannot read its format)."""
    import numpy as np
    tris = np.concatenate([p.vertices[p.faces].astype("<f4") for p in parts]) if parts else np.zeros((0, 3, 3), "<f4")
    rec = np.zeros(len(tris), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    rec["v"] = tris
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"PrintView3D export".ljust(80, b" "))
        f.write(np.uint32(len(tris)).tobytes())
        f.write(rec.tobytes())
    return path


def open_in_freecad(install: FreeCADInstall, path: str) -> None:
    from .slicer import clean_environment
    kwargs = {"start_new_session": True} if sys.platform != "win32" else {}
    subprocess.Popen(install.gui + [path], env=clean_environment(), stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)
