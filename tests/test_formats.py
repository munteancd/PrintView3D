"""OBJ, PLY, OFF and glTF / GLB readers (no GUI needed)."""

import base64
import json
import os
import struct
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)

import make_samples  # noqa: E402
from printview3d.freecad import export_stl  # noqa: E402
from printview3d.loaders import SEND_AS_STL, file_kind, load_file, load_stl  # noqa: E402

DATA = os.path.join(HERE, "data")


@pytest.fixture(scope="module", autouse=True)
def samples():
    make_samples.main()


def signed_volume(part):
    v, f = part.vertices.astype(np.float64), part.faces
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)


def size(m):
    b = m.bounds()
    return round(b[1] - b[0], 3), round(b[3] - b[2], 3), round(b[5] - b[4], 3)


# ---------------------------------------------------------------- the sample files
@pytest.mark.parametrize("name,parts,dims", [
    ("two_parts.obj", ["Red cube", "Green block"], (50, 20, 20)),
    ("cube_binary.ply", ["cube_binary"], (20, 20, 20)),
    ("quads_ascii.ply", ["quads_ascii"], (20, 20, 20)),
    ("cube_colors.off", ["cube_colors"], (20, 20, 20)),
    ("two_nodes.glb", ["Left cube", "Right cube"], (50, 20, 20)),
    ("embedded.gltf", ["Big cube"], (40, 40, 40)),
])
def test_samples(name, parts, dims):
    m = load_file(os.path.join(DATA, name))
    assert [p.name for p in m.parts] == parts
    assert size(m) == dims
    for p in m.parts:
        assert len(p.faces) == 12                      # quads were split into triangles
        assert signed_volume(p) > 0                    # outside faces out (Z up for glTF)


def test_obj_materials():
    m = load_file(os.path.join(DATA, "two_parts.obj"))
    assert [p.color for p in m.parts] == ["#e63333", "#33cc4c"]


def test_ply_vertex_colors():
    p = load_file(os.path.join(DATA, "cube_binary.ply")).parts[0]
    assert p.vertex_colors.shape == (8, 3) and p.vertex_colors.dtype == np.uint8
    assert tuple(p.vertex_colors[1]) == (255, 128, 40)


def test_off_face_colors():
    p = load_file(os.path.join(DATA, "cube_colors.off")).parts[0]
    assert p.face_colors.shape == (12, 3)
    assert tuple(p.face_colors[0]) == (255, 0, 0) and tuple(p.face_colors[-1]) == (255, 0, 255)


def test_gltf_material_and_meta():
    m = load_file(os.path.join(DATA, "two_nodes.glb"))
    assert m.parts[0].color == "#e75959"               # baseColorFactor 0.8/0.1/0.1 (linear) as sRGB
    assert m.meta["Created with"] == "PrintView3D sample"
    assert m.bounds()[4] == pytest.approx(0) and m.bounds()[5] == pytest.approx(20)


def test_send_as_stl_kinds():
    assert {file_kind("x.ply"), file_kind("x.off"), file_kind("x.glb"), file_kind("x.gltf")} <= set(SEND_AS_STL)
    assert "obj" not in SEND_AS_STL                    # slicers read OBJ themselves


def test_export_round_trip(tmp_path):
    m = load_file(os.path.join(DATA, "two_nodes.glb"))
    out = export_stl(m.parts, str(tmp_path / "x.stl"))
    back = load_stl(out)
    assert back.n_triangles == 24 and size(back) == (50, 20, 20)


# ---------------------------------------------------------------- OBJ details
def test_obj_groups_vertex_colors_and_no_mtl(tmp_path):
    p = tmp_path / "g.obj"
    p.write_text("mtllib missing.mtl\ng first\n"
                 "v 0 0 0 1 0 0\nv 1 0 0 1 0 0\nv 0 1 0 1 0 0\nf 1 2 3\n"
                 "g second\nv 0 0 1 0 0 1\nv 1 0 1 0 0 1\nv 0 1 1 0 0 1\nf -3//1 -2//1 -1//1\n")
    m = load_file(str(p))
    assert [x.name for x in m.parts] == ["first", "second"]
    assert [x.color for x in m.parts] == ["#ff0000", "#0000ff"]   # one colour each: no per-vertex array
    assert all(len(x.vertices) == 3 for x in m.parts)               # each part keeps only its vertices


def test_obj_bad_index(tmp_path):
    p = tmp_path / "bad.obj"
    p.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 9\n")
    with pytest.raises(ValueError, match="do not exist"):
        load_file(str(p))


# ---------------------------------------------------------------- PLY details
def test_ply_big_endian_mixed_polygons(tmp_path):
    v = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 1)]
    head = ("ply\nformat binary_big_endian 1.0\nelement vertex 5\nproperty double x\nproperty double y\n"
            "property double z\nelement face 2\nproperty list uchar uint vertex_indices\n"
            "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n")
    data = head.encode()
    for x in v:
        data += struct.pack(">ddd", *x)
    data += struct.pack(">BIIIIBBB", 4, 0, 3, 2, 1, 10, 20, 30)       # a quad, then a triangle
    data += struct.pack(">BIIIBBB", 3, 0, 1, 4, 40, 50, 60)
    p = tmp_path / "be.ply"
    p.write_bytes(data)
    part = load_file(str(p)).parts[0]
    assert len(part.faces) == 3
    assert [tuple(c) for c in part.face_colors] == [(10, 20, 30), (10, 20, 30), (40, 50, 60)]


def test_ply_point_cloud(tmp_path):
    p = tmp_path / "pts.ply"
    p.write_text("ply\nformat ascii 1.0\nelement vertex 2\nproperty float x\nproperty float y\n"
                 "property float z\nend_header\n0 0 0\n1 1 1\n")
    with pytest.raises(ValueError, match="point cloud"):
        load_file(str(p))


# ---------------------------------------------------------------- OFF details
def test_coff_counts_on_first_line(tmp_path):
    p = tmp_path / "c.off"
    p.write_text("COFF 3 1 0\n0 0 0 1 0 0 1\n1 0 0 1 0 0 1\n0 1 0 1 0 0 1\n3 0 1 2\n")
    part = load_file(str(p)).parts[0]
    assert part.color == "#ff0000" and len(part.faces) == 1


def test_binary_off_is_refused(tmp_path):
    p = tmp_path / "b.off"
    p.write_bytes(b"OFF BINARY\n" + b"\0" * 12)
    with pytest.raises(ValueError, match="Binary OFF"):
        load_file(str(p))


# ---------------------------------------------------------------- glTF details
def _gltf(tmp_path, doc, buf, external=False, name="t.gltf"):
    if external:
        (tmp_path / "t.bin").write_bytes(buf)
        doc["buffers"] = [{"byteLength": len(buf), "uri": "t.bin"}]
    else:
        doc["buffers"] = [{"byteLength": len(buf),
                           "uri": "data:application/octet-stream;base64," + base64.b64encode(buf).decode()}]
    p = tmp_path / name
    p.write_text(json.dumps(doc))
    return str(p)


def _strip_doc(stride_pad=0, mode=5, color=False):
    """Two triangles as a strip, positions interleaved with padding (byteStride)."""
    pts = [(0, 0, 0), (0.01, 0, 0), (0, 0.01, 0), (0.01, 0.01, 0)]
    buf = b"".join(struct.pack("<fff", *pt) + b"\0" * stride_pad for pt in pts)
    acc = [{"bufferView": 0, "componentType": 5126, "count": 4, "type": "VEC3"}]
    views = [{"buffer": 0, "byteLength": len(buf), "byteStride": 12 + stride_pad}]
    attrs = {"POSITION": 0}
    if color:
        cols = bytes([255, 0, 0, 255] * 4)
        views.append({"buffer": 0, "byteOffset": len(buf), "byteLength": len(cols)})
        acc.append({"bufferView": 1, "componentType": 5121, "normalized": True, "count": 4, "type": "VEC4"})
        attrs["COLOR_0"] = 1
        buf += cols
    doc = {"asset": {"version": "2.0"}, "nodes": [{"mesh": 0}], "scenes": [{"nodes": [0]}],
           "meshes": [{"primitives": [{"attributes": attrs, "mode": mode}]}],
           "accessors": acc, "bufferViews": views}
    return doc, buf


def test_gltf_strip_interleaved_external_bin(tmp_path):
    doc, buf = _strip_doc(stride_pad=4)
    m = load_file(_gltf(tmp_path, doc, buf, external=True))
    p = m.parts[0]
    assert len(p.faces) == 2 and p.color is None               # no material: PrintView3D's own colour
    assert size(m) == (10, 0, 10)                              # 1 cm in metres -> 10 mm; Y up -> Z up


def test_gltf_normalized_vertex_colors(tmp_path):
    doc, buf = _strip_doc(color=True)
    p = load_file(_gltf(tmp_path, doc, buf)).parts[0]
    assert p.color == "#ff0000"


def test_gltf_missing_bin(tmp_path):
    doc, buf = _strip_doc()
    path = _gltf(tmp_path, doc, buf, external=True)
    os.remove(tmp_path / "t.bin")
    with pytest.raises(ValueError, match="missing"):
        load_file(path)


def test_gltf_draco_is_explained(tmp_path):
    doc, buf = _strip_doc()
    doc["extensionsRequired"] = ["KHR_draco_mesh_compression"]
    with pytest.raises(ValueError, match="Draco"):
        load_file(_gltf(tmp_path, doc, buf))


def test_gltf_written_in_millimetres(tmp_path):
    doc, buf = _strip_doc()
    doc["nodes"][0]["scale"] = [2000, 2000, 2000]              # 20 m if metres: really 20 mm
    assert size(load_file(_gltf(tmp_path, doc, buf))) == (20, 0, 20)


def test_gltf_mirrored_node_keeps_orientation(tmp_path):
    with open(os.path.join(DATA, "embedded.gltf")) as f:
        doc = json.load(f)
    doc["nodes"][0]["scale"] = [-2, 2, 2]
    p = tmp_path / "m.gltf"
    p.write_text(json.dumps(doc))
    assert signed_volume(load_file(str(p)).parts[0]) > 0


def test_uncoloured_parts_become_grey_next_to_coloured_ones(tmp_path):
    p = tmp_path / "mix.obj"
    (tmp_path / "mix.mtl").write_text("newmtl blue\nKd 0 0 1\n")
    p.write_text("mtllib mix.mtl\no a\nusemtl blue\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n"
                 "o b\nusemtl textured_only\nv 0 0 1\nv 1 0 1\nv 0 1 1\nf 4 5 6\n")
    assert [x.color for x in load_file(str(p)).parts] == ["#0000ff", "#c8c8c8"]
