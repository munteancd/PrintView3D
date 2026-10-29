"""The Export STL button: a click does what Settings -> Files says, the arrow's menu offers
all three ways (one STL, one STL per object, choose objects), for 3MF and FreeCAD files."""

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from printview3d import freecad as fc  # noqa: E402
from printview3d.loaders import mesh as mesh_loader  # noqa: E402
from printview3d.settings import EXPORT_MODES, Settings  # noqa: E402
from test_freecad import fake_install, make_fcstd  # noqa: E402,F401  (fixture used by name)

HERE = os.path.dirname(os.path.abspath(__file__))
TWO_PARTS = os.path.join(HERE, "data", "two_parts.3mf")


@pytest.fixture
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, tmp_path):
    """window(mode) gives a main window. Every window is closed and really deleted afterwards,
    so later tests don't run with a pile of left-over windows (each with a 3D view)."""
    from PySide6.QtCore import QEvent
    from printview3d.ui import main_window as mw
    made = []

    def make(mode=None):
        s = Settings(str(tmp_path / "settings.json"))
        if mode is not None:
            s.set("export_mode", mode)
        w = mw.MainWindow(s)
        made.append(w)
        return w

    yield make
    for w in made:
        w.close()
        w.deleteLater()
    app.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()


@pytest.fixture
def saving(tmp_path, monkeypatch):
    """Answer the save dialogs without showing them, and count every way the export can go."""
    from PySide6.QtWidgets import QFileDialog
    from printview3d.ui.export_stl import ExportStlDialog

    calls = {"save": 0, "folder": 0, "dialog": 0}
    one = tmp_path / "one.stl"
    each = tmp_path / "each"
    each.mkdir()

    def save_name(*a, **k):
        calls["save"] += 1
        return str(one), ""

    def folder(*a, **k):
        calls["folder"] += 1
        return str(each)

    def dialog_exec(self):
        calls["dialog"] += 1
        return ExportStlDialog.Accepted                     # all objects ticked

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(save_name))
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(folder))
    monkeypatch.setattr(ExportStlDialog, "exec", dialog_exec)
    monkeypatch.setattr(ExportStlDialog, "per_object", lambda self: False)
    return calls, one, each


def _wait_for_export(app, w, timeout=20.0):
    """3MF objects are read in the background; wait until the button is usable again."""
    end = time.time() + timeout
    while not w.act_export_stl.isEnabled() and time.time() < end:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()
    assert w.act_export_stl.isEnabled()


def _faces(path):
    return len(mesh_loader.load_stl(str(path)).parts[0].faces)


def test_default_setting_is_the_dialog(tmp_path):
    s = Settings(str(tmp_path / "settings.json"))
    assert s.get("export_mode") == "dialog"
    assert EXPORT_MODES == ("dialog", "combined", "per_object")


def test_button_has_a_menu_with_all_ways(window):
    from PySide6.QtWidgets import QToolButton
    w = window()
    assert w.export_btn.popupMode() == QToolButton.MenuButtonPopup
    acts = [a for a in w.export_menu.actions() if not a.isSeparator()]
    assert acts == [w.act_export_one, w.act_export_each, w.act_export_choose, w.act_export_setting]
    assert all(a.text() for a in acts)
    # Nothing open: no button, and Ctrl+E does nothing.
    assert not w.act_export_stl.isVisible() and not w.export_btn_act.isVisible()
    w.load_sync(os.path.join(HERE, "data", "cube_binary.stl"))
    assert not w.export_btn_act.isVisible()               # STL -> STL makes no sense
    w.load_sync(TWO_PARTS)
    assert w.act_export_stl.isVisible() and w.export_btn_act.isVisible()


@pytest.mark.parametrize("mode,bold", [("dialog", "act_export_choose"), ("combined", "act_export_one"),
                                       ("per_object", "act_export_each"), ("nonsense", "act_export_choose")])
def test_menu_shows_what_a_click_does_in_bold(window, mode, bold):
    w = window(mode)
    w._mark_export_default()
    assert w.export_menu.defaultAction() is getattr(w, bold)


@pytest.mark.parametrize("mode", ["dialog", "combined", "per_object"])
def test_click_follows_the_setting_3mf(app, window, saving, mode):
    calls, one, each = saving
    w = window(mode)
    w.load_sync(TWO_PARTS)
    w.act_export_stl.trigger()                            # same as a click or Ctrl+E
    _wait_for_export(app, w)
    if mode == "per_object":
        assert calls == {"save": 0, "folder": 1, "dialog": 0}
        assert len(os.listdir(each)) == 2
    else:
        assert calls == {"save": 1, "folder": 0, "dialog": 1 if mode == "dialog" else 0}
        assert one.exists()


def test_menu_choices_3mf(app, window, saving):
    """Whatever the setting, each menu choice does its own thing."""
    calls, one, each = saving
    w = window("per_object")
    w.load_sync(TWO_PARTS)
    w.act_export_one.trigger()
    _wait_for_export(app, w)
    assert calls == {"save": 1, "folder": 0, "dialog": 0}
    two_in_one = _faces(one)

    w.act_export_choose.trigger()
    _wait_for_export(app, w)
    assert calls == {"save": 2, "folder": 0, "dialog": 1}

    w.act_export_each.trigger()
    _wait_for_export(app, w)
    assert calls == {"save": 2, "folder": 1, "dialog": 1}
    files = sorted(os.listdir(each))
    assert len(files) == 2
    assert sum(_faces(os.path.join(each, f)) for f in files) == two_in_one


def test_per_object_asks_before_replacing(app, window, saving, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    calls, one, each = saving
    asked = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: asked.append(self.text()) or 0)
    w = window()
    w.load_sync(TWO_PARTS)
    w.act_export_each.trigger()
    _wait_for_export(app, w)
    assert not asked
    stamps = {f: os.path.getmtime(each / f) for f in os.listdir(each)}
    w.act_export_each.trigger()                           # the same files again: asked, Cancel
    _wait_for_export(app, w)
    assert len(asked) == 1
    assert stamps == {f: os.path.getmtime(each / f) for f in os.listdir(each)}   # untouched


@pytest.mark.parametrize("mode", ["dialog", "combined", "per_object"])
def test_click_follows_the_setting_freecad(window, tmp_path, saving, fake_install, monkeypatch, mode):  # noqa: F811
    calls, one, each = saving
    monkeypatch.setattr(fc, "find_freecad", lambda *a, **k: fake_install)
    w = window(mode)
    w.load_sync(make_fcstd(str(tmp_path / "a.FCStd")))
    assert w.current_kind == "freecad" and len(w.model.parts) == 2
    assert w.export_btn_act.isVisible()
    w.act_export_stl.trigger()
    if mode == "per_object":
        assert calls == {"save": 0, "folder": 1, "dialog": 0}
        files = sorted(os.listdir(each))
        assert len(files) == 2 and all(_faces(os.path.join(each, f)) == 12 for f in files)
    else:
        assert calls == {"save": 1, "folder": 0, "dialog": 1 if mode == "dialog" else 0}
        assert _faces(one) == 24                          # both boxes, 12 triangles each


def test_one_object_is_saved_straight_away(window, saving, monkeypatch):
    """A file with one object: every way goes straight to Save, no list and no folder."""
    calls, one, each = saving
    w = window("per_object")
    w.load_sync(TWO_PARTS)
    part = w.model.parts[0]
    monkeypatch.setattr(w, "current_kind", "freecad")     # export the parts as shown
    monkeypatch.setattr(w.model, "parts", [part])
    for act in (w.act_export_stl, w.act_export_each, w.act_export_choose, w.act_export_one):
        act.trigger()
    assert calls == {"save": 4, "folder": 0, "dialog": 0}


@pytest.mark.parametrize("platform", ["linux", "darwin"])   # the two Files page layouts
def test_setting_in_the_settings_window(app, tmp_path, monkeypatch, platform):
    """The choice is on the Files page and OK saves it. On a Mac the Files page has no
    "Opening files" box; OK must still work there (it used to fail)."""
    from printview3d.ui import settings_dialog as sd
    monkeypatch.setattr(sd.sys, "platform", platform)
    s = Settings(str(tmp_path / "settings.json"))
    dlg = sd.SettingsDialog(s, page="files")
    try:
        assert dlg.export_combo.currentData() == "dialog"
        assert [dlg.export_combo.itemData(i) for i in range(dlg.export_combo.count())] == list(EXPORT_MODES)
        dlg.export_combo.setCurrentIndex(dlg.export_combo.findData("per_object"))
        dlg._save()
    finally:
        dlg.deleteLater()
    assert Settings(str(tmp_path / "settings.json")).get("export_mode") == "per_object"
    again = sd.SettingsDialog(s)
    try:
        assert again.export_combo.currentData() == "per_object"
    finally:
        again.deleteLater()
        app.processEvents()
