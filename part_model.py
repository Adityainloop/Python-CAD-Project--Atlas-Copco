"""
part_model.py  — extended data model
Stores all deep geometry analysis results per part.
"""
import os
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple


@dataclass
class CylinderFeature:
    radius: float                    # mm
    diameter: float                  # mm  (= radius * 2)
    length: float                    # mm  (estimated axial extent)
    axis_dir: tuple                  # (dx, dy, dz) unit vector
    center: tuple                    # (x, y, z) centre point
    face: Any = None                 # OCC TopoDS_Face
    is_hole: bool = False            # True = bore/hole, False = shaft/boss
    is_through: bool = False         # True = through-hole
    depth: float = 0.0               # hole depth if blind (mm)
    threaded: bool = False           # True if thread features detected


@dataclass
class PlaneFeature:
    normal: Any                      # OCC gp_Dir
    point: Any                       # OCC gp_Pnt
    face: Any = None                 # OCC TopoDS_Face
    area: float = 0.0                # mm²
    is_inner: bool = False           # True = cavity/slot wall face


@dataclass
class HolePattern:
    """A group of holes at consistent spacing — bolt circle, grid, etc."""
    holes: List[CylinderFeature] = field(default_factory=list)
    pattern_type: str = "unknown"    # "bolt_circle" | "linear" | "grid"
    bolt_circle_dia: float = 0.0     # mm (if bolt_circle)
    centre: tuple = (0.0, 0.0, 0.0) # pattern centre
    count: int = 0


@dataclass
class PartModel:
    file_path: str
    shape: Any = None
    cylinders:    List[CylinderFeature] = field(default_factory=list)
    planes:       List[PlaneFeature]    = field(default_factory=list)
    hole_patterns: List[HolePattern]    = field(default_factory=list)

    # Deep geometry analysis results
    part_type: str = "unknown"       # shaft|plate|housing|bracket|fastener|flange|generic
    volume: float = 0.0              # mm³
    bbox_dims: tuple = (0.0, 0.0, 0.0)   # (dx, dy, dz)
    bbox_min:  tuple = (0.0, 0.0, 0.0)
    bbox_max:  tuple = (0.0, 0.0, 0.0)
    centroid:  tuple = (0.0, 0.0, 0.0)
    primary_axis: Optional[tuple] = None  # dominant axis direction

    @property
    def name(self) -> str:
        return os.path.splitext(os.path.basename(self.file_path))[0]

    @property
    def is_loaded(self) -> bool:
        return self.shape is not None and not self.shape.IsNull()

    @property
    def shafts(self) -> List[CylinderFeature]:
        return [c for c in self.cylinders if not c.is_hole]

    @property
    def holes(self) -> List[CylinderFeature]:
        return [c for c in self.cylinders if c.is_hole]

    def summary(self) -> str:
        return (f"{self.name} [{self.part_type}]  "
                f"bbox={self.bbox_dims[0]:.1f}x{self.bbox_dims[1]:.1f}x{self.bbox_dims[2]:.1f}mm  "
                f"cylinders={len(self.cylinders)}(holes={len(self.holes)},shafts={len(self.shafts)})  "
                f"planes={len(self.planes)}  "
                f"hole_patterns={len(self.hole_patterns)}")