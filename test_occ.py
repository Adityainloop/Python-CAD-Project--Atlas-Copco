"""
test_occ.py
-----------
Verifies PythonOCC is installed and the core modules are importable.
Run this before using the assembly system:
    python test_occ.py
"""

def check_occ():
    results = []

    modules = [
        ("OCC.Core.STEPControl", "STEPControl_Reader"),
        ("OCC.Core.TopExp",      "TopExp_Explorer"),
        ("OCC.Core.BRepAdaptor", "BRepAdaptor_Surface"),
        ("OCC.Core.GeomAbs",     "GeomAbs_Cylinder"),
        ("OCC.Core.gp",          "gp_Trsf"),
        ("OCC.Core.BRep",        "BRep_Builder"),
        ("OCC.Core.BRepAlgoAPI", "BRepAlgoAPI_Common"),
    ]

    print("Checking PythonOCC installation...\n")

    all_ok = True
    for mod_name, cls_name in modules:
        try:
            mod = __import__(mod_name, fromlist=[cls_name])
            getattr(mod, cls_name)
            results.append((mod_name, "OK"))
            print(f"  ✓  {mod_name}.{cls_name}")
        except Exception as e:
            results.append((mod_name, f"FAIL: {e}"))
            print(f"  ✗  {mod_name}.{cls_name}  →  {e}")
            all_ok = False

    # Check display separately (may fail in headless environments)
    try:
        from OCC.Display.SimpleGui import init_display
        print(f"  ✓  OCC.Display.SimpleGui (3D viewer available)")
    except Exception as e:
        print(f"  ⚠  OCC.Display.SimpleGui  →  {e}  (viewer disabled)")

    print()
    if all_ok:
        print("✓ PythonOCC installed correctly — system ready.\n")
    else:
        print("✗ Some OCC modules failed — check your environment.\n")

    return all_ok


if __name__ == "__main__":
    check_occ()