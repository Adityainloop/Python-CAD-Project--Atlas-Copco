"""
check_geometry.py - Run this to see EXACT geometry
python check_geometry.py
"""
import sys, os, math, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.GeomAbs import GeomAbs_Cylinder
from OCC.Core.BRepGProp import brepgprop
from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.Bnd import Bnd_Box
import math

def load(path):
    r = STEPControl_Reader()
    if r.ReadFile(os.path.abspath(path)) != IFSelect_RetDone: return None
    r.TransferRoots(); s = r.OneShape()
    return None if s.IsNull() else s

def bbox(shape):
    b = Bnd_Box(); brepbndlib.Add(shape, b); return b.Get()

def cyls(shape):
    result = []
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = exp.Current()
        surf = BRepAdaptor_Surface(face)
        if surf.GetType() == GeomAbs_Cylinder:
            c = surf.Cylinder()
            ax = c.Axis().Direction()
            loc = c.Location()
            r = c.Radius()
            sp = GProp_GProps()
            brepgprop.SurfaceProperties(face, sp)
            area = sp.Mass()
            L = area / (2*math.pi*r) if r > 1e-6 else 0
            is_hole = face.Orientation() == TopAbs_REVERSED
            result.append({
                'r': round(r,3), 'd': round(r*2,3), 'L': round(L,2),
                'ax': (round(ax.X(),3), round(ax.Y(),3), round(ax.Z(),3)),
                'center': (round(loc.X(),3), round(loc.Y(),3), round(loc.Z(),3)),
                'hole': is_hole
            })
        exp.Next()
    return sorted(result, key=lambda c: c['r'])

files = [f for f in glob.glob("*.step")+glob.glob("*.stp") if "assembled" not in f.lower()]
print(f"Found: {files}\n")

for f in files:
    s = load(f)
    if not s: print(f"FAILED: {f}"); continue
    b = bbox(s)
    dims = (b[3]-b[0], b[4]-b[1], b[5]-b[2])
    bc = ((b[0]+b[3])/2, (b[1]+b[4])/2, (b[2]+b[5])/2)
    print(f"=== {f} ===")
    print(f"  bbox: {dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f} mm")
    print(f"  bbox_center: ({bc[0]:.2f}, {bc[1]:.2f}, {bc[2]:.2f})")
    cs = cyls(s)
    print(f"  cylinders ({len(cs)}):")
    for c in cs:
        t = "HOLE" if c['hole'] else "SHAFT"
        print(f"    {t} d={c['d']} L={c['L']} axis={c['ax']} center={c['center']}")
    print()