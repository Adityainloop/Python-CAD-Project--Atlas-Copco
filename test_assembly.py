"""
test_assembly.py - Run: python test_assembly.py
Tests assembly with plate_with_holes, fastener_for_plate, screw_for_plate
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Hardcode the 3 correct files
files = [
    "fastener_for_plate.step",
    "plate_with_holes.step",
    "screw_for_plate.step",
]

# Verify they exist
for f in files:
    if not os.path.exists(f):
        print(f"ERROR: {f} not found in project folder!")
        sys.exit(1)

print(f"Using files: {files}")
print()

from assembler import AssemblyEngine
from ai_assembly_engine import _rule_based_parse, build_parts_context
from geometry_analyzer import analyze_part
from part_model import PartModel
from step_loader import load_step

def cb(msg, pct):
    print(f"  [{pct:3d}%] {msg}")

# First show geometry of each file
print("="*60)
print("GEOMETRY OF EACH FILE:")
print("="*60)
for f in files:
    p = PartModel(file_path=f)
    p.shape = load_step(f)
    if p.is_loaded:
        analyze_part(p)
        print(f"\n{f}:")
        print(f"  type={p.part_type} bbox={p.bbox_dims}")
        print(f"  holes={len(p.holes)} shafts={len(p.shafts)}")
        for c in p.cylinders:
            print(f"  {'HOLE' if c.is_hole else 'SHAFT'} d={c.diameter:.2f}mm "
                  f"center=({c.center[0]:.2f},{c.center[1]:.2f},{c.center[2]:.2f}) "
                  f"axis={c.axis_dir}")

print()
print("="*60)
print("RUNNING ASSEMBLY")
print("="*60)

prompt = "insert screw 20mm into middle hole, insert fastener 10mm into edge hole"
print(f"Prompt: {prompt}")
print()

# Build context and parse
parts_ctx = []
for fp in files:
    p = PartModel(file_path=fp)
    p.shape = load_step(fp)
    if p.is_loaded:
        analyze_part(p)
        parts_ctx.append(p)

parts_info = build_parts_context(parts_ctx)
ops = _rule_based_parse(prompt, parts_info)
print(f"Parsed {len(ops)} operations:")
for i, op in enumerate(ops):
    print(f"  Op{i+1}: hole='{op.hole_description}' depth={op.insertion_depth}mm strategy={op.strategy}")
print()

# Run assembly
engine = AssemblyEngine(progress_cb=cb)
engine.load_parts(files)
engine.set_instruction(ops)
result = engine.run()

print()
print("="*60)
print(f"Success: {result.get('success')}")
for res in result.get("pair_results", []):
    print(f"  {res['part_a']} -> {res['part_b']}")
    print(f"    strategy={res['strategy']} conf={res['confidence']:.0%} fit={res.get('fit_class','')}")
    print(f"    translation={tuple(round(x,2) for x in res['translation'])}")
    print(f"    collision={res['collision']}")