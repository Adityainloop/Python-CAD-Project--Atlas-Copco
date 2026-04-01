"""
assemble_knuckle.py
Directly assembles Fork End + Knuckle Joint Part with correct geometry.
Run: python assemble_knuckle.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import math
from OCC.Core.gp import gp_Trsf, gp_Vec, gp_Ax1, gp_Pnt, gp_Dir
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
from step_loader import load_step
from step_exporter import export_step
from OCC.Core.TopoDS import TopoDS_Compound
from OCC.Core.BRep import BRep_Builder

# Load parts
fork_file    = "Fork End.step"
knuckle_file = "Knuckle joint Part.step"

for f in [fork_file, knuckle_file]:
    if not os.path.exists(f):
        print(f"ERROR: {f} not found!")
        sys.exit(1)

print("Loading parts...")
fork    = load_step(fork_file)
knuckle = load_step(knuckle_file)
print("OK")

# ── Step 1: Rotate knuckle 90° around Z axis ──────────────────────────────
# Knuckle eye axis is (0,1,0), fork bore axis is (-1,0,0)
# Rotation: 90° around Z at knuckle eye center (40, 0, 55)
pivot = gp_Pnt(40.0, 0.0, 55.0)
z_axis = gp_Dir(0.0, 0.0, 1.0)
rot_ax = gp_Ax1(pivot, z_axis)

trsf_rot = gp_Trsf()
trsf_rot.SetRotation(rot_ax, math.radians(90.0))

knuckle_rot = BRepBuilderAPI_Transform(knuckle, trsf_rot, True).Shape()
print("Rotation applied: 90° around Z")

# After rotation, knuckle eye center transforms:
# (40,0,55) rotated 90° around Z at (40,0,55) = stays at (40,0,55)
# (the pivot IS the center, so center doesn't move)
# But axis (0,1,0) becomes (-1,0,0) ✓

# ── Step 2: Translate to align eye center with fork bore center ────────────
# Knuckle eye center after rotation: (40, 0, 55)
# Fork bore center: (-75, 0, 80)
# Translation needed: (-115, 0, 25)

tx = -75.0 - 40.0   # = -115
ty =   0.0 -  0.0   # =    0
tz =  80.0 - 55.0   # =   25

trsf_t = gp_Trsf()
trsf_t.SetTranslation(gp_Vec(tx, ty, tz))

knuckle_final = BRepBuilderAPI_Transform(knuckle_rot, trsf_t, True).Shape()
print(f"Translation applied: ({tx}, {ty}, {tz})")
print(f"Knuckle eye center now at: ({40+tx:.0f}, {0+ty:.0f}, {55+tz:.0f})")
print(f"Fork bore center:          (-75, 0, 80)")

# ── Build compound ─────────────────────────────────────────────────────────
builder = BRep_Builder()
compound = TopoDS_Compound()
builder.MakeCompound(compound)
builder.Add(compound, fork)
builder.Add(compound, knuckle_final)

export_step(compound, "assembled_knuckle.step")
print("\nAssembly saved: assembled_knuckle.step")
print("Open in 3D viewer to check!")

# ── Open viewer ────────────────────────────────────────────────────────────
try:
    from OCC.Display.SimpleGui import init_display
    display, start_display, _, __ = init_display()
    display.DisplayShape(fork,          color="RED",  update=False)
    display.DisplayShape(knuckle_final, color="BLUE", update=False)
    display.FitAll()
    print("Viewer open. Close window to exit.")
    start_display()
except Exception as e:
    print(f"Viewer error: {e}")
    print("Check assembled_knuckle.step in FreeCAD/Fusion360")