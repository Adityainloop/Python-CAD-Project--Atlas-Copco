"""
assembler_pro.py — Industry wrapper around the proven assembler.py engine.
Adds: BOM, tolerance analysis, assembly sequence, constraints, multi-format export.
The core assembly logic is 100% from assembler.py (which works correctly).
"""
import os, re, time
from typing import List, Callable, Optional, Dict

# ── Import the PROVEN working engine ──────────────────────────────────────
from assembler import AssemblyEngine

# ── Industry add-on modules ───────────────────────────────────────────────
from bom_generator      import BOMGenerator
from assembly_sequence  import AssemblySequence
from tolerance_analysis import classify_fit
from constraints        import ConstraintSolver, Constraint

try:
    from export_formats import (export_step, export_step_catia,
                                 export_step_solidworks, export_step_ap242,
                                 export_iges, export_stl,
                                 export_all_formats, export_freecad_script)
    HAS_EXPORT = True
except Exception:
    HAS_EXPORT = False

try:
    from claude_ai_engine import call_claude_api, build_geometry_context
    HAS_CLAUDE = True
except Exception:
    HAS_CLAUDE = False


class AssemblyEnginePro:
    """
    Industry-level CAD assembly engine.
    Wraps the proven AssemblyEngine and adds BOM, tolerance,
    sequence tracking, constraints, multi-format export, Claude AI.
    """

    def __init__(self, progress_cb=None, use_claude_api=False):
        self._engine         = AssemblyEngine(progress_cb=progress_cb)
        self.use_claude_api  = use_claude_api
        self.bom             = BOMGenerator()
        self.sequence        = AssemblySequence()
        self.constraints     = ConstraintSolver()
        self.tolerance_reports: Dict[str, dict] = {}
        self.export_results: dict = {}

        # Mirror engine attributes so GUI works
        self.parts            = self._engine.parts
        self.pair_results     = self._engine.pair_results
        self.compound         = self._engine.compound
        self.assembled_shapes = self._engine.assembled_shapes

    def load_parts(self, file_paths):
        self._engine.load_parts(file_paths)
        self.parts = self._engine.parts

    def set_instruction(self, ops):
        self._engine.set_instruction(ops)

    def run(self) -> dict:
        start = time.time()

        # Optional Claude AI enhancement
        if self.use_claude_api and HAS_CLAUDE:
            self._claude_enhance()

        # ── Run the PROVEN assembly engine (assembler.py) ──────────────
        result = self._engine.run()

        # Mirror results back
        self.parts            = self._engine.parts
        self.compound         = self._engine.compound
        self.assembled_shapes = self._engine.assembled_shapes

        # Normalize pair_results: ensure 'shape' key exists (assembler.py uses 'moved_shape')
        self.pair_results = []
        for r in self._engine.pair_results:
            normalized = dict(r)
            if "moved_shape" in normalized and "shape" not in normalized:
                normalized["shape"] = normalized["moved_shape"]
            if "shape" not in normalized:
                normalized["shape"] = None
            self.pair_results.append(normalized)

        # ── Build BOM from loaded parts ────────────────────────────────
        loaded = [p for p in self.parts if p.is_loaded]
        self.bom.add_from_parts(loaded)

        # ── Tolerance analysis + constraints for each pair ─────────────
        for r in self.pair_results:
            part_name = r.get("part_b", "")
            note      = r.get("note", "")
            try:
                m = re.search(r'd=([\d.]+)mm', note)
                if m:
                    hole_d  = float(m.group(1))
                    shaft_d = hole_d
                    for p in self.parts:
                        if p.name == part_name:
                            shafts = [c for c in p.cylinders if not c.is_hole]
                            if shafts:
                                shaft_d = shafts[0].diameter
                    fit = classify_fit(hole_d, shaft_d)
                    self.tolerance_reports[part_name] = fit
                    self.constraints.add_constraint(Constraint(
                        type="coincident",
                        entity_a={"part": r.get("part_a", ""), "feature": "hole"},
                        entity_b={"part": part_name, "feature": "shaft"},
                        description=(f"{part_name} → {r.get('part_a','')} "
                                     f"[{fit['fit_class']}]")
                    ))
            except Exception:
                pass

            # Sequence step
            step = self.sequence.add_step(
                f"Insert {part_name} into {r.get('part_a','')}",
                part_name, "insert",
                {"hole": r.get("fit_class",""),
                 "translation": r.get("translation")})
            self.sequence.mark_complete(
                step, r.get("shape"), success=True,
                notes=f"Fit: {r.get('fit_class','')}")

        # ── Save industry output files ─────────────────────────────────
        self._save_outputs()

        total_ms = (time.time() - start) * 1000
        result.update({
            "bom":         self.bom.to_txt(),
            "sequence":    self.sequence.to_report(),
            "tolerance":   self.tolerance_reports,
            "exports":     self.export_results,
            "total_ms":    total_ms,
            "constraints": self.constraints.summary(),
        })
        return result

    def _claude_enhance(self):
        if not HAS_CLAUDE: return
        try:
            ops    = self._engine.operations
            loaded = [p for p in self.parts if p.is_loaded]
            if not ops or not loaded: return
            parts_data = [{"name": p.name,
                           "bbox": str(getattr(p, 'bbox_dims', '')),
                           "type": p.part_type,
                           "cylinders": [{"d": c.diameter, "is_hole": c.is_hole,
                                           "axis": c.axis_dir, "center": c.center}
                                          for c in p.cylinders]}
                          for p in loaded]
            ctx    = build_geometry_context(parts_data)
            prompt = " ".join(getattr(op, 'raw_prompt', '') for op in ops)
            plan   = call_claude_api("", ctx, prompt or "assemble parts")
            if plan.confidence > 0.6:
                for op in ops:
                    if plan.hole_description and not op.hole_description:
                        op.hole_description   = plan.hole_description
                    if plan.insertion_depth > 0 and not op.insertion_depth:
                        op.insertion_depth    = plan.insertion_depth
                    if plan.rotation_needed and not getattr(op,'pre_rotate_axis',''):
                        op.pre_rotate_axis    = plan.rotation_axis
                        op.pre_rotate_degrees = plan.rotation_degrees
        except Exception as e:
            print(f"[Claude AI] {e}")

    def _save_outputs(self):
        try:
            self.bom.save("bom", "txt"); self.bom.save("bom", "csv")
            self.export_results["BOM_txt"] = "bom.txt"
            self.export_results["BOM_csv"] = "bom.csv"
        except Exception as e:
            self.export_results["BOM_error"] = str(e)
        try:
            with open("assembly_sequence.txt", "w") as f:
                f.write(self.sequence.to_report())
            self.export_results["sequence"] = "assembly_sequence.txt"
        except Exception as e:
            self.export_results["sequence_error"] = str(e)
        try:
            lines = ["TOLERANCE ANALYSIS\n" + "="*50]
            for name, fit in self.tolerance_reports.items():
                lines += [f"\n{name}:",
                          f"  {fit['fit_class']} — {fit['fit_description']}",
                          f"  ISO: {fit['iso_suggestion']}",
                          f"  Force: {fit['assembly_force']}"]
            with open("tolerance_report.txt", "w") as f:
                f.write("\n".join(lines))
            self.export_results["tolerance"] = "tolerance_report.txt"
        except Exception as e:
            self.export_results["tolerance_error"] = str(e)

    # ── Export methods ─────────────────────────────────────────────────────
    def export_to_format(self, shape, path: str, fmt: str = "STEP_AP214") -> bool:
        if not HAS_EXPORT: return False
        try:
            fm = {"STEP_AP214": export_step_catia,
                  "STEP_AP203": export_step_solidworks,
                  "STEP_AP242": export_step_ap242,
                  "IGES":       export_iges,
                  "STL":        export_stl}
            return fm.get(fmt, export_step)(shape, path)
        except Exception as e:
            print(f"Export error: {e}"); return False

    def export_all(self, base_name: str, output_dir: str = ".") -> dict:
        if self.compound and HAS_EXPORT:
            return export_all_formats(self.compound, base_name, output_dir)
        return {}

    def export_freecad(self, output_path: str) -> str:
        if not HAS_EXPORT: return ""
        parts_info = [{"name": p.name, "filepath": p.file_path}
                      for p in self.parts if p.is_loaded]
        transforms = [(0,0,0)] + [r.get("translation",(0,0,0))
                                    for r in self.pair_results]
        return export_freecad_script(parts_info, transforms, output_path)

    # ── Undo/Redo ──────────────────────────────────────────────────────────
    def undo(self):
        self.constraints.undo()
        return self.sequence.undo()

    def redo(self):
        return self.sequence.redo()

    def get_undo_redo_state(self) -> dict:
        return {"can_undo":     self.sequence.can_undo(),
                "can_redo":     self.sequence.can_redo(),
                "current_step": self.sequence.current_step,
                "total_steps":  len(self.sequence.steps)}

    # ── Accessors ──────────────────────────────────────────────────────────
    def get_bom(self, fmt="txt") -> str:
        if fmt == "csv":  return self.bom.to_csv()
        if fmt == "json": return self.bom.to_json()
        return self.bom.to_txt()

    def get_constraints_summary(self) -> List[str]:
        return self.constraints.summary()

    def get_tolerance_report(self, part_name="") -> str:
        if not self.tolerance_reports:
            return "Run assembly first to see tolerance data."
        lines = ["TOLERANCE ANALYSIS", "="*50]
        for name, fit in self.tolerance_reports.items():
            lines += [f"\n{name}:",
                      f"  Clearance:  {fit['clearance']:+.3f} mm",
                      f"  Fit Class:  {fit['fit_class']}",
                      f"  ISO:        {fit['iso_suggestion']}",
                      f"  Grade:      {fit['tolerance_grade']}",
                      f"  Force:      {fit['assembly_force']}",
                      f"  Use:        {fit['application']}"]
        return "\n".join(lines)