"""Tests for the Linux desktop integration, using a temporary home folder."""

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from printview3d import assoc_linux as al  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="Linux only")


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("APPIMAGE", "/home/u/Apps/PrintView3D-x86_64.AppImage")
    # Pretend the desktop helper tools are missing so the test is the same everywhere.
    monkeypatch.setattr(al.shutil, "which", lambda name: None)
    return tmp_path


def test_register_writes_entry_mime_and_icon(home):
    al.register()
    entry = open(al.desktop_path()).read()
    assert 'Exec="/home/u/Apps/PrintView3D-x86_64.AppImage" %f' in entry
    assert "MimeType=model/stl;model/3mf;text/x.gcode;" in entry
    assert "PrefersNonDefaultGPU=true" in entry
    assert '<glob pattern="*.gcode"/>' in open(al.mime_package_path()).read()
    assert os.path.isfile(al.icon_install_path())
    assert al.is_registered()
    assert al.status()[".stl"] == 'In "Open With" (not default)'


def test_set_default_and_unregister(home):
    mimeapps = os.path.join(os.environ["XDG_CONFIG_HOME"], "mimeapps.list")
    os.makedirs(os.path.dirname(mimeapps))
    with open(mimeapps, "w") as f:
        f.write("[Default Applications]\nimage/png=org.gnome.eog.desktop\nmodel/stl=other.desktop\n")
    al.register()
    al.set_default()
    text = open(mimeapps).read()
    assert "model/stl=printview3d.desktop" in text and "other.desktop" not in text
    assert "image/png=org.gnome.eog.desktop" in text            # others untouched
    assert al.status()[".gcode"] == "Default app"

    al.unregister()
    text = open(mimeapps).read()
    assert "printview3d" not in text
    assert "image/png=org.gnome.eog.desktop" in text
    assert not al.is_registered()
    assert not os.path.exists(al.icon_install_path())


def _desktop_exec_args(value: str) -> list[str]:
    """Undo the quoting the way a desktop (GLib) reads an Exec= value: string escapes first,
    then the quoted arguments, then the %% field code."""
    value = value.replace("\\\\", "\\")
    args, cur, i, quoted = [], "", 0, False
    while i < len(value):
        c = value[i]
        if quoted and c == "\\" and i + 1 < len(value):
            cur += value[i + 1]
            i += 2
            continue
        if c == '"':
            quoted = not quoted
        elif c == " " and not quoted:
            args.append(cur)
            cur = ""
        else:
            cur += c
        i += 1
    args.append(cur)
    return [a.replace("%%", "%") for a in args]


@pytest.mark.parametrize("path", ["/opt/Print View/PrintView3D.AppImage",
                                  "/home/me/$HOME/100%/a`b`/q\"uote/back\\slash/PrintView3D.AppImage"])
def test_menu_entry_starts_odd_program_paths(path, monkeypatch):
    from printview3d import assoc_linux
    monkeypatch.setenv("APPIMAGE", path)
    args = _desktop_exec_args(assoc_linux.exec_line())
    assert args == [path, "%f"]
