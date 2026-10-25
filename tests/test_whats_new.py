"""'What's new' once after an update: which versions, and when it is shown."""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from printview3d import __version__  # noqa: E402
from printview3d import updates as up  # noqa: E402
from printview3d.settings import Settings  # noqa: E402

LOG = """# Changelog

## 0.20.0
- Twenty, see [the guide](docs/TRANSLATING.md) and [GitHub](https://github.com/x).

## 0.19.1
- Nineteen one.

## 0.19.0
- Nineteen.

## 0.18.0
- Eighteen.
"""


def test_only_versions_since_the_old_one_up_to_this_one():
    got = [v for v, _ in up.notes_since("0.18.0", "0.19.1", LOG)]
    assert got == ["0.19.1", "0.19.0"]


def test_repository_links_become_full_urls():
    (_, notes), = up.notes_since("0.19.1", "0.20.0", LOG)
    assert "](https://github.com/sevagjb/PrintView3D/blob/main/docs/TRANSLATING.md)" in notes
    assert "](https://github.com/x)" in notes


def test_bundled_changelog_has_this_version():
    assert __version__ in [v for v, _ in up.changelog_sections(up.changelog_text())]


def test_new_install_shows_nothing_but_records_the_version(tmp_path):
    s = Settings(str(tmp_path / "settings.json"))
    assert up.just_updated(s, "0.18.0") == ""
    assert s.get("last_run_version") == "0.18.0"


def test_update_shows_once(tmp_path):
    path = str(tmp_path / "settings.json")
    Settings(path).set("last_run_version", "0.18.0")
    s = Settings(path)
    assert up.just_updated(s, "0.19.0") == "0.18.0"
    assert up.just_updated(Settings(path), "0.19.0") == ""      # next start: nothing


def test_update_from_before_018_counts_as_017(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"language": "ar"}), encoding="utf-8")
    assert up.just_updated(Settings(str(path)), "0.18.0") == "0.17.0"


def test_going_back_to_an_older_version_shows_nothing(tmp_path):
    path = str(tmp_path / "settings.json")
    Settings(path).set("last_run_version", "0.19.0")
    assert up.just_updated(Settings(path), "0.18.0") == ""
