from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.GeomAbs import GeomAbs_Cylinder
from part_model import CylinderFeature
import math

def find_cylinders(shape):
    if shape is None or shape.IsNull(): return []
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
            cyls.append(CylinderFeature(
                radius=r, diameter=r*2, length=0.0,
                axis_dir=(ax.X(),ax.Y(),ax.Z()),
                center=(ct.X(),ct.Y(),ct.Z()),
                face=face,
                is_hole=(face.Orientation()==TopAbs_REVERSED)))
        exp.Next()
    cyls.sort(key=lambda c: c.radius)
    return cyls

def get_cylinder_faces(shape):
    return [c.face for c in find_cylinders(shape)]

def get_primary_axis(shape):
    cyls = find_cylinders(shape)
    if not cyls: return None, None
    lg = max(cyls, key=lambda c: c.radius)
    return lg.axis_dir, lg.center