"""Stand-in for FreeCADCmd in the tests: runs a script with tiny fake
'FreeCAD' and 'Mesh' modules (every object becomes a 10 mm cube, moved by
its index), so the conversion pipeline can be tested without FreeCAD."""

import os
import runpy
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
runpy.run_path(sys.argv[1], run_name="__main__")
