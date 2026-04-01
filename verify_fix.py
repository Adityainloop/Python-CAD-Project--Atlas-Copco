"""
verify_fix.py - Run this to confirm the fix is installed AND working.
python verify_fix.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Check 1: Is the new assembler.py installed?
import assembler, inspect
src = inspect.getsource(assembler.AssemblyEngine._by_hole)
has_depth_fix = 'hole_depth / 2' in src and 'direct translate' in src
has_sort = 'loaded.sort' in inspect.getsource(assembler.AssemblyEngine.run)
print(f"[{'OK' if has_depth_fix else 'FAIL'}] _by_hole has depth centering fix: {has_depth_fix}")
print(f"[{'OK' if has_sort else 'FAIL'}] run() has anchor sort: {has_sort}")

# Check 2: Simulate the exact transform
import math
print()
print("=== Simulating fastener -> middle hole ===")
shaft_center = (0,0,0)
shaft_axis = (0,1,0)
hole_center = (20,0,0)   # OCC location = entry face
hole_axis = (-1,0,0)
hole_depth = 20.0        # plate thickness

# Step 1: rotate shaft axis to hole axis
dot = sum(a*b for a,b in zip(shaft_axis, hole_axis))
rx = shaft_axis[1]*hole_axis[2] - shaft_axis[2]*hole_axis[1]
ry = shaft_axis[2]*hole_axis[0] - shaft_axis[0]*hole_axis[2]
rz = shaft_axis[0]*hole_axis[1] - shaft_axis[1]*hole_axis[0]
rmag = math.sqrt(rx**2+ry**2+rz**2)
angle_deg = math.degrees(math.acos(max(-1,min(1,abs(dot)))))
print(f"  Rotation: {angle_deg:.0f}° around ({rx/rmag:.2f},{ry/rmag:.2f},{rz/rmag:.2f})")
print(f"  Shaft axis {shaft_axis} -> aligns with hole axis {hole_axis}")

# Step 2: shaft center stays at (0,0,0) after rotation (rotation is around origin)
rsc = (0,0,0)

# Step 3: translate to hole entry
tx = hole_center[0] - rsc[0]
ty = hole_center[1] - rsc[1]
tz = hole_center[2] - rsc[2]
print(f"  Before depth offset: translate=({tx},{ty},{tz})")

# Step 4: offset half-depth along hole axis INTO hole
hax,hay,haz = hole_axis
tx += hax * (hole_depth/2)
ty += hay * (hole_depth/2)
tz += haz * (hole_depth/2)
print(f"  After depth offset:  translate=({tx},{ty},{tz})")
print(f"  Shaft center ends at ({tx},{ty},{tz})")
print(f"  Plate runs X=0 to X=20. Shaft (30mm long) runs X={tx-15:.0f} to X={tx+15:.0f}")
print(f"  Shaft {'GOES THROUGH PLATE' if tx-15 < 0 and tx+15 > 20 else 'CENTERED IN PLATE' if 0 < tx < 20 else 'OUTSIDE PLATE!'}")

print()
print("=== Now running actual assembly ===")
from assembler import AssemblyEngine
from ai_assembly_engine import _rule_based_parse, build_parts_context
from geometry_analyzer import analyze_part
from part_model import PartModel
from step_loader import load_step

files = ['fastener_for_plate.step', 'plate_with_holes.step', 'screw_for_plate.step']
for f in files:
    if not os.path.exists(f):
        print(f"ERROR: {f} not found! Copy it to project folder.")
        sys.exit(1)

def cb(msg,pct): 
    if any(k in msg for k in ['direct','translate','Anchor','hole=','Assembling','complete']):
        print(f"  [{pct}%] {msg}")

engine = AssemblyEngine(progress_cb=cb)
engine.load_parts(files)

parts_ctx = []
for fp in files:
    p = PartModel(file_path=fp); p.shape = load_step(fp)
    if p.is_loaded: analyze_part(p); parts_ctx.append(p)

ops = _rule_based_parse("insert screw 20mm into middle hole, insert fastener 10mm into edge hole",
                         build_parts_context(parts_ctx))
engine.set_instruction(ops)
result = engine.run()

print()
print("=== RESULTS ===")
for r in result.get('pair_results', []):
    t = r['translation']
    print(f"  {r['part_b']}: translate=({t[0]:.1f},{t[1]:.1f},{t[2]:.1f}) fit={r.get('fit_class','')}")
    
print()
print("If translations show (10,0,0) and (10,0,-30) -> fix is working correctly")
print("Run 'python gui_app.py' and the viewer should show shafts through holes")