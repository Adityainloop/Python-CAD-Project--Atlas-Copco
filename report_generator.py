"""
report_generator.py  — advanced with full tolerance analysis
"""
from datetime import datetime
from typing import List, Dict, Any


def generate_report(parts, pair_results, output_file="assembly_report.txt"):
    lines = []
    sep = "=" * 62

    lines += [sep, "   AI CAD ASSEMBLY REPORT  —  Advanced Analysis", sep]
    lines.append(f"Generated  : {datetime.now().strftime('%Y-%m-%d  %H:%M:%S')}")
    lines.append(f"Parts      : {len(parts)}")
    lines.append(f"Pairs      : {len(pair_results)}")
    lines.append("")

    # Parts
    lines += ["LOADED PARTS  —  Deep Geometry Analysis", "-"*45]
    for i,p in enumerate(parts,1):
        status = "OK" if p.is_loaded else "FAILED"
        lines.append(f"  {i:2d}. {p.name:<22} [{status}]  "
                     f"type={p.part_type}")
        if p.is_loaded:
            dx,dy,dz = p.bbox_dims
            lines.append(f"       BBox: {dx:.1f} x {dy:.1f} x {dz:.1f} mm  "
                         f"Volume: {p.volume:.1f} mm³")
            lines.append(f"       Cylinders: {len(p.cylinders)} "
                         f"(holes={len(p.holes)}, shafts={len(p.shafts)})  "
                         f"Planes: {len(p.planes)}  "
                         f"Patterns: {len(p.hole_patterns)}")
            for c in p.cylinders:
                role = "HOLE" if c.is_hole else "SHAFT"
                thru = " through" if c.is_through else " blind"
                lines.append(f"         [{role}{thru}] "
                             f"∅{c.diameter:.3f}mm  L={c.length:.2f}mm  "
                             f"ax=({c.axis_dir[0]:.2f},{c.axis_dir[1]:.2f},{c.axis_dir[2]:.2f})")
            for pat in p.hole_patterns:
                lines.append(f"         [PATTERN:{pat.pattern_type}] "
                             f"N={pat.count}  "
                             f"BCD={pat.bolt_circle_dia:.1f}mm")
    lines.append("")

    # Assembly pairs
    lines += ["ASSEMBLY PAIRS", "-"*45]
    for i,res in enumerate(pair_results,1):
        strat = res.get("strategy","?")
        conf  = res.get("confidence",0)*100
        coll  = res.get("collision",False)
        tx    = res.get("translation",(0,0,0))

        lines.append(f"\n  Pair {i}: {res.get('part_a','?')}  ←→  {res.get('part_b','?')}")
        lines.append(f"    Strategy      : {strat}")
        lines.append(f"    Confidence    : {conf:.1f} %")
        if res.get("description"):
            lines.append(f"    Match detail  : {res['description']}")

        # Cylinder fit details
        if strat == "cylinder":
            lines.append(f"    Shaft dia     : {res.get('shaft_dia', res.get('shaft_d',0)):.4f} mm")
            lines.append(f"    Hole dia      : {res.get('hole_dia',  res.get('hole_d',0)):.4f} mm")
            lines.append(f"    Clearance     : {res.get('diametral_clearance', res.get('clearance',0)):+.4f} mm")
            lines.append(f"    Fit class     : {res.get('fit_class','')}")
            lines.append(f"    ISO grade     : {res.get('fit_grade','')}")
            lines.append(f"    Note          : {res.get('note','')}")
            lines.append(f"    Insertion     : {res.get('insertion_depth',0):.2f} mm")
            lines.append(f"    Engagement    : {res.get('engagement_length',0):.2f} mm")
            overhang = res.get("overhang",0)
            if overhang > 0:
                lines.append(f"    Overhang      : {overhang:.2f} mm")

        elif strat == "bolt_pattern":
            lines.append(f"    Bolt count    : {res.get('hole_count','?')}")
            lines.append(f"    Pattern note  : {res.get('note','')}")

        elif strat in ("plane","slot"):
            lines.append(f"    Fit type      : {res.get('fit_class','Plane Mating')}")
            lines.append(f"    Note          : {res.get('note','')}")

        lines.append(f"    Translation   : ({tx[0]:.3f}, {tx[1]:.3f}, {tx[2]:.3f}) mm")
        lines.append(f"    Collision     : {'⚠  YES' if coll else 'None ✓'}")

    lines += ["", "-"*45, "MODULES", "  • Deep Geometry Analysis (diameter/length/depth/axis)",
              "  • Part Classification (shaft/plate/housing/bracket/flange)",
              "  • Hole Pattern Detection (bolt circle/linear/grid)",
              "  • Smart Feature Matching (ranked candidates)",
              "  • ISO Tolerance Analysis (fit class + grade)",
              "  • User Prompt Parsing (natural language)",
              "  • Multi-Part Chain Assembly",
              "  • Collision Detection",
              "", sep, "END OF REPORT", sep]

    content = "\n".join(lines)
    with open(output_file,"w",encoding="utf-8") as f:
        f.write(content)
    print(f"[Report] Written: {output_file}")
    return output_file