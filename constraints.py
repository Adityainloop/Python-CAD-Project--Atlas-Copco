"""Assembly constraints: coincident, parallel, perpendicular, distance."""
import math
from dataclasses import dataclass, field
from typing import List
from OCC.Core.gp import gp_Trsf, gp_Vec, gp_Ax1, gp_Pnt, gp_Dir
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform

@dataclass
class Constraint:
    type: str
    entity_a: dict
    entity_b: dict
    value: float = 0.0
    description: str = ""

class ConstraintSolver:
    def __init__(self):
        self.constraints: List[Constraint] = []
        self._history: List[Constraint] = []

    def add_constraint(self, c: Constraint):
        self.constraints.append(c); self._history.append(c)

    def undo(self):
        if self.constraints: self.constraints.pop(); return True
        return False

    def apply_coincident(self, shape_b, pnt_a, pnt_b):
        tx,ty,tz = pnt_a[0]-pnt_b[0],pnt_a[1]-pnt_b[1],pnt_a[2]-pnt_b[2]
        t = gp_Trsf(); t.SetTranslation(gp_Vec(tx,ty,tz))
        return BRepBuilderAPI_Transform(shape_b,t,True).Shape(),(tx,ty,tz)

    def apply_distance(self, shape_b, direction, distance):
        dx,dy,dz = direction
        m = math.sqrt(dx**2+dy**2+dz**2)
        if m<1e-10: return shape_b,(0,0,0)
        tx,ty,tz = dx/m*distance,dy/m*distance,dz/m*distance
        t = gp_Trsf(); t.SetTranslation(gp_Vec(tx,ty,tz))
        return BRepBuilderAPI_Transform(shape_b,t,True).Shape(),(tx,ty,tz)

    def summary(self):
        return [f"{c.type}: {c.description}" for c in self.constraints]
