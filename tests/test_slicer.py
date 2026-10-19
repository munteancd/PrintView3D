"""Tests for slicer detection and selection (no GUI, no Windows needed)."""

import os
import stat
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from printview3d import slicer as sl  # noqa: E402
from printview3d.settings import Settings  # noqa: E402


def _fake_exe(folder, name):
    # On Windows, PATH lookups only find files with an extension like .exe
    if sys.platform == "win32" and not name.lower().endswith(".exe"):
        name += ".exe"
    p = os.path.join(folder, name)
    with open(p, "w") as f:
        f.write("#!/bin/sh\n")
    os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC)
    return p


@pytest.fixture
def settings(tmp_path):
    return Settings(str(tmp_path / "settings.json"))


@pytest.fixture(autouse=True)
def isolate_from_this_pc(monkeypatch):
    """Ignore slicers really installed on the test machine (registry / Program Files).

    Without this, the tests depend on what happens to be installed: on a PC with
    Creality Print, 'nothing installed' would find it.
    """
    monkeypatch.setattr(sl, "_registry_candidates", lambda s: [])
    monkeypatch.setattr(sl, "_folder_candidates", lambda s: [])


@pytest.fixture
def fake_path(tmp_path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    monkeypatch.setenv("PATH", str(bindir))
    return str(bindir)


def test_every_slicer_has_a_name_and_exe():
    ids = [s.id for s in sl.SLICERS]
    assert len(ids) == len(set(ids))
    for s in sl.SLICERS:
        assert s.name and s.exe_names and s.keywords


def test_nothing_installed(settings, fake_path):
    assert sl.resolve(settings) == ("", "slicer", None)


def test_first_installed_is_default(settings, fake_path):
    exe = _fake_exe(fake_path, "orca-slicer")
    sid, name, path = sl.resolve(settings)
    assert (sid, name) == ("orcaslicer", "OrcaSlicer")
    assert os.path.samefile(path, exe)


def test_explicit_choice_wins(settings, fake_path):
    _fake_exe(fake_path, "orca-slicer")
    prusa = _fake_exe(fake_path, "prusa-slicer")
    settings.set("slicer_id", "prusaslicer")
    assert sl.resolve(settings)[0] == "prusaslicer"
    assert os.path.samefile(sl.resolve(settings)[2], prusa)
    # a one-off request for another slicer
    assert sl.resolve(settings, "orcaslicer")[0] == "orcaslicer"


def test_chosen_but_missing(settings, fake_path):
    settings.set("slicer_id", "bambu_studio")
    assert sl.resolve(settings) == ("bambu_studio", "Bambu Studio", None)


def test_manual_path(settings, fake_path, tmp_path):
    exe = _fake_exe(str(tmp_path), "MyCreality.exe")
    settings.set("slicer_id", "creality_print")
    settings.set("slicer_paths", {"creality_print": exe})
    assert sl.resolve(settings)[2] == exe


def test_custom_slicer(settings, tmp_path):
    exe = _fake_exe(str(tmp_path), "superslicer.exe")
    settings.set("slicer_id", sl.CUSTOM)
    settings.set("custom_slicer", {"name": "SuperSlicer", "path": exe})
    assert sl.resolve(settings) == (sl.CUSTOM, "SuperSlicer", exe)


def test_migrate_old_creality_path(settings, tmp_path):
    exe = _fake_exe(str(tmp_path), "CrealityPrint.exe")
    settings.set("slicer_path", exe)
    sl.migrate_settings(settings)
    assert settings.get("slicer_id") == "creality_print"
    assert settings.get("slicer_paths") == {"creality_print": exe}
    assert settings.get("slicer_path") == ""


@pytest.mark.parametrize("name,ok", [
    ("orca-slicer.exe", True), ("Uninstall.exe", False), ("prusa-gcodeviewer.exe", False),
    ("prusa-slicer-console.exe", False), ("CuraEngine.exe", False),
])
def test_helper_programs_are_skipped(tmp_path, name, ok):
    p = _fake_exe(str(tmp_path), name)
    assert sl._usable(p) is ok


def test_folder_scan_finds_renamed_exe(tmp_path):
    folder = str(tmp_path)
    _fake_exe(folder, "unins000.exe")
    exe = _fake_exe(folder, "ElegooSlicer-v1.exe")
    assert sl._exe_in_folder(sl.BY_ID["elegoo_slicer"], folder) == [exe]
