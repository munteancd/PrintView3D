# Runs INSIDE FreeCAD (FreeCADCmd), started by PrintView3D to turn the visible
# objects of a FreeCAD document into triangle meshes it can show.
#
# Input:  the JSON file named in the PRINTVIEW3D_FREECAD_JOB environment variable:
#         {"file": "...FCStd", "objects": ["Body", ...], "out_dir": "..."}
# Output: <out_dir>/<n>.stl per object and <out_dir>/result.json
# Nothing is written to the FreeCAD document; it is opened read-only and closed.

import json
import os
import traceback

result = {"objects": [], "errors": [], "version": ""}
out_dir = "."
try:
    import FreeCAD
    import Mesh

    result["version"] = ".".join(FreeCAD.Version()[:3])
    job = json.load(open(os.environ["PRINTVIEW3D_FREECAD_JOB"], encoding="utf-8"))
    out_dir = job["out_dir"]
    try:
        import MeshPart
    except ImportError:
        MeshPart = None

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
                deflection = max(0.01, shape.BoundBox.DiagonalLength * 0.0005)
                if MeshPart is not None:
                    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=deflection,
                                                  AngularDeflection=0.35, Relative=False)
                else:
                    mesh = Mesh.Mesh(shape.tessellate(deflection))
            if mesh.CountFacets == 0:
                continue
            path = os.path.join(out_dir, "%d.stl" % i)
            mesh.write(path)
            result["objects"].append({"name": name, "label": obj.Label, "stl": path})
        except Exception as e:  # keep going with the other objects
            result["errors"].append("%s: %s" % (name, e))
    FreeCAD.closeDocument(doc.Name)
except Exception:
    result["errors"].append(traceback.format_exc())

with open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8") as f:
    json.dump(result, f)
os._exit(0)   # FreeCADCmd would otherwise wait in its console
