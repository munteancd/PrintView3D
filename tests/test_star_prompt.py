"""The one-time GitHub star message: new installs see it once, people updating never do."""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from printview3d.settings import Settings  # noqa: E402


def test_new_install_has_not_seen_it(tmp_path):
    s = Settings(str(tmp_path / "settings.json"))          # no settings file yet = new install
    assert s.get("star_prompt_shown") is False


def test_update_from_older_version_never_shows_it(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"language": "nl", "update_check": True}), encoding="utf-8")
    assert Settings(str(path)).get("star_prompt_shown") is True


def test_settings_saved_before_the_first_window_still_count_as_new(tmp_path):
    # e.g. "Send to slicer" from the Explorer menu right after installing, before ever opening PrintView3D
    path = str(tmp_path / "settings.json")
    Settings(path).set("slicer_id", "orca")
    assert Settings(path).get("star_prompt_shown") is False


def test_shown_once_is_remembered(tmp_path):
    path = str(tmp_path / "settings.json")
    s = Settings(path)
    s.set("star_prompt_shown", True)
    assert Settings(path).get("star_prompt_shown") is True
