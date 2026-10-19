import struct


class Mesh:
    def __init__(self, data):
        self.pts, self.tris = data
        self.CountFacets = len(self.tris)

    def write(self, path):
        with open(path, "wb") as f:
            f.write(b"\0" * 80 + struct.pack("<I", len(self.tris)))
            for t in self.tris:
                f.write(struct.pack("<3f", 0, 0, 0))
                for k in t:
                    f.write(struct.pack("<3f", *self.pts[k]))
                f.write(b"\0\0")
