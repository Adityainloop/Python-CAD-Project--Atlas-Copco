"""
debug_radial.py
---------------
Run: python debug_radial.py bearing.step pin.step

Shows EXACTLY where every cylinder is, what direction it faces,
and where the hole entry point is computed to be.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.GeomAbs import GeomAbs_Cylinder
from OCC.Core.BRepGProp import brepgprop_SurfaceProperties
from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.Bnd import Bnd_Box

def load(path):
    r = STEPControl_Reader()
    if r.ReadFile(os.path.abspath(path)) != IFSelect_RetDone:
        print(f"FAIL: {path}"); return None
    r.TransferRoots()
    s = r.OneShape()
    return None if s.IsNull() else s

def bbox(shape):
    b = Bnd_Box(); brepbndlib.Add(shape, b); return b.Get()

def bbox_center(shape):
    x0,y0,z0,x1,y1,z1 = bbox(shape)
    return (x0+x1)/2, (y0+y1)/2, (z0+z1)/2

def get_cylinders(shape):
    cyls = []
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = exp.Current()
        surf = BRepAdaptor_Surface(face)
        if surf.GetType() == GeomAbs_Cylinder:
            cyl = surf.Cylinder()
            ax = cyl.Axis().Direction()
            ct = cyl.Location()
            r  = cyl.Radius()
            sp = GProp_GProps()
            brepgprop_SurfaceProperties(face, sp)
            area = sp.Mass()
            length = area / (2*math.pi*r) if r > 0 else 0
            is_hole = face.Orientation() == TopAbs_REVERSED
            cyls.append({
                "r": r, "d": r*2, "length": length,
                "axis": (ax.X(), ax.Y(), ax.Z()),
                "center": (ct.X(), ct.Y(), ct.Z()),
                "is_hole": is_hole,
                "area": area
            })
        exp.Next()
    cyls.sort(key=lambda c: c["r"])
    return cyls

def outward_dir(hole_center, part_bbox_center, hole_axis):
    hx,hy,hz = hole_center
    bcx,bcy,bcz = part_bbox_center
    dx,dy,dz = hx-bcx, hy-bcy, hz-bcz
    ax,ay,az = hole_axis
    proj = dx*ax + dy*ay + dz*az
    if proj >= 0:
        return ax,ay,az
    else:
        return -ax,-ay,-az

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python debug_radial.py bearing.step pin.step")
        sys.exit(1)

    f1, f2 = sys.argv[1], sys.argv[2]
    s1 = load(f1); s2 = load(f2)
    if not s1 or not s2:
        print("Load failed"); sys.exit(1)

    print("\n" + "="*65)

    for name, shape, path in [(os.path.basename(f1),s1,f1),
                               (os.path.basename(f2),s2,f2)]:
        b = bbox(shape)
        bc = bbox_center(shape)
        dims = (b[3]-b[0], b[4]-b[1], b[5]-b[2])
        print(f"\nPART: {name}")
        print(f"  BBox: {dims[0]:.2f} x {dims[1]:.2f} x {dims[2]:.2f} mm")
        print(f"  BBox min: ({b[0]:.2f}, {b[1]:.2f}, {b[2]:.2f})")
        print(f"  BBox max: ({b[3]:.2f}, {b[4]:.2f}, {b[5]:.2f})")
        print(f"  BBox center: ({bc[0]:.2f}, {bc[1]:.2f}, {bc[2]:.2f})")
        cyls = get_cylinders(shape)
        print(f"  Cylinders ({len(cyls)}):")
        for i,c in enumerate(cyls):
            role = "HOLE(inner)" if c["is_hole"] else "SHAFT(outer)"
            print(f"    [{i}] {role}  d={c['d']:.3f}mm  L={c['length']:.2f}mm")
            print(f"         center=({c['center'][0]:.3f},{c['center'][1]:.3f},{c['center'][2]:.3f})")
            print(f"         axis  =({c['axis'][0]:.3f},{c['axis'][1]:.3f},{c['axis'][2]:.3f})")

    print("\n" + "="*65)
    print("\nRADIAL HOLE ANALYSIS:")
    cyls1 = get_cylinders(s1)
    cyls2 = get_cylinders(s2)
    bc1 = bbox_center(s1)
    bc2 = bbox_center(s2)

    # Find smallest cylinders (likely the radial hole and pin)
    holes1   = [c for c in cyls1 if c["is_hole"]]
    shafts2  = [c for c in cyls2 if not c["is_hole"]]

    if not holes1:
        holes1 = cyls1   # fallback
    if not shafts2:
        shafts2 = cyls2

    print("\nSmallest hole on part1 (bearing):")
    h = min(holes1, key=lambda c: c["r"])
    print(f"  d={h['d']:.3f}mm  center={h['center']}  axis={h['axis']}")
    ow = outward_dir(h["center"], bc1, h["axis"])
    print(f"  Computed outward direction: {ow}")
    entry = (
        h["center"][0] + ow[0]*h["length"]/2,
        h["center"][1] + ow[1]*h["length"]/2,
        h["center"][2] + ow[2]*h["length"]/2,
    )
    print(f"  Computed hole ENTRY point: ({entry[0]:.3f},{entry[1]:.3f},{entry[2]:.3f})")
    b1 = bbox(s1)
    print(f"  Bearing outer surface approx X range: {b1[0]:.2f} to {b1[3]:.2f}")
    print(f"  Bearing outer surface approx Y range: {b1[1]:.2f} to {b1[4]:.2f}")
    print(f"  Bearing outer surface approx Z range: {b1[2]:.2f} to {b1[5]:.2f}")
    print(f"\n  Is entry point OUTSIDE bearing bbox?")
    outside = (entry[0]<b1[0] or entry[0]>b1[3] or
               entry[1]<b1[1] or entry[1]>b1[4] or
               entry[2]<b1[2] or entry[2]>b1[5])
    print(f"  {'YES — entry is outside (CORRECT)' if outside else 'NO — entry is inside bbox (WRONG DIRECTION)'}")

    print("\nPin shaft:")
    p = min(shafts2, key=lambda c: c["r"])
    print(f"  d={p['d']:.3f}mm  center={p['center']}  axis={p['axis']}")
    print(f"  Length={p['length']:.2f}mm")
    print("\n" + "="*65)