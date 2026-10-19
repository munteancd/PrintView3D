import zipfile
import xml.etree.ElementTree as ET


def Version():
    return ["9", "9", "9", "fake"]


class _BoundBox:
    DiagonalLength = 17.3


class _Shape:
    def __init__(self, offset):
        self.offset = offset
        self.Faces = [1, 2, 3, 4, 5, 6]
        self.BoundBox = _BoundBox()
        self.Placement = None

    def copy(self):
        return self

    def tessellate(self, _tol):
        o = self.offset
        pts = [(x + o, y, z) for x in (0, 10) for y in (0, 10) for z in (0, 10)]
        tris = [(0, 2, 1), (1, 2, 3), (4, 5, 6), (5, 7, 6), (0, 1, 4), (1, 5, 4),
                (2, 6, 3), (3, 6, 7), (0, 4, 2), (2, 4, 6), (1, 3, 5), (3, 7, 5)]
        return pts, tris


class _Obj:
    def __init__(self, name, label, i):
        self.Name, self.Label = name, label
        self.Shape = _Shape(i * 20)

    def isDerivedFrom(self, _t):
        return False

    def getGlobalPlacement(self):
        return None


class _Doc:
    Name = "fake"

    def __init__(self, path):
        root = ET.fromstring(zipfile.ZipFile(path).read("Document.xml"))
        self.objs = {}
        for i, o in enumerate(root.find("Objects")):
            self.objs[o.get("name")] = _Obj(o.get("name"), o.get("name"), i)

    def getObject(self, name):
        return self.objs.get(name)


def openDocument(path):
    return _Doc(path)


def closeDocument(_name):
    pass
