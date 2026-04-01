"""
viewer.py
---------
Standalone 3D viewer for previewing STEP files or an assembled compound.
Can be run directly:
    python viewer.py part_a.step part_b.step ...
"""

import sys
import os

try:
    from OCC.Display.SimpleGui import init_display
    VIEWER_AVAILABLE = True
except ImportError:
    VIEWER_AVAILABLE = False
    print("[Viewer] PythonOCC display not available.")

from step_loader import load_step

# Colour cycle for multiple parts
COLORS = ["BLUE", "RED", "GREEN", "ORANGE", "MAGENTA",
          "CYAN", "YELLOW", "WHITE", "BROWN"]


def view_shapes(shapes_and_colors: list, title: str = "CAD Assembly Viewer"):
    """
    Display a list of (shape, color) pairs in the OCC viewer.

    Args:
        shapes_and_colors: List of (TopoDS_Shape, color_str) tuples.
        title:             Window title string.
    """
    if not VIEWER_AVAILABLE:
        print("[Viewer] Cannot open display.")
        return

    display, start_display, add_menu, add_function = init_display()

    for shape, color in shapes_and_colors:
        if shape is not None and not shape.IsNull():
            display.DisplayShape(shape, color=color, update=False)

    display.FitAll()
    print(f"[Viewer] Showing {len(shapes_and_colors)} shape(s). Close window to exit.")
    start_display()


def view_step_files(file_paths: list):
    """
    Load and display STEP files directly from paths.
    """
    pairs = []
    for i, fp in enumerate(file_paths):
        shape = load_step(fp)
        if shape:
            pairs.append((shape, COLORS[i % len(COLORS)]))

    if pairs:
        view_shapes(pairs)
    else:
        print("[Viewer] No valid shapes to display.")


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python viewer.py file1.step [file2.step ...]")
        sys.exit(1)

    files = sys.argv[1:]
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        print("Files not found:")
        for m in missing:
            print(f"  {m}")
        sys.exit(1)

    view_step_files(files)