"""Cross-axis assembly for knuckle joints and perpendicular fits."""
import math
from OCC.Core.gp import gp_Trsf, gp_Vec, gp_Ax1, gp_Pnt, gp_Dir
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform

def _dot(a,b): return sum(x*y for x,y in zip(a,b))
def _cross(a,b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def _norm(v):
    m=math.sqrt(sum(x**2 for x in v)); return tuple(x/m for x in v) if m>1e-10 else v

def detect_rotation_needed(fixed_cyl, moving_cyl) -> dict:
    ha = tuple(fixed_cyl.axis_dir)
    sa = tuple(moving_cyl.axis_dir)
    angle = math.degrees(math.acos(max(-1.0,min(1.0,abs(_dot(ha,sa))))))
    if angle < 5:
        return {"needed":False,"angle":0,"axis":(0,0,1)}
    rot_axis = _norm(_cross(sa, ha))
    return {"needed":True,"angle":angle,"axis":rot_axis,
            "shaft_axis":sa,"hole_axis":ha}

def apply_cross_axis_assembly(fixed_shape, moving_shape,
                               fixed_cyl, moving_cyl,
                               pre_rotate_axis=None, pre_rotate_deg=None):
    rot = detect_rotation_needed(fixed_cyl, moving_cyl)
    pivot = gp_Pnt(*moving_cyl.center)
    trsf_rot = gp_Trsf()
    if pre_rotate_axis and pre_rotate_deg:
        ax = {"x":(1,0,0),"y":(0,1,0),"z":(0,0,1)}.get(
             pre_rotate_axis.lower(),(0,0,1))
        trsf_rot.SetRotation(gp_Ax1(pivot,gp_Dir(*ax)),
                              math.radians(pre_rotate_deg))
    elif rot["needed"]:
        rx,ry,rz = rot["axis"]
        trsf_rot.SetRotation(gp_Ax1(pivot,gp_Dir(rx,ry,rz)),
                              math.radians(rot["angle"]))
    rotated = BRepBuilderAPI_Transform(moving_shape,trsf_rot,True).Shape()
    mc = gp_Pnt(*moving_cyl.center).Transformed(trsf_rot)
    hc = fixed_cyl.center
    hax,hay,haz = fixed_cyl.axis_dir
    hd = getattr(fixed_cyl,"depth",0) or getattr(fixed_cyl,"length",20)
    tx = hc[0]-mc.X()+hax*(hd/2)
    ty = hc[1]-mc.Y()+hay*(hd/2)
    tz = hc[2]-mc.Z()+haz*(hd/2)
    trsf_t = gp_Trsf(); trsf_t.SetTranslation(gp_Vec(tx,ty,tz))
    assembled = BRepBuilderAPI_Transform(rotated,trsf_t,True).Shape()
    return assembled,(tx,ty,tz),rot
