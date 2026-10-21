"""Windows taskbar: tell Windows which icon, name and command belong to the PrintView3D window.

PrintView3D gives itself an app ID (app.APP_USER_MODEL_ID) so its windows are grouped as one
program. The taskbar then looks for the icon of that ID: in a Start-menu shortcut with the same ID
(the installer makes one), and otherwise in these window properties. Without either, a running or
pinned PrintView3D shows a generic icon. Setting them on the window also makes pinning work for the
portable zip, which has no shortcut.

Everything here is best effort: if anything fails, the window simply keeps Windows' default.
"""

from __future__ import annotations

import sys


def set_window_identity(hwnd: int, app_id: str, display_name: str) -> bool:
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return False             # only for the real PrintView3D.exe (not python.exe in development)
    try:
        return _set(hwnd, app_id, display_name, sys.executable)
    except Exception:            # noqa: BLE001 - never let the taskbar break the program
        return False


def read_window_identity(hwnd: int) -> dict:
    """The four properties as Windows reports them for the window (for the CI self-test)."""
    return _set(hwnd, "", "", "", read_only=True)


def _set(hwnd: int, app_id: str, display_name: str, exe: str, read_only: bool = False):
    import ctypes
    from ctypes import POINTER, Structure, byref, c_ulong, c_ushort, c_void_p, c_wchar_p, wintypes

    class GUID(Structure):
        _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                    ("Data4", ctypes.c_ubyte * 8)]

    def guid(s: str) -> GUID:
        import uuid
        u = uuid.UUID(s)
        g = GUID(u.time_low, u.time_mid, u.time_hi_version)
        for i, b in enumerate(u.bytes[8:]):
            g.Data4[i] = b
        return g

    class PROPERTYKEY(Structure):
        _fields_ = [("fmtid", GUID), ("pid", wintypes.DWORD)]

    class PROPVARIANT(Structure):            # only the VT_LPWSTR case is used
        _fields_ = [("vt", c_ushort), ("r1", c_ushort), ("r2", c_ushort), ("r3", c_ushort),
                    ("pwszVal", c_wchar_p), ("pad", c_void_p)]

    VT_LPWSTR = 31
    fmt = "{9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}"           # System.AppUserModel.*
    ID, RELAUNCH_COMMAND, RELAUNCH_ICON, RELAUNCH_NAME = 5, 2, 3, 4

    store = c_void_p()
    shgp = ctypes.windll.shell32.SHGetPropertyStoreForWindow
    shgp.argtypes = [wintypes.HWND, POINTER(GUID), POINTER(c_void_p)]
    iid = guid("{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}")    # IID_IPropertyStore
    if shgp(hwnd, byref(iid), byref(store)) != 0 or not store:
        return False

    vtbl = ctypes.cast(ctypes.cast(store, POINTER(c_void_p))[0], POINTER(c_void_p))
    proto = ctypes.WINFUNCTYPE
    release = proto(c_ulong, c_void_p)(vtbl[2])
    get_value = proto(ctypes.HRESULT, c_void_p, POINTER(PROPERTYKEY), POINTER(PROPVARIANT))(vtbl[5])
    set_value = proto(ctypes.HRESULT, c_void_p, POINTER(PROPERTYKEY), POINTER(PROPVARIANT))(vtbl[6])
    commit = proto(ctypes.HRESULT, c_void_p)(vtbl[7])
    try:
        if read_only:
            names = {ID: "id", RELAUNCH_COMMAND: "command", RELAUNCH_ICON: "icon", RELAUNCH_NAME: "name"}
            out = {}
            clear = ctypes.windll.ole32.PropVariantClear
            for pid, name in names.items():
                key = PROPERTYKEY(guid(fmt), pid)
                pv = PROPVARIANT()
                get_value(store, byref(key), byref(pv))
                out[name] = pv.pwszVal if pv.vt == VT_LPWSTR else None
                clear(byref(pv))
            return out
        # The relaunch properties first; the app ID last (Windows applies them when the ID is set).
        for pid, value in ((RELAUNCH_COMMAND, f'"{exe}"'), (RELAUNCH_ICON, f"{exe},0"),
                           (RELAUNCH_NAME, display_name), (ID, app_id)):
            key = PROPERTYKEY(guid(fmt), pid)
            pv = PROPVARIANT(VT_LPWSTR, 0, 0, 0, value, None)
            set_value(store, byref(key), byref(pv))           # raises OSError on a failure HRESULT
        commit(store)
        return True
    finally:
        release(store)
