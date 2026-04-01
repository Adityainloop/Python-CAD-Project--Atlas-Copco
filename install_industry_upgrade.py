"""
install_industry_upgrade.py
===========================
Run ONCE in Anaconda Prompt:
    python install_industry_upgrade.py

Installs all industry-level upgrades to your project.
"""
import os, sys, shutil, ast

PROJECT = os.path.dirname(os.path.abspath(__file__))
print(f"Installing to: {PROJECT}")
print("=" * 60)

# ── Files to write ─────────────────────────────────────────────────
FILES = {}

FILES["bom_generator.py"] = '''"""Bill of Materials generator."""
import os, json
from datetime import datetime
from typing import List, Dict

class BOMGenerator:
    def __init__(self):
        self.items: List[Dict] = []

    def add_part(self, name, qty=1, material="Steel",
                 finish="Machined", mass_g=None, notes=""):
        self.items.append({
            "item": len(self.items)+1,
            "part_name": os.path.splitext(os.path.basename(name))[0],
            "filename": name, "quantity": qty,
            "material": material, "finish": finish,
            "mass_g": mass_g, "notes": notes
        })

    def add_from_parts(self, parts_list, tolerance_data=None):
        self.items = []
        for p in parts_list:
            name = getattr(p, "name", str(p))
            mass = None
            if hasattr(p, "bbox_dims") and p.bbox_dims:
                dx,dy,dz = p.bbox_dims
                mass = round((dx*dy*dz/1000)*7.85, 1)
            notes = ""
            if tolerance_data and name in tolerance_data:
                notes = f"Fit: {tolerance_data[name].get('fit_class','')}"
            self.add_part(name, qty=1, mass_g=mass, notes=notes)

    def to_txt(self, title="Assembly") -> str:
        lines = [
            f"BILL OF MATERIALS — {title}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "="*80,
            f"{'#':<4} {'Part Name':<30} {'Qty':<5} {'Material':<12} "
            f"{'Finish':<12} {'Mass(g)':<9} Notes",
            "-"*80,
        ]
        total = 0
        for i in self.items:
            m = i["mass_g"] or 0
            total += m * i["quantity"]
            lines.append(
                f"{i['item']:<4} {i['part_name']:<30} {i['quantity']:<5} "
                f"{i['material']:<12} {i['finish']:<12} "
                f"{str(round(m,1))+'g':<9} {i['notes']}")
        lines += ["-"*80,
                  f"Total items: {len(self.items)}   "
                  f"Est. mass: {round(total,1)}g = {round(total/1000,3)}kg",
                  "="*80]
        return "\\n".join(lines)

    def to_csv(self, title="Assembly") -> str:
        lines = ["Item,Part Name,Filename,Qty,Material,Finish,Mass_g,Notes"]
        for i in self.items:
            lines.append(f"{i['item']},{i['part_name']},{i['filename']},"
                         f"{i['quantity']},{i['material']},{i['finish']},"
                         f"{i['mass_g'] or ''},\\"{i['notes']}\\"")
        return "\\n".join(lines)

    def to_json(self) -> str:
        return json.dumps({"bom": self.items,
                           "generated": datetime.now().isoformat(),
                           "total_items": len(self.items)}, indent=2)

    def save(self, prefix="bom", fmt="txt", title="Assembly"):
        path = f"{prefix}.{fmt}"
        with open(path, "w") as f:
            f.write(getattr(self, f"to_{fmt}")(title) if fmt != "json"
                    else self.to_json())
        return path
'''

FILES["tolerance_analysis.py"] = '''"""ISO fit classification and tolerance analysis."""

def classify_fit(hole_d: float, shaft_d: float) -> dict:
    clearance = hole_d - shaft_d
    r = {"hole_d": round(hole_d,3), "shaft_d": round(shaft_d,3),
         "clearance": round(clearance,3),
         "fit_class":"", "fit_description":"",
         "iso_suggestion":"", "tolerance_grade":"",
         "assembly_force":"", "application":""}
    if clearance > 0.5:
        r.update(fit_class="Loose Clearance",
                 fit_description="Free movement, significant play",
                 iso_suggestion="H11/c11 or H8/e8",
                 assembly_force="None — slides freely",
                 application="Hinges, loose pivots")
    elif clearance > 0.1:
        r.update(fit_class="Clearance Fit",
                 fit_description="Running fit, easy assembly",
                 iso_suggestion="H8/f7 or H7/g6",
                 assembly_force="None — hand push",
                 application="Rotating shafts, sliding parts")
    elif clearance > 0.02:
        r.update(fit_class="Close Clearance",
                 fit_description="Accurate location, minimal play",
                 iso_suggestion="H7/h6",
                 assembly_force="Light hand press",
                 application="Precision location, gear hubs")
    elif clearance > -0.01:
        r.update(fit_class="Transition Fit",
                 fit_description="May be clearance or interference",
                 iso_suggestion="H7/k6 or H7/m6",
                 assembly_force="Mallet or light press",
                 application="Precision fits, good alignment needed")
    elif clearance > -0.05:
        r.update(fit_class="Light Interference",
                 fit_description="Light press, permanent assembly",
                 iso_suggestion="H7/p6 or H7/n6",
                 assembly_force="Hydraulic press",
                 application="Bearing rings, bushings")
    else:
        r.update(fit_class="Heavy Interference",
                 fit_description="Heavy press or shrink fit",
                 iso_suggestion="H7/s6 or H7/u6",
                 assembly_force="Heating/cooling required",
                 application="Permanent joints, high torque")
    D = hole_d
    r["tolerance_grade"] = ("IT6/IT7" if D<18 else
                             "IT7/IT8" if D<80 else "IT8/IT9")
    return r

def full_tolerance_report(hole_d, shaft_d, part_a, part_b) -> str:
    fit = classify_fit(hole_d, shaft_d)
    return "\\n".join([
        "="*50, "TOLERANCE ANALYSIS REPORT", "="*50,
        f"Hole part:  {part_a}",
        f"Shaft part: {part_b}",
        f"Hole dia:   {hole_d:.3f} mm",
        f"Shaft dia:  {shaft_d:.3f} mm",
        f"Clearance:  {fit['clearance']:+.3f} mm",
        "", f"CLASS: {fit['fit_class']}",
        f"ISO:   {fit['iso_suggestion']}",
        f"Grade: {fit['tolerance_grade']}",
        f"Force: {fit['assembly_force']}",
        f"Use:   {fit['application']}", "="*50])
'''

FILES["assembly_sequence.py"] = '''"""Multi-step assembly sequence with undo/redo."""
import json, time
from dataclasses import dataclass, field
from typing import List, Optional, Callable

@dataclass
class AssemblyStep:
    step_num: int
    description: str
    part_name: str
    action: str
    params: dict = field(default_factory=dict)
    shape_after = None
    duration_ms: float = 0.0
    success: bool = False
    notes: str = ""

class AssemblySequence:
    def __init__(self):
        self.steps: List[AssemblyStep] = []
        self.current_step = 0
        self._undo_stack: List[int] = []
        self._redo_stack: List[int] = []
        self.on_step_change: Optional[Callable] = None

    def add_step(self, description, part_name, action, params=None):
        s = AssemblyStep(len(self.steps)+1, description,
                         part_name, action, params or {})
        self.steps.append(s); return s

    def mark_complete(self, step, shape_after, duration_ms=0,
                      success=True, notes=""):
        step.shape_after = shape_after
        step.duration_ms = duration_ms
        step.success     = success
        step.notes       = notes
        self._undo_stack.append(step.step_num)
        self._redo_stack.clear()
        self.current_step = step.step_num
        if self.on_step_change: self.on_step_change(step)

    def can_undo(self): return len(self._undo_stack) > 0
    def can_redo(self): return len(self._redo_stack) > 0

    def undo(self):
        if not self.can_undo(): return None
        n = self._undo_stack.pop(); self._redo_stack.append(n)
        s = self.steps[n-1]
        self.current_step = self._undo_stack[-1] if self._undo_stack else 0
        if self.on_step_change: self.on_step_change(s)
        return s

    def redo(self):
        if not self.can_redo(): return None
        n = self._redo_stack.pop(); self._undo_stack.append(n)
        s = self.steps[n-1]; self.current_step = n
        if self.on_step_change: self.on_step_change(s)
        return s

    def to_report(self) -> str:
        lines = ["ASSEMBLY SEQUENCE REPORT", "="*60,
                 f"Total steps: {len(self.steps)}",
                 f"Completed:   {sum(1 for s in self.steps if s.success)}",
                 "-"*60]
        for s in self.steps:
            st = "OK" if s.success else "FAIL"
            lines.append(f"Step {s.step_num:2d} [{st:4s}] "
                         f"[{s.action.upper():10s}] {s.part_name}: {s.description}")
            if s.notes: lines.append(f"           Note: {s.notes}")
        lines.append("="*60)
        return "\\n".join(lines)

    def to_json(self): return json.dumps([{
        "step":s.step_num,"description":s.description,
        "part":s.part_name,"action":s.action,
        "params":s.params,"success":s.success,
        "notes":s.notes} for s in self.steps], indent=2)
'''

FILES["constraints.py"] = '''"""Assembly constraints: coincident, parallel, perpendicular, distance."""
import math
from dataclasses import dataclass, field
from typing import List
from OCC.Core.gp import gp_Trsf, gp_Vec, gp_Ax1, gp_Pnt, gp_Dir
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform

@dataclass
class Constraint:
    type: str
    entity_a: dict
    entity_b: dict
    value: float = 0.0
    description: str = ""

class ConstraintSolver:
    def __init__(self):
        self.constraints: List[Constraint] = []
        self._history: List[Constraint] = []

    def add_constraint(self, c: Constraint):
        self.constraints.append(c); self._history.append(c)

    def undo(self):
        if self.constraints: self.constraints.pop(); return True
        return False

    def apply_coincident(self, shape_b, pnt_a, pnt_b):
        tx,ty,tz = pnt_a[0]-pnt_b[0],pnt_a[1]-pnt_b[1],pnt_a[2]-pnt_b[2]
        t = gp_Trsf(); t.SetTranslation(gp_Vec(tx,ty,tz))
        return BRepBuilderAPI_Transform(shape_b,t,True).Shape(),(tx,ty,tz)

    def apply_distance(self, shape_b, direction, distance):
        dx,dy,dz = direction
        m = math.sqrt(dx**2+dy**2+dz**2)
        if m<1e-10: return shape_b,(0,0,0)
        tx,ty,tz = dx/m*distance,dy/m*distance,dz/m*distance
        t = gp_Trsf(); t.SetTranslation(gp_Vec(tx,ty,tz))
        return BRepBuilderAPI_Transform(shape_b,t,True).Shape(),(tx,ty,tz)

    def summary(self):
        return [f"{c.type}: {c.description}" for c in self.constraints]
'''

FILES["cross_axis_assembler.py"] = '''"""Cross-axis assembly for knuckle joints and perpendicular fits."""
import math
from OCC.Core.gp import gp_Trsf, gp_Vec, gp_Ax1, gp_Pnt, gp_Dir
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform

def _dot(a,b): return sum(x*y for x,y in zip(a,b))
def _cross(a,b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def _norm(v):
    m=math.sqrt(sum(x**2 for x in v)); return tuple(x/m for x in v) if m>1e-10 else v

def detect_rotation_needed(fixed_cyl, moving_cyl) -> dict:
    ha = tuple(fixed_cyl.axis_dir)
    sa = tuple(moving_cyl.axis_dir)
    angle = math.degrees(math.acos(max(-1.0,min(1.0,abs(_dot(ha,sa))))))
    if angle < 5:
        return {"needed":False,"angle":0,"axis":(0,0,1)}
    rot_axis = _norm(_cross(sa, ha))
    return {"needed":True,"angle":angle,"axis":rot_axis,
            "shaft_axis":sa,"hole_axis":ha}

def apply_cross_axis_assembly(fixed_shape, moving_shape,
                               fixed_cyl, moving_cyl,
                               pre_rotate_axis=None, pre_rotate_deg=None):
    rot = detect_rotation_needed(fixed_cyl, moving_cyl)
    pivot = gp_Pnt(*moving_cyl.center)
    trsf_rot = gp_Trsf()
    if pre_rotate_axis and pre_rotate_deg:
        ax = {"x":(1,0,0),"y":(0,1,0),"z":(0,0,1)}.get(
             pre_rotate_axis.lower(),(0,0,1))
        trsf_rot.SetRotation(gp_Ax1(pivot,gp_Dir(*ax)),
                              math.radians(pre_rotate_deg))
    elif rot["needed"]:
        rx,ry,rz = rot["axis"]
        trsf_rot.SetRotation(gp_Ax1(pivot,gp_Dir(rx,ry,rz)),
                              math.radians(rot["angle"]))
    rotated = BRepBuilderAPI_Transform(moving_shape,trsf_rot,True).Shape()
    mc = gp_Pnt(*moving_cyl.center).Transformed(trsf_rot)
    hc = fixed_cyl.center
    hax,hay,haz = fixed_cyl.axis_dir
    hd = getattr(fixed_cyl,"depth",0) or getattr(fixed_cyl,"length",20)
    tx = hc[0]-mc.X()+hax*(hd/2)
    ty = hc[1]-mc.Y()+hay*(hd/2)
    tz = hc[2]-mc.Z()+haz*(hd/2)
    trsf_t = gp_Trsf(); trsf_t.SetTranslation(gp_Vec(tx,ty,tz))
    assembled = BRepBuilderAPI_Transform(rotated,trsf_t,True).Shape()
    return assembled,(tx,ty,tz),rot
'''

FILES["export_formats.py"] = '''"""Export to STEP, IGES, STL, FreeCAD script."""
import os
from OCC.Core.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCC.Core.IGESControl import IGESControl_Writer
from OCC.Core.BRepMesh    import BRepMesh_IncrementalMesh
from OCC.Core.StlAPI      import StlAPI_Writer
from OCC.Core.Interface   import Interface_Static
from OCC.Core.IFSelect    import IFSelect_RetDone

def _step(shape, path, schema="AP214CD"):
    w = STEPControl_Writer()
    Interface_Static.SetCVal("write.step.schema", schema)
    w.Transfer(shape, STEPControl_AsIs)
    return w.Write(path) == IFSelect_RetDone

def export_step_catia(shape, path):     return _step(shape,path,"AP214CD")
def export_step_solidworks(shape,path): return _step(shape,path,"AP203")
def export_step_ap242(shape, path):     return _step(shape,path,"AP242DIS")

def export_iges(shape, path):
    w = IGESControl_Writer(); w.AddShape(shape); w.ComputeModel()
    return w.Write(path)

def export_stl(shape, path, lin=0.1, ang=0.5):
    BRepMesh_IncrementalMesh(shape,lin,False,ang).Perform()
    w = StlAPI_Writer(); w.SetASCIIMode(False)
    return w.Write(shape, path)

def export_all_formats(shape, base, out_dir="."):
    os.makedirs(out_dir, exist_ok=True)
    res = {}
    for name,func,ext in [
        ("STEP_AP214", export_step_catia,      ".step"),
        ("STEP_AP203", export_step_solidworks, "_sw.step"),
        ("STEP_AP242", export_step_ap242,      "_ap242.step"),
        ("IGES",       export_iges,            ".igs"),
        ("STL",        export_stl,             ".stl"),
    ]:
        p = os.path.join(out_dir, base+ext)
        try: ok=func(shape,p); res[name]={"path":p,"ok":ok}
        except Exception as e: res[name]={"path":p,"ok":False,"error":str(e)}
    return res

def export_step(shape, path):
    """Alias — default STEP export (AP214)."""
    return _step(shape, path, "AP214CD")

def export_freecad_script(parts_info, transforms, out_path):
    lines = ["# FreeCAD Assembly Script — AI CAD System",
             "import FreeCAD, Part","doc = FreeCAD.newDocument('Assembly')",""]
    for i,(p,t) in enumerate(zip(parts_info,transforms)):
        n = p.get("name","Part").replace(" ","_").replace(".","_")
        fp = p.get("filepath","").replace("\\\\","/")
        tx,ty,tz = t if t else (0,0,0)
        lines += [f"s{i}=Part.Shape(); s{i}.read(r\'{fp}\')",
                  f"o{i}=doc.addObject(\'Part::Feature\',\'{n}\')",
                  f"o{i}.Shape=s{i}",
                  f"o{i}.Placement=FreeCAD.Placement(",
                  f"  FreeCAD.Vector({tx:.3f},{ty:.3f},{tz:.3f}),",
                  f"  FreeCAD.Rotation(0,0,0,1))",""]
    lines += ["doc.recompute()","doc.save(\'assembly.FCStd\')"]
    with open(out_path,"w") as f: f.write("\\n".join(lines))
    return "\\n".join(lines)
'''

FILES["claude_ai_engine.py"] = r'''"""
Claude API integration for intelligent geometry understanding.
Falls back to rule-based if API unavailable.
"""
import json, re, math
from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class AssemblyPlan:
    moving_part: str = ""
    fixed_part: str = ""
    hole_description: str = ""
    insertion_depth: float = 0.0
    rotation_needed: bool = False
    rotation_axis: str = ""
    rotation_degrees: float = 0.0
    fit_type: str = "clearance"
    constraints: list = field(default_factory=list)
    steps: list = field(default_factory=list)
    confidence: float = 0.0
    explanation: str = ""

def build_geometry_context(parts_data: list) -> str:
    lines = []
    for p in parts_data:
        lines.append(f"Part: {p['name']}")
        lines.append(f"  BBox: {p.get('bbox','')} mm")
        lines.append(f"  Type: {p.get('type','unknown')}")
        for c in p.get("cylinders",[]):
            kind = "HOLE" if c.get("is_hole") else "SHAFT"
            lines.append(f"  {kind}: d={c['d']:.1f}mm axis={c.get('axis')} "
                        f"center={c.get('center')}")
        lines.append("")
    return "\n".join(lines)

def call_claude_api(prompt: str, geometry_context: str,
                    user_instruction: str) -> AssemblyPlan:
    plan = AssemblyPlan()
    sys_prompt = (
        "You are a CAD assembly engineer. Analyze geometry and plan assemblies. "
        "Respond ONLY with valid JSON: {"
        '"moving_part":"","fixed_part":"","hole_description":"",'
        '"insertion_depth":0,"rotation_needed":false,"rotation_axis":"",'
        '"rotation_degrees":0,"fit_type":"clearance",'
        '"constraints":[],"steps":[],"confidence":0.9,"explanation":""}')
    messages = [{"role":"user","content":
        f'Assembly: "{user_instruction}"\n\nGeometry:\n{geometry_context}\n'
        f'Plan the assembly. Detect cross-axis rotation if shaft and bore axes differ.'}]
    try:
        import urllib.request
        payload = json.dumps({"model":"claude-sonnet-4-20250514",
                              "max_tokens":1000,
                              "system":sys_prompt,
                              "messages":messages}).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages", data=payload,
            headers={"Content-Type":"application/json",
                     "anthropic-version":"2023-06-01"}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            text = data["content"][0]["text"]
            m = re.search(r'\{.*\}', text, re.DOTALL)
            if m:
                d = json.loads(m.group())
                plan.moving_part      = d.get("moving_part","")
                plan.fixed_part       = d.get("fixed_part","")
                plan.hole_description = d.get("hole_description","")
                plan.insertion_depth  = float(d.get("insertion_depth",0))
                plan.rotation_needed  = bool(d.get("rotation_needed",False))
                plan.rotation_axis    = d.get("rotation_axis","")
                plan.rotation_degrees = float(d.get("rotation_degrees",0))
                plan.fit_type         = d.get("fit_type","clearance")
                plan.constraints      = d.get("constraints",[])
                plan.steps            = d.get("steps",[])
                plan.confidence       = float(d.get("confidence",0.8))
                plan.explanation      = d.get("explanation","")
    except Exception as e:
        plan.explanation = f"API unavailable: {e}"
        plan.confidence  = 0.0
    return plan

def analyze_cross_axis(part_a: dict, part_b: dict) -> dict:
    def dot(a,b): return sum(x*y for x,y in zip(a,b))
    cyls_a = part_a.get("cylinders",[])
    cyls_b = part_b.get("cylinders",[])
    bore   = next((c for c in cyls_a if c.get("is_hole") and c["d"]>20),None)
    shaft  = next((c for c in cyls_b if not c.get("is_hole") and c["d"]>20),None)
    if bore and shaft:
        import math
        ax_a = bore.get("axis",(0,1,0))
        ax_b = shaft.get("axis",(0,1,0))
        angle = math.degrees(math.acos(max(-1,min(1,abs(dot(ax_a,ax_b))))))
        if angle > 30:
            cx=ax_a[1]*ax_b[2]-ax_a[2]*ax_b[1]
            cy=ax_a[2]*ax_b[0]-ax_a[0]*ax_b[2]
            cz=ax_a[0]*ax_b[1]-ax_a[1]*ax_b[0]
            best = ["x","y","z"][[abs(cx),abs(cy),abs(cz)].index(
                    max(abs(cx),abs(cy),abs(cz)))]
            return {"rotation_needed":True,"degrees":angle,"axis":best}
    return {"rotation_needed":False,"degrees":0,"axis":""}
'''

# ── Now write all files ─────────────────────────────────────────────
written = []
errors  = []
for fname, code in FILES.items():
    path = os.path.join(PROJECT, fname)
    try:
        ast.parse(code)
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        written.append(fname)
        print(f"  ✓ {fname}")
    except SyntaxError as e:
        errors.append((fname, str(e)))
        print(f"  ✗ {fname} — SYNTAX ERROR: {e}")

# ── Copy gui_pro.py ─────────────────────────────────────────────────
gui_src = os.path.join(os.path.dirname(__file__), "gui_pro.py")
gui_dst = os.path.join(PROJECT, "gui_pro.py")
if os.path.exists(gui_src) and os.path.abspath(gui_src) != os.path.abspath(gui_dst):
    shutil.copy2(gui_src, gui_dst)
    print(f"  ✓ gui_pro.py (copied)")
    written.append("gui_pro.py")
elif os.path.exists(gui_dst):
    print(f"  ✓ gui_pro.py (already in place)")
    written.append("gui_pro.py")

# ── Copy assembler_pro.py ───────────────────────────────────────────
asm_src = os.path.join(os.path.dirname(__file__), "assembler_pro.py")
asm_dst = os.path.join(PROJECT, "assembler_pro.py")
if os.path.exists(asm_src) and os.path.abspath(asm_src) != os.path.abspath(asm_dst):
    shutil.copy2(asm_src, asm_dst)
    print(f"  ✓ assembler_pro.py (copied)")
    written.append("assembler_pro.py")
elif os.path.exists(asm_dst):
    print(f"  ✓ assembler_pro.py (already in place)")
    written.append("assembler_pro.py")

print()
print("=" * 60)
print(f"Installed {len(written)} files successfully")
if errors:
    print(f"ERRORS in {len(errors)} files:")
    for fn, e in errors:
        print(f"  {fn}: {e}")
print()
print("TO RUN THE INDUSTRY EDITION:")
print("  python gui_pro.py")
print()
print("NEW FEATURES:")
print("  • Claude AI toggle (checkbox in toolbar)")
print("  • Tolerance analysis tab (H7/g6 etc.)")
print("  • Bill of Materials tab + CSV/JSON export")
print("  • Assembly sequence with Undo/Redo")
print("  • Constraints panel")
print("  • Export: STEP AP214/AP203/AP242, IGES, STL, FreeCAD")
print("  • Cross-axis auto-detection")
print("  • Insertion depth control")
print("  • 3D Preview button")
print("=" * 60)