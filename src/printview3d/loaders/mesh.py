"""Mesh loaders for STL and 3MF files.

Both return a ModelData object: a list of named meshes (vertices + triangles)
plus any extra information found in the file (thumbnail, printer settings,
embedded sliced G-code).

The 3MF reader understands the multi-file layout used by Creality Print,
OrcaSlicer and Bambu Studio (objects stored in 3D/Objects/*.model and
referenced from the main model through the 3MF "production" extension).
"""

from __future__ import annotations

import json
import re
import struct
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

from .gcode import parse_bed_shape


@dataclass
class MeshPart:
    name: str
    vertices: np.ndarray   # (N, 3) float32
    faces: np.ndarray      # (M, 3) int64

    @property
    def n_triangles(self) -> int:
        return int(len(self.faces))


@dataclass
class ModelData:
    parts: list[MeshPart]
    meta: dict = field(default_factory=dict)
    bed: Optional[tuple] = None
    thumbnail: Optional[bytes] = None
    embedded_gcode: list[str] = field(default_factory=list)   # zip member names

    @property
    def n_triangles(self) -> int:
        return sum(p.n_triangles for p in self.parts)

    def bounds(self):
        if not self.parts:
            return None
        allv = np.vstack([p.vertices for p in self.parts if len(p.vertices)])
        mn, mx = allv.min(axis=0), allv.max(axis=0)
        return (float(mn[0]), float(mx[0]), float(mn[1]), float(mx[1]), float(mn[2]), float(mx[2]))


# ==========================================================================
# STL
# ==========================================================================
def load_stl(path: str, progress: Optional[Callable[[float], None]] = None) -> ModelData:
    """Read binary or ASCII STL into a de-duplicated triangle mesh."""
    with open(path, "rb") as f:
        data = f.read()

    tris = None
    name = None
    if len(data) >= 84:
        n = struct.unpack_from("<I", data, 80)[0]
        if 84 + n * 50 == len(data):
            rec = np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
            tris = np.frombuffer(data, dtype=rec, count=n, offset=84)["v"]
    if tris is None:
        text = data.decode("utf-8", errors="replace")
        m = re.match(r"\s*solid\s*([^\r\n]*)", text)
        if m and m.group(1).strip():
            name = m.group(1).strip()
        nums = re.findall(r"vertex\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)", text)
        if not nums:
            raise ValueError("This STL file contains no triangles (or is not a valid STL).")
        v = np.array(nums, dtype=np.float32)
        tris = v[: (len(v) // 3) * 3].reshape(-1, 3, 3)

    if progress:
        progress(0.6)
    if len(tris) == 0:
        raise ValueError("This STL file contains no triangles.")

    flat = np.ascontiguousarray(tris.reshape(-1, 3), dtype=np.float32)
    verts, inverse = np.unique(flat, axis=0, return_inverse=True)
    faces = inverse.reshape(-1, 3).astype(np.int64)
    if progress:
        progress(1.0)

    import os
    part_name = name or os.path.splitext(os.path.basename(path))[0]
    return ModelData(parts=[MeshPart(part_name, verts.astype(np.float32), faces)])


# ==========================================================================
# 3MF
# ==========================================================================
NS_CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
NS_PROD = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
NS_RELS = "http://schemas.openxmlformats.org/package/2006/relationships"
C = "{%s}" % NS_CORE
P_PATH = "{%s}path" % NS_PROD


# --------------------------------------------------------------------------
# Tolerant XML parsing
#
# Some slicers write 3MF model files that use a namespace prefix (for
# example "p:" or "slic3rpe:") without declaring it with xmlns:... . Strict
# XML parsers, including Python's, reject that with "unbound prefix".
# Slicers ignore the problem, so we do too: declare any missing prefixes on
# the root element and parse again.
# --------------------------------------------------------------------------
_PREFIX_USE = re.compile(rb"(?:</?|\s)([A-Za-z_][\w.-]*):[A-Za-z_][\w.-]*")
_PREFIX_DECL = re.compile(rb"xmlns:([A-Za-z_][\w.-]*)\s*=")
_ROOT_TAG = re.compile(rb"<(?![?!])[A-Za-z_][\w.:-]*")
KNOWN_PREFIXES = {b"p": NS_PROD.encode()}


def _parse_xml(data: bytes) -> ET.Element:
    try:
        return ET.fromstring(data)
    except ET.ParseError as e:
        if "unbound prefix" not in str(e):
            raise
    declared = set(_PREFIX_DECL.findall(data))
    used = set(_PREFIX_USE.findall(data))
    missing = sorted(used - declared - {b"xml", b"xmlns", b"http", b"https", b"urn"})
    m = _ROOT_TAG.search(data)
    if not missing or not m:
        raise ValueError("The 3MF file contains invalid XML that could not be repaired.")
    decl = b"".join(
        b' xmlns:' + pfx + b'="' + KNOWN_PREFIXES.get(pfx, b"urn:printview3d:undeclared:" + pfx) + b'"'
        for pfx in missing
    )
    return ET.fromstring(data[:m.end()] + decl + data[m.end():])


def _path_attr(el) -> Optional[str]:
    """The production-extension 'path' attribute, whatever its namespace."""
    v = el.get(P_PATH)
    if v:
        return v
    for k, val in el.attrib.items():
        if k.endswith("}path"):
            return val
    return None

UNIT_SCALE = {
    "micron": 0.001, "millimeter": 1.0, "centimeter": 10.0,
    "inch": 25.4, "foot": 304.8, "meter": 1000.0,
}


def _parse_transform(s: Optional[str]) -> np.ndarray:
    """3MF transform: 12 numbers, row-vector convention -> 4x4 matrix."""
    m = np.eye(4)
    if not s:
        return m
    try:
        v = [float(t) for t in s.split()]
    except ValueError:
        return m
    if len(v) != 12:
        return m
    m[0, :3] = v[0:3]
    m[1, :3] = v[3:6]
    m[2, :3] = v[6:9]
    m[3, :3] = v[9:12]
    return m


def _norm(p: str) -> str:
    return p.lstrip("/")


def _find_root_model(z: zipfile.ZipFile) -> str:
    try:
        rels = _parse_xml(z.read("_rels/.rels"))
        for r in rels.iter("{%s}Relationship" % NS_RELS):
            if r.get("Type", "").endswith("/3dmodel"):
                return _norm(r.get("Target", ""))
    except KeyError:
        pass
    for name in z.namelist():
        if name.lower().endswith(".model") and name.lower().startswith("3d/"):
            return name
    raise ValueError("No 3D model found inside this 3MF file.")


def _mesh_arrays(mesh_el) -> tuple[np.ndarray, np.ndarray]:
    vs = mesh_el.find(C + "vertices")
    ts = mesh_el.find(C + "triangles")
    if vs is None or ts is None:
        return np.zeros((0, 3), np.float32), np.zeros((0, 3), np.int64)
    verts = np.array([(v.get("x"), v.get("y"), v.get("z")) for v in vs.iter(C + "vertex")], dtype=np.float64)
    faces = np.array([(t.get("v1"), t.get("v2"), t.get("v3")) for t in ts.iter(C + "triangle")], dtype=np.int64)
    if verts.size == 0 or faces.size == 0:
        return np.zeros((0, 3), np.float32), np.zeros((0, 3), np.int64)
    return verts.reshape(-1, 3), faces.reshape(-1, 3)


def load_3mf(path: str, progress: Optional[Callable[[float], None]] = None) -> ModelData:
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        lower = {n.lower(): n for n in names}
        root_path = _find_root_model(z)

        parts_cache: dict[str, tuple[dict, float, ET.Element]] = {}

        def get_part(part_path: str):
            part_path = _norm(part_path)
            if part_path not in parts_cache:
                real = lower.get(part_path.lower(), part_path)
                root = _parse_xml(z.read(real))
                scale = UNIT_SCALE.get(root.get("unit", "millimeter"), 1.0)
                objects = {}
                res = root.find(C + "resources")
                if res is not None:
                    for obj in res.iter(C + "object"):
                        objects[obj.get("id")] = obj
                parts_cache[part_path] = (objects, scale, root)
            return parts_cache[part_path]

        def collect(part_path, obj_id, matrix, out_v, out_f, depth=0):
            if depth > 16:
                return
            objects, scale, _ = get_part(part_path)
            obj = objects.get(obj_id)
            if obj is None:
                return
            mesh = obj.find(C + "mesh")
            if mesh is not None:
                v, f = _mesh_arrays(mesh)
                if len(v):
                    v = v * scale
                    vh = np.hstack([v, np.ones((len(v), 1))])
                    v = (vh @ matrix)[:, :3]
                    out_f.append(f + sum(len(a) for a in out_v))
                    out_v.append(v.astype(np.float32))
            comps = obj.find(C + "components")
            if comps is not None:
                for c in comps.iter(C + "component"):
                    sub_path = _path_attr(c) or part_path
                    m = _parse_transform(c.get("transform")) @ matrix
                    collect(sub_path, c.get("objectid"), m, out_v, out_f, depth + 1)

        objects, _, root = get_part(root_path)
        meta = {}
        for md in root.iter(C + "metadata"):
            n = md.get("name")
            if n in ("Title", "Designer", "Application", "Description") and (md.text or "").strip():
                meta[{"Application": "Created with"}.get(n, n)] = md.text.strip()

        parts: list[MeshPart] = []
        build = root.find(C + "build")
        items = list(build.iter(C + "item")) if build is not None else []
        if not items:   # Some exporters omit <build>: show every mesh object.
            items = [ET.Element("item", {"objectid": oid}) for oid in objects]

        for i, item in enumerate(items):
            if progress:
                progress(0.1 + 0.8 * i / max(1, len(items)))
            item_path = _path_attr(item) or root_path
            oid = item.get("objectid")
            out_v, out_f = [], []
            collect(item_path, oid, _parse_transform(item.get("transform")), out_v, out_f)
            if not out_v:
                continue
            obj_el = get_part(item_path)[0].get(oid)
            name = (obj_el.get("name") if obj_el is not None else None) or f"Object {i + 1}"
            parts.append(MeshPart(name, np.vstack(out_v), np.vstack(out_f)))

        if not parts:
            raise ValueError("This 3MF file contains no printable objects.")

        # ---- slicer project settings (Creality Print / Orca / Bambu) ----
        bed = None
        cfg_name = lower.get("metadata/project_settings.config")
        if cfg_name:
            try:
                cfg = json.loads(z.read(cfg_name).decode("utf-8", "replace"))

                def first(v):
                    return v[0] if isinstance(v, list) and v else v

                for key, label in (("printer_model", "Printer"),
                                   ("printer_settings_id", "Printer profile"),
                                   ("print_settings_id", "Process profile"),
                                   ("layer_height", "Layer height"),
                                   ("nozzle_diameter", "Nozzle"),
                                   ("filament_type", "Filament type"),
                                   ("filament_settings_id", "Filament profile")):
                    val = first(cfg.get(key))
                    if val not in (None, ""):
                        meta.setdefault(label, str(val))
                if cfg.get("printable_area"):
                    bed = parse_bed_shape(cfg["printable_area"])
            except (ValueError, KeyError):
                pass

        # ---- thumbnail ----
        thumb = None
        for cand in ("metadata/plate_1.png", "metadata/thumbnail.png", "metadata/top_1.png"):
            if cand in lower:
                thumb = z.read(lower[cand])
                break
        if thumb is None:
            for n in names:
                nl = n.lower()
                if (nl.startswith("metadata/") or nl.startswith("thumbnails/")) and nl.endswith((".png", ".jpg", ".jpeg")):
                    thumb = z.read(n)
                    break

        gcodes = sorted(n for n in names if re.match(r"(?i)metadata/plate_\d+\.gcode$", n))

    if progress:
        progress(1.0)
    return ModelData(parts=parts, meta=meta, bed=bed, thumbnail=thumb, embedded_gcode=gcodes)


def read_embedded_gcode(path: str, member: str) -> str:
    with zipfile.ZipFile(path) as z:
        return z.read(member).decode("utf-8", errors="replace")
