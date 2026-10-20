"""Tests for the file loaders (no GUI needed).

Run:  python tests/make_samples.py && python -m pytest -q tests
"""

import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)

import make_samples  # noqa: E402
from printview3d.loaders import (  # noqa: E402
    FEATURES, GcodeData, ModelData, file_kind, load_file, parse_gcode_text, read_embedded_gcode,
)
from printview3d.loaders.gcode import FEATURE_INDEX, classify_feature, parse_bed_shape  # noqa: E402

DATA = os.path.join(HERE, "data")


@pytest.fixture(scope="session", autouse=True)
def samples():
    make_samples.main()


def test_file_kind():
    assert file_kind("a.STL") == "stl"
    assert file_kind("a.3mf") == "3mf"
    assert file_kind("a.gcode") == "gcode"
    assert file_kind("a.OBJ") == "obj"
    assert file_kind("a.glb") == "gltf"
    assert file_kind("a.dwg") == ""


@pytest.mark.parametrize("name,size", [("cube_binary.stl", 20.0), ("cube_ascii.stl", 10.0)])
def test_stl(name, size):
    m = load_file(os.path.join(DATA, name))
    assert isinstance(m, ModelData)
    assert m.n_triangles == 12
    assert len(m.parts[0].vertices) == 8          # duplicates merged
    b = m.bounds()
    assert b[1] - b[0] == pytest.approx(size)


def test_3mf_multifile_layout():
    path = os.path.join(DATA, "two_parts.3mf")
    m = load_file(path)
    assert [p.name for p in m.parts] == ["Big cube", "Small cube"]
    # build-item transforms applied (big cube centred at 160,175)
    b = m.parts[0].vertices
    assert b[:, 0].min() == pytest.approx(150) and b[:, 0].max() == pytest.approx(170)
    assert m.bed == (0, 350, 0, 350)
    assert m.meta["Printer"] == "Creality K2 Plus"
    assert m.thumbnail and m.thumbnail[:4] == b"\x89PNG"
    assert m.embedded_gcode == ["Metadata/plate_1.gcode"]
    g = parse_gcode_text(read_embedded_gcode(path, m.embedded_gcode[0]))
    assert g.n_layers == 20


def test_gcode_layers_and_features():
    g = load_file(os.path.join(DATA, "cylinder.gcode"))
    assert isinstance(g, GcodeData)
    assert g.n_layers == 50
    assert g.layer_z[0] == pytest.approx(0.2)
    assert g.layer_z[-1] == pytest.approx(10.0)
    assert np.all(np.diff(g.layers) >= 0)                 # non-decreasing
    assert g.layer_end[-1] == g.n_segments
    for k in ("outer_wall", "inner_wall", "infill", "top_bottom", "travel"):
        assert k in g.feature_counts
    assert g.meta["Print time"] == "12m 34s"
    assert g.meta["Filament (g)"] == "3.70"
    assert g.bed == (0, 220, 0, 220)
    assert g.thumbnail[:4] == b"\x89PNG"
    # purge line (no TYPE) must not affect the model size
    xmin, xmax = g.extrusion_bounds[0], g.extrusion_bounds[1]
    assert xmax - xmin == pytest.approx(30.0, abs=0.1)


def test_arcs_follow_circle():
    g = parse_gcode_text("G90\nM83\nG1 X10 Y0 Z0.2\n;TYPE:Outer wall\nG3 X-10 Y0 I-10 J0 E1\n")
    ext = g.types != FEATURE_INDEX["travel"]
    r = np.hypot(g.ends[ext][:, 0], g.ends[ext][:, 1])
    assert np.allclose(r, 10.0, atol=1e-3)
    assert g.ends[ext][:, 1].max() == pytest.approx(10.0, abs=0.05)   # CCW goes through +Y


def test_relative_and_absolute_extrusion():
    absolute = parse_gcode_text("M82\nG92 E0\nG1 X0 Y0 Z0.2\nG1 X10 E1\nG1 X20 E2\nG1 X30 E2\n")
    relative = parse_gcode_text("M83\nG1 X0 Y0 Z0.2\nG1 X10 E1\nG1 X20 E1\nG1 X30 E0\n")
    for g in (absolute, relative):
        t = g.types.tolist()
        assert t.count(FEATURE_INDEX["travel"]) == 2          # first move + non-extruding move
        assert len(t) - t.count(FEATURE_INDEX["travel"]) == 2


def test_z_based_layers_without_markers():
    txt = "M83\n" + "".join(f"G1 Z{z:.1f}\nG1 X0 Y0\nG1 X10 Y0 E1\n" for z in (0.2, 0.4, 0.6))
    g = parse_gcode_text(txt)
    assert g.n_layers == 3


@pytest.mark.parametrize("name,key", [
    ("Outer wall", "outer_wall"), ("WALL-OUTER", "outer_wall"), ("External perimeter", "outer_wall"),
    ("Inner wall", "inner_wall"), ("Perimeter", "inner_wall"), ("Sparse infill", "infill"),
    ("FILL", "infill"), ("Internal solid infill", "solid_infill"), ("Top surface", "top_bottom"),
    ("SKIN", "top_bottom"), ("Support interface", "support_interface"), ("SUPPORT", "support"),
    ("Bridge", "bridge"), ("Skirt", "skirt_brim"), ("Brim", "skirt_brim"), ("Prime tower", "prime_tower"),
    ("Custom", "other"),
])
def test_classify(name, key):
    assert FEATURES[classify_feature(name)][0] == key


def test_bed_shape():
    assert parse_bed_shape("0x0,220x0,220x220,0x220") == (0, 220, 0, 220)
    assert parse_bed_shape(["-5x-5", "300x-5", "300x300", "-5x300"]) == (-5, 300, -5, 300)
    assert parse_bed_shape("garbage") is None


def test_3mf_with_undeclared_prefixes(tmp_path):
    """Some slicers use namespace prefixes (p:, slic3rpe:) without declaring them."""
    core = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
    cube_v, cube_f = make_samples.cube_tris(10)
    verts = "".join(f'<vertex x="{x}" y="{y}" z="{z}"/>' for x, y, z in cube_v)
    tris = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in cube_f)
    obj = (f'<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xmlns="{core}">\n'
           f' <resources>\n  <object id="1" p:UUID="abc" type="model">\n'
           f'   <mesh><vertices>{verts}</vertices><triangles>{tris}</triangles></mesh>\n'
           f'  </object>\n </resources>\n</model>\n')
    root = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<model unit="millimeter" xml:lang="en-US" xmlns="{core}" requiredextensions="p">\n'
            f' <metadata name="Application">CrealityPrint-6.2</metadata>\n'
            f' <resources>\n'
            f'  <object id="2" name="Undeclared" type="model">\n'
            f'   <components>\n'
            f'    <component p:path="/3D/Objects/object_1.model" objectid="1"/>\n'
            f'    <slic3rpe:extra value="1"/>\n'
            f'   </components>\n'
            f'  </object>\n'
            f' </resources>\n'
            f' <build><item objectid="2" p:UUID="x"/></build>\n'
            f'</model>\n')
    rels = ('<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="r0" '
            'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    import zipfile
    path = tmp_path / "undeclared.3mf"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", root)
        z.writestr("3D/Objects/object_1.model", obj)
    m = load_file(str(path))
    assert [p.name for p in m.parts] == ["Undeclared"]
    assert m.n_triangles == 12
