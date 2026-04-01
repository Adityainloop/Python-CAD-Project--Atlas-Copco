"""
smart_matcher.py  — size-aware matching (fixes pin-into-radial-hole bug)

ROOT CAUSE OF BUG:
  Bearing has 2 cylinders:
    1. Large bore  r~30mm, axis=X  <- was WRONGLY winning (big = high score)
    2. Small radial hole r~3mm, axis=Z  <- should match the pin

  Pin has 1 cylinder:
    1. Shaft r~3mm, axis=X

OLD scoring: 0.85 - small_penalty_for_clearance
  Pin(r=3) vs bore(r=30): clearance=54mm, penalty=54/25*0.25=0.54, score=0.31
  Pin(r=3) vs hole(r=3):  clearance=0mm,  penalty=0,             score=0.85
  --> hole(r=3) SHOULD win. But if bore axis is parallel and hole axis is perp,
      the axis penalty was also applied, killing the radial hole score.

NEW scoring: PRIMARY = diameter similarity ratio
  Pin(r=3) vs bore(r=30): dia_score = 1 - 54/6 = NEGATIVE -> clamped to 0.0
  Pin(r=3) vs hole(r=3):  dia_score = 1 - 0/6  = 1.0 -> score = 0.70
  --> Small hole wins decisively.
"""

import math
from typing import List, Optional, Dict, Any
from part_model import PartModel, CylinderFeature, PlaneFeature, HolePattern
from geometry_analyzer import analyse_fit
from prompt_parser import AssemblyInstruction

MAX_DIA_CLEARANCE = 30.0
MIN_DIA_CLEARANCE = -2.0
MAX_AXIS_ANGLE    = 90.0
MIN_AREA_RATIO    = 0.15


def find_all_matches(part_a, part_b, instruction=None):
    candidates = []
    candidates.extend(_shaft_hole_matches(part_a, part_b, instruction))
    candidates.extend(_bolt_pattern_matches(part_a, part_b, instruction))
    candidates.extend(_plane_matches(part_a, part_b, instruction))
    if instruction:
        for c in candidates:
            if instruction.prefer_cylinder and c["strategy"]=="cylinder":
                c["confidence"]=min(1.0,c["confidence"]+0.15)
            if instruction.prefer_plane and c["strategy"] in ("plane","slot"):
                c["confidence"]=min(1.0,c["confidence"]+0.15)
            if instruction.prefer_bolt and c["strategy"]=="bolt_pattern":
                c["confidence"]=min(1.0,c["confidence"]+0.15)
    candidates.sort(key=lambda c:c["confidence"],reverse=True)
    return candidates


def best_match(part_a, part_b, instruction=None):
    m=find_all_matches(part_a,part_b,instruction)
    return m[0] if m else None


def _shaft_hole_matches(part_a, part_b, inst):
    results=[]
    all_a=part_a.cylinders; all_b=part_b.cylinders
    if not all_a or not all_b: return results
    for ca in all_a:
        for cb in all_b:
            if ca is cb: continue
            m=_eval_pair(ca,cb,"a","b",inst)
            if m: results.append(m)
            m=_eval_pair(cb,ca,"b","a",inst)
            if m: results.append(m)
    # Deduplicate
    seen=set(); unique=[]
    for r in results:
        k=(id(r["shaft"]),id(r["hole"]))
        if k not in seen: seen.add(k); unique.append(r)
    return unique


def _eval_pair(shaft, hole, sp, hp, inst):
    clearance = hole.diameter - shaft.diameter
    if clearance < MIN_DIA_CLEARANCE: return None
    if clearance > MAX_DIA_CLEARANCE: return None

    # PRIMARY: diameter similarity (most important)
    # 0mm clearance -> dia_score=1.0
    # clearance > shaft_diameter -> dia_score < 0 -> clamped to 0
    ref = max(shaft.diameter, 1.0)
    dia_score = max(0.0, 1.0 - abs(clearance)/ref)
    primary = dia_score * 0.70

    # SECONDARY: axis alignment
    angle = _axis_angle(shaft.axis_dir, hole.axis_dir)
    if   angle <= 20.0: axis_score = 0.20  # parallel (normal)
    elif angle <= 70.0: axis_score = 0.05  # oblique
    else:               axis_score = 0.12  # perpendicular = radial hole

    # TERTIARY: shaft < hole (correct direction)
    dir_score = 0.10 if clearance >= 0 else 0.0

    score = primary + axis_score + dir_score
    if inst:
        if inst.press_fit and clearance < 0: score += 0.05
        if inst.prefer_cylinder: score += 0.05
    score = max(0.0, min(1.0, score))
    if score < 0.05: return None

    depth = 0.0
    if inst and inst.full_depth: depth=0.0
    elif inst and inst.insertion_depth: depth=inst.insertion_depth
    else: depth=hole.depth if (hole.depth and hole.depth>0) else hole.length

    fit=analyse_fit(shaft.diameter,hole.diameter,shaft.length,depth)
    asm_type="radial" if angle>70 else "axial"

    return {
        "strategy":"cylinder","confidence":score,
        "description":(f"{asm_type.upper()}: shaft∅{shaft.diameter:.2f}mm "
                      f"→ hole∅{hole.diameter:.2f}mm  "
                      f"cl={clearance:+.2f}mm  angle={angle:.0f}°  "
                      f"[{fit['fit_class']}]"),
        "shaft":shaft,"hole":hole,"shaft_part":sp,"hole_part":hp,
        "fit_info":fit,"insertion_depth":depth,"asm_type":asm_type,"axis_angle":angle,
    }


def _bolt_pattern_matches(part_a, part_b, inst):
    results=[]
    for pa in part_a.hole_patterns:
        for pb in part_b.hole_patterns:
            if pa.count!=pb.count: continue
            if pa.holes and pb.holes:
                if abs(pa.holes[0].diameter-pb.holes[0].diameter)>3.0: continue
            bcd_diff=0.0
            if pa.pattern_type=="bolt_circle" and pb.pattern_type=="bolt_circle":
                bcd_diff=abs(pa.bolt_circle_dia-pb.bolt_circle_dia)
                if bcd_diff>3.0: continue
            score=max(0.0,0.80-bcd_diff/10.0)
            if inst and inst.prefer_bolt: score=min(1.0,score+0.1)
            n=pa.count; bcd=(pa.bolt_circle_dia+pb.bolt_circle_dia)/2
            results.append({"strategy":"bolt_pattern","confidence":score,
                "description":f"Bolt pattern: {n} holes  BCD={bcd:.1f}mm",
                "pattern_a":pa,"pattern_b":pb,"hole_count":n,
                "fit_info":{"fit_class":"Bolt Pattern","note":f"{n}-hole BCD≈{bcd:.1f}mm"}})
    return results


def _plane_matches(part_a, part_b, inst):
    results=[]
    for p1 in part_a.planes:
        for p2 in part_b.planes:
            n1,n2=p1.normal,p2.normal
            dot=n1.X()*n2.X()+n1.Y()*n2.Y()+n1.Z()*n2.Z()
            if abs(dot)<0.88: continue
            ar=min(p1.area,p2.area)/max(p1.area,p2.area,1e-6)
            if ar<MIN_AREA_RATIO: continue
            score=0.35+ar*0.35
            if dot<0: score+=0.12
            if p1.is_inner or p2.is_inner: score+=0.10
            if inst and inst.prefer_plane: score+=0.15
            if inst and inst.flush: score+=0.05
            score=max(0.0,min(1.0,score))
            is_slot=p1.is_inner or p2.is_inner
            results.append({"strategy":"slot" if is_slot else "plane",
                "confidence":score,
                "description":f"{'Slot' if is_slot else 'Plane'} ar={ar:.2f} dot={dot:+.3f}",
                "p1":p1,"p2":p2,"gap":inst.gap if (inst and inst.gap) else 0.0,
                "fit_info":{"fit_class":"Slot Fit" if is_slot else "Plane Mating","note":f"ar={ar:.2f}"}})
    results.sort(key=lambda c:c["confidence"],reverse=True)
    return results


def _axis_angle(a, b):
    dot=max(-1.0,min(1.0,a[0]*b[0]+a[1]*b[1]+a[2]*b[2]))
    return math.degrees(math.acos(abs(dot)))