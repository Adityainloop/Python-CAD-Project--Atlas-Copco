"""
gui_app.py — final clean version
Passes ALL ops as list to engine. No attribute errors.
"""
import os, sys, threading, traceback
import tkinter as tk
from tkinter import filedialog, ttk, scrolledtext

_last_result = None

def run_tkinter():
    global _last_result
    step_files = []

    root = tk.Tk()
    root.title("AI-Assisted CAD Assembly System")
    root.geometry("1080x800")
    root.configure(bg="#1a1a2e")

    FT=("Arial",17,"bold"); FN=("Arial",10); FB=("Arial",10,"bold"); FM=("Consolas",9)

    tk.Label(root,text="AI-Assisted CAD Assembly System",font=FT,fg="#e94560",bg="#1a1a2e").pack(pady=(12,2))
    tk.Label(root,text="Upload STEP files  ·  Describe in plain language  ·  AI-powered",font=("Arial",9),fg="#9e9e9e",bg="#1a1a2e").pack(pady=(0,8))

    split=tk.Frame(root,bg="#1a1a2e"); split.pack(fill="both",expand=True,padx=12,pady=4)
    left=tk.Frame(split,bg="#1a1a2e",width=530); right=tk.Frame(split,bg="#1a1a2e")
    left.pack(side="left",fill="both",expand=False,padx=(0,6)); left.pack_propagate(False)
    right.pack(side="right",fill="both",expand=True)

    pf=tk.LabelFrame(left,text="  Loaded Parts  ",font=FB,fg="white",bg="#16213e",bd=1,relief="groove",padx=6,pady=6)
    pf.pack(fill="x",pady=(0,6))
    lf=tk.Frame(pf,bg="#16213e"); lf.pack(fill="both")
    file_list=tk.Listbox(lf,width=62,height=5,font=FM,bg="#0d1117",fg="#c9d1d9",selectbackground="#e94560",bd=0,highlightthickness=0)
    file_list.pack(side="left",fill="both",expand=True)
    sb=tk.Scrollbar(lf,bg="#16213e"); sb.pack(side="right",fill="y")
    file_list.config(yscrollcommand=sb.set); sb.config(command=file_list.yview)
    count_var=tk.StringVar(value="No files loaded")
    tk.Label(pf,textvariable=count_var,font=("Arial",8),fg="#9e9e9e",bg="#16213e",anchor="w").pack(fill="x")

    def upload_files():
        files=filedialog.askopenfilenames(title="Select STEP Files",filetypes=[("STEP","*.step *.stp"),("All","*.*")])
        if files:
            added=0
            for f in files:
                f=os.path.abspath(f)
                if f not in step_files: step_files.append(f); added+=1
            _refresh_list(); _log(f"Added {added} file(s). Total: {len(step_files)}","info")
            _update_suggestions()

    def clear_files():
        step_files.clear(); file_list.delete(0,tk.END)
        count_var.set("No files loaded"); _set_btns(False)

    def remove_selected():
        sel=file_list.curselection()
        if sel: step_files.pop(sel[0]); _refresh_list()

    def _refresh_list():
        file_list.delete(0,tk.END)
        for i,f in enumerate(step_files,1):
            name=os.path.basename(f); folder=os.path.dirname(f)
            if len(folder)>38: folder="…"+folder[-35:]
            file_list.insert(tk.END,f"  {i:2d}.  {name:<26} {folder}")
        n=len(step_files)
        count_var.set(f"{n} file(s)"+(" — need ≥2" if n<2 else " — ready ✓"))

    br=tk.Frame(pf,bg="#16213e"); br.pack(fill="x",pady=(4,0))
    for txt,cmd,col in [("📂 Add STEP Files",upload_files,"#4caf50"),
                         ("✕ Remove",remove_selected,"#607d8b"),
                         ("🗑 Clear",clear_files,"#455a64")]:
        tk.Button(br,text=txt,command=cmd,font=FN,bg=col,fg="white",
                  relief="flat",padx=8,pady=3,cursor="hand2").pack(side="left",padx=(0,4))

    promptf=tk.LabelFrame(left,text="  Assembly Instructions  ",font=FB,fg="white",
                           bg="#16213e",bd=1,relief="groove",padx=6,pady=6)
    promptf.pack(fill="x",pady=(0,6))
    tk.Label(promptf,text="Describe the assembly in plain language:",
             font=("Arial",9),fg="#9e9e9e",bg="#16213e").pack(anchor="w")
    prompt_var=tk.StringVar()
    prompt_entry=tk.Entry(promptf,textvariable=prompt_var,font=("Consolas",11),
                           bg="#0d1117",fg="#c9d1d9",insertbackground="#e94560",
                           relief="flat",bd=6)
    prompt_entry.pack(fill="x",pady=(4,4))
    tk.Label(promptf,
             text='Examples: "insert screw 20mm into middle hole, insert fastener 10mm into edge hole"  |  "rotate part 90 degrees around x, insert into slot"',
             font=("Arial",8),fg="#555",bg="#16213e",wraplength=490,justify="left").pack(anchor="w")
    ai_status_var=tk.StringVar(value="")
    tk.Label(promptf,textvariable=ai_status_var,font=("Arial",8),fg="#ab47bc",bg="#16213e").pack(anchor="w",pady=(2,0))
    tk.Label(promptf,text="Quick suggestions:",font=("Arial",8),fg="#555",bg="#16213e").pack(anchor="w")
    suggest_frame=tk.Frame(promptf,bg="#16213e"); suggest_frame.pack(fill="x")
    _suggest_btns=[]

    def _use_suggestion(txt): prompt_var.set(txt); prompt_entry.focus()

    def _update_suggestions():
        for b in _suggest_btns: b.destroy()
        _suggest_btns.clear()
        try:
            from prompt_parser import suggest_prompt
            types=[]
            for f in step_files[:3]:
                n=os.path.splitext(os.path.basename(f))[0].lower()
                if any(w in n for w in ["shaft","pin","rod","bolt","screw","fastener"]): types.append("shaft")
                elif any(w in n for w in ["plate","panel","flat","base"]): types.append("plate")
                elif any(w in n for w in ["housing","block","body","bracket"]): types.append("housing")
                elif any(w in n for w in ["ring","bearing","sleeve"]): types.append("bearing")
                else: types.append("generic")
            suggs=suggest_prompt(types[0] if types else "generic",
                                  types[1] if len(types)>1 else "generic")
            for s in suggs[:5]:
                btn=tk.Button(suggest_frame,text=s,command=lambda t=s:_use_suggestion(t),
                              font=("Arial",8),bg="#0f3460",fg="#9e9e9e",relief="flat",
                              padx=6,pady=2,cursor="hand2")
                btn.pack(side="left",padx=(0,4),pady=2); _suggest_btns.append(btn)
        except Exception: pass

    pgf=tk.Frame(left,bg="#1a1a2e"); pgf.pack(fill="x",pady=(0,4))
    progress_var=tk.IntVar(value=0)
    style=ttk.Style(); style.theme_use("default")
    style.configure("G.Horizontal.TProgressbar",troughcolor="#16213e",
                    background="#4caf50",thickness=16)
    ttk.Progressbar(pgf,variable=progress_var,maximum=100,
                    style="G.Horizontal.TProgressbar").pack(side="left",fill="x",expand=True)
    status_var=tk.StringVar(value="Waiting…")
    tk.Label(pgf,textvariable=status_var,font=("Arial",9),fg="lightgreen",
             bg="#1a1a2e",width=22,anchor="w").pack(side="left",padx=6)

    mf=tk.LabelFrame(left,text="  Assembly Results  ",font=FB,fg="white",
                      bg="#16213e",bd=1,relief="groove",padx=6,pady=4)
    mf.pack(fill="both",expand=True,pady=(0,6))
    cols=("Pair","Strategy","Fit","Conf","Collision")
    result_tree=ttk.Treeview(mf,columns=cols,show="headings",height=5)
    for c,w in zip(cols,[190,90,130,55,65]):
        result_tree.heading(c,text=c); result_tree.column(c,width=w,anchor="w")
    result_tree.pack(fill="both",expand=True)
    style.configure("Treeview",background="#0d1117",foreground="#c9d1d9",
                    fieldbackground="#0d1117",rowheight=22)
    style.configure("Treeview.Heading",background="#0f3460",foreground="white")

    act=tk.Frame(left,bg="#1a1a2e"); act.pack(pady=6)
    assemble_btn=tk.Button(act,text="⚙  Run Assembly",font=("Arial",12,"bold"),
                            bg="#e94560",fg="white",relief="flat",padx=16,pady=7,cursor="hand2")
    assemble_btn.pack(side="left",padx=4)
    view_btn=tk.Button(act,text="🔭  3D Viewer",font=FB,bg="#673ab7",fg="white",
                        relief="flat",padx=10,pady=7,state="disabled",cursor="hand2")
    view_btn.pack(side="left",padx=4)
    report_btn=tk.Button(act,text="📄  Report",font=FN,bg="#1976d2",fg="white",
                          relief="flat",padx=10,pady=7,state="disabled",cursor="hand2")
    report_btn.pack(side="left",padx=4)

    lf2=tk.LabelFrame(right,text="  Assembly Log  ",font=FB,fg="white",bg="#16213e",
                       bd=1,relief="groove",padx=6,pady=6)
    lf2.pack(fill="both",expand=True)
    log_box=scrolledtext.ScrolledText(lf2,font=FM,bg="#0d1117",fg="#c9d1d9",
                                       bd=0,highlightthickness=0,state="disabled")
    log_box.pack(fill="both",expand=True)
    for tag,col in [("ok","#4caf50"),("err","#e94560"),("info","#64b5f6"),
                    ("warn","#ffb74d"),("sep","#333"),("dim","#666"),("ai","#ab47bc")]:
        log_box.tag_config(tag,foreground=col)

    def _log(msg,tag=""):
        log_box.configure(state="normal")
        log_box.insert(tk.END,msg+"\n",tag)
        log_box.see(tk.END)
        log_box.configure(state="disabled")

    def assemble():
        if len(step_files)<2:
            _log("⚠  Add at least 2 STEP files first.","warn"); return
        assemble_btn.config(state="disabled"); _set_btns(False)
        progress_var.set(0); result_tree.delete(*result_tree.get_children())
        _log("─"*52,"sep")
        raw=prompt_var.get().strip()

        def _run():
            global _last_result
            try:
                from assembler import AssemblyEngine
                from step_exporter import export_step
                from report_generator import generate_report

                def _cb(msg,pct): root.after(0,lambda m=msg,p=pct:_ui(m,p))
                engine=AssemblyEngine(progress_cb=_cb)
                engine.load_parts(step_files)

                # ── Parse prompt ──────────────────────────────────────────
                all_ops = []
                if raw:
                    root.after(0,lambda:ai_status_var.set("🤖 Parsing…"))
                    root.after(0,lambda:_log(f'Prompt: "{raw}"',"info"))
                    try:
                        from ai_assembly_engine import _rule_based_parse, build_parts_context
                        from geometry_analyzer import analyze_part
                        from part_model import PartModel
                        from step_loader import load_step

                        parts_ctx=[]
                        for fp in step_files:
                            p=PartModel(file_path=fp); p.shape=load_step(fp)
                            if p.is_loaded: analyze_part(p); parts_ctx.append(p)

                        parts_info=build_parts_context(parts_ctx)
                        all_ops=_rule_based_parse(raw, parts_info)

                        # Log each parsed op
                        for i,op in enumerate(all_ops):
                            msg=(f"  Op{i+1}: hole='{op.hole_description}' "
                                 f"depth={op.insertion_depth}mm "
                                 f"strategy={op.strategy} "
                                 f"rotate={op.pre_rotate_axis}/{op.pre_rotate_degrees}°")
                            root.after(0,lambda m=msg:_log(m,"ai"))

                    except Exception as e:
                        root.after(0,lambda:_log(f"  Parse error: {e}","err"))

                    root.after(0,lambda:ai_status_var.set(""))
                else:
                    root.after(0,lambda:_log("No prompt — auto-detect","dim"))

                # Pass list of ops (or empty list for auto)
                if all_ops:
                    engine.set_instruction(all_ops)  # pass the LIST

                result=engine.run(); _last_result=result
                if result.get("success"):
                    export_step(result["compound"],"assembled_model.step")
                    generate_report(parts=result["parts"],
                                    pair_results=result["pair_results"],
                                    output_file="assembly_report.txt")
                    root.after(0,_on_ok,result)
                else:
                    root.after(0,_on_fail,"Assembly failed")

            except Exception as e:
                root.after(0,lambda:ai_status_var.set(""))
                root.after(0,_on_fail,f"{e}\n{traceback.format_exc()}")

        _log(f"Assembling {len(step_files)} part(s)…","info")
        threading.Thread(target=_run,daemon=True).start()

    def _ui(msg,pct):
        progress_var.set(pct); status_var.set(msg[:28])
        tag=("err" if "ERROR" in msg or "[ERR" in msg
             else "warn" if "⚠" in msg
             else "ok" if "✓" in msg else "")
        _log(msg,tag)

    def _on_ok(result):
        assemble_btn.config(state="normal"); progress_var.set(100)
        status_var.set("Complete ✓"); _log("─"*52,"sep")
        _log("✓  Assembly complete!","ok")
        for res in result.get("pair_results",[]):
            conf=res.get("confidence",0)*100
            coll="⚠" if res.get("collision") else "✓"
            strat=res.get("strategy","?")
            fit=res.get("fit_class",res.get("fit_type",""))
            pair=f"{res['part_a']} ↔ {res['part_b']}"
            tag="warn" if res.get("collision") else "ok"
            _log(f"  {pair}  [{strat}]  {fit}  conf={conf:.0f}%  {coll}",tag)
            if res.get("description"): _log(f"    {res['description']}","dim")
            cl=res.get("diametral_clearance")
            if cl is not None:
                _log(f"    Clearance={cl:+.3f}mm  {res.get('note','')}","dim")
            result_tree.insert("","end",values=(pair,strat,fit,f"{conf:.0f}%",coll))
        _set_btns(True,len(result.get("assembled_shapes",[])))

    def _on_fail(msg):
        assemble_btn.config(state="normal"); status_var.set("Error ✗")
        _log("─"*52,"sep")
        for line in str(msg).split("\n"): _log(line,"err")

    def _set_btns(enabled,n=0):
        s="normal" if enabled else "disabled"
        view_btn.config(state=s); report_btn.config(state=s)
        if enabled: view_btn.config(text=f"🔭  3D Viewer ({n} parts)")

    assemble_btn.config(command=assemble)

    def open_viewer():
        global _last_result
        if not _last_result or not _last_result.get("success"):
            _log("Run assembly first.","warn"); return
        assembled=_last_result.get("assembled_shapes",[])
        if not assembled: _log("No shapes.","err"); return
        _log("Opening viewer…","info"); root.update()
        try:
            from OCC.Display.SimpleGui import init_display
            COLORS=["BLUE","RED","GREEN","ORANGE","MAGENTA",
                    "CYAN","YELLOW","WHITE","BROWN","PINK"]
            display,start_display,_,__=init_display()
            shown=0
            for i,item in enumerate(assembled):
                shape=item[0]; name=item[2] if len(item)>2 else f"Part{i+1}"
                if shape and not shape.IsNull():
                    display.DisplayShape(shape,color=COLORS[i%len(COLORS)],update=False)
                    _log(f"  → {name}  [{COLORS[i%len(COLORS)]}]","info"); shown+=1
            if shown==0: _log("All shapes null.","err"); return
            display.FitAll()
            _log(f"Viewer: {shown} parts. Close to return.","ok")
            start_display()
        except Exception as e: _log(f"Viewer error: {e}","err")

    def open_report():
        path=os.path.abspath("assembly_report.txt")
        if os.path.exists(path): os.startfile(path)
        else: _log("No report yet.","warn")

    view_btn.config(command=open_viewer)
    report_btn.config(command=open_report)
    tk.Label(root,
             text="AI-Assisted CAD Assembly  |  PythonOCC  |  Cylinder·Plane·Slot·Multi-hole",
             font=("Arial",8),fg="#333",bg="#1a1a2e").pack(side="bottom",pady=4)
    root.mainloop()

if __name__=="__main__":
    run_tkinter()