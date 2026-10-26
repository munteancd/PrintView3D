"""ZIP files: which files are used, safety limits, unpacking and the Show all grid."""

import os
import sys
import zipfile

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from printview3d import archive  # noqa: E402
from printview3d.loaders import MeshPart, ModelData, load_file  # noqa: E402

CUBE_STL = b"""solid cube
facet normal 0 0 1
 outer loop
  vertex 0 0 0
  vertex 10 0 0
  vertex 0 20 5
 endloop
endfacet
endsolid cube
"""
GCODE = b"G28\nG1 Z0.2 F600\nG1 X10 Y10 E1 F1200\nG1 X20 Y10 E2\n"


@pytest.fixture(autouse=True)
def private_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(archive, "cache_root", lambda: str(tmp_path / "cache"))


def make_zip(path, files: dict):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return str(path)


def test_only_3d_files_are_used(tmp_path):
    z = make_zip(tmp_path / "kit.zip", {
        "files/base.stl": CUBE_STL, "files/lid.stl": CUBE_STL, "base.gcode": GCODE,
        "images/photo.jpg": b"\xff\xd8", "README.txt": b"hi", "Printables.url": b"[InternetShortcut]",
        "__MACOSX/files/._base.stl": b"x", ".DS_Store": b"x", "inner.zip": b"PK",
        "LICENSE.pdf": b"%PDF",
    })
    c = archive.read_contents(z)
    assert [e.name for e in c.entries] == ["base.stl", "lid.stl", "base.gcode"]   # models first
    assert [e.kind for e in c.entries] == ["stl", "stl", "gcode"]
    assert c.skipped == 5                     # photo, readme, link, nested zip, pdf (hidden ones silently)
    assert [e.name for e in c.arrangeable] == ["base.stl", "lid.stl"]


def test_unpacked_files_open_and_stay_in_the_cache(tmp_path):
    z = make_zip(tmp_path / "kit.zip", {"a/part.stl": CUBE_STL, "../../evil.stl": CUBE_STL})
    c = archive.open_archive(z)
    cache = str(tmp_path / "cache")
    for e in c.entries:
        assert os.path.abspath(e.path).startswith(os.path.abspath(cache))
        assert load_file(e.path).n_triangles == 1
    assert not (tmp_path.parent / "evil.stl").exists()


def test_same_names_show_their_folder(tmp_path):
    z = make_zip(tmp_path / "kit.zip", {"small/arm.stl": CUBE_STL, "large/arm.stl": CUBE_STL})
    names = sorted(e.name for e in archive.read_contents(z).entries)
    assert names == ["large/arm.stl", "small/arm.stl"]


def test_natural_order(tmp_path):
    z = make_zip(tmp_path / "kit.zip", {f"part{i}.stl": CUBE_STL for i in (10, 2, 1)})
    assert [e.name for e in archive.read_contents(z).entries] == ["part1.stl", "part2.stl", "part10.stl"]


def test_not_a_zip(tmp_path):
    p = tmp_path / "fake.zip"
    p.write_bytes(b"not a zip")
    with pytest.raises(archive.ArchiveError):
        archive.read_contents(str(p))


def test_zip_bomb_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(archive, "RATIO_CHECK_FROM", 1000)
    z = make_zip(tmp_path / "bomb.zip", {"huge.stl": b"\0" * 2_000_000})   # compresses ~1000x
    with pytest.raises(archive.ArchiveError):
        archive.read_contents(z)


def test_too_large_file_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(archive, "MAX_FILE_BYTES", 100)
    z = make_zip(tmp_path / "big.zip", {"big.stl": CUBE_STL})
    with pytest.raises(archive.ArchiveError):
        archive.read_contents(z)


@pytest.mark.parametrize("n,cols", [(1, 1), (2, 2), (3, 3), (4, 2), (5, 3), (6, 3), (7, 3), (9, 3),
                                    (10, 4), (16, 4), (17, 5)])
def test_grid_columns(n, cols):
    assert archive.grid_columns(n) == cols


def _box(w, d, h, z0=5.0):
    v = np.array([[0, 0, z0], [w, 0, z0], [0, d, z0], [w, d, z0 + h]], dtype=np.float32)
    return ModelData(parts=[MeshPart("p", v, np.array([[0, 1, 2], [1, 3, 2]], dtype=np.int64))])


def test_arrange_grid_without_overlap():
    models = [(f"m{i}", _box(10 + 10 * i, 20, 5)) for i in range(4)]       # 4 -> 2 x 2
    merged, owner = archive.arrange(models, gap=10.0)
    assert owner == [0, 1, 2, 3]
    boxes = []
    for p in merged.parts:
        mn, mx = p.vertices.min(axis=0), p.vertices.max(axis=0)
        assert abs(mn[2]) < 1e-5                                           # standing on the plate
        boxes.append((mn[0], mx[0], mn[1], mx[1]))
    ys = sorted({round(b[2], 3) for b in boxes})
    assert len(ys) == 2                                                    # two rows
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            overlap = a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3]
            assert not overlap, (i, j)
    # first model at the back left
    assert boxes[0][0] < boxes[1][0] and boxes[0][2] > boxes[2][2]


def test_arrange_keeps_parts_of_a_project_together():
    two = ModelData(parts=_box(10, 10, 5).parts + _box(4, 4, 4).parts)
    merged, owner = archive.arrange([("kit.3mf", two), ("knob.stl", _box(5, 5, 5))])
    assert owner == [0, 0, 1]
    assert merged.parts[0].name.startswith("kit.3mf — ")
    assert merged.parts[2].name == "knob.stl"


def test_zip_in_the_window(tmp_path):
    """Open a ZIP in the main window: list, Show all, files to send, and a one-model ZIP."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from printview3d.settings import Settings
    from printview3d.ui.main_window import MainWindow

    data = os.path.join(HERE, "data")
    kit = make_zip(tmp_path / "kit.zip", {
        "a/cube.stl": open(os.path.join(data, "cube_binary.stl"), "rb").read(),
        "b/two.3mf": open(os.path.join(data, "two_parts.3mf"), "rb").read(),
        "c/print.gcode": open(os.path.join(data, "cylinder.gcode"), "rb").read(),
        "photo.jpg": b"\xff\xd8",
    })
    settings = Settings(str(tmp_path / "settings.json"))
    w = MainWindow(settings)
    try:
        w.load_sync(kit)
        assert [e.kind for e in w.zip.entries] == ["3mf", "stl", "gcode"]
        assert w.zip.skipped == 1 and w._zip_index == 0 and w.current_kind == "3mf"
        assert "kit.zip" in w.windowTitle()
        assert settings.get("recent_files")[0] == os.path.abspath(kit)     # the ZIP, not the cache
        assert w._user_folder() == str(tmp_path)

        w.zip_show_all(sync=True)
        assert w.current_kind == "zip" and w._zip_index == -1
        assert set(w._zip_owner) == {0, 1}                                  # G-code left out
        assert [os.path.basename(f) for f in w._show_all_files()] == ["two.3mf", "cube.stl"]

        w._open_zip_entry(2, sync=True)
        assert w.current_kind == "gcode" and w.gcode is not None

        one = make_zip(tmp_path / "one.zip", {"only.stl": open(os.path.join(data, "cube_binary.stl"), "rb").read(),
                                              "readme.txt": b"x"})
        w.load_sync(one)
        assert w.current_kind == "stl" and not w.zip_box.isVisibleTo(w)
        assert settings.get("recent_files")[0] == os.path.abspath(one)

        w.load_sync(os.path.join(data, "cube_binary.stl"))                  # a normal file again
        assert w.zip is None
    finally:
        w.close()
        app.processEvents()


def test_zip_labels_follow_the_theme(tmp_path):
    """Switching theme recolours the type labels of the ZIP list (light text on dark themes)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QLabel
    app = QApplication.instance() or QApplication([])
    from printview3d.settings import Settings
    from printview3d.ui.main_window import MainWindow, _TYPE_TAGS

    stl = open(os.path.join(HERE, "data", "cube_binary.stl"), "rb").read()
    kit = make_zip(tmp_path / "kit.zip", {"a.stl": stl, "b.stl": stl})
    w = MainWindow(Settings(str(tmp_path / "settings.json")))
    try:
        def stl_label_style():
            app.processEvents()
            labels = [l for l in w.zip_box.findChildren(QLabel) if l.text() == "STL" and l.isVisibleTo(w)]
            assert labels
            return labels[0].styleSheet()

        w.apply_theme("light")
        w.load_sync(kit)
        assert _TYPE_TAGS["stl"][3] in stl_label_style()          # dark text on the light theme
        w.apply_theme("dark")
        assert _TYPE_TAGS["stl"][2] in stl_label_style()          # light text on the dark theme
    finally:
        w.close()
        app.processEvents()
