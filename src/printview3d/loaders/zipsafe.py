"""Reading parts of ZIP-based files (3MF, FreeCAD) with size limits.

3MF and FreeCAD files are ZIPs. A crafted file can declare a tiny packed part that unpacks to
gigabytes (a "ZIP bomb") and fill the memory. Python's zipfile never unpacks more than the size
a part declares, so checking that size (and how much it grows) before reading is enough.
archive.py uses the same limits for ZIP downloads.
"""

from __future__ import annotations

import zipfile

MAX_FILE_BYTES = 2 * 1024 ** 3       # one part (a large 3MF model can really be this big)
MAX_SMALL_BYTES = 64 * 1024 ** 2     # pictures, settings, FreeCAD's document XML
MAX_RATIO = 400                      # unpacked / packed size; plain mesh data rarely passes 20
RATIO_CHECK_FROM = 64 * 1024 ** 2    # the ratio only matters for parts bigger than this


def too_big(info: zipfile.ZipInfo, limit: int = MAX_FILE_BYTES) -> bool:
    """True when a part is larger than `limit` or grows suspiciously much when unpacked."""
    if info.file_size > limit:
        return True
    return bool(info.file_size > RATIO_CHECK_FROM and info.compress_size
                and info.file_size / info.compress_size > MAX_RATIO)


def read(z: zipfile.ZipFile, name: str, limit: int = MAX_FILE_BYTES) -> bytes:
    """z.read(name), refused with ValueError when the part is too large (KeyError if missing)."""
    info = z.getinfo(name)
    if too_big(info, limit):
        raise ValueError("This file contains a part that unpacks to far more data than a 3D file "
                         "normally does. It was not opened, to protect your computer.")
    return z.read(info)
