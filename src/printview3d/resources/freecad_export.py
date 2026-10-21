# Runs INSIDE FreeCAD (FreeCADCmd), started by PrintView3D to turn CAD shapes
# into triangle meshes it can show.
#
# Input:  the JSON file named in the PRINTVIEW3D_FREECAD_JOB environment variable:
#         FreeCAD document: {"file": "...FCStd", "objects": ["Body", ...], "out_dir": "..."}
#         STEP file:        {"file": "...step", "type": "step", "out_dir": "..."}
# Output: <out_dir>/<n>.stl per object and <out_dir>/result.json
# Nothing is written to the input file; it is opened read-only and closed.

import json
import os
import traceback

result = {"objects": [], "errors": [], "version": ""}
out_dir = "."

# STEP import: containers whose shape is just the sum of their children
CONTAINERS = ("App::Part", "App::DocumentObjectGroup", "App::LinkGroup", "App::Origin",
              "App::Line", "App::Plane", "App::Point")


def to_mesh(shape):
    import Mesh
    try:
        import MeshPart
    except ImportError:
        MeshPart = None
    deflection = max(0.01, shape.BoundBox.DiagonalLength * 0.0005)
    if MeshPart is not None:
        return MeshPart.meshFromShape(Shape=shape, LinearDeflection=deflection,
                                      AngularDeflection=0.35, Relative=False)
    return Mesh.Mesh(shape.tessellate(deflection))


def write(i, mesh, name, label):
    if mesh.CountFacets == 0:
        return
    path = os.path.join(out_dir, "%d.stl" % i)
    mesh.write(path)
    result["objects"].append({"name": name, "label": label, "stl": path})


def convert_fcstd(job):
    import FreeCAD
    doc = FreeCAD.openDocument(job["file"])
    for i, name in enumerate(job["objects"]):
        obj = doc.getObject(name)
        if obj is None:
            continue
        try:
            if obj.isDerivedFrom("Mesh::Feature"):
                mesh = obj.Mesh.copy()
            else:
                shape = obj.Shape.copy()
                if hasattr(obj, "getGlobalPlacement"):
                    # Includes the placement of parent Part containers.
                    shape.Placement = obj.getGlobalPlacement()
                if not shape.Faces:
                    continue
                mesh = to_mesh(shape)
            write(i, mesh, name, obj.Label)
        except Exception as e:  # keep going with the other objects
            result["errors"].append("%s: %s" % (name, e))
    FreeCAD.closeDocument(doc.Name)


def _step_parts(path):
    """[(label, shape)] with the part names from the file, through FreeCAD's STEP import.
    None when that import is not available or gives something unexpected."""
    import FreeCAD
    try:
        import Import
    except ImportError:
        return None
    prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Import")
    old = prefs.GetBool("UseLinkGroup", True)
    prefs.SetBool("UseLinkGroup", False)          # plain parts, no App::Link instances
    doc = FreeCAD.newDocument("PrintView3DStep")
    try:
        Import.insert(path, doc.Name)
        doc.recompute()
        parts = []
        for obj in doc.Objects:
            if obj.TypeId in CONTAINERS or obj.TypeId.startswith("App::Link"):
                continue
            shape = getattr(obj, "Shape", None)
            if shape is None or shape.isNull() or not shape.Faces:
                continue
            # A compound made of other imported objects: its children are listed themselves.
            if any(getattr(c, "TypeId", "") not in CONTAINERS and getattr(c, "Shape", None) is not None
                   for c in obj.OutList):
                continue
            s = shape.copy()
            if hasattr(obj, "getGlobalPlacement"):
                s.Placement = obj.getGlobalPlacement()
            parts.append((obj.Label, s))
        return parts or None
    except Exception as e:
        result["errors"].append("STEP import: %s" % e)
        return None
    finally:
        prefs.SetBool("UseLinkGroup", old)
        FreeCAD.closeDocument(doc.Name)


def _same_box(parts, whole):
    """The named parts must fill the same space as the whole file read in one go."""
    import FreeCAD
    bb = FreeCAD.BoundBox()
    for _label, s in parts:
        bb.add(s.BoundBox)
    ref = whole.BoundBox
    tol = max(0.01, ref.DiagonalLength * 0.01)
    return all(abs(a - b) <= tol for a, b in zip(
        (bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax),
        (ref.XMin, ref.YMin, ref.ZMin, ref.XMax, ref.YMax, ref.ZMax)))


def convert_step(job):
    import Part
    whole = Part.read(job["file"])                # always right: positions resolved by OpenCASCADE
    parts = _step_parts(job["file"])
    if parts is None or not _same_box(parts, whole):
        solids = whole.Solids or whole.Shells or [whole]
        parts = [("Solid %d" % (i + 1), s) for i, s in enumerate(solids)] if len(solids) > 1 \
            else [(os.path.splitext(os.path.basename(job["file"]))[0], whole)]
        result["fallback"] = True
    for i, (label, shape) in enumerate(parts):
        try:
            write(i, to_mesh(shape), label, label)
        except Exception as e:
            result["errors"].append("%s: %s" % (label, e))


try:
    import FreeCAD

    result["version"] = ".".join(FreeCAD.Version()[:3])
    job = json.load(open(os.environ["PRINTVIEW3D_FREECAD_JOB"], encoding="utf-8"))
    out_dir = job["out_dir"]
    if job.get("type") == "step":
        convert_step(job)
    else:
        convert_fcstd(job)
except Exception:
    result["errors"].append(traceback.format_exc())

with open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8") as f:
    json.dump(result, f)
os._exit(0)   # FreeCADCmd would otherwise wait in its console
