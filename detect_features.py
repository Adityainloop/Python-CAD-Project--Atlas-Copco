"""
detect_features.py
------------------
High-level feature detection convenience wrapper.

Accepts either:
  - A file path (str) → loads the STEP file first
  - An OCC TopoDS_Shape → used directly

Returns a dict with 'cylinders' and 'planes' lists.
"""

from step_loader import load_step
from cylinder_detection import find_cylinders
from plane_detection import find_planes


def detect_features(source) -> dict:
    """
    Detect all geometric features on a part.

    Args:
        source: File path (str) OR OCC TopoDS_Shape.

    Returns:
        {
          'shape':     TopoDS_Shape,
          'cylinders': [CylinderFeature, ...],
          'planes':    [PlaneFeature, ...]
        }
    """
    if isinstance(source, str):
        shape = load_step(source)
    else:
        shape = source

    if shape is None or shape.IsNull():
        return {"shape": None, "cylinders": [], "planes": []}

    cylinders = find_cylinders(shape)
    planes     = find_planes(shape)

    print(f"[Features] Cylinders: {len(cylinders)}  |  Planes: {len(planes)}")

    return {
        "shape":     shape,
        "cylinders": cylinders,
        "planes":    planes,
    }