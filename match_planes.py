"""
match_planes.py  (fixed - cavity/slot face detection)
------------------------------------------------------
Finds mating plane pairs between two parts.

For slot/cavity assembly specifically:
  - Identifies INNER faces (reversed orientation) on cavity parts
  - Prioritises matching the cavity ENTRY face with the moving part's face
  - Falls back to largest anti-parallel face pair for normal flat assembly

Matching rules:
  1. Anti-parallel normals (|dot| > threshold) = faces can mate
  2. Cavity inner faces get priority over outer faces
  3. Sorted by combined area (largest faces first)
  4. Each face used at most once
"""

import math
from OCC.Core.TopAbs import TopAbs_REVERSED, TopAbs_FORWARD
from part_model import PlaneFeature

PARALLEL_THRESHOLD  = 0.92   # |dot| > this = parallel/anti-parallel
MAX_FACE_DISTANCE   = 1000.0  # mm — ignore very distant planes


def _dist(p1: PlaneFeature, p2: PlaneFeature) -> float:
    dx = p1.point.X() - p2.point.X()
    dy = p1.point.Y() - p2.point.Y()
    dz = p1.point.Z() - p2.point.Z()
    return math.sqrt(dx*dx + dy*dy + dz*dz)


def _is_inner(p: PlaneFeature) -> bool:
    """True if this face points inward (cavity / slot wall)."""
    return (p.face is not None and
            p.face.Orientation() == TopAbs_REVERSED)


def match_planes(planes1: list, planes2: list) -> list:
    """
    Find mating plane pairs between two parts.

    Returns list of (PlaneFeature, PlaneFeature) sorted best-first.
    """
    if not planes1 or not planes2:
        return []

    candidates = []

    for p1 in planes1:
        for p2 in planes2:
            n1 = p1.normal
            n2 = p2.normal

            dot = (n1.X()*n2.X() +
                   n1.Y()*n2.Y() +
                   n1.Z()*n2.Z())

            if abs(dot) < PARALLEL_THRESHOLD:
                continue

            dist = _dist(p1, p2)
            if dist > MAX_FACE_DISTANCE:
                continue

            combined_area = p1.area + p2.area

            # Scoring:
            # +2.0 bonus if one face is an inner (cavity) face
            # +1.0 bonus if normals are anti-parallel (true mating)
            # Base = combined area
            inner_bonus     = 2.0 if (_is_inner(p1) or _is_inner(p2)) else 0.0
            anti_par_bonus  = 1.0 if dot < 0 else 0.0
            score = combined_area + inner_bonus * 1000 + anti_par_bonus * 500

            candidates.append((p1, p2, score, dist))

    # Sort: highest score first, then shortest distance
    candidates.sort(key=lambda c: (-c[2], c[3]))

    # Deduplicate — each face used once only
    used1 = set()
    used2 = set()
    result = []

    for p1, p2, score, dist in candidates:
        id1, id2 = id(p1), id(p2)
        if id1 not in used1 and id2 not in used2:
            result.append((p1, p2))
            used1.add(id1)
            used2.add(id2)

    return result