"""Multi-step assembly sequence with undo/redo."""
import json, time
from dataclasses import dataclass, field
from typing import List, Optional, Callable

@dataclass
class AssemblyStep:
    step_num: int
    description: str
    part_name: str
    action: str
    params: dict = field(default_factory=dict)
    shape_after = None
    duration_ms: float = 0.0
    success: bool = False
    notes: str = ""

class AssemblySequence:
    def __init__(self):
        self.steps: List[AssemblyStep] = []
        self.current_step = 0
        self._undo_stack: List[int] = []
        self._redo_stack: List[int] = []
        self.on_step_change: Optional[Callable] = None

    def add_step(self, description, part_name, action, params=None):
        s = AssemblyStep(len(self.steps)+1, description,
                         part_name, action, params or {})
        self.steps.append(s); return s

    def mark_complete(self, step, shape_after, duration_ms=0,
                      success=True, notes=""):
        step.shape_after = shape_after
        step.duration_ms = duration_ms
        step.success     = success
        step.notes       = notes
        self._undo_stack.append(step.step_num)
        self._redo_stack.clear()
        self.current_step = step.step_num
        if self.on_step_change: self.on_step_change(step)

    def can_undo(self): return len(self._undo_stack) > 0
    def can_redo(self): return len(self._redo_stack) > 0

    def undo(self):
        if not self.can_undo(): return None
        n = self._undo_stack.pop(); self._redo_stack.append(n)
        s = self.steps[n-1]
        self.current_step = self._undo_stack[-1] if self._undo_stack else 0
        if self.on_step_change: self.on_step_change(s)
        return s

    def redo(self):
        if not self.can_redo(): return None
        n = self._redo_stack.pop(); self._undo_stack.append(n)
        s = self.steps[n-1]; self.current_step = n
        if self.on_step_change: self.on_step_change(s)
        return s

    def to_report(self) -> str:
        lines = ["ASSEMBLY SEQUENCE REPORT", "="*60,
                 f"Total steps: {len(self.steps)}",
                 f"Completed:   {sum(1 for s in self.steps if s.success)}",
                 "-"*60]
        for s in self.steps:
            st = "OK" if s.success else "FAIL"
            lines.append(f"Step {s.step_num:2d} [{st:4s}] "
                         f"[{s.action.upper():10s}] {s.part_name}: {s.description}")
            if s.notes: lines.append(f"           Note: {s.notes}")
        lines.append("="*60)
        return "\n".join(lines)

    def to_json(self): return json.dumps([{
        "step":s.step_num,"description":s.description,
        "part":s.part_name,"action":s.action,
        "params":s.params,"success":s.success,
        "notes":s.notes} for s in self.steps], indent=2)
