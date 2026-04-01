"""
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
