"""
debug_planes.py  (fixed for pythonocc 7.7.1)
Run: python debug_planes.py plane1.step plane2.step
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder
from OCC.Core.BRepGProp import brepgprop_SurfaceProperties
from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.Bnd import Bnd_Box

def load_step_v2(path):
    """Fixed loader for pythonocc 7.7.1"""
    reader = STEPControl_Reader()
    status = reader.ReadFile(path)
    if status != IFSelect_RetDone:
        print(f"  [FAIL] ReadFile returned {status} for {path}")
        return None
    reader.TransferRoots()
    shape = reader.OneShape()
    if shape.IsNull():
        print(f"  [FAIL] Shape is null for {path}")
        return None
    print(f"  [OK] Loaded: {path}")
    return shape

def get_bbox(shape):
    box = Bnd_Box()
    brepbndlib.Add(shape, box)   # fixed: use brepbndlib.Add not brepbndlib_Add
    return box.Get()

def get_planes(shape):
    planes = []
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = exp.Current()
        surf = BRepAdaptor_Surface(face)
        if surf.GetType() == GeomAbs_Plane:
            pl = surf.Plane()
            props = GProp_GProps()
            brepgprop_SurfaceProperties(face, props)
            area = props.Mass()
            planes.append({
                "normal": pl.Axis().Direction(),
                "point":  pl.Location(),
                "face":   face,
                "area":   area,
                "inner":  face.Orientation() == TopAbs_REVERSED
            })
        exp.Next()
    planes.sort(key=lambda p: p["area"], reverse=True)
    return planes

def debug(f1, f2):
    print(f"\n{'='*65}")
    print(f"FILE 1: {f1}")
    s1 = load_step_v2(f1)
    planes1 = get_planes(s1) if s1 else []
    print(f"  Planes detected: {len(planes1)}")
    for i,p in enumerate(planes1):
        n = p["normal"]
        pt = p["point"]
        ori = "INNER" if p["inner"] else "OUTER"
        print(f"  [{i}] n=({n.X():+.3f},{n.Y():+.3f},{n.Z():+.3f})  "
              f"pt=({pt.X():.2f},{pt.Y():.2f},{pt.Z():.2f})  "
              f"area={p['area']:.2f}  {ori}")

    print(f"\nFILE 2: {f2}")
    s2 = load_step_v2(f2)
    planes2 = get_planes(s2) if s2 else []
    print(f"  Planes detected: {len(planes2)}")
    for i,p in enumerate(planes2):
        n = p["normal"]
        pt = p["point"]
        ori = "INNER" if p["inner"] else "OUTER"
        print(f"  [{i}] n=({n.X():+.3f},{n.Y():+.3f},{n.Z():+.3f})  "
              f"pt=({pt.X():.2f},{pt.Y():.2f},{pt.Z():.2f})  "
              f"area={p['area']:.2f}  {ori}")

    print(f"\nBounding boxes:")
    if s1:
        b=get_bbox(s1)
        print(f"  part1: {b[3]-b[0]:.2f} x {b[4]-b[1]:.2f} x {b[5]-b[2]:.2f}  "
              f"origin=({b[0]:.2f},{b[1]:.2f},{b[2]:.2f})")
    if s2:
        b=get_bbox(s2)
        print(f"  part2: {b[3]-b[0]:.2f} x {b[4]-b[1]:.2f} x {b[5]-b[2]:.2f}  "
              f"origin=({b[0]:.2f},{b[1]:.2f},{b[2]:.2f})")

    print(f"\nPlane matching (all pairs with |dot|>0.9):")
    for i,p1 in enumerate(planes1):
        for j,p2 in enumerate(planes2):
            n1,n2 = p1["normal"],p2["normal"]
            dot = n1.X()*n2.X()+n1.Y()*n2.Y()+n1.Z()*n2.Z()
            if abs(dot) > 0.9:
                dx=p1["point"].X()-p2["point"].X()
                dy=p1["point"].Y()-p2["point"].Y()
                dz=p1["point"].Z()-p2["point"].Z()
                dist=math.sqrt(dx*dx+dy*dy+dz*dz)
                print(f"  planes1[{i}] <-> planes2[{j}]  dot={dot:+.4f}  "
                      f"dist={dist:.2f}  "
                      f"{'ANTI-PARALLEL' if dot<0 else 'PARALLEL'}")
    print('='*65)

if __name__=="__main__":
    if len(sys.argv)<3:
        print("Usage: python debug_planes.py plane1.step plane2.step")
        sys.exit(1)
    debug(sys.argv[1], sys.argv[2])