"""
collision_check.py
------------------
Detects geometric interference between two OCC shapes using Boolean Common.
Accepts TopoDS_Shape objects — no file paths.
"""

from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Common
from OCC.Core.BRepCheck import BRepCheck_Analyzer
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_SOLID


def check_collision(shape1, shape2) -> bool:
    """
    Check for volumetric interference (collision) between two shapes.

    Uses Boolean Common operation: if the intersection volume is
    non-null, the parts overlap.

    Args:
        shape1: Fixed OCC TopoDS_Shape.
        shape2: Moved OCC TopoDS_Shape.

    Returns:
        True if collision detected, False otherwise.
    """
    if shape1 is None or shape2 is None:
        return False

    try:
        common = BRepAlgoAPI_Common(shape1, shape2)
        common.Build()

        if not common.IsDone():
            print("[Collision] Boolean operation failed — skipping check")
            return False

        result = common.Shape()

        if result.IsNull():
            print("[Collision] No collision detected ✓")
            return False

        # Check if the intersection contains any solid volume
        exp = TopExp_Explorer(result, TopAbs_SOLID)
        if exp.More():
            print("[Collision] ⚠  Interference / collision detected between parts!")
            return True

        print("[Collision] No solid intersection — no collision ✓")
        return False

    except Exception as e:
        print(f"[Collision] Check error: {e}")
        return False