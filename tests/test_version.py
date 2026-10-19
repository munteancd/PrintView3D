"""The version must be the same everywhere a build or installer reads it."""

import os
import re

from printview3d import __version__

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_pyproject_matches():
    text = open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8").read()
    assert re.search(r'^version = "(.+?)"', text, re.M).group(1) == __version__


def test_changelog_has_entry():
    text = open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read()
    assert f"## {__version__}" in text
