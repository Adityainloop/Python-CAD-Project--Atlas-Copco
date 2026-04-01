"""
claude_ai_engine_v2.py
======================
Proper Claude API integration for geometry-aware assembly planning.
Claude receives full geometry data + user prompt and returns EXACT
3D transforms (translation + rotation) for each part.
"""
import json, re, math
from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class PartTransform:
    part_name: str
    translate: tuple = (0.0, 0.0, 0.0)   # (tx, ty, tz) mm
    rotate_axis: tuple = (0.0, 0.0, 1.0)  # rotation axis
    rotate_degrees: float = 0.0            # rotation angle
    assembly_type: str = "hole_shaft"      # hole_shaft / stack_top / stack_bottom / plane / manual
    hole_description: str = ""
    insertion_depth: float = 0.0
    confidence: float = 0.0
    explanation: str = ""
    raw: dict = field(default_factory=dict)

@dataclass 
class AssemblyPlanV2:
    anchor_part: str = ""
    transforms: List[PartTransform] = field(default_factory=list)
    assembly_sequence: List[str] = field(default_factory=list)
    overall_explanation: str = ""
    confidence: float = 0.0
    fallback_to_rules: bool = False

def build_rich_geometry_context(parts_data: list) -> str:
    """Build detailed geometry description for Claude."""
    lines = ["=== PART GEOMETRY DATA ===\n"]
    for p in parts_data:
        name = p.get('name', '?')
        bbox = p.get('bbox_dims', (0,0,0))
        center = p.get('bbox_center', (0,0,0))
        lines.append(f"PART: {name}")
        lines.append(f"  BBox: {bbox[0]:.0f}x{bbox[1]:.0f}x{bbox[2]:.0f}mm")
        lines.append(f"  Center: ({center[0]:.1f}, {center[1]:.1f}, {center[2]:.1f})")
        
        holes  = [c for c in p.get('cylinders',[]) if c.get('is_hole')]
        shafts = [c for c in p.get('cylinders',[]) if not c.get('is_hole')]
        planes = p.get('planes', [])
        
        if holes:
            lines.append(f"  HOLES ({len(holes)}):")
            # Show only significant holes (d > 10mm) to avoid noise
            sig = sorted([h for h in holes if h.get('d',0)>10],
                        key=lambda x: -x.get('d',0))[:5]
            for h in sig:
                lines.append(f"    d={h['d']:.1f}mm L={h.get('L',0):.1f}mm "
                             f"axis={tuple(round(x,2) for x in h.get('axis',(0,1,0)))} "
                             f"center={tuple(round(x,1) for x in h.get('center',(0,0,0)))}")
        if shafts:
            lines.append(f"  SHAFTS ({len(shafts)}):")
            sig = sorted([s for s in shafts if s.get('d',0)>10],
                        key=lambda x: -x.get('d',0))[:5]
            for s in sig:
                lines.append(f"    d={s['d']:.1f}mm L={s.get('L',0):.1f}mm "
                             f"axis={tuple(round(x,2) for x in s.get('axis',(0,1,0)))} "
                             f"center={tuple(round(x,1) for x in s.get('center',(0,0,0)))}")
        if planes:
            lines.append(f"  PLANES ({len(planes)}):")
            for pl in planes[:3]:
                lines.append(f"    normal={tuple(round(x,2) for x in pl.get('normal',(0,1,0)))} "
                             f"area={pl.get('area',0):.0f}mm²")
        lines.append("")
    return "\n".join(lines)

SYSTEM_PROMPT = """You are an expert CAD assembly engineer with deep knowledge of mechanical engineering.

You receive:
1. Detailed geometry data of each part (bounding boxes, holes, shafts, planes with exact 3D positions)
2. A natural language assembly instruction from the user

Your job is to plan the EXACT 3D assembly by returning precise transforms for each part.

RULES:
- The anchor part (usually the largest structural part with most holes) stays at origin
- All other parts are moved relative to the anchor
- For shaft-into-hole: align shaft axis with hole axis, translate shaft center to hole center
- For stacking (frame on frame): translate so bottom face of upper part meets top face of lower part
- For blades on shaft: space them evenly along shaft axis
- When axes are perpendicular (e.g. shaft X-axis, bore Y-axis): pre-rotate the moving part first
- Return EXACT translate (tx,ty,tz) values based on the actual coordinate data provided

Respond ONLY with valid JSON in exactly this format:
{
  "anchor_part": "name of fixed part",
  "assembly_sequence": ["part1", "part2", ...],
  "overall_explanation": "brief description of assembly approach",
  "confidence": 0.95,
  "transforms": [
    {
      "part_name": "exact filename stem",
      "assembly_type": "hole_shaft|stack_top|stack_bottom|plane|manual",
      "translate": [tx, ty, tz],
      "rotate_axis": [rx, ry, rz],
      "rotate_degrees": 0.0,
      "hole_description": "large|middle|edge|bore|small|side",
      "insertion_depth": 0.0,
      "explanation": "why this transform"
    }
  ]
}

Assembly types:
- "hole_shaft": shaft goes into hole (system handles axis alignment, you provide depth/hole_description)  
- "stack_top": place part on top of anchor (system uses bbox top face)
- "stack_bottom": place part below anchor (system uses bbox bottom face)
- "plane": face-to-face contact
- "manual": use exact translate/rotate values you provide (for complex cases)"""

def call_claude_for_assembly(user_prompt: str, parts_data: list,
                              api_key: str = "") -> AssemblyPlanV2:
    """
    Call Claude API with full geometry context.
    Returns AssemblyPlanV2 with exact transforms per part.
    """
    plan = AssemblyPlanV2()
    
    geometry_ctx = build_rich_geometry_context(parts_data)
    
    user_message = f"""Assembly instruction: "{user_prompt}"

{geometry_ctx}

Based on the geometry data above, plan the complete assembly.
Use the EXACT coordinate values from the geometry data to compute transforms.
Pay attention to axis directions and part centers."""

    try:
        import urllib.request
        
        payload = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 2000,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_message}]
        }).encode()
        
        headers = {"Content-Type": "application/json",
                   "anthropic-version": "2023-06-01"}
        if api_key:
            headers["x-api-key"] = api_key
        
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload, headers=headers, method="POST")
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            text = data["content"][0]["text"]
            
            # Parse JSON response
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                plan.anchor_part         = parsed.get("anchor_part", "")
                plan.assembly_sequence   = parsed.get("assembly_sequence", [])
                plan.overall_explanation = parsed.get("overall_explanation", "")
                plan.confidence          = float(parsed.get("confidence", 0.8))
                
                for t in parsed.get("transforms", []):
                    tr = PartTransform(
                        part_name      = t.get("part_name", ""),
                        assembly_type  = t.get("assembly_type", "hole_shaft"),
                        translate      = tuple(t.get("translate", [0,0,0])),
                        rotate_axis    = tuple(t.get("rotate_axis", [0,0,1])),
                        rotate_degrees = float(t.get("rotate_degrees", 0)),
                        hole_description = t.get("hole_description", ""),
                        insertion_depth  = float(t.get("insertion_depth", 0)),
                        explanation    = t.get("explanation", ""),
                        confidence     = plan.confidence,
                        raw            = t
                    )
                    plan.transforms.append(tr)
                    
    except Exception as e:
        print(f"[Claude API] Error: {e}")
        plan.fallback_to_rules = True
        plan.overall_explanation = f"API error: {e}"
    
    return plan


def apply_claude_plan(plan: AssemblyPlanV2, engine) -> bool:
    """
    Apply Claude's assembly plan to the engine.
    Returns True if plan was applied, False if fallback needed.
    """
    if plan.fallback_to_rules or not plan.transforms:
        return False
    
    from ai_assembly_engine import GeometricOperation
    
    ops = []
    for t in plan.transforms:
        op = GeometricOperation(raw_prompt=t.explanation)
        op.moving_part_hint  = t.part_name
        op.hole_description  = t.hole_description or "large"
        op.insertion_depth   = t.insertion_depth
        op.assembly_type     = t.assembly_type
        op._claude_translate = t.translate       # exact override
        op._claude_rotate_axis    = t.rotate_axis
        op._claude_rotate_degrees = t.rotate_degrees
        ops.append(op)
    
    engine.set_instruction(ops)
    engine._claude_plan = plan  # store for assembler to use
    return True