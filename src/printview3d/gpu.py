"""Graphics card information and the Windows "high performance GPU" setting.

Laptops with two GPUs (e.g. Intel + NVIDIA) start most programs on the
slower built-in GPU. 3D viewing is much smoother on the dedicated GPU.
Windows stores the per-program choice (Settings > System > Display >
Graphics) under HKCU\\Software\\Microsoft\\DirectX\\UserGpuPreferences; we
write the same value, so it can also be changed back there.
"""

from __future__ import annotations

import re
import sys

_KEY = r"Software\Microsoft\DirectX\UserGpuPreferences"


def renderer_info(plotter) -> dict[str, str]:
    """Which GPU/driver VTK is actually drawing with."""
    info = {}
    try:
        text = plotter.ren_win.ReportCapabilities()
    except Exception:
        return info
    for key, label in (("OpenGL vendor string", "Vendor"),
                       ("OpenGL renderer string", "GPU"),
                       ("OpenGL version string", "OpenGL")):
        m = re.search(re.escape(key) + r":\s*(.+)", text)
        if m:
            info[label] = m.group(1).strip()
    return info


def looks_integrated(gpu_name: str) -> bool:
    n = gpu_name.lower()
    return any(k in n for k in ("intel", "uhd", "iris", "llvmpipe", "microsoft basic", "gdi generic"))


def is_supported() -> bool:
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def high_performance_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY) as k:
            val, _ = winreg.QueryValueEx(k, sys.executable)
            return "GpuPreference=2" in str(val)
    except OSError:
        return False


def set_high_performance(enabled: bool) -> None:
    """Ask Windows to run this program on the dedicated GPU (takes effect after restart)."""
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _KEY, 0, winreg.KEY_SET_VALUE) as k:
        if enabled:
            winreg.SetValueEx(k, sys.executable, 0, winreg.REG_SZ, "GpuPreference=2;")
        else:
            try:
                winreg.DeleteValue(k, sys.executable)
            except OSError:
                pass
