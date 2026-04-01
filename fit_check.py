"""
fit_check.py
------------
Analyses shaft–hole fit type (clearance / transition / interference).
Works with radius values (floats), not file paths.
"""


def check_fit(shaft_radii: list, hole_radii: list) -> dict:
    """
    Perform fit analysis given lists of shaft and hole radii.

    Args:
        shaft_radii: List of shaft radii (mm).
        hole_radii:  List of hole radii (mm).

    Returns:
        Dict with keys: shaft_d, hole_d, clearance, fit_type.
    """
    if not shaft_radii or not hole_radii:
        return {
            "shaft_d": 0.0,
            "hole_d": 0.0,
            "clearance": 0.0,
            "fit_type": "Unknown — no cylinders detected"
        }

    shaft_d = min(shaft_radii) * 2   # smallest shaft diameter
    hole_d  = max(hole_radii)  * 2   # largest hole diameter
    clearance = hole_d - shaft_d

    print(f"\n--- Fit Analysis ---")
    print(f"  Shaft diameter : {shaft_d:.4f} mm")
    print(f"  Hole  diameter : {hole_d:.4f} mm")
    print(f"  Clearance      : {clearance:.4f} mm")

    if clearance > 0.005:
        fit_type = "Clearance Fit"
    elif abs(clearance) <= 0.005:
        fit_type = "Transition Fit"
    else:
        fit_type = "Interference Fit"

    print(f"  Result         : {fit_type}")

    return {
        "shaft_d": shaft_d,
        "hole_d": hole_d,
        "clearance": clearance,
        "fit_type": fit_type
    }