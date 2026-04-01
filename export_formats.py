"""Export to STEP, IGES, STL, FreeCAD script."""
import os
from OCC.Core.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCC.Core.IGESControl import IGESControl_Writer
from OCC.Core.BRepMesh    import BRepMesh_IncrementalMesh
from OCC.Core.StlAPI      import StlAPI_Writer
from OCC.Core.Interface   import Interface_Static
from OCC.Core.IFSelect    import IFSelect_RetDone

def _step(shape, path, schema="AP214CD"):
    w = STEPControl_Writer()
    Interface_Static.SetCVal("write.step.schema", schema)
    w.Transfer(shape, STEPControl_AsIs)
    return w.Write(path) == IFSelect_RetDone

def export_step_catia(shape, path):     return _step(shape,path,"AP214CD")
def export_step_solidworks(shape,path): return _step(shape,path,"AP203")
def export_step_ap242(shape, path):     return _step(shape,path,"AP242DIS")

def export_iges(shape, path):
    w = IGESControl_Writer(); w.AddShape(shape); w.ComputeModel()
    return w.Write(path)

def export_stl(shape, path, lin=0.1, ang=0.5):
    BRepMesh_IncrementalMesh(shape,lin,False,ang).Perform()
    w = StlAPI_Writer(); w.SetASCIIMode(False)
    return w.Write(shape, path)

def export_all_formats(shape, base, out_dir="."):
    os.makedirs(out_dir, exist_ok=True)
    res = {}
    for name,func,ext in [
        ("STEP_AP214", export_step_catia,      ".step"),
        ("STEP_AP203", export_step_solidworks, "_sw.step"),
        ("STEP_AP242", export_step_ap242,      "_ap242.step"),
        ("IGES",       export_iges,            ".igs"),
        ("STL",        export_stl,             ".stl"),
    ]:
        p = os.path.join(out_dir, base+ext)
        try: ok=func(shape,p); res[name]={"path":p,"ok":ok}
        except Exception as e: res[name]={"path":p,"ok":False,"error":str(e)}
    return res

def export_step(shape, path):
    """Alias — default STEP export (AP214)."""
    return _step(shape, path, "AP214CD")

def export_freecad_script(parts_info, transforms, out_path):
    lines = ["# FreeCAD Assembly Script — AI CAD System",
             "import FreeCAD, Part","doc = FreeCAD.newDocument('Assembly')",""]
    for i,(p,t) in enumerate(zip(parts_info,transforms)):
        n = p.get("name","Part").replace(" ","_").replace(".","_")
        fp = p.get("filepath","").replace("\\","/")
        tx,ty,tz = t if t else (0,0,0)
        lines += [f"s{i}=Part.Shape(); s{i}.read(r'{fp}')",
                  f"o{i}=doc.addObject('Part::Feature','{n}')",
                  f"o{i}.Shape=s{i}",
                  f"o{i}.Placement=FreeCAD.Placement(",
                  f"  FreeCAD.Vector({tx:.3f},{ty:.3f},{tz:.3f}),",
                  f"  FreeCAD.Rotation(0,0,0,1))",""]
    lines += ["doc.recompute()","doc.save('assembly.FCStd')"]
    with open(out_path,"w") as f: f.write("\n".join(lines))
    return "\n".join(lines)
