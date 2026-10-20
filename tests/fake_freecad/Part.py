"""Fake 'Part' module: Part.read() of any file gives two 10 mm cubes (x 0..10 and 20..30)."""
from FreeCAD import _Shape


class _Compound:
    def __init__(self):
        self.Solids = [_Shape(0), _Shape(20)]
        self.Shells = []


def read(_path):
    return _Compound()
