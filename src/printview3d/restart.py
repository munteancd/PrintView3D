"""Restarting PrintView3D, for settings that only take effect at start
(window transparency, graphics card).

The new start gets the open file back and --new-window, so it never hands the file to the window
that is just closing (see single_instance).
"""

from __future__ import annotations

import os
import sys


def command(file: str | None = None, frozen: bool | None = None,
            environ: dict | None = None) -> tuple[str, list[str]]:
    """(program, arguments) that start this PrintView3D again."""
    frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    environ = os.environ if environ is None else environ
    if frozen:
        # Linux AppImage: sys.executable lives inside the AppImage's mount, which goes away when
        # this copy exits; $APPIMAGE is the AppImage file itself.
        program, args = environ.get("APPIMAGE") or sys.executable, []
    else:                                       # running from source
        program, args = sys.executable, ["-m", "printview3d"]
    if file:
        args.append(os.path.abspath(file))
    args.append("--new-window")
    return program, args
