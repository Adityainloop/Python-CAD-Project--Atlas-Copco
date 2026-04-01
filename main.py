import sys, os

def run_assembly(file_paths, output_step="assembled_model.step",
                 output_report="assembly_report.txt",
                 progress_cb=None, open_viewer=True,
                 instruction=None):
    from assembler import AssemblyEngine
    from step_exporter import export_step
    from report_generator import generate_report

    def cb(msg,pct): print(f"[{pct:3d}%] {msg}")
    engine = AssemblyEngine(progress_cb=progress_cb or cb)
    engine.load_parts(file_paths)
    if instruction:
        engine.set_instruction(instruction)
    result = engine.run()
    if result.get("success"):
        export_step(result["compound"], output_step)
        generate_report(parts=result["parts"],
                        pair_results=result["pair_results"],
                        output_file=output_report)
    if open_viewer and result.get("success"):
        _open_viewer(result)
    return result

def _open_viewer(result):
    from OCC.Display.SimpleGui import init_display
    COLORS=["BLUE","RED","GREEN","ORANGE","MAGENTA","CYAN","YELLOW"]
    display,start_display,_,__=init_display()
    for i,(shape,color,name) in enumerate(result.get("assembled_shapes",[])):
        if shape and not shape.IsNull():
            display.DisplayShape(shape,color=COLORS[i%len(COLORS)],update=False)
    display.FitAll(); start_display()

if __name__=="__main__":
    if len(sys.argv)<3:
        print("Usage: python main.py part1.step part2.step [...]"); sys.exit(1)
    run_assembly(sys.argv[1:])