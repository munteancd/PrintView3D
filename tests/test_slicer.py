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
    real_linux, real_desktop = sl._linux_candidates, sl._desktop_candidates
    monkeypatch.setattr(sl, "_linux_candidates", lambda s, d=None: real_linux(s, d) if d is not None else [])
    monkeypatch.setattr(sl, "_desktop_candidates", lambda s, d=None: real_desktop(s, d) if d is not None else [])


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


# ---------------------------------------------------------------- Linux bits
linux_only = pytest.mark.skipif(sys.platform == "win32", reason="Linux file layout / permissions")


@linux_only
def test_linux_appimage_flatpak_and_opt(tmp_path):
    apps, flat, opt = tmp_path / "Applications", tmp_path / "flatpak", tmp_path / "opt"
    for d in (apps, flat, opt / "OrcaSlicer"):
        d.mkdir(parents=True)
    creality = _fake_exe(str(apps), "CrealityPrint_Ubuntu2404_V6.2.1.AppImage")
    _fake_exe(str(apps), "Bambu_Studio_linux_ubuntu-24.04_v02.02.00.AppImage")
    plain = apps / "OrcaSlicer_notes.txt"                 # not executable, not an AppImage
    plain.write_text("x")
    cura = _fake_exe(str(flat), "com.ultimaker.cura")
    orca_opt = _fake_exe(str(opt / "OrcaSlicer"), "orca-slicer")
    dirs = [str(apps), str(flat), str(opt)]
    assert sl._linux_candidates(sl.BY_ID["creality_print"], dirs) == [creality]
    assert sl._linux_candidates(sl.BY_ID["cura"], dirs) == [cura]
    assert sl._linux_candidates(sl.BY_ID["orcaslicer"], dirs) == [orca_opt]
    assert len(sl._linux_candidates(sl.BY_ID["bambu_studio"], dirs)) == 1
    assert sl._linux_candidates(sl.BY_ID["prusaslicer"], dirs) == []


@linux_only
def test_linux_skips_gcode_viewer(tmp_path):
    d = str(tmp_path)
    _fake_exe(d, "PrusaSlicer-gcodeviewer-2.8.AppImage")
    real = _fake_exe(d, "PrusaSlicer-2.8.1+linux-x64-GTK3.AppImage")
    assert sl._linux_candidates(sl.BY_ID["prusaslicer"], [d]) == [real]


@linux_only
def test_linux_desktop_entries(tmp_path):
    exe = _fake_exe(str(tmp_path), "orca-slicer-bin")
    apps = tmp_path / "applications"
    apps.mkdir()
    (apps / "orca-slicer.desktop").write_text(f'[Desktop Entry]\nName=OrcaSlicer\nExec="{exe}" %U\n')
    (apps / "flatpak-thing.desktop").write_text("[Desktop Entry]\nName=OrcaSlicer\nExec=flatpak run x %U\n")
    assert sl._desktop_candidates(sl.BY_ID["orcaslicer"], [str(apps)]) == [exe]


@linux_only
def test_newest_version_wins(tmp_path):
    d = str(tmp_path)
    _fake_exe(d, "OrcaSlicer_Linux_V2.1.0.AppImage")
    new = _fake_exe(d, "OrcaSlicer_Linux_V2.3.1.AppImage")
    cands = sl._linux_candidates(sl.BY_ID["orcaslicer"], [d])
    assert sorted(cands, key=sl._version_key, reverse=True)[0] == new


def test_clean_environment(monkeypatch):
    env = {"LD_LIBRARY_PATH": "/tmp/_MEI123", "LD_LIBRARY_PATH_ORIG": "/usr/lib/custom",
           "APPIMAGE": "/home/u/PrintView3D.AppImage", "APPDIR": "/tmp/.mount_X",
           "QT_PLUGIN_PATH": "/tmp/.mount_X/usr/plugins", "QT_QPA_PLATFORM": "xcb",
           "PRINTVIEW3D_SET_QPA": "1", "HOME": "/home/u", "QT_API": "pyside6"}
    out = sl.clean_environment(env)
    assert out["LD_LIBRARY_PATH"] == "/usr/lib/custom"
    for gone in ("APPIMAGE", "APPDIR", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM", "QT_API",
                 "LD_LIBRARY_PATH_ORIG", "PRINTVIEW3D_SET_QPA"):
        assert gone not in out
    assert out["HOME"] == "/home/u"


def test_user_choice_of_qt_platform_is_kept():
    out = sl.clean_environment({"QT_QPA_PLATFORM": "wayland"})
    assert out["QT_QPA_PLATFORM"] == "wayland"


def test_mac_apps_are_found_by_name(tmp_path):
    from printview3d import slicer as sl
    for name in ("OrcaSlicer.app", "Bambu Studio.app", "UltiMaker Cura.app", "Notes.app"):
        (tmp_path / name).mkdir()
    found = {s.id: sl._mac_candidates(s, [str(tmp_path)]) for s in sl.SLICERS}
    assert [os.path.basename(p) for p in found["orcaslicer"]] == ["OrcaSlicer.app"]
    assert [os.path.basename(p) for p in found["bambu_studio"]] == ["Bambu Studio.app"]
    assert [os.path.basename(p) for p in found["cura"]] == ["UltiMaker Cura.app"]
    assert found["prusaslicer"] == []
