"""ISO fit classification and tolerance analysis."""

def classify_fit(hole_d: float, shaft_d: float) -> dict:
    clearance = hole_d - shaft_d
    r = {"hole_d": round(hole_d,3), "shaft_d": round(shaft_d,3),
         "clearance": round(clearance,3),
         "fit_class":"", "fit_description":"",
         "iso_suggestion":"", "tolerance_grade":"",
         "assembly_force":"", "application":""}
    if clearance > 0.5:
        r.update(fit_class="Loose Clearance",
                 fit_description="Free movement, significant play",
                 iso_suggestion="H11/c11 or H8/e8",
                 assembly_force="None — slides freely",
                 application="Hinges, loose pivots")
    elif clearance > 0.1:
        r.update(fit_class="Clearance Fit",
                 fit_description="Running fit, easy assembly",
                 iso_suggestion="H8/f7 or H7/g6",
                 assembly_force="None — hand push",
                 application="Rotating shafts, sliding parts")
    elif clearance > 0.02:
        r.update(fit_class="Close Clearance",
                 fit_description="Accurate location, minimal play",
                 iso_suggestion="H7/h6",
                 assembly_force="Light hand press",
                 application="Precision location, gear hubs")
    elif clearance > -0.01:
        r.update(fit_class="Transition Fit",
                 fit_description="May be clearance or interference",
                 iso_suggestion="H7/k6 or H7/m6",
                 assembly_force="Mallet or light press",
                 application="Precision fits, good alignment needed")
    elif clearance > -0.05:
        r.update(fit_class="Light Interference",
                 fit_description="Light press, permanent assembly",
                 iso_suggestion="H7/p6 or H7/n6",
                 assembly_force="Hydraulic press",
                 application="Bearing rings, bushings")
    else:
        r.update(fit_class="Heavy Interference",
                 fit_description="Heavy press or shrink fit",
                 iso_suggestion="H7/s6 or H7/u6",
                 assembly_force="Heating/cooling required",
                 application="Permanent joints, high torque")
    D = hole_d
    r["tolerance_grade"] = ("IT6/IT7" if D<18 else
                             "IT7/IT8" if D<80 else "IT8/IT9")
    return r

def full_tolerance_report(hole_d, shaft_d, part_a, part_b) -> str:
    fit = classify_fit(hole_d, shaft_d)
    return "\n".join([
        "="*50, "TOLERANCE ANALYSIS REPORT", "="*50,
        f"Hole part:  {part_a}",
        f"Shaft part: {part_b}",
        f"Hole dia:   {hole_d:.3f} mm",
        f"Shaft dia:  {shaft_d:.3f} mm",
        f"Clearance:  {fit['clearance']:+.3f} mm",
        "", f"CLASS: {fit['fit_class']}",
        f"ISO:   {fit['iso_suggestion']}",
        f"Grade: {fit['tolerance_grade']}",
        f"Force: {fit['assembly_force']}",
        f"Use:   {fit['application']}", "="*50])
