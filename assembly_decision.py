"""assembly_decision.py — kept for backward compat, logic now in smart_matcher"""
from part_model import PartModel
def choose_best_alignment(part_a, part_b, plane_matches, shaft=None, hole=None):
    if shaft and hole: return "cylinder"
    if plane_matches:  return "plane"
    if part_a.planes and part_b.planes: return "plane"
    return "bbox"