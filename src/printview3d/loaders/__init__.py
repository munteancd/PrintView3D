"""File loaders: STL, 3MF, G-code and FreeCAD documents."""

import os

from .gcode import FEATURES, GcodeData, parse_gcode_file, parse_gcode_text
from .mesh import MeshPart, ModelData, load_3mf, load_stl, read_embedded_gcode

MESH_EXTENSIONS = (".stl", ".3mf")
GCODE_EXTENSIONS = (".gcode", ".gco", ".g")
FREECAD_EXTENSIONS = (".fcstd",)
SUPPORTED_EXTENSIONS = (".stl", ".3mf", ".gcode", ".gco", ".g", ".fcstd")


def file_kind(path: str) -> str:
    """Return 'stl', '3mf', 'gcode', 'freecad' or '' for unsupported files."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".stl":
        return "stl"
    if ext == ".3mf":
        return "3mf"
    if ext in (".gcode", ".gco", ".g"):
        return "gcode"
    if ext in FREECAD_EXTENSIONS:
        return "freecad"
    return ""


def load_file(path: str, progress=None, freecad_path: str = ""):
    kind = file_kind(path)
    if kind == "freecad":
        from .. import freecad          # not at import time: freecad imports this package
        return freecad.load_fcstd(path, progress, freecad.find_freecad(freecad_path))
    if kind == "stl":
        return load_stl(path, progress)
    if kind == "3mf":
        return load_3mf(path, progress)
    if kind == "gcode":
        return parse_gcode_file(path, progress)
    raise ValueError(f"Unsupported file type: {os.path.basename(path)}")


__all__ = [
    "FEATURES", "FREECAD_EXTENSIONS", "GcodeData", "MeshPart", "ModelData", "SUPPORTED_EXTENSIONS",
    "file_kind", "load_file", "load_3mf", "load_stl", "parse_gcode_file",
    "parse_gcode_text", "read_embedded_gcode",
]
