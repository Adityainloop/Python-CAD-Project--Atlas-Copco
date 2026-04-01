"""
ai_assembly_engine.py — AI-driven geometric operation engine
"""
import json, re, math, urllib.request, urllib.error
from typing import Optional, List
from dataclasses import dataclass, field


@dataclass
class GeometricOperation:
    moving_part_hint: str = ""
    fixed_part_hint:  str = ""
    strategy: str = "auto"
    pre_rotate_axis: str = ""
    pre_rotate_degrees: float = 0.0
    hole_description: str = ""
    insertion_depth: float = 0.0
    full_depth: bool = True
    clearance: float = 0.0
    gap: float = 0.0
    press_fit: bool = False
    prefer_cylinder: bool = False
    prefer_plane: bool = False
    side_by_side: bool = False
    confidence: float = 0.0
    ai_explanation: str = ""
    raw_prompt: str = ""


SYSTEM_PROMPT = """You are a CAD assembly AI. Convert user instructions to JSON assembly operations.

Return ONLY a JSON array. Each item:
{
  "moving_part_hint": "words from filename of part to move",
  "fixed_part_hint": "words from filename of fixed part",
  "strategy": "slot" | "shaft_hole" | "side_hole" | "plane" | "bbox" | "side_by_side",
  "pre_rotate_axis": "" | "x" | "y" | "z",
  "pre_rotate_degrees": 0,
  "hole_description": "" | "small" | "large" | "side" | "middle" | "slot" | "cavity" | "edge",
  "insertion_depth": 0,
  "full_depth": true,
  "press_fit": false,
  "gap": 0,
  "prefer_plane": false,
  "side_by_side": false,
  "ai_explanation": "what you understood"
}

RULES:
- "rotate X degrees around Y axis" = pre_rotate_axis=Y, pre_rotate_degrees=X
- "rotate 90 around x" = pre_rotate_axis="x", pre_rotate_degrees=90
- "turn to Y axis" = pre_rotate_axis="y", pre_rotate_degrees=90
- "flip" = pre_rotate_degrees=180
- "slot" / "cavity" / "groove" = strategy="slot"
- "insert plate into slot" = strategy="slot", prefer_plane=true
- "side hole" = strategy="side_hole", hole_description="side"
- "small hole" = hole_description="small"
- "insert Xmm" = insertion_depth=X, full_depth=false
- "fully" = full_depth=true
- "face to face" / "flush" = strategy="plane"
- "side by side" = side_by_side=true"""


def parse_with_ai(prompt: str, parts_info: list, api_key: str = "") -> List[GeometricOperation]:
    if not prompt.strip():
        return []
    if api_key:
        try:
            ops = _call_claude(prompt, parts_info, api_key)
            if ops: return ops
        except Exception as e:
            print(f"[AI] API failed: {e} — using rule parser")
    return _rule_based_parse(prompt, parts_info)


def _call_claude(prompt, parts_info, api_key):
    ctx = f"Parts:\n{json.dumps(parts_info, indent=2)}\n\nInstruction: {prompt}"
    payload = json.dumps({
        "model": "claude-sonnet-4-20250514", "max_tokens": 1000,
        "system": SYSTEM_PROMPT,
        "messages": [{"role":"user","content":ctx}]
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=payload,
        headers={"Content-Type":"application/json","x-api-key":api_key,
                 "anthropic-version":"2023-06-01"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode())
    text = "".join(b.get("text","") for b in data.get("content",[]) if b.get("type")=="text")
    text = re.sub(r"```json\s*|\s*```","",text).strip()
    parsed = json.loads(text)
    if isinstance(parsed, dict): parsed = [parsed]
    return [_dict_to_op(d, prompt) for d in parsed]


def _dict_to_op(d, raw):
    op = GeometricOperation(raw_prompt=raw)
    for k in ['moving_part_hint','fixed_part_hint','strategy','pre_rotate_axis',
              'hole_description','ai_explanation']:
        setattr(op, k, str(d.get(k,"")))
    op.pre_rotate_axis = op.pre_rotate_axis.lower()
    op.pre_rotate_degrees = float(d.get("pre_rotate_degrees",0))
    op.insertion_depth = float(d.get("insertion_depth",0))
    op.full_depth = bool(d.get("full_depth",True))
    op.press_fit = bool(d.get("press_fit",False))
    op.gap = float(d.get("gap",0))
    op.prefer_plane = bool(d.get("prefer_plane",False))
    op.side_by_side = bool(d.get("side_by_side",False))
    if op.insertion_depth > 0: op.full_depth = False
    if op.strategy in ("shaft_hole","side_hole"): op.prefer_cylinder = True
    elif op.strategy in ("plane","slot"): op.prefer_plane = True
    op.confidence = 0.95
    return op


def _rule_based_parse(prompt: str, parts_info: list) -> List[GeometricOperation]:
    """Rule-based parser — handles all common phrasings."""
    t = prompt.lower().strip()
    
    # Split into segments
    segments = re.split(
        r',\s*(?=insert|place|put|rotate|turn|mate|assemble|slide|push)'
        r'|\s+and\s+(?=insert|place|put|rotate|turn|slide)',
        t)
    
    ops = []
    for seg in [s.strip() for s in segments if s.strip()]:
        op = _parse_one(seg, parts_info)
        if op: ops.append(op)
    
    if not ops:
        op = _parse_one(t, parts_info)
        if op: ops.append(op)
    
    return ops


def _parse_one(seg: str, parts_info: list) -> Optional[GeometricOperation]:
    op = GeometricOperation(raw_prompt=seg)
    score = 0

    # ── ROTATION (many phrasings) ─────────────────────────────────────────
    # "rotate X degrees around Y axis"
    # "rotate 90 around x"  
    # "rotate X 90 degrees"
    # "turn X to Y axis"
    # "change X to Y plane"

    # Pattern 1: "rotate [partname] [N] degrees around [axis]"
    m = re.search(r'rotate\s+(?:\w+\s+)*?(\d+(?:\.\d+)?)\s*(?:degrees?|deg|°)?\s*'
                  r'(?:around\s+|about\s+)?([xyz])\s*(?:axis)?', seg)
    if m:
        op.pre_rotate_degrees = float(m.group(1))
        op.pre_rotate_axis    = m.group(2)
        score += 4

    # Pattern 2: "rotate [N] degrees [axis]"  or "rotate [axis] [N]"
    if not op.pre_rotate_axis:
        m = re.search(r'rotate\s+(\d+(?:\.\d+)?)\s*(?:degrees?|deg)?\s*([xyz])', seg)
        if m:
            op.pre_rotate_degrees = float(m.group(1))
            op.pre_rotate_axis    = m.group(2)
            score += 4
    if not op.pre_rotate_axis:
        m = re.search(r'rotate\s+([xyz])\s*(?:axis)?\s*(\d+(?:\.\d+)?)', seg)
        if m:
            op.pre_rotate_axis    = m.group(1)
            op.pre_rotate_degrees = float(m.group(2))
            score += 4

    # Pattern 3: "turn [part] to Y axis"
    if not op.pre_rotate_axis:
        m = re.search(r'turn\s+(?:\w+\s+)*?to\s+([xyz])\s*(?:axis|plane)', seg)
        if m:
            op.pre_rotate_axis    = m.group(1)
            op.pre_rotate_degrees = 90.0
            score += 4

    # Pattern 4: "change to Y axis/plane" or "move to Y"
    if not op.pre_rotate_axis:
        m = re.search(r'(?:change|move|switch)\s+(?:to\s+)?([xyz])\s*(?:axis|plane)', seg)
        if m:
            op.pre_rotate_axis    = m.group(1)
            op.pre_rotate_degrees = 90.0
            score += 3

    # Flip
    if 'flip' in seg or 'upside down' in seg or '180' in seg:
        op.pre_rotate_degrees = 180.0
        if not op.pre_rotate_axis: op.pre_rotate_axis = 'x'
        score += 3

    # ── STRATEGY ─────────────────────────────────────────────────────────
    if any(w in seg for w in ['press fit','force fit','interference']):
        op.strategy='shaft_hole'; op.press_fit=True; op.prefer_cylinder=True; score+=3

    elif any(w in seg for w in ['slot','cavity','groove','channel','rectangular hole',
                                  'rectangular slot','insert plate','slide plate','plate into']):
        op.strategy='slot'; op.prefer_plane=True; score+=3

    elif any(w in seg for w in ['side hole','radial hole','surface hole','hole on side']):
        op.strategy='side_hole'; op.hole_description='side'; op.prefer_cylinder=True; score+=3

    elif any(w in seg for w in ['shaft','bore','pin','cylinder','bearing']):
        op.strategy='shaft_hole'; op.prefer_cylinder=True; score+=2

    elif any(w in seg for w in ['face','flush','flat','plane','surface']):
        op.strategy='plane'; op.prefer_plane=True; score+=2

    elif any(w in seg for w in ['side by side','next to','beside','adjacent','apart']):
        op.strategy='side_by_side'; op.side_by_side=True; score+=3

    elif any(w in seg for w in ['insert','assemble','mate','put','place','slide','push']):
        # Generic insert — determine from context
        if any(w in seg for w in ['hole','bore','cavity','slot']):
            op.strategy='auto'; score+=1
        else:
            op.strategy='auto'; score+=1

    # ── HOLE DESCRIPTION ─────────────────────────────────────────────────
    import re as _re
    for kw,val in [('small','small'),('smallest','small'),('large','large'),
                   ('biggest','large'),('main bore','large'),
                   ('side hole','side'),('edge hole','edge'),('surface hole','side'),
                   ('middle','middle'),('center','middle'),('central','middle'),
                   ('slot','slot'),('cavity','slot'),('rectangular','slot')]:
        if ' ' in kw: matches = kw in seg
        else: matches = bool(_re.search(r'\b' + kw + r'\b', seg))
        if matches and not op.hole_description:
            op.hole_description = val; break
    if not op.hole_description:
        if _re.search(r'\bside\b', seg): op.hole_description = 'side'
        elif _re.search(r'\bedge\b', seg): op.hole_description = 'edge'

    m = re.search(r'(\d+(?:\.\d+)?)\s*mm\s*hole', seg)
    if m: op.hole_description = f"{m.group(1)}mm"; score+=2

    # ── DEPTH ─────────────────────────────────────────────────────────────
    if any(w in seg for w in ['fully','completely','through','all the way','full depth']):
        op.full_depth=True; score+=2
    else:
        for pat in [r'(\d+(?:\.\d+)?)\s*mm\s*(?:deep|inside|into|depth|inward)',
                    r'(?:insert|push|slide|go)\s+(\d+(?:\.\d+)?)\s*mm',
                    r'(\d+(?:\.\d+)?)\s*mm\s*(?:in\b|inside\b)']:
            m = re.search(pat, seg)
            if m:
                op.insertion_depth = float(m.group(1))
                op.full_depth = False; score+=3; break

    # ── GAP ───────────────────────────────────────────────────────────────
    m = re.search(r'(\d+(?:\.\d+)?)\s*mm\s*gap', seg)
    if m: op.gap=float(m.group(1)); score+=1

    # ── PART HINTS ────────────────────────────────────────────────────────
    for p in parts_info:
        name = p.get('name','').lower()
        words = [w for w in re.sub(r'[_\-]',' ',name).split() if len(w)>2]
        for w in words:
            if w in seg:
                if any(x in name for x in ['solid','plate','block','flat']) and \
                   not any(x in name for x in ['hole','cavity','slot','bore']):
                    if not op.moving_part_hint: op.moving_part_hint=name
                else:
                    if not op.fixed_part_hint: op.fixed_part_hint=name

    op.confidence = min(1.0, score/8.0)
    
    # Return if we got something meaningful
    if score>0 or op.pre_rotate_degrees>0:
        return op
    return None


def apply_pre_rotation(shape, axis: str, degrees: float):
    """Rotate shape around world axis by given degrees."""
    if not axis or abs(degrees) < 0.01:
        return shape
    from OCC.Core.gp import gp_Trsf, gp_Ax1, gp_Pnt, gp_Dir
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCC.Core.BRepBndLib import brepbndlib
    from OCC.Core.Bnd import Bnd_Box
    box=Bnd_Box(); brepbndlib.Add(shape,box)
    x0,y0,z0,x1,y1,z1=box.Get()
    cx,cy,cz=(x0+x1)/2,(y0+y1)/2,(z0+z1)/2
    axes={'x':(1,0,0),'y':(0,1,0),'z':(0,0,1)}
    ax=axes.get(axis.lower(),(0,1,0))
    trsf=gp_Trsf()
    trsf.SetRotation(gp_Ax1(gp_Pnt(cx,cy,cz),gp_Dir(*ax)),math.radians(degrees))
    b=BRepBuilderAPI_Transform(shape,trsf,True); b.Build()
    return b.Shape()


def build_parts_context(parts) -> list:
    result=[]
    for p in parts:
        import math
        holes=[]
        for c in p.holes[:4]:
            hx,hy,hz=c.center; bcx,bcy,bcz=[(p.bbox_min[i]+p.bbox_max[i])/2 for i in range(3)]
            dx,dy,dz=p.bbox_dims; r=max(dx,dy,dz)/2
            dist=math.sqrt((hx-bcx)**2+(hy-bcy)**2+(hz-bcz)**2)
            htype="side_hole" if dist>r*0.4 else "bore"
            holes.append({"d_mm":round(c.diameter,2),"type":htype})
        result.append({"name":p.name,"type":p.part_type,
                       "size_mm":[round(d,1) for d in p.bbox_dims],
                       "holes":holes,"shafts":[{"d_mm":round(c.diameter,2)} for c in p.shafts[:2]],
                       "n_planes":len(p.planes)})
    return result