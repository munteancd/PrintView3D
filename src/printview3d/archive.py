"""ZIP files: the 3D files inside a downloaded model package (Printables, Thingiverse, ...).

Only files PrintView3D can open are used: STL, 3MF, OBJ, PLY, OFF, glTF/GLB, STEP, FreeCAD and
G-code. Everything else - pictures, PDFs, read-me files, web links, the hidden __MACOSX folder
that Macs add, ZIPs inside the ZIP, password-protected files - is skipped and never unpacked.

The 3D files are unpacked into PrintView3D's own cache folder, each in a numbered folder of its
own under its own file name. Real files are needed anyway: every loader reads a path, and a
slicer can only open a file on disk. Taking only the file name (never the folder path stored in
the ZIP) means a crafted name such as "../../Windows/x.stl" cannot write outside the cache.

Before anything is unpacked, the sizes the ZIP declares are checked, so a "ZIP bomb" (a tiny
download that unpacks to gigabytes) is refused instead of filling the disk or the memory.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import shutil
import time
import zipfile
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Optional

from .i18n import tr
from .loaders import file_kind
from .loaders.zipsafe import MAX_FILE_BYTES, MAX_RATIO, RATIO_CHECK_FROM  # noqa: F401 - same limits

if TYPE_CHECKING:
    from .loaders import ModelData

ARCHIVE_EXTENSIONS = (".zip",)

# Limits (uncompressed sizes). Real model packages stay far below these.
MAX_ENTRIES = 500                    # 3D files used from one ZIP
MAX_TOTAL_BYTES = 6 * 1024 ** 3      # all 3D files together

# Kinds that "Show all" can place side by side: plain meshes. G-code is already sliced for one
# printer at a fixed place on its bed, and STEP/FreeCAD need FreeCAD to convert (slow), so those
# are opened one at a time.
ARRANGEABLE = ("stl", "3mf", "obj", "ply", "off", "gltf")
# Kinds every slicer opens itself, for "Send all models".
SENDABLE = ("stl", "3mf", "obj")
# Order of the list: projects and models first, then CAD files, then sliced G-code.
_KIND_ORDER = {"3mf": 0, "stl": 1, "obj": 2, "ply": 2, "off": 2, "gltf": 2,
               "step": 3, "freecad": 3, "gcode": 4}


class ArchiveError(Exception):
    """The ZIP cannot be used; the message is shown to the user."""


@dataclass
class ZipEntry:
    member: str          # name inside the ZIP (with its folders)
    name: str            # name shown in the list
    kind: str            # "stl", "3mf", "gcode", ... (loaders.file_kind)
    size: int            # unpacked size in bytes
    path: str = ""       # where it was unpacked


@dataclass
class ZipContents:
    path: str
    entries: list[ZipEntry]
    skipped: int = 0     # files that are not 3D files (pictures, documents, ...)
    folder: str = ""     # cache folder of this ZIP

    @property
    def arrangeable(self) -> list[ZipEntry]:
        return [e for e in self.entries if e.kind in ARRANGEABLE]

    @property
    def sendable(self) -> list[ZipEntry]:
        return [e for e in self.entries if e.kind in SENDABLE]


def is_archive(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in ARCHIVE_EXTENSIONS


def _natural_key(text: str):
    """'part2' before 'part10'."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text)]


def _skip_member(info: zipfile.ZipInfo) -> bool:
    name = info.filename.replace("\\", "/")
    if info.is_dir():
        return True
    parts = [p for p in name.split("/") if p]
    if not parts:
        return True
    # macOS resource forks and hidden files ("__MACOSX/...", "._model.stl", ".DS_Store")
    return any(p == "__MACOSX" or p.startswith(".") for p in parts)


def read_contents(path: str) -> ZipContents:
    """List the 3D files in a ZIP (nothing is unpacked). Raises ArchiveError."""
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as e:
        raise ArchiveError(tr("This is not a valid ZIP file.") + f" ({e})") from e
    entries: list[ZipEntry] = []
    skipped = 0
    with zf:
        for info in zf.infolist():
            if _skip_member(info):
                continue
            kind = file_kind(info.filename)
            if not kind or info.flag_bits & 0x1:        # not a 3D file, or password-protected
                skipped += 1
                continue
            base = os.path.basename(info.filename.replace("\\", "/"))
            entries.append(ZipEntry(member=info.filename, name=base, kind=kind, size=info.file_size))
            if info.file_size > MAX_FILE_BYTES:
                raise ArchiveError(tr("{name} is too large to unpack ({size} GB).").format(
                    name=base, size=f"{info.file_size / 1024 ** 3:.1f}"))
            if (info.file_size > RATIO_CHECK_FROM and info.compress_size
                    and info.file_size / info.compress_size > MAX_RATIO):
                raise ArchiveError(tr("{name} unpacks to far more data than a 3D file normally does. "
                                      "It was not opened, to protect your computer.").format(name=base))
    if len(entries) > MAX_ENTRIES:
        raise ArchiveError(tr("This ZIP contains {n} 3D files; at most {max} can be opened.").format(
            n=len(entries), max=MAX_ENTRIES))
    if sum(e.size for e in entries) > MAX_TOTAL_BYTES:
        raise ArchiveError(tr("The 3D files in this ZIP are too large together to unpack."))

    # Two files with the same name in different folders: show the folder too.
    counts: dict[str, int] = {}
    for e in entries:
        counts[e.name.lower()] = counts.get(e.name.lower(), 0) + 1
    for e in entries:
        if counts[e.name.lower()] > 1:
            folder = os.path.basename(os.path.dirname(e.member.replace("\\", "/").rstrip("/")))
            if folder:
                e.name = f"{folder}/{e.name}"
    entries.sort(key=lambda e: (_KIND_ORDER.get(e.kind, 9), _natural_key(e.name)))
    return ZipContents(path=os.path.abspath(path), entries=entries, skipped=skipped)


def cache_root() -> str:
    from . import freecad as fc                     # same place as FreeCAD's cache
    return os.path.join(os.path.dirname(fc.cache_dir()), "zip")


def _folder_for(path: str) -> str:
    st = os.stat(path)
    key = f"{os.path.abspath(path)}|{st.st_size}|{st.st_mtime_ns}"
    return os.path.join(cache_root(), hashlib.sha1(key.encode("utf-8")).hexdigest()[:16])


def _clean_old(keep: str, max_age_s: float = 24 * 3600) -> None:
    """Remove the unpacked files of ZIPs opened more than a day ago. (Not newer ones: a slicer
    may still be reading the files of a ZIP that was open a moment ago.)"""
    root = cache_root()
    try:
        names = os.listdir(root)
    except OSError:
        return
    now = time.time()
    for n in names:
        p = os.path.join(root, n)
        try:
            if os.path.abspath(p) != os.path.abspath(keep) and now - os.path.getmtime(p) > max_age_s:
                shutil.rmtree(p, ignore_errors=True)
        except OSError:
            pass


_UNSAFE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(10)), *(f"lpt{i}" for i in range(10))}


def safe_file_name(member: str, fallback: str) -> str:
    """The file name of a ZIP member, made safe to create on Windows, macOS and Linux.

    Only the last part of the name is used (never the folders, so "../x.stl" stays in the
    cache). Characters Windows does not allow are replaced: a ":" would otherwise write into a
    hidden "alternate data stream" of another file. Names Windows reserves (CON, NUL, ...) and
    names ending in a dot or space get a "_"."""
    name = os.path.basename(member.replace("\\", "/"))
    name = _UNSAFE_NAME.sub("_", name).rstrip(" .")
    if not name or name in (".", ".."):
        return fallback
    stem = name.split(".", 1)[0].lower()
    if stem in _RESERVED:
        name = "_" + name
    if len(name) > 200:                                 # keep the extension
        root, ext = os.path.splitext(name)
        name = root[: 200 - len(ext)] + ext
    return name


def unpack(contents: ZipContents, progress: Optional[Callable[[float], None]] = None) -> ZipContents:
    """Unpack the 3D files into the cache (again only when the ZIP changed). Sets entry.path."""
    folder = _folder_for(contents.path)
    contents.folder = folder
    _clean_old(folder)
    total = max(1, sum(e.size for e in contents.entries))
    done = 0
    with zipfile.ZipFile(contents.path) as zf:
        for i, e in enumerate(contents.entries):
            safe = safe_file_name(e.member, f"model{i}")
            target = os.path.join(folder, str(i), safe)
            e.path = target
            if not (os.path.isfile(target) and os.path.getsize(target) == e.size):
                os.makedirs(os.path.dirname(target), exist_ok=True)
                tmp = target + ".part"
                written = 0
                try:
                    with zf.open(e.member) as src, open(tmp, "wb") as dst:
                        while True:
                            chunk = src.read(1024 * 1024)
                            if not chunk:
                                break
                            written += len(chunk)
                            if written > e.size:            # more data than the ZIP declared
                                raise ArchiveError(tr("{name} in the ZIP is damaged.").format(name=e.name))
                            dst.write(chunk)
                    os.replace(tmp, target)
                except BaseException:
                    try:                                    # don't leave half a file behind
                        os.remove(tmp)
                    except OSError:
                        pass
                    raise
            done += e.size
            if progress:
                progress(done / total)
    try:
        os.utime(folder)                                # "recently used" for _clean_old
    except OSError:
        pass
    return contents


def open_archive(path: str, progress: Optional[Callable[[float], None]] = None) -> ZipContents:
    """List and unpack the 3D files of a ZIP. Raises ArchiveError."""
    contents = read_contents(path)
    if contents.entries:
        unpack(contents, progress)
    return contents


# ============================================================================ Show all
def grid_columns(n: int) -> int:
    """Models per row: up to three in one row, then a near-square grid
    (4 -> 2 x 2, 5-6 -> 3 per row, 7-9 -> 3 x 3, 10-16 -> 4 per row, ...)."""
    if n <= 3:
        return max(1, n)
    return math.ceil(math.sqrt(n))


def arrange(models: list[tuple[str, "ModelData"]], gap: float = 10.0):
    """Place whole models side by side in rows, each standing on the plate (Z = 0), spaced by
    their real footprint: every row is as deep as its deepest model, and each row is centred.
    The first model is at the back left, like reading a page from above.

    models: (name, ModelData) pairs. Returns (ModelData with all parts moved, owner) where
    owner[i] is the index in `models` that part i came from."""
    import numpy as np
    from .loaders import MeshPart, ModelData

    items = []
    for idx, (name, m) in enumerate(models):
        b = m.bounds()
        if b is None:
            continue
        items.append((idx, name, m, b))
    cols = grid_columns(len(items))
    rows = [items[i:i + cols] for i in range(0, len(items), cols)]
    widths = [sum(b[1] - b[0] for *_, b in row) + gap * (len(row) - 1) for row in rows]
    depths = [max(b[3] - b[2] for *_, b in row) for row in rows]
    total_d = sum(depths) + gap * max(0, len(rows) - 1)

    parts: list[MeshPart] = []
    owner: list[int] = []
    y_top = total_d / 2
    for row, w, d in zip(rows, widths, depths):
        x = -w / 2
        for idx, name, m, b in row:
            dx = x - b[0]
            dy = (y_top - d / 2) - (b[2] + b[3]) / 2       # centred in its row's depth
            dz = -b[4]                                       # standing on the plate
            shift = np.array([dx, dy, dz], dtype=np.float32)
            for p in m.parts:
                label = name if len(m.parts) == 1 else f"{name} — {p.name}"
                parts.append(MeshPart(name=label, vertices=p.vertices + shift, faces=p.faces,
                                      color=p.color, vertex_colors=p.vertex_colors,
                                      face_colors=p.face_colors))
                owner.append(idx)
            x += (b[1] - b[0]) + gap
        y_top -= d + gap
    return ModelData(parts=parts), owner
