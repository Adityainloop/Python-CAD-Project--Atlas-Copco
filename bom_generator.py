"""Bill of Materials generator."""
import os, json
from datetime import datetime
from typing import List, Dict

class BOMGenerator:
    def __init__(self):
        self.items: List[Dict] = []

    def add_part(self, name, qty=1, material="Steel",
                 finish="Machined", mass_g=None, notes=""):
        self.items.append({
            "item": len(self.items)+1,
            "part_name": os.path.splitext(os.path.basename(name))[0],
            "filename": name, "quantity": qty,
            "material": material, "finish": finish,
            "mass_g": mass_g, "notes": notes
        })

    def add_from_parts(self, parts_list, tolerance_data=None):
        self.items = []
        for p in parts_list:
            name = getattr(p, "name", str(p))
            mass = None
            if hasattr(p, "bbox_dims") and p.bbox_dims:
                dx,dy,dz = p.bbox_dims
                mass = round((dx*dy*dz/1000)*7.85, 1)
            notes = ""
            if tolerance_data and name in tolerance_data:
                notes = f"Fit: {tolerance_data[name].get('fit_class','')}"
            self.add_part(name, qty=1, mass_g=mass, notes=notes)

    def to_txt(self, title="Assembly") -> str:
        lines = [
            f"BILL OF MATERIALS — {title}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "="*80,
            f"{'#':<4} {'Part Name':<30} {'Qty':<5} {'Material':<12} "
            f"{'Finish':<12} {'Mass(g)':<9} Notes",
            "-"*80,
        ]
        total = 0
        for i in self.items:
            m = i["mass_g"] or 0
            total += m * i["quantity"]
            lines.append(
                f"{i['item']:<4} {i['part_name']:<30} {i['quantity']:<5} "
                f"{i['material']:<12} {i['finish']:<12} "
                f"{str(round(m,1))+'g':<9} {i['notes']}")
        lines += ["-"*80,
                  f"Total items: {len(self.items)}   "
                  f"Est. mass: {round(total,1)}g = {round(total/1000,3)}kg",
                  "="*80]
        return "\n".join(lines)

    def to_csv(self, title="Assembly") -> str:
        lines = ["Item,Part Name,Filename,Qty,Material,Finish,Mass_g,Notes"]
        for i in self.items:
            lines.append(f"{i['item']},{i['part_name']},{i['filename']},"
                         f"{i['quantity']},{i['material']},{i['finish']},"
                         f"{i['mass_g'] or ''},\"{i['notes']}\"")
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps({"bom": self.items,
                           "generated": datetime.now().isoformat(),
                           "total_items": len(self.items)}, indent=2)

    def save(self, prefix="bom", fmt="txt", title="Assembly"):
        path = f"{prefix}.{fmt}"
        with open(path, "w") as f:
            f.write(getattr(self, f"to_{fmt}")(title) if fmt != "json"
                    else self.to_json())
        return path
