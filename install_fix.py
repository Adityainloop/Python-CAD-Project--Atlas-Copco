"""
install_fix.py
==============
Run this ONCE in Anaconda Prompt:
    python install_fix.py

It will completely rewrite assembler.py and gui_app.py in your project folder.
No manual file copying needed.
"""
import os
import sys

PROJECT = os.path.dirname(os.path.abspath(__file__))
print(f"Project folder: {PROJECT}")

# ─────────────────────────────────────────────────────────────────────────────
# Write assembler.py directly
# ─────────────────────────────────────────────────────────────────────────────

ASSEMBLER = '''"""
assembler.py - fixed version
"""
import os, re, math
from typing import List, Callable, Optional
from OCC.Core.TopoDS import TopoDS_Compound
from OCC.Core.BRep import BRep_Builder
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.Bnd import Bnd_Box

from step_loader import load_step
from part_model import PartModel
from geometry_analyzer import analyze_part
from ai_assembly_engine import GeometricOperation, apply_pre_rotation
from prompt_driven_assembler import find_hole_from_description
from alignment import (align_radial, align_shaft_through_hole,
                       align_planes, align_slot, align_bolt_pattern,
                       align_bbox, apply_transform)
from collision_check import check_collision

PART_COLORS = ["BLUE","RED","GREEN","ORANGE","MAGENTA","CYAN","YELLOW","WHITE","BROWN","PINK"]


def _get_bbox(shape):
    box = Bnd_Box()
    brepbndlib.Add(shape, box)
    return box.Get()


def _is_true_side_hole(hole, fixed_shape) -> bool:
    """True only for radial holes on cylindrical parts, NOT for through-holes on flat plates."""
    x0,y0,z0,x1,y1,z1 = _get_bbox(fixed_shape)
    dx,dy,dz = x1-x0, y1-y0, z1-z0
    dims = sorted([dx,dy,dz])
    min_dim, max_dim = dims[0], dims[2]
    flatness = min_dim / max(max_dim, 1.0)
    is_plate = flatness <= 0.30

    if is_plate:
        # For plates: check if hole axis is parallel to thin dimension
        ax,ay,az = hole.axis_dir
        if dz == min_dim: thin = (0,0,1)
        elif dy == min_dim: thin = (0,1,0)
        else: thin = (1,0,0)
        dot = abs(ax*thin[0] + ay*thin[1] + az*thin[2])
        if dot > 0.7:
            return False  # through-hole on plate face

    hx,hy,hz = hole.center
    bcx,bcy,bcz = (x0+x1)/2,(y0+y1)/2,(z0+z1)/2
    dist = math.sqrt((hx-bcx)**2 + (hy-bcy)**2 + (hz-bcz)**2)
    part_max_r = max(dx,dy,dz) / 2
    return dist > part_max_r * 0.4


class AssemblyEngine:
    def __init__(self, progress_cb=None):
        self.progress_cb = progress_cb or (lambda m,p: print(f"[{p:3d}%] {m}"))
        self.parts: List[PartModel] = []
        self.assembled_shapes = []
        self.pair_results = []
        self.compound = None
        self.operations: List[GeometricOperation] = []
        self._used_holes: set = set()  # track used holes to prevent two parts in same hole

    def load_parts(self, file_paths):
        self.parts = []
        for path in file_paths:
            part = PartModel(file_path=path)
            part.shape = load_step(path)
            self.parts.append(part)

    def set_instruction(self, instruction):
        if isinstance(instruction, list):
            self.operations = instruction
        elif hasattr(instruction, "pre_rotate_axis"):
            self.operations = [instruction]
        else:
            op = GeometricOperation(raw_prompt=getattr(instruction,"raw_prompt",""))
            op.insertion_depth = getattr(instruction,"insertion_depth",None) or 0.0
            op.full_depth      = getattr(instruction,"full_depth", True)
            op.press_fit       = getattr(instruction,"press_fit", False)
            op.prefer_cylinder = getattr(instruction,"prefer_cylinder", False)
            op.prefer_plane    = getattr(instruction,"prefer_plane", False)
            op.side_by_side    = getattr(instruction,"side_by_side", False)
            op.gap             = getattr(instruction,"gap", None) or 0.0
            atype = getattr(instruction,"assembly_type","auto")
            if atype == "shaft_hole": op.strategy="shaft_hole"; op.prefer_cylinder=True
            elif atype in ("plane","slot"): op.strategy=atype; op.prefer_plane=True
            self.operations = [op]

    def _op_for(self, idx: int, part_name: str = "") -> Optional[GeometricOperation]:
        """Match op to part by name hint. Falls back to sequential index."""
        if not self.operations: return None
        if part_name:
            pn = part_name.lower().replace("_","").replace("-","")
            # Try: does any op's moving_part_hint match this part name?
            for op in self.operations:
                hint = (op.moving_part_hint or "").lower().replace("_","").replace("-","")
                if not hint: continue
                # Extract meaningful words (skip short words)
                hint_words = [w for w in hint.split() if len(w) > 2]
                part_words = [w for w in pn.split() if len(w) > 2]
                # Check direct substring match
                if any(w in pn for w in hint_words) or any(w in hint for w in part_words):
                    return op
        # Sequential fallback
        return self.operations[min(idx-1, len(self.operations)-1)]

    def run(self) -> dict:
        self._used_holes = set()  # reset for each assembly run
        loaded = [p for p in self.parts if p.is_loaded]
        if len(loaded) < 2:
            self._progress("Need at least 2 valid parts", 0)
            return self._fail()
        total = len(loaded)

        for i,part in enumerate(loaded):
            pct = int((i/total)*35)
            self._progress(f"Analysing: {part.name}...", pct)
            analyze_part(part)
            self._progress(part.summary(), pct+1)

        # KEY FIX 1: Sort so part with most holes is always anchor
        loaded.sort(key=lambda p: (len(p.holes), -len(p.shafts)), reverse=True)
        self._progress(
            f"Anchor: {loaded[0].name} "
            f"(holes={len(loaded[0].holes)} shafts={len(loaded[0].shafts)})", 36)

        for op in self.operations:
            if op.pre_rotate_axis and abs(op.pre_rotate_degrees) > 0.01:
                target = self._find_by_hint(loaded, op.moving_part_hint) or \\
                         self._find_by_hint(loaded, op.fixed_part_hint)
                if target:
                    self._progress(
                        f"Rotating {target.name} "
                        f"{op.pre_rotate_degrees:.0f} around {op.pre_rotate_axis.upper()}", 37)
                    target.shape = apply_pre_rotation(
                        target.shape, op.pre_rotate_axis, op.pre_rotate_degrees)
                    analyze_part(target)

        assembled_shapes = [(loaded[0].shape, PART_COLORS[0], loaded[0].name)]
        accumulated = [loaded[0]]
        self.pair_results = []

        for idx in range(1, len(loaded)):
            moving = loaded[idx]
            color  = PART_COLORS[idx % len(PART_COLORS)]
            pct    = 38 + int((idx/total)*57)
            op     = self._op_for(idx, moving.name)
            hole_s = op.hole_description if op else "auto"
            dep_s  = op.insertion_depth if op else 0
            self._progress(f"Assembling {moving.name} [hole=\\'{hole_s}\\' depth={dep_s}mm]", pct)

            best_res = None; best_conf = -1.0
            for anchor in accumulated:
                res = self._assemble_pair(anchor, moving, op)
                if res["confidence"] > best_conf:
                    best_conf = res["confidence"]
                    best_res  = res

            self.pair_results.append(best_res)
            assembled_shapes.append((best_res["moved_shape"], color, moving.name))
            moving.shape = best_res["moved_shape"]
            analyze_part(moving)
            accumulated.append(moving)

        self.assembled_shapes = assembled_shapes
        self.compound = self._build_compound([s for s,_,_ in assembled_shapes])
        self._progress("Assembly complete", 100)
        return {
            "success": True, "compound": self.compound,
            "parts": self.parts, "pair_results": self.pair_results,
            "assembled_shapes": self.assembled_shapes,
        }

    def _assemble_pair(self, fixed, moving, op):
        if op and op.side_by_side:
            trsf = align_bbox(fixed.shape, moving.shape)
            moved = apply_transform(moving.shape, trsf)
            t = trsf.TranslationPart()
            return self._result(fixed, moving, "bbox", moved,
                                (t.X(),t.Y(),t.Z()), 0.95, {"fit_class":"Side by Side"})

        depth      = op.insertion_depth if op else 0.0
        full_depth = (op.full_depth if op else True) if depth == 0 else False

        if op and op.hole_description:
            r = self._by_hole(fixed, moving, op.hole_description, depth, full_depth, op)
            if r: return r

        if op and op.strategy == "slot":
            r = self._slot_assembly(fixed, moving, op)
            if r: return r

        from smart_matcher import find_all_matches
        from prompt_parser import AssemblyInstruction
        inst = None
        if op:
            inst = AssemblyInstruction()
            inst.prefer_cylinder = op.prefer_cylinder
            inst.prefer_plane    = op.prefer_plane
            inst.insertion_depth = op.insertion_depth if op.insertion_depth > 0 else None
            inst.full_depth      = op.full_depth
            inst.press_fit       = op.press_fit
            inst.gap             = op.gap if op.gap > 0 else None

        candidates = find_all_matches(fixed, moving, inst)
        if op and op.prefer_plane and not op.prefer_cylinder:
            pc = [c for c in candidates if c["strategy"] in ("plane","slot")]
            if pc: candidates = pc

        if not candidates:
            trsf = align_bbox(fixed.shape, moving.shape)
            moved = apply_transform(moving.shape, trsf)
            t = trsf.TranslationPart()
            return self._result(fixed, moving, "bbox", moved,
                                (t.X(),t.Y(),t.Z()), 0.15, {"fit_class":"BBox"})

        match = candidates[0]; strategy = match["strategy"]
        self._progress(f"  [{strategy}] conf={match[\'confidence\']:.0%}  {match[\'description\']}", 0)

        moved_shape = moving.shape; translation = (0.,0.,0.)
        try:
            if strategy == "cylinder":
                shaft = match["shaft"]; hole = match["hole"]
                shaft_on_moving = (match["shaft_part"] == "b")
                # KEY FIX 2: correct side hole detection
                hole_is_side = _is_true_side_hole(hole, fixed.shape)
                self._progress(f"  hole_is_side={hole_is_side}", 0)
                if hole_is_side or (op and op.strategy == "side_hole"):
                    trsf = (align_radial(shaft, hole, moving.shape, fixed.shape, depth, full_depth)
                            if shaft_on_moving else
                            align_radial(hole, shaft, moving.shape, fixed.shape, depth, full_depth))
                else:
                    trsf = (align_shaft_through_hole(shaft, hole, moving.shape, depth, full_depth)
                            if shaft_on_moving else
                            align_shaft_through_hole(hole, shaft, moving.shape, depth, full_depth))
                moved_shape = apply_transform(moving.shape, trsf)
                t = trsf.TranslationPart(); translation = (t.X(),t.Y(),t.Z())

            elif strategy in ("plane","slot"):
                p1 = match["p1"]; p2 = match["p2"]
                gap = op.gap if (op and op.gap) else match.get("gap",0.0)
                trsf = (align_slot(fixed.shape, moving.shape, p1, p2)
                        if strategy == "slot"
                        else align_planes(p1, p2, shape2=moving.shape, gap=gap))
                moved_shape = apply_transform(moving.shape, trsf)
                t = trsf.TranslationPart(); translation = (t.X(),t.Y(),t.Z())

            elif strategy == "bolt_pattern":
                trsf = align_bolt_pattern(match["pattern_a"], match["pattern_b"])
                moved_shape = apply_transform(moving.shape, trsf)
                t = trsf.TranslationPart(); translation = (t.X(),t.Y(),t.Z())

            else:
                trsf = align_bbox(fixed.shape, moving.shape)
                moved_shape = apply_transform(moving.shape, trsf)
                t = trsf.TranslationPart(); translation = (t.X(),t.Y(),t.Z())

        except Exception as e:
            self._progress(f"  Transform error: {e}", 0)
            trsf = align_bbox(fixed.shape, moving.shape)
            moved_shape = apply_transform(moving.shape, trsf)
            t = trsf.TranslationPart(); translation = (t.X(),t.Y(),t.Z())
            strategy = "bbox"

        collision = check_collision(fixed.shape, moved_shape)
        return self._result(fixed, moving, strategy, moved_shape, translation,
                            match["confidence"], match["fit_info"], collision,
                            match.get("description",""))

    def _by_hole(self, fixed, moving, hole_desc, depth, full_depth, op):
        if len(fixed.holes) >= len(moving.holes):
            receiver, inserter = fixed, moving
        else:
            receiver, inserter = moving, fixed

        hole = find_hole_from_description(receiver, hole_desc)
        if not hole:
            self._progress(f"  Cannot find \\'{hole_desc}\\' hole", 0)
            return None

        cyls = inserter.cylinders
        if not cyls:
            self._progress(f"  No cylinders on {inserter.name}", 0)
            return None

        # Skip already-used holes to prevent two parts in same hole
        hole_key = (receiver.name, round(hole.center[0],1), round(hole.center[1],1), round(hole.center[2],1))
        if hole_key in self._used_holes:
            self._progress(f"  Hole {hole.center} already used, finding next hole", 0)
            all_holes = [c for c in receiver.cylinders if c.is_hole]
            unused = [h for h in all_holes
                      if (receiver.name, round(h.center[0],1), round(h.center[1],1), round(h.center[2],1)) not in self._used_holes]
            if unused:
                hole = min(unused, key=lambda h: abs(h.diameter - hole.diameter))
                hole_key = (receiver.name, round(hole.center[0],1), round(hole.center[1],1), round(hole.center[2],1))
                self._progress(f"  Redirected to hole at {hole.center} d={hole.diameter:.2f}mm", 0)
        self._used_holes.add(hole_key)

        shaft = min(cyls, key=lambda c: abs(c.diameter - hole.diameter))
        self._progress(f"  \\'{hole_desc}\\': hole={hole.diameter:.2f}mm shaft={shaft.diameter:.2f}mm", 0)

        try:
            from OCC.Core.gp import gp_Trsf, gp_Vec, gp_Ax1, gp_Pnt, gp_Dir
            import math as _math

            sx,sy,sz = shaft.axis_dir
            hax,hay,haz = hole.axis_dir
            hcx,hcy,hcz = hole.center
            scx,scy,scz = shaft.center

            # Rotate shaft axis to align with hole axis
            dot = sx*hax + sy*hay + sz*haz
            trsf_rot = gp_Trsf()
            if abs(abs(dot) - 1.0) > 1e-6:
                rx = sy*haz - sz*hay
                ry = sz*hax - sx*haz
                rz = sx*hay - sy*hax
                rmag = _math.sqrt(rx*rx+ry*ry+rz*rz)
                if rmag > 1e-10:
                    angle = _math.acos(max(-1.0, min(1.0, abs(dot))))
                    trsf_rot.SetRotation(
                        gp_Ax1(gp_Pnt(scx,scy,scz), gp_Dir(rx/rmag,ry/rmag,rz/rmag)),
                        angle)

            # Translate rotated shaft center to hole center
            rsc = gp_Pnt(scx,scy,scz).Transformed(trsf_rot)
            tx = hcx - rsc.X()
            ty = hcy - rsc.Y()
            tz = hcz - rsc.Z()

            # OCC hole 'center' = axis LOCATION = ENTRY FACE of hole, not midpoint.
            # Push shaft center to middle of hole along hole axis direction.
            hole_depth = hole.depth if (hole.depth and hole.depth > 1.0) else hole.length
            if hole_depth < 1.0:
                x0,y0,z0,x1,y1,z1 = _get_bbox(receiver.shape)
                hole_depth = abs(hax*(x1-x0) + hay*(y1-y0) + haz*(z1-z0))
            # Position shaft based on user depth or center in hole
            user_depth = depth if (depth and depth > 0) else 0.0
            if user_depth > 0:
                # User specified depth: shaft tip is user_depth mm inside from entry face
                # Clamp to hole_depth so shaft doesn't go past the hole
                actual_depth = min(user_depth, hole_depth) if hole_depth > 0.5 else user_depth
                # Get actual shaft half-length from bbox
                from OCC.Core.BRepBndLib import brepbndlib as _bb
                from OCC.Core.Bnd import Bnd_Box as _BndBox
                _bx = _BndBox(); _bb.Add(moving.shape, _bx); _bxd = _bx.Get()
                # shaft half = half extent along hole axis direction
                shaft_half = abs(hax*(_bxd[3]-_bxd[0]) + hay*(_bxd[4]-_bxd[1]) + haz*(_bxd[5]-_bxd[2])) / 2
                if shaft_half < 1.0: shaft_half = 15.0  # fallback
                # shaft_center = hole_entry + hole_axis*(depth - shaft_half)
                # hole_center from OCC is already at entry face
                tx += hax * (actual_depth - shaft_half)
                ty += hay * (actual_depth - shaft_half)
                tz += haz * (actual_depth - shaft_half)
            elif hole_depth > 0.5:
                # No depth specified: center shaft in hole
                tx += hax * (hole_depth / 2)
                ty += hay * (hole_depth / 2)
                tz += haz * (hole_depth / 2)
            self._progress(f"  direct translate=({tx:.1f},{ty:.1f},{tz:.1f}) depth={hole_depth:.1f}mm user_depth={depth}mm", 0)

            trsf_t = gp_Trsf()
            trsf_t.SetTranslation(gp_Vec(tx,ty,tz))
            # Apply: rotate first, then translate
            from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
            rotated = BRepBuilderAPI_Transform(moving.shape, trsf_rot, True).Shape()
            moved = BRepBuilderAPI_Transform(rotated, trsf_t, True).Shape()

            collision = check_collision(fixed.shape, moved)
            return self._result(fixed, moving, "cylinder", moved,
                                (tx,ty,tz), 0.92,
                                {"fit_class": f"Hole:{hole_desc}",
                                 "note": f"d={hole.diameter:.2f}mm"},
                                collision)
        except Exception as e:
            self._progress(f"  Hole error: {e}", 0)
            return None

    def _slot_assembly(self, fixed, moving, op):
        from smart_matcher import _plane_matches
        from prompt_parser import AssemblyInstruction
        inst = AssemblyInstruction(); inst.prefer_plane = True
        pm = _plane_matches(fixed, moving, inst)
        if not pm: return None
        best = pm[0]; p1,p2 = best["p1"], best["p2"]
        try:
            trsf = (align_slot(fixed.shape, moving.shape, p1, p2)
                    if best["strategy"] == "slot"
                    else align_planes(p1, p2, shape2=moving.shape, gap=op.gap or 0.0))
            moved = apply_transform(moving.shape, trsf)
            t = trsf.TranslationPart()
            collision = check_collision(fixed.shape, moved)
            return self._result(fixed, moving, best["strategy"], moved,
                                (t.X(),t.Y(),t.Z()), best["confidence"],
                                best["fit_info"], collision, best["description"])
        except Exception as e:
            self._progress(f"  Slot error: {e}", 0); return None

    def _find_by_hint(self, parts, hint):
        if not hint: return None
        h = hint.lower()
        for p in parts:
            if h in p.name.lower(): return p
        words = [w for w in re.sub(r"[_-]"," ",h).split() if len(w)>2]
        for p in parts:
            if any(w in p.name.lower() for w in words): return p
        return None

    def _result(self, fixed, moving, strategy, moved_shape, translation,
                confidence, fit_info, collision=False, description=""):
        r = {
            "part_a": fixed.name, "part_b": moving.name,
            "strategy": strategy, "moved_shape": moved_shape,
            "translation": translation, "collision": collision,
            "confidence": confidence, "description": description,
        }
        r.update(fit_info)
        return r

    def _fail(self):
        return {"success":False,"compound":None,"parts":self.parts,
                "pair_results":[],"assembled_shapes":[]}

    @staticmethod
    def _build_compound(shapes):
        b = BRep_Builder(); c = TopoDS_Compound(); b.MakeCompound(c)
        for s in shapes:
            if s and not s.IsNull(): b.Add(c,s)
        return c

    def _progress(self, msg, pct):
        if self.progress_cb:
            self.progress_cb(msg, max(0, min(100, pct)))
'''

# Write assembler.py
path_asm = os.path.join(PROJECT, "assembler.py")
with open(path_asm, "w", encoding="utf-8") as f:
    f.write(ASSEMBLER)
print(f"Written: {path_asm}")

# Verify syntax
import ast
try:
    ast.parse(ASSEMBLER)
    print("assembler.py syntax OK")
except SyntaxError as e:
    print(f"SYNTAX ERROR: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# Fix gui_app.py - just patch the broken line
# ─────────────────────────────────────────────────────────────────────────────
import re

path_gui = os.path.join(PROJECT, "gui_app.py")
with open(path_gui, "r", encoding="utf-8") as f:
    gui = f.read()

# Count how many times 'hole_description' appears accessed on 'operation' (not op)
bad = re.findall(r'operation\.hole_description', gui)
print(f"\ngui_app.py: found {len(bad)} bad 'operation.hole_description' references")

if bad:
    # Fix: pass list, remove bad log line
    gui = re.sub(r'operation\s*=\s*ops\[-1\]', 'operation = ops', gui)
    gui = re.sub(
        r'root\.after\(0,lambda:_log\(\s*f"  Using:.*?,"dim"\)\)',
        '',
        gui, flags=re.DOTALL
    )
    # Also remove the rotation copy hack
    gui = re.sub(
        r'# If first op has rotation.*?operation\.pre_rotate_degrees\s*=\s*ops\[0\]\.pre_rotate_degrees\s*\n',
        '',
        gui, flags=re.DOTALL
    )
    with open(path_gui, "w", encoding="utf-8") as f:
        f.write(gui)
    print("gui_app.py patched")
    
    # Verify no more bad references
    remaining = re.findall(r'operation\.hole_description', gui)
    if remaining:
        print(f"WARNING: still has {len(remaining)} bad references!")
    else:
        print("gui_app.py: no more bad references")
else:
    print("gui_app.py: already clean, no changes needed")

# ── Patch ai_assembly_engine.py to fix 'inside' matching 'side' ──────
import re as _re2
path_ai = os.path.join(PROJECT, "ai_assembly_engine.py")
if os.path.exists(path_ai):
    with open(path_ai, "r", encoding="utf-8") as f:
        ai_content = f.read()
    
    old_kw = """    for kw,val in [('small','small'),('smallest','small'),('large','large'),
                   ('biggest','large'),('main bore','large'),
                   ('side','side'),('edge','edge'),('surface','side'),
                   ('middle','middle'),('center','middle'),('central','middle'),
                   ('slot','slot'),('cavity','slot'),('rectangular','slot')]:
        if kw in seg and not op.hole_description:
            op.hole_description = val; break"""
    
    new_kw = """    import re as _re
    for kw,val in [('small','small'),('smallest','small'),('large','large'),
                   ('biggest','large'),('main bore','large'),
                   ('side hole','side'),('edge hole','edge'),('surface hole','side'),
                   ('middle','middle'),('center','middle'),('central','middle'),
                   ('slot','slot'),('cavity','slot'),('rectangular','slot')]:
        if ' ' in kw: matches = kw in seg
        else: matches = bool(_re.search(r'\\b' + kw + r'\\b', seg))
        if matches and not op.hole_description:
            op.hole_description = val; break
    if not op.hole_description:
        if _re.search(r'\\bside\\b', seg): op.hole_description = 'side'
        elif _re.search(r'\\bedge\\b', seg): op.hole_description = 'edge'"""
    
    if old_kw in ai_content:
        ai_content = ai_content.replace(old_kw, new_kw)
        with open(path_ai, "w", encoding="utf-8") as f:
            f.write(ai_content)
        print("ai_assembly_engine.py patched (fixed 'inside' matching 'side')")
    else:
        print("ai_assembly_engine.py: already patched or pattern changed")
else:
    print(f"WARNING: {path_ai} not found")

print("\nDone! Now run: python gui_app.py")