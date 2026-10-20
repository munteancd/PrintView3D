"""STEP files (.step / .stp): the information in the file header.

The 3D shapes in a STEP file are exact CAD geometry (curved surfaces, not
triangles); turning them into a mesh needs a CAD kernel. PrintView3D uses the
user's FreeCAD for that (see printview3d.freecad.load_step). This module only
reads the header, which works without FreeCAD:

    FILE_DESCRIPTION(...);
    FILE_NAME('name', '2024-05-01T10:00:00', ('author'), ('organization'),
              'preprocessor', 'originating system', 'authorization');
    FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Application protocols by their schema names
SCHEMAS = {
    "CONFIG_CONTROL_DESIGN": "AP203",
    "CONFIG_CONTROL_3D_DESIGN": "AP203",
    "AUTOMOTIVE_DESIGN": "AP214",
    "AP242_MANAGED_MODEL_BASED_3D_ENGINEERING": "AP242",
    "AP203_CONFIGURATION_CONTROLLED_3D_DESIGN_OF_MECHANICAL_PARTS_AND_ASSEMBLIES_MIM_LF": "AP203",
}


@dataclass
class StepHeader:
    name: str = ""
    date: str = ""
    authors: list[str] = field(default_factory=list)
    organizations: list[str] = field(default_factory=list)
    preprocessor: str = ""
    system: str = ""
    schema: str = ""


def _decode(s: str) -> str:
    """STEP string escapes: '' for a quote, \\X2\\hhhh...\\X0\\ (UTF-16), \\X\\hh (Latin-1), \\S\\c."""
    s = s.replace("''", "'")

    def x2(m):
        h = m.group(1)
        return "".join(chr(int(h[i:i + 4], 16)) for i in range(0, len(h) - 3, 4))

    def x4(m):
        h = m.group(1)
        return "".join(chr(int(h[i:i + 8], 16)) for i in range(0, len(h) - 7, 8))

    s = re.sub(r"\\X2\\([0-9A-Fa-f]*)\\X0\\", x2, s)
    s = re.sub(r"\\X4\\([0-9A-Fa-f]*)\\X0\\", x4, s)
    s = re.sub(r"\\X\\([0-9A-Fa-f]{2})", lambda m: bytes([int(m.group(1), 16)]).decode("latin-1"), s)
    s = re.sub(r"\\S\\(.)", lambda m: chr(ord(m.group(1)) + 128), s)
    return s.replace("\\\\", "\\")


def _params(text: str, start: int):
    """Parse the parameter list that starts at text[start] == '('. Returns (value, end):
    strings become str, lists become list, anything else (numbers, $, *, .ENUM.) str."""
    i = start + 1
    out: list = []
    while i < len(text):
        c = text[i]
        if c in " \t\r\n,":
            i += 1
        elif c == "'":
            j = i + 1
            buf = []
            while j < len(text):
                if text[j] == "'":
                    if j + 1 < len(text) and text[j + 1] == "'":
                        buf.append("''")
                        j += 2
                        continue
                    break
                buf.append(text[j])
                j += 1
            out.append(_decode("".join(buf)))
            i = j + 1
        elif c == "(":
            v, i = _params(text, i)
            out.append(v)
        elif c == ")":
            return out, i + 1
        else:
            j = i
            while j < len(text) and text[j] not in ",)":
                j += 1
            out.append(text[i:j].strip())
            i = j
    return out, i


def _strings(v) -> list[str]:
    if isinstance(v, list):
        return [x for x in (s.strip() for s in v if isinstance(s, str)) if x and x not in ("$", "*")]
    return [v.strip()] if isinstance(v, str) and v.strip() and v.strip() not in ("$", "*") else []


def is_step(data: bytes) -> bool:
    return data.lstrip()[:13].upper() == b"ISO-10303-21;"


def read_step_header(path: str) -> StepHeader:
    with open(path, "rb") as f:
        head = f.read(256 * 1024)
    if not is_step(head):
        raise ValueError("This is not a STEP file (it should start with ISO-10303-21).")
    text = head.decode("utf-8", errors="replace")
    end = text.upper().find("ENDSEC;")
    text = text[: end if end > 0 else len(text)]
    h = StepHeader()
    m = re.search(r"FILE_NAME\s*\(", text, re.I)
    if m:
        p, _ = _params(text, m.end() - 1)
        p += [""] * (7 - len(p))
        h.name = (_strings(p[0]) or [""])[0]
        h.date = (_strings(p[1]) or [""])[0]
        h.authors = _strings(p[2])
        h.organizations = _strings(p[3])
        h.preprocessor = (_strings(p[4]) or [""])[0]
        h.system = (_strings(p[5]) or [""])[0]
    m = re.search(r"FILE_SCHEMA\s*\(", text, re.I)
    if m:
        p, _ = _params(text, m.end() - 1)
        names = _strings(p[0]) if p else []
        if names:
            key = names[0].split("{")[0].strip().upper()
            h.schema = SCHEMAS.get(key, key.title())
    return h


def header_meta(h: StepHeader) -> dict:
    """Details for the side panel (keys as in ui.labels.META_LABELS)."""
    meta = {}
    if h.schema:
        meta["Format"] = f"STEP {h.schema}" if h.schema.startswith("AP") else f"STEP ({h.schema})"
    made_with = h.system or h.preprocessor
    if made_with:
        meta["Created with"] = made_with
    if h.authors:
        meta["Designer"] = ", ".join(h.authors)
    if h.organizations:
        meta["Organization"] = ", ".join(h.organizations)
    if h.date:
        meta["Date"] = h.date.replace("T", " ")[:16]
    return meta
