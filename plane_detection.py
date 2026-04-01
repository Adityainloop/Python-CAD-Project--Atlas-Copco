from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.GeomAbs import GeomAbs_Plane
from OCC.Core.BRepGProp import brepgprop_SurfaceProperties
from OCC.Core.GProp import GProp_GProps
from part_model import PlaneFeature

def find_planes(shape):
    if shape is None or shape.IsNull(): return []
    planes = []
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = exp.Current()
        surf = BRepAdaptor_Surface(face)
        if surf.GetType() == GeomAbs_Plane:
            pl = surf.Plane()
            props = GProp_GProps()
            brepgprop_SurfaceProperties(face, props)
            planes.append(PlaneFeature(
                normal=pl.Axis().Direction(),
                point=pl.Location(),
                face=face,
                area=props.Mass(),
                is_inner=(face.Orientation()==TopAbs_REVERSED)))
        exp.Next()
    planes.sort(key=lambda p: p.area, reverse=True)
    return planes