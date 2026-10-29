"""FreeCAD documents: reading, choosing what is visible, conversion through FreeCAD."""

import os
import subprocess
import sys
import zipfile

import pytest

from printview3d import freecad as fc
from printview3d.loaders import file_kind, load_file
from printview3d.loaders.freecad import read_fcstd

HERE = os.path.dirname(os.path.abspath(__file__))
FAKE = os.path.join(HERE, "fake_freecad", "fake_freecadcmd.py")
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f"
       b"\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")


def _obj_data(name, label, visible=True, shape=None, mesh=None, group=None):
    props = [f'<Property name="Label" type="App::PropertyString"><String value="{label}"/></Property>',
             f'<Property name="Visibility" type="App::PropertyBool"><Bool value="{str(visible).lower()}"/></Property>']
    if shape:
        props.append(f'<Property name="Shape" type="Part::PropertyPartShape"><Part file="{shape}"/></Property>')
    if mesh:
        props.append(f'<Property name="Mesh" type="Mesh::PropertyMeshKernel"><Mesh file="{mesh}"/></Property>')
    if group:
        links = "".join(f'<Link value="{g}"/>' for g in group)
        props.append(f'<Property name="Group" type="App::PropertyLinkList"><LinkList count="{len(group)}">'
                     f'{links}</LinkList></Property>')
    return f'<Object name="{name}"><Properties Count="{len(props)}">{"".join(props)}</Properties></Object>'


def make_fcstd(path, part_visible=True, empty_box=False):
    objs = [  # name, type, label, doc-visible, gui-visible, shape, mesh, group
        ("Part", "App::Part", "Assembly", True, part_visible, None, None, ["Body", "Box"]),
        ("Body", "PartDesign::Body", "Stand", True, True, "Body.Shape.brp", None, ["Sketch", "Pad"]),
        ("Sketch", "Sketcher::SketchObject", "Sketch", False, False, "Sketch.Shape.brp", None, None),
        ("Pad", "PartDesign::Pad", "Pad", True, True, "Pad.Shape.brp", None, None),
        ("Box", "Part::Box", "Foot", True, True, "Box.Shape.brp", None, None),
        ("Cylinder", "Part::Cylinder", "Old cylinder", True, False, "Cylinder.Shape.brp", None, None),
        ("XY_Plane", "App::Plane", "XY-plane", True, True, None, None, None),
        ("Mesh", "Mesh::Feature", "Imported STL", False, False, None, "MeshKernel.bms", None),
    ]
    doc = ['<?xml version="1.0" encoding="utf-8"?>',
           '<Document SchemaVersion="4" ProgramVersion="1.0.2R39319 (Git)" FileVersion="1">',
           '<Properties Count="1"><Property name="Label" type="App::PropertyString">'
           '<String value="Test stand"/></Property></Properties>',
           f'<Objects Count="{len(objs)}">']
    doc += [f'<Object type="{t}" name="{n}" id="{i}"/>' for i, (n, t, *_r) in enumerate(objs)]
    doc.append(f'</Objects><ObjectData Count="{len(objs)}">')
    doc += [_obj_data(n, lab, dv, sh, me, gr) for n, _t, lab, dv, _gv, sh, me, gr in objs]
    doc.append("</ObjectData></Document>")
    gui = ['<?xml version="1.0" encoding="utf-8"?><Document SchemaVersion="1">',
           f'<ViewProviderData Count="{len(objs)}">']
    for n, _t, _l, _dv, gv, *_r in objs:
        gui.append(f'<ViewProvider name="{n}"><Properties Count="1"><Property name="Visibility" '
                   f'type="App::PropertyBool"><Bool value="{str(gv).lower()}"/></Property>'
                   '</Properties></ViewProvider>')
    gui.append("</ViewProviderData></Document>")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("Document.xml", "\n".join(doc))
        z.writestr("GuiDocument.xml", "".join(gui))
        for _n, _t, _l, _dv, _gv, sh, me, _g in objs:
            for f in (sh, me):
                if f:
                    z.writestr(f, "" if (empty_box and f.startswith("Box")) else "CASCADE Topology V1")
        z.writestr("thumbnails/Thumbnail.png", PNG)
    return path


def test_file_kind():
    assert file_kind("stand.FCStd") == "freecad"
    assert file_kind("stand.fcstd") == "freecad"


def test_reads_objects_and_picks_what_freecad_shows(tmp_path):
    doc = read_fcstd(make_fcstd(str(tmp_path / "a.FCStd")))
    assert doc.version == "1.0.2"
    assert doc.label == "Test stand"
    assert doc.thumbnail == PNG
    assert doc.objects["Pad"].parent == "Body"
    assert doc.objects["Body"].parent == "Part"
    # The Body (not its Pad/Sketch), the visible box; not hidden, datum or mesh objects
    assert [o.label for o in doc.shown()] == ["Stand", "Foot"]


def test_hidden_container_hides_its_contents(tmp_path):
    doc = read_fcstd(make_fcstd(str(tmp_path / "a.FCStd"), part_visible=False))
    assert doc.shown() == []


def test_empty_shapes_are_skipped(tmp_path):
    doc = read_fcstd(make_fcstd(str(tmp_path / "a.FCStd"), empty_box=True))
    assert [o.label for o in doc.shown()] == ["Stand"]


def test_without_freecad_gives_picture_and_list(tmp_path, monkeypatch):
    monkeypatch.setattr(fc, "find_freecad", lambda *_a: None)
    m = load_file(make_fcstd(str(tmp_path / "a.FCStd")))
    assert m.parts == []
    assert m.thumbnail == PNG
    assert m.freecad["status"] == "no_freecad"
    assert m.meta["Created with"] == "FreeCAD 1.0.2"


def test_not_a_freecad_file(tmp_path):
    p = tmp_path / "bad.FCStd"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("x.txt", "hi")
    with pytest.raises(ValueError):
        read_fcstd(str(p))


@pytest.fixture
def fake_install(tmp_path, monkeypatch):
    monkeypatch.setattr(fc, "cache_dir", lambda: str(tmp_path / "cache"))
    return fc.FreeCADInstall([sys.executable, FAKE], [sys.executable, FAKE], "fake")


def test_conversion_through_freecad(tmp_path, fake_install, monkeypatch):
    path = make_fcstd(str(tmp_path / "a.FCStd"))
    m = fc.load_fcstd(path, install=fake_install)
    assert m.freecad["status"] == "ok"
    assert [p.name for p in m.parts] == ["Body", "Box"]        # labels come from FreeCAD
    assert all(p.n_triangles == 12 for p in m.parts)
    # Second time: from the cache, FreeCAD is not started again
    monkeypatch.setattr(fc.subprocess, "run", lambda *a, **k: pytest.fail("FreeCAD started again"))
    assert len(fc.load_fcstd(path, install=fake_install).parts) == 2


def test_conversion_failure_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(fc, "cache_dir", lambda: str(tmp_path / "cache"))
    broken = fc.FreeCADInstall([sys.executable, "-c", "pass"], [], "broken")
    m = fc.load_fcstd(make_fcstd(str(tmp_path / "a.FCStd")), install=broken)
    assert m.freecad["status"] == "failed"
    assert m.parts == []


def test_finds_freecad_from_a_chosen_program(tmp_path):
    exe = ".exe" if sys.platform == "win32" else ""
    bindir = tmp_path / "FreeCAD 1.0" / "bin"
    bindir.mkdir(parents=True)
    for n in ("freecad", "freecadcmd"):
        (bindir / (n + exe)).write_text("")
    found = fc.find_freecad(str(bindir / ("freecad" + exe)))
    assert found.cmd == [str(bindir / ("freecadcmd" + exe))]
    assert found.gui == [str(bindir / ("freecad" + exe))]


# ------------------------------------------------------- with a real FreeCAD
WANT_REAL = bool(os.environ.get("PRINTVIEW3D_REAL_FREECAD"))
REAL = fc.find_freecad() if WANT_REAL else None

MAKE_DOC = r'''
import os, FreeCAD, Part
doc = FreeCAD.newDocument("Test")
part = doc.addObject("App::Part", "Part")
part.Placement.Base = FreeCAD.Vector(100, 0, 0)
box = doc.addObject("Part::Box", "Box"); box.Label = "Foot"
box.Length, box.Width, box.Height = 20, 10, 5
part.addObject(box)
cyl = doc.addObject("Part::Cylinder", "Cylinder"); cyl.Visibility = False
doc.recompute()
doc.saveAs(os.environ["OUT_FCSTD"])
os._exit(0)
'''


@pytest.mark.skipif(not WANT_REAL, reason="set PRINTVIEW3D_REAL_FREECAD=1 with FreeCAD installed")
def test_real_freecad(tmp_path, monkeypatch):
    assert REAL is not None, "PRINTVIEW3D_REAL_FREECAD is set but FreeCAD was not found"
    print("Using FreeCAD:", REAL)
    monkeypatch.setattr(fc, "cache_dir", lambda: str(tmp_path / "cache"))
    script, out = tmp_path / "make.py", tmp_path / "real.FCStd"
    script.write_text(MAKE_DOC)
    subprocess.run(REAL.cmd + [str(script)], env=dict(os.environ, OUT_FCSTD=str(out)), timeout=180,
                   stdin=subprocess.DEVNULL, capture_output=True)
    assert out.is_file(), "FreeCAD did not create the test document"
    m = fc.load_fcstd(str(out), install=REAL)
    assert m.freecad["status"] == "ok", m.freecad["error"]
    # Without GuiDocument.xml FreeCADCmd's own visibility flag decides; the box is shown,
    # moved by its Part container (x 100..120).
    assert [p.name for p in m.parts] == ["Foot"]
    v = m.parts[0].vertices
    assert abs(v[:, 0].min() - 100) < 0.01 and abs(v[:, 0].max() - 120) < 0.01


# ------------------------------------------------------------------ STEP files
STEP_HEADER = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('FreeCAD Model'),'2;1');
FILE_NAME('C:/Users/sevag/Desktop/Bracket.step','2026-10-21T01:20:00',('Sevag'),(
    'Workshop \\X2\\00E9\\X0\\t\\X2\\00E9\\X0\\'),'Open CASCADE STEP processor 7.8','FreeCAD','Unknown');
FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));
ENDSEC;
DATA;
#1 = APPLICATION_PROTOCOL_DEFINITION('international standard','automotive_design',2000,#2);
ENDSEC;
END-ISO-10303-21;
"""


def make_step(path):
    with open(path, "w", newline="\n") as f:
        f.write(STEP_HEADER)
    return path


def test_step_file_kind():
    assert file_kind("a.STEP") == "step" and file_kind("a.stp") == "step"


def test_step_header_without_freecad(tmp_path, monkeypatch):
    monkeypatch.setattr(fc, "find_freecad", lambda *_a: None)
    m = load_file(make_step(str(tmp_path / "b.step")))
    assert m.parts == [] and m.freecad["status"] == "no_freecad" and m.freecad["source"] == "step"
    assert m.meta == {"Format": "STEP AP214", "Created with": "FreeCAD", "Designer": "Sevag",
                      "Organization": "Workshop été", "Date": "2026-10-21 01:20"}


def test_not_a_step_file(tmp_path):
    p = tmp_path / "x.stp"
    p.write_text("solid nope\n")
    with pytest.raises(ValueError, match="not a STEP file"):
        load_file(str(p))


def test_step_through_freecad(tmp_path, fake_install, monkeypatch):
    path = make_step(str(tmp_path / "b.step"))
    m = fc.load_step(path, install=fake_install)
    assert m.freecad["status"] == "ok", m.freecad["error"]
    assert [p.name for p in m.parts] == ["Solid 1", "Solid 2"]      # fake FreeCAD: no STEP importer
    assert m.bounds()[0] == 0 and m.bounds()[1] == 30
    assert m.meta["Format"] == "STEP AP214"
    monkeypatch.setattr(fc.subprocess, "run", lambda *a, **k: pytest.fail("FreeCAD started again"))
    assert len(fc.load_step(path, install=fake_install).parts) == 2   # from the cache


MAKE_STEP = r'''
import os, FreeCAD, Part, Import
doc = FreeCAD.newDocument("Test")
part = doc.addObject("App::Part", "Part"); part.Label = "Assembly"
part.Placement.Base = FreeCAD.Vector(100, 0, 0)
box = doc.addObject("Part::Box", "Box"); box.Label = "Foot"
box.Length, box.Width, box.Height = 20, 10, 5
cyl = doc.addObject("Part::Cylinder", "Cylinder"); cyl.Label = "Peg"
cyl.Radius, cyl.Height = 2, 15
cyl.Placement.Base = FreeCAD.Vector(10, 5, 5)
part.addObject(box); part.addObject(cyl)
doc.recompute()
Import.export([part], os.environ["OUT_STEP"])
# What FreeCAD itself reads back from the file: the reference for PrintView3D.
bb = Part.read(os.environ["OUT_STEP"]).BoundBox
import json
json.dump([bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax], open(os.environ["OUT_STEP"] + ".json", "w"))
os._exit(0)
'''


@pytest.mark.skipif(not WANT_REAL, reason="set PRINTVIEW3D_REAL_FREECAD=1 with FreeCAD installed")
def test_real_freecad_step(tmp_path, monkeypatch):
    assert REAL is not None, "PRINTVIEW3D_REAL_FREECAD is set but FreeCAD was not found"
    monkeypatch.setattr(fc, "cache_dir", lambda: str(tmp_path / "cache"))
    script, out = tmp_path / "make_step.py", tmp_path / "real.step"
    script.write_text(MAKE_STEP)
    subprocess.run(REAL.cmd + [str(script)], env=dict(os.environ, OUT_STEP=str(out)), timeout=180,
                   stdin=subprocess.DEVNULL, capture_output=True)
    assert out.is_file(), "FreeCAD did not create the test STEP file"
    m = fc.load_step(str(out), install=REAL)
    assert m.freecad["status"] == "ok", m.freecad["error"]
    import json
    ref = json.load(open(str(out) + ".json"))
    b = m.bounds()
    print("\nSTEP parts:", [p.name for p in m.parts], "named:", m.freecad.get("named_parts"),
          "bounds:", [round(x, 2) for x in b], "FreeCAD reads:", [round(x, 2) for x in ref], "details:", m.meta)
    assert len(m.parts) == 2
    assert all(abs(x - y) < 0.05 for x, y in zip(b, ref))     # exactly where FreeCAD puts it
    assert abs((b[1] - b[0]) - 20) < 0.05 and abs((b[5] - b[4]) - 20) < 0.05   # box + peg sizes
    assert {p.name for p in m.parts} == {"Foot", "Peg"}      # names from the file kept


def test_export_stl_from_a_freecad_file(tmp_path, fake_install, monkeypatch):
    """Export STL is offered for a FreeCAD file shown in 3D, and saves the solids FreeCAD made."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QFileDialog
    app = QApplication.instance() or QApplication([])  # noqa: F841
    from printview3d.loaders import mesh as mesh_loader
    from printview3d.settings import Settings
    from printview3d.ui import main_window as mw
    from printview3d.ui.export_stl import ExportStlDialog

    monkeypatch.setattr(fc, "find_freecad", lambda *a, **k: fake_install)
    out = tmp_path / "out.stl"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(out), "")))
    monkeypatch.setattr(ExportStlDialog, "exec", lambda self: ExportStlDialog.Accepted)   # all ticked
    monkeypatch.setattr(ExportStlDialog, "per_object", lambda self: False)

    w = mw.MainWindow(Settings(str(tmp_path / "settings.json")))
    try:
        w.load_sync(make_fcstd(str(tmp_path / "a.FCStd")))
        assert w.current_kind == "freecad" and len(w.model.parts) == 2
        assert w.act_export_stl.isVisible()                               # the action is offered
        assert "CAD" in w.act_export_stl.toolTip()
        w.export_stl()
        assert len(mesh_loader.load_stl(str(out)).parts[0].faces) == 24   # both boxes, 12 each
    finally:
        w.close()

    # Without FreeCAD there is no 3D model, so nothing to export: the button stays hidden.
    monkeypatch.setattr(fc, "find_freecad", lambda *a, **k: None)
    w = mw.MainWindow(Settings(str(tmp_path / "settings2.json")))
    try:
        w.load_sync(make_fcstd(str(tmp_path / "b.FCStd")))
        assert not w.act_export_stl.isVisible()
    finally:
        w.close()
