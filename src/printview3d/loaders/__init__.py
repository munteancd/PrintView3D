"""File loaders: STL, 3MF and G-code."""

import os

from .gcode import FEATURES, GcodeData, parse_gcode_file, parse_gcode_text
from .mesh import MeshPart, ModelData, load_3mf, load_stl, read_embedded_gcode

MESH_EXTENSIONS = (".stl", ".3mf")
GCODE_EXTENSIONS = (".gcode", ".gco", ".g")
SUPPORTED_EXTENSIONS = (".stl", ".3mf", ".gcode", ".gco", ".g")


def file_kind(path: str) -> str:
    """Return 'stl', '3mf', 'gcode' or '' for unsupported files."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".stl":
        return "stl"
    if ext == ".3mf":
        return "3mf"
    if ext in (".gcode", ".gco", ".g"):
        return "gcode"
    return ""


def load_file(path: str, progress=None):
    kind = file_kind(path)
    if kind == "stl":
        return load_stl(path, progress)
    if kind == "3mf":
        return load_3mf(path, progress)
    if kind == "gcode":
        return parse_gcode_file(path, progress)
    raise ValueError(f"Unsupported file type: {os.path.basename(path)}")


__all__ = [
    "FEATURES", "GcodeData", "MeshPart", "ModelData", "SUPPORTED_EXTENSIONS",
    "file_kind", "load_file", "load_3mf", "load_stl", "parse_gcode_file",
    "parse_gcode_text", "read_embedded_gcode",
]
