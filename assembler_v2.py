"""
assembler_v2.py
===============
Upgraded assembly engine that:
1. Uses Claude API for intelligent geometry-aware planning
2. Supports stack_top/stack_bottom (bbox face alignment)
3. Supports manual exact transforms from Claude
4. Falls back to proven rule-based for simple cases
"""
import os, re, math, time
from typing import List, Callable, Optional, Dict

from OCC.Core.TopoDS  import TopoDS_Compound
from OCC.Core.BRep    import BRep_Builder
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.Bnd     import Bnd_Box
from OCC.Core.gp      import gp_Trsf, gp_Vec, gp_Ax1, gp_Pnt, gp_Dir
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform

from step_loader       import load_step
from part_model        import PartModel
from geometry_analyzer import analyze_part
from prompt_driven_assembler import find_hole_from_description
from collision_check   import check_collision
from ai_assembly_engine import GeometricOperation, _rule_based_parse, build_parts_context

# Industry modules
from bom_generator      import BOMGenerator
from assembly_sequence  import AssemblySequence
from tolerance_analysis import classify_fit
from constraints        import ConstraintSolver, Constraint

try:
    from export_formats import export_step
    HAS_EXPORT = True
except Exception:
    HAS_EXPORT = False

PART_COLORS = ["BLUE","RED","GREEN","ORANGE","MAGENTA","CYAN","YELLOW","BROWN"]

def _get_bbox(shape):
    b = Bnd_Box(); brepbndlib.Add(shape, b); return b.Get()

def _translate(shape, tx, ty, tz):
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(tx, ty, tz))
    return BRepBuilderAPI_Transform(shape, t, True).Shape()

def _rotate(shape, axis, degrees, pivot=(0,0,0)):
    if abs(degrees) < 0.01:
        return shape
    t = gp_Trsf()
    t.SetRotation(
        gp_Ax1(gp_Pnt(*pivot), gp_Dir(*axis)),
        math.radians(degrees))
    return BRepBuilderAPI_Transform(shape, t, True).Shape()

def _stack_on_top(fixed_shape, moving_shape):
    """Place moving_shape so its bottom face sits on top of fixed_shape."""
    x0f,y0f,z0f,x1f,y1f,z1f = _get_bbox(fixed_shape)
    x0m,y0m,z0m,x1m,y1m,z1m = _get_bbox(moving_shape)
    # Center X,Y, stack Z
    tx = (x0f+x1f)/2 - (x0m+x1m)/2
    ty = (y0f+y1f)/2 - (y0m+y1m)/2
    tz = z1f - z0m   # fixed top = moving bottom
    return _translate(moving_shape, tx, ty, tz), (tx, ty, tz)

def _stack_on_bottom(fixed_shape, moving_shape):
    """Place moving_shape below fixed_shape (lower hopper)."""
    x0f,y0f,z0f,x1f,y1f,z1f = _get_bbox(fixed_shape)
    x0m,y0m,z0m,x1m,y1m,z1m = _get_bbox(moving_shape)
    tx = (x0f+x1f)/2 - (x0m+x1m)/2
    ty = (y0f+y1f)/2 - (y0m+y1m)/2
    tz = z0f - z1m   # fixed bottom = moving top
    return _translate(moving_shape, tx, ty, tz), (tx, ty, tz)

def _apply_manual_transform(shape, translate, rotate_axis, rotate_degrees, pivot=(0,0,0)):
    """Apply exact transform specified by Claude."""
    result = shape
    if abs(rotate_degrees) > 0.01:
        result = _rotate(result, rotate_axis, rotate_degrees, pivot)
    tx, ty, tz = translate
    if abs(tx)+abs(ty)+abs(tz) > 0.01:
        result = _translate(result, tx, ty, tz)
    return result, (tx, ty, tz)

def _shaft_into_hole(fixed, moving, hole_desc, depth=0.0, pre_rot_ax="", pre_rot_dg=0.0):
    """Original proven hole-shaft assembly logic."""
    holes  = fixed.holes
    shafts = [c for c in moving.cylinders if not c.is_hole]
    if not shafts: shafts = moving.cylinders
    if not shafts or not holes: return None, (0,0,0)

    hole = find_hole_from_description(fixed, hole_desc)
    if not hole and holes: hole = holes[0]
    if not hole: return None, (0,0,0)

    shaft = min(shafts, key=lambda c: abs(c.diameter - hole.diameter))

    sx,sy,sz = shaft.axis_dir
    hax,hay,haz = hole.axis_dir
    scx,scy,scz = shaft.center
    hcx,hcy,hcz = hole.center

    # Rotation
    trsf_rot = gp_Trsf()
    if pre_rot_ax and abs(pre_rot_dg) > 0.1:
        ax = {"x":(1,0,0),"y":(0,1,0),"z":(0,0,1)}.get(pre_rot_ax.lower(),(0,0,1))
        trsf_rot.SetRotation(gp_Ax1(gp_Pnt(scx,scy,scz), gp_Dir(*ax)),
                              math.radians(pre_rot_dg))
    else:
        dot = sx*hax + sy*hay + sz*haz
        if abs(abs(dot)-1.0) > 1e-6:
            cx = sy*haz - sz*hay; cy = sz*hax - sx*haz; cz = sx*hay - sy*hax
            mg = math.sqrt(cx**2+cy**2+cz**2)
            if mg > 1e-10:
                ang = math.acos(max(-1.0, min(1.0, abs(dot))))
                trsf_rot.SetRotation(
                    gp_Ax1(gp_Pnt(scx,scy,scz), gp_Dir(cx/mg,cy/mg,cz/mg)), ang)

    rsc = gp_Pnt(scx,scy,scz).Transformed(trsf_rot)
    tx = hcx - rsc.X(); ty = hcy - rsc.Y(); tz = hcz - rsc.Z()

    # Depth
    hole_depth = (getattr(hole,'depth',0) or getattr(hole,'length',0) or 20.0)
    if hole_depth < 1.0:
        x0,y0,z0,x1,y1,z1 = _get_bbox(fixed.shape)
        hole_depth = abs(hax*(x1-x0)+hay*(y1-y0)+haz*(z1-z0))

    if depth and depth > 0:
        b = Bnd_Box(); brepbndlib.Add(moving.shape, b); bd = b.Get()
        sh = abs(hax*(bd[3]-bd[0])+hay*(bd[4]-bd[1])+haz*(bd[5]-bd[2]))/2
        if sh < 1: sh = 15.0
        actual = min(depth, hole_depth) if hole_depth > 0.5 else depth
        tx += hax*(actual-sh); ty += hay*(actual-sh); tz += haz*(actual-sh)
    else:
        tx += hax*(hole_depth/2); ty += hay*(hole_depth/2); tz += haz*(hole_depth/2)

    trsf_t = gp_Trsf(); trsf_t.SetTranslation(gp_Vec(tx,ty,tz))
    rotated = BRepBuilderAPI_Transform(moving.shape, trsf_rot, True).Shape()
    moved   = BRepBuilderAPI_Transform(rotated, trsf_t, True).Shape()
    return moved, (tx, ty, tz)


class AssemblyEngineV2:
    """
    V2 Engine — Claude AI plans assembly, engine executes exact transforms.
    Falls back to rule-based for simple/standard assemblies.
    """
    def __init__(self, progress_cb=None, use_claude=False, api_key=""):
        self.progress_cb   = progress_cb or (lambda m,p: print(f"[{p}%] {m}"))
        self.use_claude    = use_claude
        self.api_key       = api_key
        self.parts:        List[PartModel] = []
        self.operations:   List[GeometricOperation] = []
        self.pair_results  = []
        self.compound      = None
        self._used_holes   = set()
        self._claude_plan  = None

        # Industry modules
        self.bom         = BOMGenerator()
        self.sequence    = AssemblySequence()
        self.constraints = ConstraintSolver()
        self.tolerance_reports: Dict[str,dict] = {}
        self.export_results: dict = {}

    def _progress(self, msg, pct=0):
        self.progress_cb(msg, pct)

    def load_parts(self, file_paths):
        self.parts = []
        for path in file_paths:
            p = PartModel(file_path=path)
            p.shape = load_step(path)
            if p.is_loaded:
                analyze_part(p)
                self._progress(f"Loaded: {p.name}", 5)
            self.parts.append(p)

    def set_instruction(self, ops):
        self.operations = ops if isinstance(ops, list) else [ops]

    def _build_parts_data(self) -> list:
        """Build geometry context for Claude API."""
        result = []
        for p in self.parts:
            if not p.is_loaded: continue
            cyls = []
            for c in p.cylinders:
                cyls.append({
                    "d": round(c.diameter, 2),
                    "L": round(getattr(c,'length',0) or getattr(c,'depth',0), 2),
                    "is_hole": c.is_hole,
                    "axis": tuple(round(x,3) for x in c.axis_dir),
                    "center": tuple(round(x,2) for x in c.center)
                })
            pls = []
            for pl in getattr(p,'planes',[])[:5]:
                pls.append({
                    "normal": tuple(round(x,3) for x in pl.normal),
                    "area": round(pl.area, 1),
                    "center": tuple(round(x,2) for x in pl.center)
                })
            result.append({
                "name": p.name,
                "bbox_dims": tuple(round(x,1) for x in (p.bbox_dims or (0,0,0))),
                "bbox_center": tuple(round(x,1) for x in (p.bbox_center or (0,0,0))),
                "part_type": p.part_type,
                "cylinders": cyls,
                "planes": pls
            })
        return result

    def run(self, user_prompt: str = "") -> dict:
        self._used_holes  = set()
        self.pair_results = []
        start = time.time()

        loaded = [p for p in self.parts if p.is_loaded]
        if len(loaded) < 2:
            return {"error":"Need at least 2 parts","pair_results":[]}

        # ── Claude AI Planning ─────────────────────────────────────────
        claude_plan = None
        if self.use_claude and user_prompt:
            self._progress("Claude AI analyzing geometry...", 10)
            try:
                from claude_ai_engine_v2 import call_claude_for_assembly, apply_claude_plan
                parts_data = self._build_parts_data()
                claude_plan = call_claude_for_assembly(
                    user_prompt, parts_data, self.api_key)
                if not claude_plan.fallback_to_rules:
                    self._progress(
                        f"Claude: {claude_plan.overall_explanation[:60]}", 20)
                    self._claude_plan = claude_plan
                else:
                    self._progress("Claude unavailable, using rule-based", 20)
            except Exception as e:
                self._progress(f"Claude error: {e}", 20)

        # ── Parse prompt with rule-based (fallback or supplement) ──────
        if not self.operations and user_prompt:
            parts_ctx = build_parts_context(loaded)
            ops = _rule_based_parse(user_prompt, parts_ctx)
            if ops: self.operations = ops

        # ── Sort: most holes = anchor ──────────────────────────────────
        loaded.sort(key=lambda p:(len(p.holes),-len(p.shafts)), reverse=True)
        anchor = loaded[0]
        self._progress(f"Anchor: {anchor.name}", 30)

        self.bom.add_from_parts(loaded)

        idx = 1
        for moving in loaded[1:]:
            self._progress(f"Assembling {moving.name}...", 40+idx*10)

            # Get operation for this part
            op = self._get_op_for(idx, moving.name)
            idx += 1

            # Determine assembly method
            result = None

            # Method 1: Claude provided exact transform
            if claude_plan and not claude_plan.fallback_to_rules:
                ct = self._find_claude_transform(claude_plan, moving.name)
                if ct:
                    result = self._apply_claude_transform(anchor, moving, ct)

            # Method 2: Rule-based hole-shaft
            if result is None:
                result = self._rule_based_assembly(anchor, moving, op)

            if result:
                self.pair_results.append(result)
                # Tolerance
                self._calc_tolerance(result, moving)
                # Sequence
                step = self.sequence.add_step(
                    f"Insert {moving.name} into {anchor.name}",
                    moving.name, "insert")
                self.sequence.mark_complete(
                    step, result.get("shape") or result.get("moved_shape"),
                    success=True,
                    notes=f"Method: {result.get('method','rule')}")

        # Build compound
        builder = BRep_Builder()
        comp    = TopoDS_Compound()
        builder.MakeCompound(comp)
        builder.Add(comp, anchor.shape)
        for r in self.pair_results:
            sh = r.get("shape") or r.get("moved_shape")
            if sh and not sh.IsNull():
                builder.Add(comp, sh)
        self.compound = comp

        # Export
        self._save_outputs()
        total_ms = (time.time()-start)*1000
        self._progress(f"Assembly complete in {total_ms:.0f}ms", 100)

        return {
            "compound":     self.compound,
            "pair_results": self.pair_results,
            "bom":          self.bom.to_txt(),
            "sequence":     self.sequence.to_report(),
            "tolerance":    self.tolerance_reports,
            "exports":      self.export_results,
            "total_ms":     total_ms,
            "claude_used":  (claude_plan is not None and not claude_plan.fallback_to_rules),
            "claude_explanation": claude_plan.overall_explanation if claude_plan else "",
        }

    def _find_claude_transform(self, plan, part_name: str):
        """Find Claude's transform for this part by name matching."""
        pn = part_name.lower().replace(" ","").replace("_","").replace(".","")
        for t in plan.transforms:
            tn = t.part_name.lower().replace(" ","").replace("_","").replace(".","")
            if pn in tn or tn in pn:
                return t
        return None

    def _apply_claude_transform(self, anchor, moving, ct) -> Optional[dict]:
        """Apply Claude's planned transform to the moving part."""
        try:
            atype = ct.assembly_type

            if atype == "stack_top":
                moved, translation = _stack_on_top(anchor.shape, moving.shape)

            elif atype == "stack_bottom":
                moved, translation = _stack_on_bottom(anchor.shape, moving.shape)

            elif atype == "manual":
                moved, translation = _apply_manual_transform(
                    moving.shape,
                    ct.translate,
                    ct.rotate_axis,
                    ct.rotate_degrees)

            elif atype == "hole_shaft":
                moved, translation = _shaft_into_hole(
                    anchor, moving,
                    ct.hole_description or "large",
                    ct.insertion_depth)

            else:  # default hole_shaft
                moved, translation = _shaft_into_hole(
                    anchor, moving,
                    ct.hole_description or "large",
                    ct.insertion_depth)

            if moved is None: return None

            collision = check_collision(anchor.shape, moved)
            return {
                "part_a":     anchor.name,
                "part_b":     moving.name,
                "shape":      moved,
                "moved_shape": moved,
                "translation": translation,
                "method":     f"claude:{atype}",
                "fit_class":  ct.explanation[:40],
                "collision":  collision,
                "note":       f"Claude: {ct.explanation}"
            }
        except Exception as e:
            self._progress(f"Claude transform error for {moving.name}: {e}", 0)
            return None

    def _rule_based_assembly(self, anchor, moving, op) -> Optional[dict]:
        """Original proven rule-based assembly."""
        hole_desc  = op.hole_description  if op else ""
        depth      = op.insertion_depth   if op else 0.0
        pre_rot_ax = op.pre_rotate_axis   if op else ""
        pre_rot_dg = op.pre_rotate_degrees if op else 0.0

        moved, translation = _shaft_into_hole(
            anchor, moving, hole_desc, depth, pre_rot_ax, pre_rot_dg)

        if moved is None: return None

        # Find matching hole for tolerance
        holes  = anchor.holes
        shafts = [c for c in moving.cylinders if not c.is_hole]
        fit_class = ""
        note = ""
        if holes and shafts:
            hole = find_hole_from_description(anchor, hole_desc) or holes[0]
            shaft = min(shafts, key=lambda c: abs(c.diameter-hole.diameter))
            fit = classify_fit(hole.diameter, shaft.diameter)
            fit_class = fit["fit_class"]
            note = f"d={hole.diameter:.2f}mm"

        collision = check_collision(anchor.shape, moved)
        return {
            "part_a":      anchor.name,
            "part_b":      moving.name,
            "shape":       moved,
            "moved_shape": moved,
            "translation": translation,
            "method":      "rule_based",
            "fit_class":   fit_class,
            "collision":   collision,
            "note":        note
        }

    def _get_op_for(self, idx: int, part_name: str = "") -> Optional[GeometricOperation]:
        if not self.operations: return None
        if part_name:
            pn = part_name.lower().replace("_","").replace("-","").replace(" ","")
            for op in self.operations:
                hint = (op.moving_part_hint or "").lower().replace("_","").replace("-","").replace(" ","")
                if not hint: continue
                words = [w for w in re.sub(r"[_\-\s]"," ",hint).split() if len(w)>2]
                if any(w in pn for w in words):
                    return op
        return self.operations[min(idx-1, len(self.operations)-1)]

    def _calc_tolerance(self, result, moving):
        try:
            note = result.get("note","")
            m = re.search(r'd=([\d.]+)mm', note)
            if m:
                hd = float(m.group(1))
                sd = hd
                for p in self.parts:
                    if p.name == moving.name:
                        shafts = [c for c in p.cylinders if not c.is_hole]
                        if shafts: sd = shafts[0].diameter
                self.tolerance_reports[moving.name] = classify_fit(hd, sd)
        except Exception:
            pass

    def _save_outputs(self):
        try:
            if self.compound and HAS_EXPORT:
                export_step(self.compound, "assembled_model.step")
                self.export_results["STEP"] = "assembled_model.step"
        except Exception as e:
            self.export_results["STEP_error"] = str(e)
        try:
            self.bom.save("bom","txt"); self.bom.save("bom","csv")
            self.export_results["BOM"] = "bom.txt"
        except Exception: pass
        try:
            with open("assembly_sequence.txt","w") as f:
                f.write(self.sequence.to_report())
        except Exception: pass

    # ── Industry accessors ────────────────────────────────────────────
    def undo(self):
        self.constraints.undo(); return self.sequence.undo()
    def redo(self): return self.sequence.redo()
    def get_undo_redo_state(self):
        return {"can_undo":self.sequence.can_undo(),
                "can_redo":self.sequence.can_redo(),
                "current_step":self.sequence.current_step,
                "total_steps":len(self.sequence.steps)}
    def get_bom(self,fmt="txt"):
        if fmt=="csv": return self.bom.to_csv()
        if fmt=="json": return self.bom.to_json()
        return self.bom.to_txt()
    def get_constraints_summary(self): return self.constraints.summary()