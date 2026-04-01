"""
step_exporter.py
----------------
Exports an assembled OCC shape / compound to a STEP file.
"""

from OCC.Core.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCC.Core.IFSelect import IFSelect_RetDone


def export_step(shape, filename: str = "assembled_model.step") -> bool:
    """
    Write an OCC shape to a STEP file.

    Args:
        shape:    OCC TopoDS_Shape to export (may be a Compound).
        filename: Output file path.

    Returns:
        True on success, False on failure.
    """
    if shape is None or shape.IsNull():
        print("[Export] Cannot export — shape is null")
        return False

    writer = STEPControl_Writer()
    writer.Transfer(shape, STEPControl_AsIs)
    status = writer.Write(filename)

    if status == IFSelect_RetDone:
        print(f"[Export] STEP assembly saved: {filename}")
        return True
    else:
        print(f"[Export] Failed to write STEP file: {filename}")
        return False