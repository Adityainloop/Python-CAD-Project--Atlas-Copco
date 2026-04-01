"""
alignment.py — prompt-driven, handles all plane configurations
"""
import math
from OCC.Core.gp import gp_Trsf, gp_Vec, gp_Pnt, gp_Dir, gp_Ax1
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.Bnd import Bnd_Box
from part_model import CylinderFeature, PlaneFeature

def _get_bbox(shape):
    box=Bnd_Box(); brepbndlib.Add(shape,box); return box.Get()

def _bbox_center(shape):
    x0,y0,z0,x1,y1,z1=_get_bbox(shape)
    return (x0+x1)/2,(y0+y1)/2,(z0+z1)/2

def _combine(trsf_trans,trsf_rot):
    trsf_trans.PreMultiply(trsf_rot); return trsf_trans

def _make_rotation(n2,tx,ty,tz,pivot):
    dot=n2.X()*tx+n2.Y()*ty+n2.Z()*tz; t=gp_Trsf()
    if abs(abs(dot)-1.0)>1e-6:
        cx=n2.Y()*tz-n2.Z()*ty; cy=n2.Z()*tx-n2.X()*tz; cz=n2.X()*ty-n2.Y()*tx
        mag=math.sqrt(cx*cx+cy*cy+cz*cz)
        if mag>1e-10:
            angle=math.acos(max(-1.0,min(1.0,dot)))
            t.SetRotation(gp_Ax1(pivot,gp_Dir(cx/mag,cy/mag,cz/mag)),angle)
    return t

def _is_side_hole(hole,fixed_shape):
    hx,hy,hz=hole.center; bcx,bcy,bcz=_bbox_center(fixed_shape)
    x0,y0,z0,x1,y1,z1=_get_bbox(fixed_shape)
    part_max_r=max(x1-x0,y1-y0,z1-z0)/2
    dist=math.sqrt((hx-bcx)**2+(hy-bcy)**2+(hz-bcz)**2)
    return dist>part_max_r*0.4

def _outward(hole,fixed_shape):
    hx,hy,hz=hole.center; bcx,bcy,bcz=_bbox_center(fixed_shape)
    dx,dy,dz=hx-bcx,hy-bcy,hz-bcz
    mag=math.sqrt(dx*dx+dy*dy+dz*dz)
    return (dx/mag,dy/mag,dz/mag) if mag>1e-10 else (1.0,0.0,0.0)

def _shaft_half(shaft_shape,trsf_rot,axis):
    if shaft_shape is None: return 5.0
    rot=BRepBuilderAPI_Transform(shaft_shape,trsf_rot,True).Shape()
    bx0,by0,bz0,bx1,by1,bz1=_get_bbox(rot)
    ax,ay,az=axis
    corners=[(bx0,by0,bz0),(bx1,by0,bz0),(bx0,by1,bz0),(bx1,by1,bz0),
             (bx0,by0,bz1),(bx1,by0,bz1),(bx0,by1,bz1),(bx1,by1,bz1)]
    projs=[c[0]*ax+c[1]*ay+c[2]*az for c in corners]
    return (max(projs)-min(projs))/2.0

def align_radial(shaft,hole,shaft_shape,fixed_shape,insertion_depth=0.0,full_depth=False):
    """Insert shaft into side hole. Works for same-plane AND cross-plane parts."""
    had=hole.axis_dir; hx,hy,hz=hole.center; sad=shaft.axis_dir
    dot_sh=sad[0]*had[0]+sad[1]*had[1]+sad[2]*had[2]

    # Rotate shaft axis to align with hole axis
    trsf_rot=gp_Trsf()
    if abs(abs(dot_sh)-1.0)>1e-6:
        cx=sad[1]*had[2]-sad[2]*had[1]; cy=sad[2]*had[0]-sad[0]*had[2]; cz=sad[0]*had[1]-sad[1]*had[0]
        mag=math.sqrt(cx*cx+cy*cy+cz*cz)
        if mag>1e-10:
            angle=math.acos(max(-1.0,min(1.0,abs(dot_sh))))
            trsf_rot.SetRotation(gp_Ax1(gp_Pnt(*shaft.center),gp_Dir(cx/mag,cy/mag,cz/mag)),angle)

    rotated_sc=gp_Pnt(*shaft.center).Transformed(trsf_rot)
    ox,oy,oz=_outward(hole,fixed_shape)
    half=_shaft_half(shaft_shape,trsf_rot,had)
    hole_depth=hole.depth if (hole.depth and hole.depth>1.0) else hole.length
    if hole_depth<1.0: hole_depth=half*2

    if full_depth or insertion_depth<=0:
        # Center shaft in hole
        tx=hx-rotated_sc.X(); ty=hy-rotated_sc.Y(); tz=hz-rotated_sc.Z()
    else:
        # Partial: insertion_depth mm inside from entry
        entry_x=hx+ox*hole_depth/2; entry_y=hy+oy*hole_depth/2; entry_z=hz+oz*hole_depth/2
        tip_x=entry_x-ox*insertion_depth; tip_y=entry_y-oy*insertion_depth; tip_z=entry_z-oz*insertion_depth
        target_x=tip_x+ox*half; target_y=tip_y+oy*half; target_z=tip_z+oz*half
        tx=target_x-rotated_sc.X(); ty=target_y-rotated_sc.Y(); tz=target_z-rotated_sc.Z()

    t=gp_Trsf(); t.SetTranslation(gp_Vec(tx,ty,tz))
    return _combine(t,trsf_rot)

def align_shaft_through_hole(shaft,hole,shaft_shape,insertion_depth=0.0,full_depth=True):
    """Axial shaft through bore."""
    sad,had=shaft.axis_dir,hole.axis_dir
    dot=sad[0]*had[0]+sad[1]*had[1]+sad[2]*had[2]
    trsf_rot=gp_Trsf()
    if abs(abs(dot)-1.0)>1e-6:
        cx=sad[1]*had[2]-sad[2]*had[1]; cy=sad[2]*had[0]-sad[0]*had[2]; cz=sad[0]*had[1]-sad[1]*had[0]
        mag=math.sqrt(cx*cx+cy*cy+cz*cz)
        if mag>1e-10:
            angle=math.acos(max(-1.0,min(1.0,abs(dot))))
            trsf_rot.SetRotation(gp_Ax1(gp_Pnt(*shaft.center),gp_Dir(cx/mag,cy/mag,cz/mag)),angle)
    rsc=gp_Pnt(*shaft.center).Transformed(trsf_rot)
    hx,hy,hz=hole.center
    tx=hx-rsc.X(); ty=hy-rsc.Y(); tz=hz-rsc.Z()
    if not full_depth and insertion_depth>0 and shaft_shape:
        half=_shaft_half(shaft_shape,trsf_rot,had)
        hd=hole.depth if hole.depth>1.0 else hole.length
        if hd<1.0: hd=half*2
        hax,hay,haz=had
        entry=(hx*hax+hy*hay+hz*haz)-hd/2
        target=entry+insertion_depth-half
        cur=((rsc.X()+tx)*hax+(rsc.Y()+ty)*hay+(rsc.Z()+tz)*haz)
        extra=target-cur; tx+=hax*extra; ty+=hay*extra; tz+=haz*extra
    t=gp_Trsf(); t.SetTranslation(gp_Vec(tx,ty,tz)); return _combine(t,trsf_rot)

def align_cylinders(shaft,hole,insertion_depth=0.0,shaft_shape=None,full_depth=False):
    if shaft_shape: return align_shaft_through_hole(shaft,hole,shaft_shape,insertion_depth,full_depth)
    sad,had=shaft.axis_dir,hole.axis_dir; dot=sad[0]*had[0]+sad[1]*had[1]+sad[2]*had[2]
    trsf_rot=gp_Trsf()
    if abs(abs(dot)-1.0)>1e-6:
        cx=sad[1]*had[2]-sad[2]*had[1]; cy=sad[2]*had[0]-sad[0]*had[2]; cz=sad[0]*had[1]-sad[1]*had[0]
        mag=math.sqrt(cx*cx+cy*cy+cz*cz)
        if mag>1e-10:
            angle=math.acos(max(-1.0,min(1.0,abs(dot))))
            trsf_rot.SetRotation(gp_Ax1(gp_Pnt(*shaft.center),gp_Dir(cx/mag,cy/mag,cz/mag)),angle)
    rsc=gp_Pnt(*shaft.center).Transformed(trsf_rot); hx,hy,hz=hole.center
    t=gp_Trsf(); t.SetTranslation(gp_Vec(hx-rsc.X(),hy-rsc.Y(),hz-rsc.Z())); return _combine(t,trsf_rot)

def align_planes(p1,p2,shape2=None,gap=0.0):
    n1,n2=p1.normal,p2.normal; pt1,pt2=p1.point,p2.point
    trsf_rot=_make_rotation(n2,-n1.X(),-n1.Y(),-n1.Z(),pt2); rpt2=pt2.Transformed(trsf_rot)
    t=gp_Trsf(); t.SetTranslation(gp_Vec(pt1.X()-rpt2.X()+n1.X()*gap,pt1.Y()-rpt2.Y()+n1.Y()*gap,pt1.Z()-rpt2.Z()+n1.Z()*gap))
    return _combine(t,trsf_rot)

def align_slot(fixed_shape,moving_shape,p1,p2):
    n1,n2=p1.normal,p2.normal; pt1,pt2=p1.point,p2.point
    trsf_rot=_make_rotation(n2,-n1.X(),-n1.Y(),-n1.Z(),pt2); rpt2=pt2.Transformed(trsf_rot)
    rot_m=BRepBuilderAPI_Transform(moving_shape,trsf_rot,True).Shape()
    mx0,my0,mz0,mx1,my1,mz1=_get_bbox(rot_m); fx0,fy0,fz0,fx1,fy1,fz1=_get_bbox(fixed_shape)
    nx,ny,nz=abs(n1.X()),abs(n1.Y()),abs(n1.Z())
    ins=(mx1-mx0) if nx>=ny and nx>=nz else ((my1-my0) if ny>=nx and ny>=nz else (mz1-mz0))
    tx=pt1.X()-rpt2.X()-n1.X()*ins*0.5; ty=pt1.Y()-rpt2.Y()-n1.Y()*ins*0.5; tz=pt1.Z()-rpt2.Z()-n1.Z()*ins*0.5
    fcx=(fx0+fx1)/2; fcy=(fy0+fy1)/2; fcz=(fz0+fz1)/2
    mcx=(mx0+mx1)/2+tx; mcy=(my0+my1)/2+ty; mcz=(mz0+mz1)/2+tz
    t=gp_Trsf(); t.SetTranslation(gp_Vec(tx+(fcx-mcx)*(1-nx),ty+(fcy-mcy)*(1-ny),tz+(fcz-mcz)*(1-nz)))
    return _combine(t,trsf_rot)

def align_bolt_pattern(pa,pb):
    ca,cb=pa.centre,pb.centre; t=gp_Trsf(); t.SetTranslation(gp_Vec(ca[0]-cb[0],ca[1]-cb[1],ca[2]-cb[2])); return t

def align_bbox(fixed_shape,moving_shape,axis="x"):
    fx0,fy0,fz0,fx1,fy1,fz1=_get_bbox(fixed_shape); mx0,my0,mz0,mx1,my1,mz1=_get_bbox(moving_shape)
    GAP=2.0; tx,ty,tz=0.0,0.0,0.0
    if axis=="x": tx=fx1-mx0+GAP
    elif axis=="y": ty=fy1-my0+GAP
    else: tz=fz1-mz0+GAP
    t=gp_Trsf(); t.SetTranslation(gp_Vec(tx,ty,tz)); return t

def apply_transform(shape,trsf):
    b=BRepBuilderAPI_Transform(shape,trsf,True); b.Build(); return b.Shape()