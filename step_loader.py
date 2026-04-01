"""
step_loader.py  — fixed for pythonocc 7.7.1
Accepts absolute OR relative paths.
"""
import os
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.IFSelect import IFSelect_RetDone


def load_step(file_path: str):
    path = os.path.abspath(file_path)
    if not os.path.isfile(path):
        print(f"[ERROR] File not found: {path}")
        return None
    reader = STEPControl_Reader()
    status = reader.ReadFile(path)
    if status != IFSelect_RetDone:
        print(f"[ERROR] STEP read failed (code {status}): {path}")
        return None
    reader.TransferRoots()
    shape = reader.OneShape()
    if shape is None or shape.IsNull():
        print(f"[ERROR] Shape is null: {path}")
        return None
    print(f"[OK] Loaded: {os.path.basename(path)}")
    return shape