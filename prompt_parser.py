"""
prompt_parser.py  — complete rewrite
--------------------------------------
Parses natural language assembly instructions into structured parameters
that ACTUALLY change how the assembly is computed.

Key fix: old parser set flags but the assembler never used them to
change the actual transform. Now every parsed parameter maps directly
to a concrete geometric action.
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class AssemblyInstruction:
    # Core assembly type
    assembly_type: str = "auto"
    # "auto" | "shaft_hole" | "plane" | "slot" | "bolt_pattern" | "press_fit" | "side_by_side"

    # Geometric parameters — these DIRECTLY control the transform
    insertion_depth: Optional[float] = None   # mm — how far shaft enters hole
    clearance:       Optional[float] = None   # mm — diametral clearance override
    gap:             Optional[float] = None   # mm — gap between plane faces
    offset_x:        Optional[float] = None   # mm — manual X offset after assembly
    offset_y:        Optional[float] = None   # mm — manual Y offset
    offset_z:        Optional[float] = None   # mm — manual Z offset

    # Strategy flags
    prefer_cylinder:  bool = False
    prefer_plane:     bool = False
    prefer_bolt:      bool = False
    press_fit:        bool = False
    flush:            bool = False
    full_depth:       bool = False  # insert shaft completely through
    centered:         bool = False  # center shaft in hole (default)
    side_by_side:     bool = False  # just place parts next to each other

    # Part role hints (helps when ambiguous)
    shaft_name: str = ""    # filename hint for shaft part
    hole_name:  str = ""    # filename hint for hole/housing part

    # Bolt params
    bolt_count: Optional[int]   = None
    bolt_dia:   Optional[float] = None

    raw_prompt: str = ""
    confidence: float = 0.0

    def summary(self) -> str:
        parts = [f"type={self.assembly_type}"]
        if self.insertion_depth is not None:
            parts.append(f"depth={self.insertion_depth:.1f}mm")
        if self.clearance is not None:
            parts.append(f"clearance={self.clearance:.3f}mm")
        if self.gap is not None:
            parts.append(f"gap={self.gap:.1f}mm")
        if self.press_fit:
            parts.append("PRESS-FIT")
        if self.full_depth:
            parts.append("FULL-DEPTH")
        if self.flush:
            parts.append("FLUSH")
        if self.side_by_side:
            parts.append("SIDE-BY-SIDE")
        return "  ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Main parser
# ─────────────────────────────────────────────────────────────────────────────

def parse_prompt(text: str) -> AssemblyInstruction:
    inst = AssemblyInstruction(raw_prompt=text)
    if not text.strip():
        return inst

    t = text.lower().strip()
    score = 0

    # ── Extract all numbers with units ────────────────────────────────────
    # Matches: "50mm", "50 mm", "50millimeter", "50.5mm"
    mm_re = re.compile(r'(\d+(?:\.\d+)?)\s*(?:mm|millimeter|millimetre|mil\b)', re.I)
    numbers_mm = [float(m.group(1)) for m in mm_re.finditer(t)]

    # Plain numbers without units (might be depth or clearance)
    plain_re = re.compile(r'(?<!\d)(\d+(?:\.\d+)?)(?!\d)')
    plain_nums = [float(m.group(1)) for m in plain_re.finditer(t)
                  if not mm_re.search(text[max(0,m.start()-5):m.end()+5])]

    # ── Assembly type detection ───────────────────────────────────────────

    # Press fit
    if any(p in t for p in ["press fit", "press-fit", "pressfit",
                              "interference fit", "force fit", "force in"]):
        inst.assembly_type  = "shaft_hole"
        inst.press_fit      = True
        inst.prefer_cylinder = True
        inst.clearance      = -0.02  # slight interference
        score += 4

    # Side by side / place next to
    elif any(p in t for p in ["side by side", "next to", "beside",
                                "place next", "put next", "adjacent"]):
        inst.assembly_type  = "side_by_side"
        inst.side_by_side   = True
        score += 4

    # Bolt / fastener pattern
    elif any(p in t for p in ["bolt", "screw", "fasten", "rivet",
                                "bolt circle", "hole pattern", "bolt pattern"]):
        inst.assembly_type  = "bolt_pattern"
        inst.prefer_bolt    = True
        score += 3
        bc = re.search(r'(\d+)\s*(?:bolt|screw|fastener|hole)', t)
        if bc:
            inst.bolt_count = int(bc.group(1))
            score += 1

    # Plane / flat face / flush
    elif any(p in t for p in ["flat face", "plane", "flush", "mate face",
                                "face to face", "face-to-face", "flat surface",
                                "slot", "groove", "insert plate", "slide plate"]):
        inst.assembly_type  = "plane"
        inst.prefer_plane   = True
        score += 3
        if "flush" in t:
            inst.flush = True
        if any(p in t for p in ["slot", "groove", "slide"]):
            inst.assembly_type = "slot"

    # Shaft / cylinder / bearing / pin
    elif any(p in t for p in ["shaft", "pin", "rod", "cylinder",
                                "bore", "bearing", "insert", "through",
                                "hole", "housing", "sleeve"]):
        inst.assembly_type   = "shaft_hole"
        inst.prefer_cylinder = True
        score += 3

    # ── Depth / insertion ─────────────────────────────────────────────────
    # "insert 50mm deep", "50mm deep", "depth 50mm", "insert fully"

    if any(p in t for p in ["fully", "completely", "all the way",
                              "full depth", "through"]):
        inst.full_depth = True
        score += 2
    else:
        # Try: "<number>mm deep" or "depth <number>mm" or "insert <number>mm"
        depth_patterns = [
            r'(\d+(?:\.\d+)?)\s*mm\s*(?:deep|depth|inside|into|inward)',
            r'(?:deep|depth|insert|go|push)\s+(\d+(?:\.\d+)?)\s*mm',
            r'(\d+(?:\.\d+)?)\s*(?:mm)?\s*(?:deep|depth)',
            r'(?:insert|put|place|push)\w*\s+(\d+(?:\.\d+)?)',
        ]
        for pat in depth_patterns:
            m = re.search(pat, t)
            if m:
                inst.insertion_depth = float(m.group(1))
                score += 3
                break

        # Fallback: first mm number if type is shaft_hole
        if inst.insertion_depth is None and numbers_mm and inst.prefer_cylinder:
            inst.insertion_depth = numbers_mm[0]
            score += 1

    # ── Clearance ─────────────────────────────────────────────────────────
    cl_patterns = [
        r'(\d+(?:\.\d+)?)\s*mm\s*clearance',
        r'clearance\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*mm',
        r'clearance\s*[=:]\s*(\d+(?:\.\d+)?)',
        r'(\d+(?:\.\d+)?)\s*mm\s*gap',
    ]
    for pat in cl_patterns:
        m = re.search(pat, t)
        if m:
            val = float(m.group(1))
            if "gap" in pat:
                inst.gap = val
            else:
                inst.clearance = val
            score += 2
            break

    # ── Gap between planes ────────────────────────────────────────────────
    if inst.gap is None:
        gm = re.search(r'(\d+(?:\.\d+)?)\s*mm\s*gap', t)
        if not gm:
            gm = re.search(r'gap\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*mm', t)
        if gm:
            inst.gap = float(gm.group(1))
            score += 2

    # ── Part name hints ───────────────────────────────────────────────────
    # "shaft into housing", "bearing into block"
    role_map = {
        "shaft":    ("shaft", ""),
        "pin":      ("shaft", ""),
        "rod":      ("shaft", ""),
        "bearing":  ("shaft", "housing"),
        "sleeve":   ("shaft", "housing"),
        "housing":  ("", "housing"),
        "block":    ("", "housing"),
        "body":     ("", "housing"),
        "bracket":  ("", "housing"),
        "plate":    ("plate", ""),
    }
    for word, (a_role, b_role) in role_map.items():
        if word in t:
            if a_role: inst.shaft_name = a_role
            if b_role: inst.hole_name  = b_role
            score += 1

    # ── Confidence ────────────────────────────────────────────────────────
    inst.confidence = min(1.0, score / 10.0)

    # If we got nothing, mark as auto with low confidence
    if score == 0:
        inst.assembly_type = "auto"
        inst.confidence    = 0.0

    return inst


# ─────────────────────────────────────────────────────────────────────────────
# Suggestion generator
# ─────────────────────────────────────────────────────────────────────────────

def suggest_prompt(part_a_type: str, part_b_type: str) -> List[str]:
    a, b = part_a_type.lower(), part_b_type.lower()
    suggestions = []

    if "shaft" in (a, b) or "bearing" in (a, b):
        suggestions += [
            "insert shaft fully through bearing",
            "insert shaft 30mm deep into hole",
            "press fit shaft into bearing",
            "insert shaft with 0.1mm clearance",
            "center shaft in hole",
        ]
    if "housing" in (a, b) or "block" in (a, b):
        suggestions += [
            "insert shaft fully into housing",
            "insert shaft 40mm deep into housing",
            "press fit into housing bore",
        ]
    if "plate" in (a, b) or "flange" in (a, b):
        suggestions += [
            "mate flat faces flush",
            "align plane faces with 2mm gap",
            "insert plate into slot",
            "bolt flange faces together",
        ]
    if "ring" in (a, b):
        suggestions += [
            "insert shaft fully through ring",
            "center shaft in ring",
        ]

    suggestions += [
        "auto assemble",
        "place side by side",
    ]

    # Deduplicate while preserving order
    seen = set()
    result = []
    for s in suggestions:
        if s not in seen:
            seen.add(s)
            result.append(s)

    return result[:6]