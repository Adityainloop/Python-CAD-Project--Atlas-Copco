"""
highlight_features.py
---------------------
Helpers to highlight geometric features in the PythonOCC viewer.
Accepts OCC shapes / face lists — no file paths.
"""

from cylinder_detection import get_cylinder_faces
from plane_detection import find_planes


def highlight_cylinders(display, shape, color: str = "BLUE"):
    """
    Display all cylindrical faces of a shape in the given colour.

    Args:
        display: OCC viewer display object.
        shape:   OCC TopoDS_Shape.
        color:   OCC colour string (e.g. 'BLUE', 'RED', 'GREEN').
    """
    faces = get_cylinder_faces(shape)
    for face in faces:
        display.DisplayShape(face, color=color, update=False)
    return len(faces)


def highlight_planes(display, shape, color: str = "YELLOW"):
    """
    Display the largest planar face of a shape in the given colour.
    """
    planes = find_planes(shape)
    count = 0
    for p in planes[:3]:   # highlight top 3 largest planes only
        display.DisplayShape(p.face, color=color, update=False)
        count += 1
    return count


def display_assembly(display, parts_and_colors: list):
    """
    Display multiple parts with individual colours.

    Args:
        display: OCC viewer display object.
        parts_and_colors: List of (shape, color_string) tuples.
    """
    for shape, color in parts_and_colors:
        if shape is not None and not shape.IsNull():
            display.DisplayShape(shape, color=color, update=False)

    display.FitAll()