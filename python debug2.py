"""
debug2.py  — auto-finds STEP files, no quotes needed
Run: python debug2.py
It will find all .step files in current folder and analyze them.
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

def load(path):
    r = STEPControl_Reader()
    status = r.ReadFile(path)
    if status != IFSelect_RetDone:
        return None
    r.TransferRoots()
    s = r.OneShape()
    return None if s.IsNull() else s

def get_bbox(shape):
    b = Bnd_Box()
    brepbndlib.Add(shape, b)
    return b.Get()

def get_cyls(shape):
    cyls = []
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = exp.Current()
        surf = BRepAdaptor_Surface(face)
        if surf.GetType() == GeomAbs_Cylinder:
            cyl = surf.Cylinder()
            ax  = cyl.Axis().Direction()
            ct  = cyl.Location()
            r   = cyl.Radius()
            sp  = GProp_GProps()
            brepgprop.SurfaceProperties(face, sp)
            area = sp.Mass()
            L = area / (2*math.pi*r) if r > 1e-6 else 0
            cyls.append({
                "r": r, "d": r*2, "L": L,
                "ax": (round(ax.X(),4), round(ax.Y(),4), round(ax.Z(),4)),
                "ct": (round(ct.X(),4), round(ct.Y(),4), round(ct.Z(),4)),
                "hole": face.Orientation() == TopAbs_REVERSED
            })
        exp.Next()
    cyls.sort(key=lambda c: c["r"])
    return cyls

# Find all step files
step_files = glob.glob("*.step") + glob.glob("*.stp")
# Exclude assembled model
step_files = [f for f in step_files if "assembled" not in f.lower()]

print(f"\nFound {len(step_files)} STEP files:")
for f in step_files:
    print(f"  {f}")

print("\n" + "="*60)

parts = []
for f in step_files:
    shape = load(f)
    if shape is None:
        print(f"FAIL: {f}")
        continue
    b = get_bbox(shape)
    dims = (b[3]-b[0], b[4]-b[1], b[5]-b[2])
    bc = ((b[0]+b[3])/2, (b[1]+b[4])/2, (b[2]+b[5])/2)
    cyls = get_cyls(shape)
    print(f"\n--- {f} ---")
    print(f"  Size: {dims[0]:.2f} x {dims[1]:.2f} x {dims[2]:.2f} mm")
    print(f"  BBox center: ({bc[0]:.3f}, {bc[1]:.3f}, {bc[2]:.3f})")
    print(f"  Cylinders ({len(cyls)}):")
    for i,c in enumerate(cyls):
        role = "HOLE" if c["hole"] else "SHAFT"
        print(f"    [{i}] {role}  d={c['d']:.3f}mm  L={c['L']:.2f}mm")
        print(f"         axis  =({c['ax'][0]}, {c['ax'][1]}, {c['ax'][2]})")
        print(f"         center=({c['ct'][0]}, {c['ct'][1]}, {c['ct'][2]})")

    parts.append({"name": f, "shape": shape, "cyls": cyls, "bc": bc, "bbox": b})

print("\n" + "="*60)

if len(parts) >= 2:
    print("\nMATCHING ANALYSIS (all pairs):")
    import itertools
    for pa, pb in itertools.combinations(parts, 2):
        print(f"\n  {pa['name']}  ↔  {pb['name']}")
        for ca in pa["cyls"]:
            for cb in pb["cyls"]:
                cl = cb["d"] - ca["d"]
                if -2 <= cl <= 30:
                    # Axis angle
                    a,b_ = ca["ax"], cb["ax"]
                    dot = max(-1,min(1, a[0]*b_[0]+a[1]*b_[1]+a[2]*b_[2]))
                    ang = math.degrees(math.acos(abs(dot)))
                    asm = "RADIAL" if ang > 70 else "AXIAL"
                    # Size score
                    ref = max(ca["d"],1)
                    dia_s = max(0, 1-abs(cl)/ref)*0.70
                    ax_s  = 0.20 if ang<=20 else (0.05 if ang<=70 else 0.12)
                    score = dia_s + ax_s + (0.10 if cl>=0 else 0)
                    print(f"    shaft∅{ca['d']:.2f} → hole∅{cb['d']:.2f}  "
                          f"cl={cl:+.2f}  angle={ang:.0f}°  "
                          f"score={score:.3f}  [{asm}]")

        # Outward direction check for radial holes
        print(f"\n  Outward direction check for holes in {pa['name']}:")
        for c in pa["cyls"]:
            if c["hole"]:
                hx,hy,hz = c["ct"]; bcx,bcy,bcz = pa["bc"]
                ax,ay,az = c["ax"]
                dx,dy,dz = hx-bcx, hy-bcy, hz-bcz
                proj = dx*ax + dy*ay + dz*az
                ow = (ax,ay,az) if proj>=0 else (-ax,-ay,-az)
                entry = (hx+ow[0]*c["L"]/2, hy+ow[1]*c["L"]/2, hz+ow[2]*c["L"]/2)
                b1 = pa["bbox"]
                outside = (entry[0]<b1[0] or entry[0]>b1[3] or
                           entry[1]<b1[1] or entry[1]>b1[4] or
                           entry[2]<b1[2] or entry[2]>b1[5])
                print(f"    hole d={c['d']:.2f}  axis={c['ax']}  center={c['ct']}")
                print(f"    outward dir={ow}  entry={tuple(round(e,3) for e in entry)}")
                print(f"    entry outside bbox? {'YES(correct)' if outside else 'NO(WRONG!)'}")

print("\n" + "="*60)
print("Debug complete.") 