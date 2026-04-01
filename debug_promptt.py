"""
debug_prompt.py
---------------
Run this to see EXACTLY what happens when you give a prompt.
Put this in your project folder and run:
  python debug_prompt.py part1.step part2.step "insert shaft 30mm deep"

It will print every single step so we can see where it breaks.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    if len(sys.argv) < 4:
        print("Usage: python debug_prompt.py part1.step part2.step \"your prompt\"")
        print('Example: python debug_prompt.py part1.step part2.step "insert shaft 30mm deep"')
        sys.exit(1)

    file1  = sys.argv[1]
    file2  = sys.argv[2]
    prompt = sys.argv[3]

    print("=" * 60)
    print("DEBUG: Prompt Assembly System")
    print("=" * 60)

    # Step 1: Test prompt parsing
    print(f"\n--- STEP 1: Parsing prompt ---")
    print(f"Prompt: \"{prompt}\"")
    from prompt_parser import parse_prompt
    inst = parse_prompt(prompt)
    print(f"  assembly_type    : {inst.assembly_type}")
    print(f"  insertion_depth  : {inst.insertion_depth}")
    print(f"  full_depth       : {inst.full_depth}")
    print(f"  press_fit        : {inst.press_fit}")
    print(f"  prefer_cylinder  : {inst.prefer_cylinder}")
    print(f"  prefer_plane     : {inst.prefer_plane}")
    print(f"  side_by_side     : {inst.side_by_side}")
    print(f"  gap              : {inst.gap}")
    print(f"  clearance        : {inst.clearance}")
    print(f"  confidence       : {inst.confidence:.0%}")

    if inst.confidence == 0.0:
        print("\n  *** WARNING: Prompt confidence is 0% — prompt was NOT understood ***")
        print("  Try one of these exact phrases:")
        print('    "insert shaft 30mm deep"')
        print('    "insert shaft fully through bearing"')
        print('    "press fit shaft"')
        print('    "place side by side"')
        print('    "mate flat faces flush"')

    # Step 2: Load parts
    print(f"\n--- STEP 2: Loading parts ---")
    from step_loader import load_step
    s1 = load_step(file1)
    s2 = load_step(file2)
    if s1 is None or s2 is None:
        print("ERROR: Could not load STEP files. Check paths.")
        sys.exit(1)

    # Step 3: Analyze parts
    print(f"\n--- STEP 3: Analyzing geometry ---")
    from part_model import PartModel
    from geometry_analyzer import analyze_part
    p1 = PartModel(file_path=file1); p1.shape = s1
    p2 = PartModel(file_path=file2); p2.shape = s2
    analyze_part(p1)
    analyze_part(p2)
    print(f"  Part1 ({p1.name}): type={p1.part_type}  "
          f"cylinders={len(p1.cylinders)}(holes={len(p1.holes)},shafts={len(p1.shafts)})  "
          f"planes={len(p1.planes)}")
    for c in p1.cylinders:
        print(f"    cyl: r={c.radius:.3f}  d={c.diameter:.3f}  "
              f"{'HOLE' if c.is_hole else 'SHAFT'}  "
              f"ax=({c.axis_dir[0]:.2f},{c.axis_dir[1]:.2f},{c.axis_dir[2]:.2f})")

    print(f"  Part2 ({p2.name}): type={p2.part_type}  "
          f"cylinders={len(p2.cylinders)}(holes={len(p2.holes)},shafts={len(p2.shafts)})  "
          f"planes={len(p2.planes)}")
    for c in p2.cylinders:
        print(f"    cyl: r={c.radius:.3f}  d={c.diameter:.3f}  "
              f"{'HOLE' if c.is_hole else 'SHAFT'}  "
              f"ax=({c.axis_dir[0]:.2f},{c.axis_dir[1]:.2f},{c.axis_dir[2]:.2f})")

    # Step 4: Find matches
    print(f"\n--- STEP 4: Finding matches (with prompt) ---")
    from smart_matcher import find_all_matches
    candidates = find_all_matches(p1, p2, inst)
    print(f"  Total candidates: {len(candidates)}")
    for i, c in enumerate(candidates[:5]):
        print(f"  [{i}] strategy={c['strategy']}  "
              f"conf={c['confidence']:.2f}  "
              f"{c['description']}")

    # Step 5: Check what assembler will do
    print(f"\n--- STEP 5: Assembly decision ---")
    if not candidates:
        print("  NO CANDIDATES — will use BBox fallback")
    else:
        best = candidates[0]
        print(f"  Best match: {best['strategy']}  conf={best['confidence']:.2f}")
        if best['strategy'] == 'cylinder':
            shaft = best['shaft']
            hole  = best['hole']
            depth = inst.insertion_depth if inst.insertion_depth else 0.0
            full  = inst.full_depth
            print(f"  Shaft: d={shaft.diameter:.3f}  center={shaft.center}")
            print(f"  Hole:  d={hole.diameter:.3f}  center={hole.center}")
            print(f"  insertion_depth from prompt: {depth}")
            print(f"  full_depth: {full}")
            if depth > 0:
                print(f"  >>> Shaft will be positioned {depth}mm inside hole <<<")
            elif full:
                print(f"  >>> Shaft will be centered through hole <<<")
            else:
                print(f"  >>> Default: shaft centered through hole <<<")

    # Step 6: Run actual assembly
    print(f"\n--- STEP 6: Running assembly ---")
    from assembler import AssemblyEngine
    def cb(msg, pct): print(f"  [{pct:3d}%] {msg}")
    engine = AssemblyEngine(progress_cb=cb)
    engine.load_parts([file1, file2])
    engine.set_instruction(inst)
    result = engine.run()

    print(f"\n--- RESULT ---")
    if result.get("success"):
        for res in result.get("pair_results", []):
            print(f"  Strategy  : {res['strategy']}")
            print(f"  Confidence: {res['confidence']:.0%}")
            print(f"  Fit class : {res.get('fit_class','')}")
            print(f"  Translation: {res['translation']}")
            print(f"  Collision : {res['collision']}")
            print(f"  Description: {res.get('description','')}")
    else:
        print("  ASSEMBLY FAILED")

    print("\n" + "=" * 60)
    print("Debug complete.")
    print("=" * 60)

if __name__ == "__main__":
    main()