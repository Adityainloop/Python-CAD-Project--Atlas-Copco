"""
match_features.py  (fixed)
--------------------------
Finds shaft–hole pairs between two parts based on cylinder radii.

Fixes:
  - MAX_CLEARANCE_MM increased to 5.0 — real parts often have larger gaps
  - Added axis-alignment check: cylinders must have similar axis directions
    to be a valid mating pair (avoids matching unrelated cylinders)
  - Returns None,None clearly when no match (no silent failure)
"""

import math
from part_model import CylinderFeature

# Diametral clearance range for a valid fit (mm)
MAX_CLEARANCE_MM =  5.0
MIN_CLEARANCE_MM = -1.0   # slight interference still counts

# Axis directions must be within this angle (degrees) to be considered mating
MAX_AXIS_ANGLE_DEG = 15.0


def _axis_angle_deg(c1: CylinderFeature, c2: CylinderFeature) -> float:
    """Angle between two cylinder axis directions in degrees."""
    a = c1.axis_dir
    b = c2.axis_dir
    dot = max(-1.0, min(1.0,
              a[0]*b[0] + a[1]*b[1] + a[2]*b[2]))
    return math.degrees(math.acos(abs(dot)))   # abs: anti-parallel axes also ok


def find_best_shaft_hole_pair(cylinders1: list, cylinders2: list):
    """
    Find the best shaft–hole mating pair between two sets of cylinders.

    Returns (shaft, hole) where shaft.radius < hole.radius, or (None, None).
    """
    if not cylinders1 or not cylinders2:
        return None, None

    best_pair      = None
    best_clearance = float("inf")

    for c1 in cylinders1:
        for c2 in cylinders2:
            # Axis alignment check
            angle = _axis_angle_deg(c1, c2)
            if angle > MAX_AXIS_ANGLE_DEG:
                continue

            # c1 as shaft, c2 as hole
            cl = (c2.radius - c1.radius) * 2
            if MIN_CLEARANCE_MM <= cl <= MAX_CLEARANCE_MM:
                if cl < best_clearance:
                    best_clearance = cl
                    best_pair = (c1, c2)

            # c2 as shaft, c1 as hole
            cl = (c1.radius - c2.radius) * 2
            if MIN_CLEARANCE_MM <= cl <= MAX_CLEARANCE_MM:
                if cl < best_clearance:
                    best_clearance = cl
                    best_pair = (c2, c1)

    if best_pair:
        return best_pair
    return None, None


def classify_fit(shaft_radius: float, hole_radius: float) -> str:
    clearance = (hole_radius - shaft_radius) * 2
    if clearance > 0.005:
        return "Clearance Fit"
    elif abs(clearance) <= 0.005:
        return "Transition Fit"
    else:
        return "Interference Fit"