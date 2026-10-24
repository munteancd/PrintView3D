"""Export STL from 3MF: raw printable geometry only, binary STL, file names per object."""

import os
import struct
import zipfile

import numpy as np
import pytest

import make_samples
from printview3d.loaders import (
    MeshPart, load_3mf, load_stl, read_3mf_for_export, stl_file_names, write_binary_stl,
)
from printview3d.loaders.mesh import safe_file_name

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
PROD = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
RELS = ('<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Target="/3D/3dmodel.model" Id="r0" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')


def _mesh(size, oid, extra=""):
    v, f = make_samples.cube_tris(size)
    vs = "".join(f'<vertex x="{x}" y="{y}" z="{z}"/>' for x, y, z in v)
    ts = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in f)
    return f'<object id="{oid}" type="model"{extra}><mesh><vertices>{vs}</vertices><triangles>{ts}</triangles></mesh></object>'


def _write(path, files):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("_rels/.rels", RELS)
        for name, data in files.items():
            z.writestr(name, data)
    return str(path)


def orca_project(tmp_path):
    """Creality Print / OrcaSlicer / Bambu Studio layout: one object with a normal part, a
    modifier, a negative part, a support blocker and a support enforcer, plus a second object.
    The main model gives no names; model_settings.config does."""
    sub = (f'<?xml version="1.0" encoding="UTF-8"?><model unit="millimeter" xmlns="{CORE}"><resources>'
           + _mesh(20, 1) + _mesh(5, 2) + _mesh(6, 3) + _mesh(7, 4) + _mesh(8, 5) + _mesh(10, 6)
           + '</resources></model>')
    comps = "".join(f'<component p:path="/3D/Objects/object_1.model" objectid="{i}"/>' for i in range(1, 6))
    root = (f'<?xml version="1.0" encoding="UTF-8"?><model unit="millimeter" xmlns="{CORE}" xmlns:p="{PROD}" '
            f'requiredextensions="p"><resources>'
            f'<object id="10" type="model"><components>{comps}</components></object>'
            f'<object id="11" type="model"><components><component p:path="/3D/Objects/object_1.model" objectid="6"/>'
            f'</components></object></resources>'
            f'<build><item objectid="10" transform="1 0 0 0 1 0 0 0 1 100 100 0"/>'
            f'<item objectid="11" transform="1 0 0 0 1 0 0 0 1 150 100 0"/></build></model>')
    cfg = ('<?xml version="1.0" encoding="UTF-8"?><config>'
           '<object id="10"><metadata key="name" value="Bracket"/><metadata key="extruder" value="1"/>'
           '<part id="1" subtype="normal_part"><metadata key="name" value="body"/></part>'
           '<part id="2" subtype="modifier_part"><metadata key="infill" value="100"/></part>'
           '<part id="3" subtype="negative_part"/>'
           '<part id="4" subtype="support_blocker"/>'
           '<part id="5" subtype="support_enforcer"/></object>'
           '<object id="11"><metadata key="name" value="Clip"/>'
           '<part id="6" subtype="normal_part"/></object>'
           '<plate><metadata key="plater_id" value="1"/></plate></config>')
    return _write(tmp_path / "orca.3mf", {"3D/3dmodel.model": root, "3D/Objects/object_1.model": sub,
                                          "Metadata/model_settings.config": cfg})


def test_two_parts_sample():
    parts = read_3mf_for_export(os.path.join(DATA, "two_parts.3mf"))
    assert [p.name for p in parts] == ["Big cube", "Small cube"]
    assert [p.n_triangles for p in parts] == [12, 12]
    # Placed as on the plate, in millimetres (the build item transforms).
    assert parts[0].vertices[:, 0].min() == pytest.approx(150)
    assert parts[1].vertices[:, 0].max() == pytest.approx(200)


def test_orca_modifiers_negative_parts_and_supports_left_out(tmp_path):
    path = orca_project(tmp_path)
    parts = read_3mf_for_export(path)
    assert [p.name for p in parts] == ["Bracket", "Clip"]
    assert [p.n_triangles for p in parts] == [12, 12]
    big = parts[0].vertices
    assert big.max(axis=0) - big.min(axis=0) == pytest.approx([20, 20, 20])   # only the 20 mm body
    # The viewer still shows everything, as the slicer does, now with the slicer's names.
    m = load_3mf(path)
    assert [p.name for p in m.parts] == ["Bracket", "Clip"]
    assert m.parts[0].n_triangles == 5 * 12


def test_prusaslicer_volumes(tmp_path):
    """PrusaSlicer: one mesh per object, volumes as triangle ranges with a volume_type."""
    v1, f1 = make_samples.cube_tris(20)
    v2, f2 = make_samples.cube_tris(5, 30)
    v3, f3 = make_samples.cube_tris(5, 60)
    verts = v1 + v2 + v3
    faces = f1 + [(a + 8, b + 8, c + 8) for a, b, c in f2] + [(a + 16, b + 16, c + 16) for a, b, c in f3]
    vs = "".join(f'<vertex x="{x}" y="{y}" z="{z}"/>' for x, y, z in verts)
    ts = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in faces)
    root = (f'<?xml version="1.0" encoding="UTF-8"?><model unit="millimeter" xmlns="{CORE}"><resources>'
            f'<object id="1" type="model"><mesh><vertices>{vs}</vertices><triangles>{ts}</triangles></mesh></object>'
            f'</resources><build><item objectid="1"/></build></model>')
    cfg = ('<?xml version="1.0" encoding="UTF-8"?><config><object id="1" instances_count="1">'
           '<metadata type="object" key="name" value="Housing"/>'
           '<volume firstid="0" lastid="11"><metadata type="volume" key="volume_type" value="ModelPart"/></volume>'
           '<volume firstid="12" lastid="23"><metadata type="volume" key="volume_type" value="ParameterModifier"/></volume>'
           '<volume firstid="24" lastid="35"><metadata type="volume" key="modifier" value="1"/></volume>'
           '</object></config>')
    path = _write(tmp_path / "prusa.3mf", {"3D/3dmodel.model": root, "Metadata/Slic3r_PE_model.config": cfg})
    parts = read_3mf_for_export(path)
    assert [p.name for p in parts] == ["Housing"]
    assert parts[0].n_triangles == 12
    used = parts[0].vertices[np.unique(parts[0].faces)]
    assert used[:, 0].max() == pytest.approx(20)


def test_core_support_objects_and_units(tmp_path):
    root = (f'<?xml version="1.0" encoding="UTF-8"?><model unit="centimeter" xmlns="{CORE}"><resources>'
            + _mesh(2, 1, ' name="Part"') + _mesh(1, 2, ' name="Support"').replace('type="model"', 'type="support"')
            + '</resources><build><item objectid="1"/><item objectid="2"/></build></model>')
    parts = read_3mf_for_export(_write(tmp_path / "cm.3mf", {"3D/3dmodel.model": root}))
    assert [p.name for p in parts] == ["Part"]
    v = parts[0].vertices
    assert v.max(axis=0) - v.min(axis=0) == pytest.approx([20, 20, 20])   # 2 cm -> 20 mm


def test_binary_stl_round_trip(tmp_path):
    parts = read_3mf_for_export(os.path.join(DATA, "two_parts.3mf"))
    out = write_binary_stl(parts, str(tmp_path / "sub" / "both.stl"))
    data = open(out, "rb").read()
    assert not data[:5].lower().startswith(b"solid")
    n = struct.unpack_from("<I", data, 80)[0]
    assert n == 24 and len(data) == 84 + 50 * n
    rec = np.frombuffer(data, dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")], offset=84)
    assert np.allclose(np.linalg.norm(rec["n"], axis=1), 1.0)
    assert not rec["a"].any()                                  # no colour bits
    # Normals point outwards (the cubes are wound counter-clockwise from outside).
    centre = rec["v"].mean(axis=(0, 1))
    assert (np.einsum("ij,ij->i", rec["n"], rec["v"].mean(axis=1) - centre) > -1e-3).sum() > 12
    back = load_stl(out)
    assert back.n_triangles == 24
    assert not os.path.exists(out + ".part")


def test_degenerate_triangle_gets_zero_normal(tmp_path):
    part = MeshPart("flat", np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0]], np.float32), np.array([[0, 1, 2]]))
    data = open(write_binary_stl([part], str(tmp_path / "flat.stl")), "rb").read()
    assert struct.unpack_from("<3f", data, 84) == (0.0, 0.0, 0.0)


def test_file_names():
    assert stl_file_names(["Cube", "Cube", "cube", "Gear"]) == ["Cube.stl", "Cube (2).stl", "cube (3).stl", "Gear.stl"]
    assert safe_file_name('a<b>:c"/d\\e|f?g*') == "a_b__c__d_e_f_g_"
    assert safe_file_name("part.stl") == "part"
    assert safe_file_name("  dots... ") == "dots"
    assert safe_file_name("CON") == "CON_"
    assert safe_file_name("") == "object"
    assert safe_file_name("ترس") == "ترس"


def test_export_dialog():
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from printview3d.ui.export_stl import ExportStlDialog

    QApplication.instance() or QApplication([])
    parts = read_3mf_for_export(os.path.join(DATA, "two_parts.3mf"))
    dlg = ExportStlDialog(parts)
    assert dlg.tree.topLevelItemCount() == 2
    assert dlg.tree.topLevelItem(0).text(0) == "Big cube"
    assert dlg.tree.topLevelItem(0).text(1) == "12"
    assert dlg.selected_parts() == parts and not dlg.per_object()   # all ticked, combined
    dlg.tree.topLevelItem(0).setCheckState(0, Qt.Unchecked)
    assert [p.name for p in dlg.selected_parts()] == ["Small cube"]
    dlg.tree.topLevelItem(1).setCheckState(0, Qt.Unchecked)
    assert not dlg.ok_btn.isEnabled()
    dlg.separate_rb.setChecked(True)
    assert dlg.per_object()
