"""Colour themes: settings, migration for existing users, live switching."""

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication  # noqa: E402

from printview3d.settings import Settings  # noqa: E402
from printview3d.ui import theme  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_new_install_follows_system(tmp_path):
    assert Settings(str(tmp_path / "settings.json")).get("theme") == "auto"


def test_existing_users_keep_dark(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"language": "en", "recent_files": []}))
    assert Settings(str(p)).get("theme") == "dark"


def test_saved_choice_is_kept(tmp_path):
    p = tmp_path / "settings.json"
    s = Settings(str(p))
    s.set("theme", "light")
    assert Settings(str(p)).get("theme") == "light"


def test_all_themes_have_the_same_colour_keys():
    keys = set(theme.THEMES["dark"])
    for name, colours in theme.THEMES.items():
        assert set(colours) == keys, name
        for value in colours.values():
            assert value.startswith("#") and len(value) == 7


@pytest.mark.parametrize("name", ["dark", "gray", "light"])
def test_apply_theme(app, name):
    assert theme.apply_theme(app, name) == name
    assert theme.current() == name
    assert app.palette().window().color().name() == theme.THEMES[name]["window"]


def test_auto_resolves_to_a_real_theme(app):
    assert theme.apply_theme(app, "auto") in ("dark", "light")
    assert theme.setting() == "auto"


def test_unknown_value_falls_back_to_auto(app):
    theme.apply_theme(app, "purple")
    assert theme.setting() == "auto"


def test_graphite_is_offered_before_light():
    assert list(theme.THEME_NAMES) == ["auto", "dark", "gray", "graphite", "light"]


def test_next_theme_cycles_through_all():
    seen, t = [], "dark"
    for _ in range(4):
        t = theme.next_theme(t)
        seen.append(t)
    assert seen == ["gray", "graphite", "light", "dark"]
    assert theme.next_theme("auto") == "dark"


def test_theme_icon_draws(app):
    for name in theme.CYCLE:
        assert not theme.theme_icon(name).isNull()
