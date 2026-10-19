"""Reading FreeCAD documents (.FCStd) without FreeCAD.

An .FCStd file is a zip with:
  Document.xml        every object: type, label, properties, which file holds its shape
  GuiDocument.xml     what is visible in FreeCAD's 3D view
  *.brp / *.brep      exact solid shapes (OpenCASCADE BREP)
  *.bms               triangle meshes (Mesh workbench)
  thumbnails/Thumbnail.png   preview picture (if FreeCAD was set to save one)

This module reads the object list, works out which objects FreeCAD itself
would show (visible bodies and solids, not sketches, datum planes, hidden
objects or the features inside a PartDesign Body) and returns the preview
picture. Turning the solids into triangles needs OpenCASCADE; that is done by
the user's installed FreeCAD (see printview3d.freecad).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from typing import Optional

# Objects that never appear as solids in FreeCAD's 3D view.
NOT_SOLID_TYPES = (
    "Sketcher::", "App::Origin", "App::Line", "App::Plane", "App::Point", "App::Part",
    "App::DocumentObjectGroup", "App::Link", "PartDesign::Plane", "PartDesign::Line",
    "PartDesign::Point", "PartDesign::CoordinateSystem", "PartDesign::ShapeBinder",
    "PartDesign::SubShapeBinder", "Part::Part2DObject", "Spreadsheet::", "TechDraw::",
    "App::TextDocument", "App::MaterialObject", "App::VarSet",
)
CONTAINER_TYPES = ("App::Part", "App::DocumentObjectGroup", "PartDesign::Body")


@dataclass
class FCObject:
    name: str                       # internal name (unique), e.g. "Body001"
    label: str                      # name shown in FreeCAD's tree, e.g. "Laptop stand"
    type: str                       # e.g. "PartDesign::Body"
    visible: bool = True
    shape_file: str = ""            # zip member with the BREP shape ("" = none / empty)
    mesh_file: str = ""             # zip member with a mesh (Mesh::Feature)
    children: list[str] = field(default_factory=list)
    parent: str = ""

    @property
    def kind(self) -> str:
        """Short type for the object list: 'Body', 'Pad', 'Sketch', ..."""
        return self.type.split("::")[-1]


@dataclass
class FreeCADDoc:
    program_version: str = ""       # e.g. "1.1R20260928 (Git shallow)"
    objects: dict[str, FCObject] = field(default_factory=dict)
    thumbnail: Optional[bytes] = None
    label: str = ""                 # document label (title)

    @property
    def version(self) -> str:
        """'1.1' from '1.1R20260928 (Git shallow)'."""
        v = self.program_version.split("R")[0].strip()
        return v or self.program_version

    def shown(self) -> list[FCObject]:
        """Objects FreeCAD shows as solids, in document order."""
        out = []
        for o in self.objects.values():
            if not o.visible or not (o.shape_file or o.mesh_file):
                continue
            if any(o.type.startswith(t) for t in NOT_SOLID_TYPES):
                continue
            # Features inside a PartDesign Body: the Body's own shape is the result.
            p = self.objects.get(o.parent)
            if p is not None and p.type == "PartDesign::Body":
                continue
            if not self._containers_visible(o):
                continue
            out.append(o)
        return out

    def _containers_visible(self, o: FCObject) -> bool:
        seen = set()
        p = self.objects.get(o.parent)
        while p is not None and p.name not in seen:
            seen.add(p.name)
            if p.type in CONTAINER_TYPES and not p.visible:
                return False
            p = self.objects.get(p.parent)
        return True


def _value(prop: ET.Element) -> Optional[ET.Element]:
    return prop[0] if len(prop) else None


def read_fcstd(path: str) -> FreeCADDoc:
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        if "Document.xml" not in names:
            raise ValueError("Not a FreeCAD document (Document.xml missing)")
        sizes = {i.filename: i.file_size for i in z.infolist()}
        doc_root = ET.fromstring(z.read("Document.xml"))
        gui_root = ET.fromstring(z.read("GuiDocument.xml")) if "GuiDocument.xml" in names else None
        thumb = None
        for t in ("thumbnails/Thumbnail.png", "Thumbnail.png"):
            if t in names:
                thumb = z.read(t)
                break

    doc = FreeCADDoc(program_version=doc_root.get("ProgramVersion", ""), thumbnail=thumb)
    props = doc_root.find("Properties")
    if props is not None:
        for p in props.iter("Property"):
            if p.get("name") == "Label" and _value(p) is not None:
                doc.label = _value(p).get("value", "")

    objs = doc_root.find("Objects")
    for o in (objs if objs is not None else []):
        if o.tag == "Object" and o.get("name"):
            doc.objects[o.get("name")] = FCObject(o.get("name"), o.get("name"), o.get("type", ""))

    data = doc_root.find("ObjectData")
    for od in (data if data is not None else []):
        obj = doc.objects.get(od.get("name", ""))
        if obj is None:
            continue
        for p in od.iter("Property"):
            name, v = p.get("name"), _value(p)
            if v is None:
                continue
            if name == "Label":
                obj.label = v.get("value", obj.name)
            elif name == "Visibility":
                obj.visible = v.get("value", "true") == "true"
            elif name == "Shape" and v.get("file"):
                f = v.get("file")
                obj.shape_file = f if sizes.get(f, 0) > 0 else ""
            elif name == "Mesh" and v.get("file"):
                f = v.get("file")
                obj.mesh_file = f if sizes.get(f, 0) > 0 else ""
            elif name in ("Group", "Model") and v.tag == "LinkList":
                obj.children += [link.get("value") for link in v.iter("Link") if link.get("value")]

    # FreeCAD's 3D-view visibility (GuiDocument.xml) wins over the document flag.
    if gui_root is not None:
        for vp in gui_root.iter("ViewProvider"):
            obj = doc.objects.get(vp.get("name", ""))
            if obj is None:
                continue
            for p in vp.iter("Property"):
                if p.get("name") == "Visibility" and _value(p) is not None:
                    obj.visible = _value(p).get("value", "true") == "true"
                    break

    for o in doc.objects.values():
        for c in o.children:
            child = doc.objects.get(c)
            if child is not None and not child.parent:
                child.parent = o.name
    return doc
