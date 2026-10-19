"""Small JSON settings store.

Windows:  %APPDATA%\\PrintView3D\\settings.json
Others:   ~/.config/printview3d/settings.json
"""

from __future__ import annotations

import json
import os
import sys

DEFAULTS = {
    "slicer_id": "",            # default slicer; empty = first installed one
    "slicer_paths": {},         # {slicer_id: exe} picked manually in Settings
    "custom_slicer": {},        # {"name": ..., "path": ...} for any other program
    "slicer_path": "",          # v0.1/v0.2 setting, migrated into slicer_paths
    "recent_files": [],
    "show_travel": False,
    "show_bed": True,
    "max_recent": 10,
}


def settings_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "PrintView3D")
    return os.path.join(os.path.expanduser("~"), ".config", "printview3d")


class Settings:
    def __init__(self, path: str | None = None):
        self.path = path or os.path.join(settings_dir(), "settings.json")
        self.data = dict(DEFAULTS)
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                stored = json.load(f)
            if isinstance(stored, dict):
                self.data.update(stored)
        except (OSError, ValueError):
            pass

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
            os.replace(tmp, self.path)
        except OSError:
            pass

    def get(self, key, default=None):
        return self.data.get(key, DEFAULTS.get(key, default))

    def set(self, key, value):
        self.data[key] = value
        self.save()

    def add_recent(self, path: str):
        path = os.path.abspath(path)
        recent = [p for p in self.get("recent_files", []) if os.path.normcase(p) != os.path.normcase(path)]
        recent.insert(0, path)
        self.set("recent_files", recent[: int(self.get("max_recent", 10))])

    def clear_recent(self):
        self.set("recent_files", [])
