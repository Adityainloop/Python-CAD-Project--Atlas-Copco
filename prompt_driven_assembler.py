"""
prompt_driven_assembler.py
---------------------------
User prompt is the PRIMARY driver of assembly.
Geometry is used to EXECUTE the instruction, not to GUESS intent.

When user says:
  "insert pin into side hole"
  "insert bolt into middle hole"
  "insert shaft 30mm into the small hole"

We find the matching part and hole by NAME + SIZE hints from the prompt,
then execute the precise geometric transform.

This solves the same-plane problem completely:
  User tells us WHICH hole → we find it by size/position → we insert correctly.
"""

import math
import re
from typing import Optional, List, Tuple
from part_model import PartModel, CylinderFeature


# ─────────────────────────────────────────────────────────────────────────────
# Hole selector — find the right hole from user description
# ─────────────────────────────────────────────────────────────────────────────

def find_hole_from_description(part: PartModel, description: str
                                ) -> Optional[CylinderFeature]:
    """
    Find the specific hole the user described.

    Handles:
      "small hole"     → smallest hole on part
      "large hole"     → largest hole
      "middle hole"    → hole closest to part center
      "side hole"      → hole farthest from part center (on surface)
      "edge hole"      → same as side hole
      "top hole"       → hole with highest Z center
      "bottom hole"    → hole with lowest Z center
      "6mm hole"       → hole closest to 6mm diameter
      "10mm hole"      → hole closest to 10mm diameter
    """
    desc = description.lower()
    holes = [c for c in part.cylinders if c.is_hole]
    if not holes:
        holes = part.cylinders  # fallback: treat all as holes
    if not holes:
        return None
    if len(holes) == 1:
        return holes[0]

    # ── Size keywords ────────────────────────────────────────────────────
    if "small" in desc or "smallest" in desc or "minor" in desc:
        return min(holes, key=lambda c: c.radius)

    if "large" in desc or "largest" in desc or "big" in desc or "major" in desc or "main" in desc:
        return max(holes, key=lambda c: c.radius)

    # ── Specific diameter mentioned ───────────────────────────────────────
    # e.g. "6mm hole", "10 mm hole", "diameter 8"
    dia_match = re.search(r'(\d+(?:\.\d+)?)\s*mm', desc)
    if dia_match:
        target_dia = float(dia_match.group(1))
        return min(holes, key=lambda c: abs(c.diameter - target_dia))

    # ── Position keywords ─────────────────────────────────────────────────
    bcx = (part.bbox_min[0] + part.bbox_max[0]) / 2
    bcy = (part.bbox_min[1] + part.bbox_max[1]) / 2
    bcz = (part.bbox_min[2] + part.bbox_max[2]) / 2

    def dist_from_center(c):
        return math.sqrt((c.center[0]-bcx)**2 +
                         (c.center[1]-bcy)**2 +
                         (c.center[2]-bcz)**2)

    if any(w in desc for w in ["side", "edge", "outer", "surface",
                                "radial", "peripheral"]):
        return max(holes, key=dist_from_center)

    if any(w in desc for w in ["middle", "center", "central",
                                "inner", "bore", "main bore"]):
        return min(holes, key=dist_from_center)

    if "top" in desc or "upper" in desc:
        return max(holes, key=lambda c: c.center[2])

    if "bottom" in desc or "lower" in desc:
        return min(holes, key=lambda c: c.center[2])

    if "front" in desc:
        return max(holes, key=lambda c: c.center[1])

    if "back" in desc or "rear" in desc:
        return min(holes, key=lambda c: c.center[1])

    # ── Default: smallest hole (most specific) ────────────────────────────
    return min(holes, key=lambda c: c.radius)


def find_shaft_from_description(part: PartModel, description: str
                                  ) -> Optional[CylinderFeature]:
    """Find the shaft/pin the user wants to insert."""
    desc = description.lower()
    shafts = [c for c in part.cylinders if not c.is_hole]
    if not shafts:
        shafts = part.cylinders
    if not shafts:
        return None
    if len(shafts) == 1:
        return shafts[0]

    # Size keywords
    if "small" in desc or "pin" in desc or "minor" in desc:
        return min(shafts, key=lambda c: c.radius)
    if "large" in desc or "shaft" in desc or "major" in desc:
        return max(shafts, key=lambda c: c.radius)

    # Specific diameter
    dia_match = re.search(r'(\d+(?:\.\d+)?)\s*mm', desc)
    if dia_match:
        target = float(dia_match.group(1))
        return min(shafts, key=lambda c: abs(c.diameter - target))

    return max(shafts, key=lambda c: c.radius)


# ─────────────────────────────────────────────────────────────────────────────
# Parse multi-part instructions
# ─────────────────────────────────────────────────────────────────────────────

def parse_multi_instruction(prompt: str, parts: List[PartModel]) -> List[dict]:
    """
    Parse complex prompts like:
    "insert bolt 20mm inside middle hole of plate,
     insert pin 5mm inside edge hole of plate"

    Returns list of assembly instructions:
    [
      {
        'moving_part': PartModel,   # the part to move
        'fixed_part':  PartModel,   # the part it attaches to
        'hole_desc':   str,         # description of which hole
        'shaft_desc':  str,         # description of which shaft
        'depth':       float,       # insertion depth in mm
        'full_depth':  bool,        # go all the way through
      },
      ...
    ]
    """
    instructions = []
    prompt_lower = prompt.lower()

    # Split on commas or "and" at sentence boundaries
    # e.g. "insert bolt ..., insert pin ..."
    segments = re.split(r',\s*(?=insert|place|put|assemble|mate)|(?<=[.!])\s*', prompt_lower)
    if len(segments) == 1:
        segments = re.split(r'\s+and\s+(?=insert|place|put)', prompt_lower)

    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue

        inst = _parse_single_segment(seg, parts)
        if inst:
            instructions.append(inst)

    return instructions


def _parse_single_segment(seg: str, parts: List[PartModel]) -> Optional[dict]:
    """Parse one assembly instruction segment."""

    # Find depth
    depth = 0.0
    full_depth = True
    depth_match = re.search(
        r'(\d+(?:\.\d+)?)\s*mm|'
        r'(\d+(?:\.\d+)?)\s*millimeter', seg)
    if depth_match:
        depth = float(depth_match.group(1) or depth_match.group(2))
        full_depth = False
    if any(w in seg for w in ["fully", "completely", "through", "all the way"]):
        full_depth = True
        depth = 0.0

    # Find which part is moving (by name hint in prompt)
    moving_part = None
    fixed_part  = None

    # Try to match part names to parts list
    for part in parts:
        name_lower = part.name.lower()
        # Check if any word from part name appears in segment
        name_words = re.sub(r'[_\-]', ' ', name_lower).split()
        for word in name_words:
            if len(word) > 2 and word in seg:
                # This part is mentioned in the segment
                # The part with fewer/no holes is likely the moving part (shaft/bolt/pin)
                if not moving_part and len(part.shafts) > 0:
                    moving_part = part
                elif not fixed_part and len(part.holes) > 0:
                    fixed_part = part

    # If name matching failed, use geometry
    if not moving_part or not fixed_part:
        # Heuristic: part with more shafts = moving, part with more holes = fixed
        shaft_counts = [(p, len(p.shafts)) for p in parts]
        hole_counts  = [(p, len(p.holes))  for p in parts]
        shaft_counts.sort(key=lambda x: x[1], reverse=True)
        hole_counts.sort(key=lambda x: x[1], reverse=True)

        if not moving_part and shaft_counts:
            moving_part = shaft_counts[0][0]
        if not fixed_part and hole_counts:
            fixed_part = hole_counts[0][0]
            if fixed_part is moving_part and len(hole_counts) > 1:
                fixed_part = hole_counts[1][0]

    if not moving_part or not fixed_part or moving_part is fixed_part:
        return None

    # Extract hole description from segment
    # Look for "side hole", "middle hole", "small hole", "6mm hole" etc.
    hole_desc = seg  # pass full segment to hole finder

    return {
        "moving_part": moving_part,
        "fixed_part":  fixed_part,
        "hole_desc":   hole_desc,
        "shaft_desc":  seg,
        "depth":       depth,
        "full_depth":  full_depth,
        "segment":     seg,
    }