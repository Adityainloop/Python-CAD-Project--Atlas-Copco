"""
gui_pro.py — Industry-level GUI
Features: Claude AI toggle, 3D preview, undo/redo, BOM tab,
          constraints panel, tolerance viewer, export panel,
          assembly sequence viewer
"""
import os, sys, threading, tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# ─── Try importing OCC display ─────────────────────────────────────────────
try:
    from OCC.Display.SimpleGui import init_display
    HAS_DISPLAY = True
except Exception:
    HAS_DISPLAY = False

try:
    from assembler_v2 import AssemblyEngineV2 as AssemblyEnginePro
except Exception:
    from assembler_pro import AssemblyEnginePro
from ai_assembly_engine  import _rule_based_parse, build_parts_context
from part_model          import PartModel
from geometry_analyzer   import analyze_part
from step_loader         import load_step

TITLE   = "AI CAD Assembly System — Industry Edition"
BG      = "#1e1e2e"
FG      = "#cdd6f4"
ACCENT  = "#89b4fa"
GREEN   = "#a6e3a1"
RED_C   = "#f38ba8"
YELLOW  = "#f9e2af"
SURFACE = "#313244"
BTN_BG  = "#45475a"

class IndustrialCADApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title(TITLE)
        root.configure(bg=BG)
        root.geometry("1280x800")
        root.minsize(1000, 650)

        self.engine      = AssemblyEnginePro()
        self.file_paths  = []
        self.parts_cache = []
        self.last_result = {}
        self.use_claude  = tk.BooleanVar(value=False)
        self.status_var  = tk.StringVar(value="Ready — load STEP files to begin")

        self._build_menu()
        self._build_toolbar()
        self._build_main()
        self._build_statusbar()

    # ─── Menu ──────────────────────────────────────────────────────────
    def _build_menu(self):
        mb = tk.Menu(self.root, bg=SURFACE, fg=FG,
                     activebackground=ACCENT, activeforeground=BG)
        self.root.config(menu=mb)

        fm = tk.Menu(mb, tearoff=0, bg=SURFACE, fg=FG)
        mb.add_cascade(label="File", menu=fm)
        fm.add_command(label="Load STEP Files...",
                       command=self._load_files, accelerator="Ctrl+O")
        fm.add_command(label="Export All Formats",
                       command=self._export_all)
        fm.add_separator()
        fm.add_command(label="Exit", command=self.root.quit)

        am = tk.Menu(mb, tearoff=0, bg=SURFACE, fg=FG)
        mb.add_cascade(label="Assembly", menu=am)
        am.add_command(label="Run Assembly",
                       command=self._run_assembly, accelerator="Ctrl+R")
        am.add_command(label="Undo",
                       command=self._undo, accelerator="Ctrl+Z")
        am.add_command(label="Clear All",
                       command=self._clear_all)

        hm = tk.Menu(mb, tearoff=0, bg=SURFACE, fg=FG)
        mb.add_cascade(label="Help", menu=hm)
        hm.add_command(label="Prompt Examples",
                       command=self._show_help)

        self.root.bind("<Control-o>", lambda e: self._load_files())
        self.root.bind("<Control-r>", lambda e: self._run_assembly())
        self.root.bind("<Control-z>", lambda e: self._undo())

    # ─── Toolbar ───────────────────────────────────────────────────────
    def _build_toolbar(self):
        tb = tk.Frame(self.root, bg=SURFACE, pady=4)
        tb.pack(fill="x", padx=4, pady=(4,0))

        def btn(text, cmd, color=BTN_BG, tip=""):
            b = tk.Button(tb, text=text, command=cmd,
                          bg=color, fg=FG, relief="flat",
                          padx=10, pady=4, font=("Segoe UI",9),
                          cursor="hand2", activebackground=ACCENT,
                          activeforeground=BG)
            b.pack(side="left", padx=3)
            return b

        btn("📂 Load Files",  self._load_files,   ACCENT)
        btn("▶  Run Assembly",self._run_assembly,  GREEN)
        btn("↩  Undo",        self._undo,           BTN_BG)
        btn("👁  3D Preview",  self._preview_3d,    BTN_BG)
        btn("📋 BOM",         self._show_bom_win,   BTN_BG)
        btn("📤 Export",      self._export_all,     BTN_BG)

        # Claude AI toggle
        tk.Label(tb, text="  Claude AI:", bg=SURFACE, fg=FG,
                 font=("Segoe UI",9)).pack(side="left", padx=(20,4))
        ck = tk.Checkbutton(tb, variable=self.use_claude,
                            bg=SURFACE, fg=GREEN,
                            activebackground=SURFACE,
                            selectcolor=SURFACE,
                            font=("Segoe UI",9),
                            text="Enable")
        ck.pack(side="left")

        tk.Label(tb, text="  API Key:", bg=SURFACE, fg=FG,
                 font=("Segoe UI",9)).pack(side="left", padx=(10,2))
        self.api_key_var = tk.StringVar(value=os.environ.get("ANTHROPIC_API_KEY",""))
        api_entry = tk.Entry(tb, textvariable=self.api_key_var,
                             bg=BTN_BG, fg=FG, font=("Segoe UI",8),
                             relief="flat", width=36, show="*")
        api_entry.pack(side="left", padx=2)
        tk.Button(tb, text="👁",
                  command=lambda e=api_entry: e.config(
                      show="" if e.cget("show")=="*" else "*"),
                  bg=BTN_BG, fg=FG, font=("Segoe UI",8),
                  relief="flat").pack(side="left")

        # Undo/Redo state
        self.undo_lbl = tk.Label(tb, text="", bg=SURFACE,
                                  fg=YELLOW, font=("Segoe UI",8))
        self.undo_lbl.pack(side="right", padx=10)

    # ─── Main area ─────────────────────────────────────────────────────
    def _build_main(self):
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=4, pady=4)

        # Left panel: files + prompt
        left = tk.Frame(main, bg=BG, width=340)
        left.pack(side="left", fill="y", padx=(0,4))
        left.pack_propagate(False)
        self._build_left(left)

        # Right panel: tabs
        right = tk.Frame(main, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        self._build_tabs(right)

    def _build_left(self, parent):
        # File list
        tk.Label(parent, text="STEP Files", bg=BG, fg=ACCENT,
                 font=("Segoe UI",10,"bold")).pack(anchor="w", pady=(4,2))

        lf = tk.Frame(parent, bg=SURFACE, relief="flat")
        lf.pack(fill="both", expand=False, ipady=2)

        self.file_list = tk.Listbox(lf, bg=SURFACE, fg=FG,
                                    selectbackground=ACCENT,
                                    font=("Consolas",9), height=8,
                                    relief="flat", bd=0)
        sb = tk.Scrollbar(lf, bg=SURFACE)
        self.file_list.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.file_list.config(yscrollcommand=sb.set)
        sb.config(command=self.file_list.yview)

        bf = tk.Frame(parent, bg=BG)
        bf.pack(fill="x", pady=2)
        for txt, cmd in [("+ Add", self._load_files),
                         ("✕ Remove", self._remove_file),
                         ("⬆", self._move_up), ("⬇", self._move_down)]:
            tk.Button(bf, text=txt, command=cmd, bg=BTN_BG, fg=FG,
                      font=("Segoe UI",8), relief="flat", padx=6,
                      cursor="hand2").pack(side="left", padx=2)

        # Prompt
        tk.Label(parent, text="Assembly Prompt", bg=BG, fg=ACCENT,
                 font=("Segoe UI",10,"bold")).pack(anchor="w", pady=(10,2))

        self.prompt_box = tk.Text(parent, bg=SURFACE, fg=FG,
                                   font=("Segoe UI",10), height=5,
                                   relief="flat", bd=4,
                                   insertbackground=FG,
                                   wrap="word")
        self.prompt_box.pack(fill="x", pady=2)
        self.prompt_box.insert("1.0",
            "insert fastener into middle hole, insert screw into edge hole")

        # Quick prompts
        tk.Label(parent, text="Quick Prompts", bg=BG, fg=YELLOW,
                 font=("Segoe UI",9,"bold")).pack(anchor="w", pady=(6,2))

        qf = tk.Frame(parent, bg=BG)
        qf.pack(fill="x")
        quick = [
            ("Middle + Edge",
             "insert fastener into middle hole, insert screw into edge hole"),
            ("By Diameter",
             "insert screw into small hole, insert fastener into large hole"),
            ("With Depth",
             "insert fastener 15mm into middle hole, insert screw 10mm into edge hole"),
            ("Knuckle Joint",
             "rotate knuckle joint part 90 degrees around z, insert into fork end"),
            ("Side Hole",
             "insert shaft into side hole"),
        ]
        for label, prompt in quick:
            tk.Button(qf, text=label,
                      command=lambda p=prompt: self._set_prompt(p),
                      bg=BTN_BG, fg=FG, font=("Segoe UI",8),
                      relief="flat", cursor="hand2", pady=2
                      ).pack(fill="x", pady=1)

        # Geometry info
        tk.Label(parent, text="Part Geometry", bg=BG, fg=ACCENT,
                 font=("Segoe UI",10,"bold")).pack(anchor="w", pady=(10,2))

        self.geo_box = scrolledtext.ScrolledText(
            parent, bg=SURFACE, fg=FG, font=("Consolas",8),
            height=8, relief="flat", bd=4, state="disabled")
        self.geo_box.pack(fill="both", expand=True, pady=2)

    def _build_tabs(self, parent):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook",       background=BG, borderwidth=0)
        style.configure("TNotebook.Tab",   background=SURFACE, foreground=FG,
                        padding=[10,4], font=("Segoe UI",9))
        style.map("TNotebook.Tab",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", BG)])

        self.nb = ttk.Notebook(parent)
        self.nb.pack(fill="both", expand=True)

        tabs = [
            ("📊 Results",    self._build_results_tab),
            ("🔩 Constraints",self._build_constraints_tab),
            ("📐 Tolerance",  self._build_tolerance_tab),
            ("📋 BOM",        self._build_bom_tab),
            ("📝 Sequence",   self._build_sequence_tab),
            ("📤 Export",     self._build_export_tab),
        ]
        self.tab_frames = {}
        for title, builder in tabs:
            frame = tk.Frame(self.nb, bg=BG)
            self.nb.add(frame, text=title)
            builder(frame)
            self.tab_frames[title] = frame

    def _build_results_tab(self, parent):
        tk.Label(parent, text="Assembly Results", bg=BG, fg=ACCENT,
                 font=("Segoe UI",10,"bold")).pack(anchor="w", padx=8, pady=4)

        self.results_box = scrolledtext.ScrolledText(
            parent, bg=SURFACE, fg=FG, font=("Consolas",9),
            relief="flat", bd=8, state="disabled")
        self.results_box.pack(fill="both", expand=True, padx=8, pady=4)

    def _build_constraints_tab(self, parent):
        tk.Label(parent, text="Assembly Constraints", bg=BG, fg=ACCENT,
                 font=("Segoe UI",10,"bold")).pack(anchor="w", padx=8, pady=4)

        # Constraint list
        self.constr_list = tk.Listbox(parent, bg=SURFACE, fg=FG,
                                       font=("Consolas",9), height=10,
                                       relief="flat", bd=8)
        self.constr_list.pack(fill="x", padx=8, pady=4)

        # Add manual constraint
        af = tk.LabelFrame(parent, text=" Add Constraint ",
                           bg=BG, fg=YELLOW,
                           font=("Segoe UI",9,"bold"))
        af.pack(fill="x", padx=8, pady=8)

        row1 = tk.Frame(af, bg=BG); row1.pack(fill="x", pady=2)
        tk.Label(row1, text="Type:", bg=BG, fg=FG,
                 font=("Segoe UI",9)).pack(side="left", padx=4)
        self.constr_type = ttk.Combobox(row1, width=14,
            values=["coincident","parallel","perpendicular",
                    "distance","angle","flush"])
        self.constr_type.set("coincident")
        self.constr_type.pack(side="left", padx=4)

        row2 = tk.Frame(af, bg=BG); row2.pack(fill="x", pady=2)
        tk.Label(row2, text="Description:", bg=BG, fg=FG,
                 font=("Segoe UI",9)).pack(side="left", padx=4)
        self.constr_desc = tk.Entry(row2, bg=SURFACE, fg=FG,
                                     font=("Segoe UI",9), relief="flat",
                                     width=30)
        self.constr_desc.pack(side="left", padx=4, fill="x", expand=True)

        tk.Button(af, text="Add Constraint",
                  command=self._add_constraint,
                  bg=ACCENT, fg=BG, font=("Segoe UI",9),
                  relief="flat", cursor="hand2"
                  ).pack(pady=4)

    def _build_tolerance_tab(self, parent):
        tk.Label(parent, text="Tolerance & Fit Analysis", bg=BG, fg=ACCENT,
                 font=("Segoe UI",10,"bold")).pack(anchor="w", padx=8, pady=4)

        self.tol_box = scrolledtext.ScrolledText(
            parent, bg=SURFACE, fg=FG, font=("Consolas",9),
            relief="flat", bd=8, state="disabled")
        self.tol_box.pack(fill="both", expand=True, padx=8, pady=4)

        # Manual tolerance calc
        mf = tk.LabelFrame(parent, text=" Manual Calculation ",
                           bg=BG, fg=YELLOW, font=("Segoe UI",9,"bold"))
        mf.pack(fill="x", padx=8, pady=4)
        row = tk.Frame(mf, bg=BG); row.pack(fill="x", pady=4)

        for lbl, var_name in [("Hole Ø:", "tol_hole"), ("Shaft Ø:", "tol_shaft")]:
            tk.Label(row, text=lbl, bg=BG, fg=FG,
                     font=("Segoe UI",9)).pack(side="left", padx=4)
            e = tk.Entry(row, bg=SURFACE, fg=FG, font=("Segoe UI",9),
                         relief="flat", width=8)
            e.pack(side="left", padx=4)
            setattr(self, var_name, e)

        tk.Button(row, text="Calculate",
                  command=self._calc_tolerance,
                  bg=ACCENT, fg=BG, font=("Segoe UI",9),
                  relief="flat", cursor="hand2"
                  ).pack(side="left", padx=8)

    def _build_bom_tab(self, parent):
        tk.Label(parent, text="Bill of Materials", bg=BG, fg=ACCENT,
                 font=("Segoe UI",10,"bold")).pack(anchor="w", padx=8, pady=4)

        bf = tk.Frame(parent, bg=BG); bf.pack(fill="x", padx=8, pady=2)
        for txt, cmd in [("📋 Refresh BOM", self._refresh_bom),
                         ("💾 Save TXT",    self._save_bom_txt),
                         ("💾 Save CSV",    self._save_bom_csv)]:
            tk.Button(bf, text=txt, command=cmd, bg=BTN_BG, fg=FG,
                      font=("Segoe UI",9), relief="flat",
                      cursor="hand2", padx=8).pack(side="left", padx=4)

        self.bom_box = scrolledtext.ScrolledText(
            parent, bg=SURFACE, fg=FG, font=("Consolas",9),
            relief="flat", bd=8, state="disabled")
        self.bom_box.pack(fill="both", expand=True, padx=8, pady=4)

    def _build_sequence_tab(self, parent):
        tk.Label(parent, text="Assembly Sequence", bg=BG, fg=ACCENT,
                 font=("Segoe UI",10,"bold")).pack(anchor="w", padx=8, pady=4)

        # Undo/Redo buttons
        uf = tk.Frame(parent, bg=BG); uf.pack(fill="x", padx=8, pady=2)
        self.undo_btn = tk.Button(uf, text="↩ Undo",
                                   command=self._undo, bg=BTN_BG, fg=FG,
                                   font=("Segoe UI",9), relief="flat",
                                   cursor="hand2", padx=8)
        self.undo_btn.pack(side="left", padx=4)
        self.redo_btn = tk.Button(uf, text="↪ Redo",
                                   command=self._redo, bg=BTN_BG, fg=FG,
                                   font=("Segoe UI",9), relief="flat",
                                   cursor="hand2", padx=8)
        self.redo_btn.pack(side="left", padx=4)

        self.seq_box = scrolledtext.ScrolledText(
            parent, bg=SURFACE, fg=FG, font=("Consolas",9),
            relief="flat", bd=8, state="disabled")
        self.seq_box.pack(fill="both", expand=True, padx=8, pady=4)

    def _build_export_tab(self, parent):
        tk.Label(parent, text="Export Formats", bg=BG, fg=ACCENT,
                 font=("Segoe UI",10,"bold")).pack(anchor="w", padx=8, pady=4)

        ef = tk.LabelFrame(parent, text=" Export Options ",
                           bg=BG, fg=YELLOW, font=("Segoe UI",9,"bold"))
        ef.pack(fill="x", padx=8, pady=4)

        exports = [
            ("STEP AP214 (Standard/CATIA)", self._export_step_catia),
            ("STEP AP203 (SolidWorks)",     self._export_step_sw),
            ("STEP AP242 (Latest)",         self._export_step_ap242),
            ("IGES (Universal)",            self._export_iges),
            ("STL (3D Print)",              self._export_stl),
            ("FreeCAD Script (.py)",        self._export_freecad),
            ("Export ALL formats",          self._export_all),
        ]
        for label, cmd in exports:
            tk.Button(ef, text=f"📤 {label}", command=cmd,
                      bg=BTN_BG, fg=FG, font=("Segoe UI",9),
                      relief="flat", cursor="hand2", anchor="w",
                      pady=3).pack(fill="x", padx=8, pady=2)

        self.export_log = scrolledtext.ScrolledText(
            parent, bg=SURFACE, fg=FG, font=("Consolas",9),
            height=8, relief="flat", bd=8, state="disabled")
        self.export_log.pack(fill="both", expand=True, padx=8, pady=4)

    def _build_statusbar(self):
        sb = tk.Frame(self.root, bg=SURFACE, height=24)
        sb.pack(fill="x", side="bottom")
        tk.Label(sb, textvariable=self.status_var, bg=SURFACE, fg=FG,
                 font=("Segoe UI",9), anchor="w"
                 ).pack(side="left", padx=8)

    # ─── Actions ───────────────────────────────────────────────────────
    def _set_prompt(self, p):
        self.prompt_box.delete("1.0","end")
        self.prompt_box.insert("1.0", p)

    def _load_files(self, *_):
        paths = filedialog.askopenfilenames(
            title="Load STEP Files",
            filetypes=[("STEP files","*.step *.stp *.STEP *.STP"),
                       ("All files","*.*")])
        if not paths: return
        for p in paths:
            if p not in self.file_paths:
                self.file_paths.append(p)
                self.file_list.insert("end",
                    f"  {os.path.basename(p)}")
        self._analyze_parts()

    def _remove_file(self):
        sel = self.file_list.curselection()
        if not sel: return
        idx = sel[0]
        self.file_list.delete(idx)
        self.file_paths.pop(idx)
        self._analyze_parts()

    def _move_up(self):
        sel = self.file_list.curselection()
        if not sel or sel[0] == 0: return
        i = sel[0]
        txt = self.file_list.get(i)
        self.file_list.delete(i)
        self.file_list.insert(i-1, txt)
        self.file_paths[i-1], self.file_paths[i] = \
            self.file_paths[i], self.file_paths[i-1]
        self.file_list.selection_set(i-1)

    def _move_down(self):
        sel = self.file_list.curselection()
        if not sel or sel[0] >= self.file_list.size()-1: return
        i = sel[0]
        txt = self.file_list.get(i)
        self.file_list.delete(i)
        self.file_list.insert(i+1, txt)
        self.file_paths[i], self.file_paths[i+1] = \
            self.file_paths[i+1], self.file_paths[i]
        self.file_list.selection_set(i+1)

    def _analyze_parts(self):
        self.parts_cache = []
        lines = []
        for fp in self.file_paths:
            p = PartModel(file_path=fp)
            p.shape = load_step(fp)
            if p.is_loaded:
                analyze_part(p)
                self.parts_cache.append(p)
                lines.append(f"=== {p.name} ===")
                lines.append(f"  bbox: {p.bbox_dims[0]:.0f}×"
                             f"{p.bbox_dims[1]:.0f}×{p.bbox_dims[2]:.0f}mm")
                for c in p.cylinders:
                    kind = "HOLE" if c.is_hole else "SHAFT"
                    lines.append(f"  {kind} d={c.diameter:.1f}mm "
                                f"axis={tuple(round(x,1) for x in c.axis_dir)}")
                lines.append("")
        txt = "\n".join(lines)
        self.geo_box.config(state="normal")
        self.geo_box.delete("1.0","end")
        self.geo_box.insert("1.0", txt)
        self.geo_box.config(state="disabled")
        self.status_var.set(
            f"{len(self.parts_cache)} parts loaded — ready to assemble")

    def _run_assembly(self, *_):
        if len(self.file_paths) < 2:
            messagebox.showwarning("Need Files",
                                   "Load at least 2 STEP files first.")
            return

        prompt = self.prompt_box.get("1.0","end").strip()
        if not prompt:
            messagebox.showwarning("No Prompt", "Enter an assembly prompt.")
            return

        self.status_var.set("⏳ Running assembly...")
        self.root.update()

        def worker():
            try:
                api_key = getattr(self, 'api_key_var', tk.StringVar()).get().strip()
                use_claude = self.use_claude.get() and bool(api_key)
                
                eng = AssemblyEnginePro(
                    progress_cb=self._on_progress,
                    use_claude=use_claude,
                    api_key=api_key)
                eng.load_parts(self.file_paths)

                # Parse prompt with rule-based as baseline
                parts_ctx = build_parts_context(eng.parts)
                ops = _rule_based_parse(prompt, parts_ctx)
                if not ops: ops = []
                eng.set_instruction(ops)

                # V2 engine: pass prompt directly for Claude planning
                if hasattr(eng, 'run') and 'user_prompt' in eng.run.__code__.co_varnames:
                    result = eng.run(user_prompt=prompt)
                else:
                    result = eng.run()
                self.engine = eng
                self.last_result = result
                self.root.after(0, lambda: self._on_assembly_done(result))
            except Exception as e:
                import traceback
                err = traceback.format_exc()
                self.root.after(0, lambda: self._on_error(err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_progress(self, msg, pct):
        self.root.after(0, lambda: self.status_var.set(
            f"[{pct}%] {msg}"))

    def _on_assembly_done(self, result):
        # Results tab
        lines = ["ASSEMBLY COMPLETE\n" + "="*50]
        for r in result.get("pair_results", []):
            t = r.get("translation", (0,0,0))
            lines.append(f"\n✓ {r.get('part_b','?')}")
            lines.append(f"   → Hole type: {r.get('fit_class', r.get('hole_desc',''))}")
            lines.append(f"   → Translation: ({t[0]:.1f}, {t[1]:.1f}, {t[2]:.1f})")
            # Tolerance data from assembler_pro if available
            fit_detail = r.get('fit_detail', {})
            if fit_detail:
                lines.append(f"   → ISO: {fit_detail.get('iso_suggestion','')}")
                lines.append(f"   → Force: {fit_detail.get('assembly_force','')}")
            coll = "⚠ COLLISION" if r.get("collision") else "✓ No collision"
            lines.append(f"   → {coll}")
        if result.get("claude_used"):
            lines.append(f"\n🤖 Claude AI: {result.get('claude_explanation','')}")
        elif self.use_claude.get():
            lines.append("\n⚠ Claude AI: API key required or unavailable — used rule-based")
        lines.append(f"\nTotal time: {result.get('total_ms',0):.0f}ms")
        self._set_text(self.results_box, "\n".join(lines))

        # BOM tab
        self._set_text(self.bom_box, result.get("bom",""))

        # Sequence tab
        self._set_text(self.seq_box, result.get("sequence",""))

        # Tolerance tab
        tol_lines = ["TOLERANCE ANALYSIS\n" + "="*50]
        for name, fit in result.get("tolerance",{}).items():
            tol_lines += [
                f"\n{name}:",
                f"  Clearance:      {fit['clearance']:+.3f} mm",
                f"  Fit Class:      {fit['fit_class']}",
                f"  Description:    {fit['fit_description']}",
                f"  ISO Suggestion: {fit['iso_suggestion']}",
                f"  Grade:          {fit['tolerance_grade']}",
                f"  Assembly force: {fit['assembly_force']}",
                f"  Application:    {fit['application']}",
            ]
        self._set_text(self.tol_box, "\n".join(tol_lines))

        # Constraints tab
        self.constr_list.delete(0,"end")
        for c in self.engine.get_constraints_summary():
            self.constr_list.insert("end", f"  {c}")

        # Export tab
        exp_lines = ["EXPORTED FILES:"]
        for k,v in result.get("exports",{}).items():
            exp_lines.append(f"  {k}: {v}")
        self._set_text(self.export_log, "\n".join(exp_lines))

        # Undo state
        self._update_undo_state()

        self.status_var.set(
            f"✓ Assembly complete — "
            f"{len(result.get('pair_results',[]))} parts assembled")

    def _on_error(self, err):
        self.status_var.set("✗ Assembly failed — see results tab")
        self._set_text(self.results_box, f"ERROR:\n{err}")

    def _set_text(self, widget, text):
        widget.config(state="normal")
        widget.delete("1.0","end")
        widget.insert("1.0", text)
        widget.config(state="disabled")

    def _preview_3d(self):
        if not self.engine.compound and not self.engine.pair_results:
            messagebox.showinfo("No Assembly",
                                "Run assembly first to preview in 3D.")
            return
        if not HAS_DISPLAY:
            messagebox.showerror("Display Error",
                                 "OCC display not available.")
            return
        def show():
            try:
                display, start_display, _, __ = init_display()
                colors = ["BLUE","RED","GREEN","ORANGE","CYAN","MAGENTA"]
                # Use compound if available (shows everything)
                if self.engine.compound and not self.engine.compound.IsNull():
                    display.DisplayShape(self.engine.compound, update=False)
                else:
                    # Fallback: show parts individually
                    loaded = [p for p in self.engine.parts if p.is_loaded]
                    if loaded:
                        display.DisplayShape(loaded[0].shape,
                                            color="WHITE", update=False)
                    for i, r in enumerate(self.engine.pair_results):
                        sh = r.get("shape") or r.get("moved_shape")
                        if sh and not sh.IsNull():
                            display.DisplayShape(sh,
                                                color=colors[i % len(colors)],
                                                update=False)
                display.FitAll()
                start_display()
            except Exception as ex:
                err_msg = str(ex)
                self.root.after(0, lambda: messagebox.showerror(
                    "Viewer Error", err_msg))
        threading.Thread(target=show, daemon=True).start()

    def _undo(self, *_):
        step = self.engine.undo()
        if step:
            self.status_var.set(f"↩ Undone: {step.description}")
            self._update_undo_state()
        else:
            self.status_var.set("Nothing to undo")

    def _redo(self, *_):
        step = self.engine.sequence.redo() if self.engine.sequence else None
        if step:
            self.status_var.set(f"↪ Redone: {step.description}")
            self._update_undo_state()

    def _update_undo_state(self):
        state = self.engine.get_undo_redo_state()
        steps = state["total_steps"]
        cur   = state["current_step"]
        self.undo_lbl.config(
            text=f"Step {cur}/{steps}  "
                 f"{'[Undo available]' if state['can_undo'] else ''}")

    def _add_constraint(self):
        from constraints import Constraint
        c = Constraint(
            type=self.constr_type.get(),
            entity_a={"part": "part_a"},
            entity_b={"part": "part_b"},
            description=self.constr_desc.get()
        )
        self.engine.constraints.add_constraint(c)
        self.constr_list.insert("end",
            f"  {c.type}: {c.description}")
        self.constr_desc.delete(0,"end")

    def _calc_tolerance(self):
        try:
            hd = float(self.tol_hole.get())
            sd = float(self.tol_shaft.get())
            from tolerance_analysis import classify_fit
            fit = classify_fit(hd, sd)
            lines = [
                f"Hole:  {hd:.3f}mm",
                f"Shaft: {sd:.3f}mm",
                f"Clearance: {fit['clearance']:+.3f}mm",
                "",
                f"FIT CLASS: {fit['fit_class']}",
                f"{fit['fit_description']}",
                f"ISO: {fit['iso_suggestion']}",
                f"Grade: {fit['tolerance_grade']}",
                f"Force: {fit['assembly_force']}",
                f"Use: {fit['application']}",
            ]
            self._set_text(self.tol_box, "\n".join(lines))
        except ValueError:
            messagebox.showerror("Input Error",
                                 "Enter valid numbers for hole and shaft diameters.")

    def _refresh_bom(self):
        if self.engine.bom.items:
            self._set_text(self.bom_box, self.engine.bom.to_txt())
        elif self.parts_cache:
            self.engine.bom.add_from_parts(self.parts_cache)
            self._set_text(self.bom_box, self.engine.bom.to_txt())

    def _save_bom_txt(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text","*.txt")])
        if path:
            with open(path,"w") as f:
                f.write(self.engine.bom.to_txt())
            self.status_var.set(f"BOM saved: {path}")

    def _save_bom_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV","*.csv")])
        if path:
            with open(path,"w") as f:
                f.write(self.engine.bom.to_csv())
            self.status_var.set(f"BOM CSV saved: {path}")

    def _show_bom_win(self):
        self.nb.select(3)  # Jump to BOM tab
        self._refresh_bom()

    def _export_step_catia(self):
        self._do_export("STEP_AP214", ".step")

    def _export_step_sw(self):
        self._do_export("STEP_AP203", "_solidworks.step")

    def _export_step_ap242(self):
        self._do_export("STEP_AP242", "_ap242.step")

    def _export_iges(self):
        self._do_export("IGES", ".igs")

    def _export_stl(self):
        self._do_export("STL", ".stl")

    def _export_freecad(self):
        if not self.engine.compound:
            messagebox.showinfo("No Assembly","Run assembly first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".py",
            filetypes=[("Python script","*.py")])
        if path:
            from export_formats import export_freecad_script
            parts_info = [{"name":p.name,"filepath":p.file_path}
                          for p in self.engine.parts if p.is_loaded]
            transforms = [(r["translation"] if r else (0,0,0))
                          for r in self.engine.pair_results]
            export_freecad_script(parts_info, [(0,0,0)]+transforms, path)
            self.status_var.set(f"FreeCAD script saved: {path}")
            self._log_export(f"FreeCAD script: {path}")

    def _export_all(self):
        if not self.engine.compound:
            messagebox.showinfo("No Assembly","Run assembly first.")
            return
        d = filedialog.askdirectory(title="Choose output folder")
        if not d: return
        from export_formats import export_all_formats
        results = export_all_formats(self.engine.compound,
                                      "assembly", d)
        lines = ["EXPORT RESULTS:"]
        for fmt, info in results.items():
            ok = "✓" if info["ok"] else "✗"
            lines.append(f"  {ok} {fmt}: {info['path']}")
        self._log_export("\n".join(lines))
        self.status_var.set(f"Exported {len(results)} formats to {d}")

    def _do_export(self, fmt, ext):
        if not self.engine.compound:
            messagebox.showinfo("No Assembly","Run assembly first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=[(f"{fmt} files", f"*{ext}")])
        if not path: return
        from export_formats import (export_step_catia, export_step_solidworks,
                                     export_step_ap242, export_iges, export_stl)
        func_map = {
            "STEP_AP214": export_step_catia,
            "STEP_AP203": export_step_solidworks,
            "STEP_AP242": export_step_ap242,
            "IGES":       export_iges,
            "STL":        export_stl,
        }
        try:
            ok = func_map[fmt](self.engine.compound, path)
            msg = f"✓ Exported {fmt}: {path}" if ok else f"✗ Export failed: {path}"
            self.status_var.set(msg)
            self._log_export(msg)
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def _log_export(self, msg):
        self.export_log.config(state="normal")
        self.export_log.insert("end", msg + "\n")
        self.export_log.config(state="disabled")
        self.export_log.see("end")

    def _show_help(self):
        win = tk.Toplevel(self.root, bg=BG)
        win.title("Prompt Examples")
        win.geometry("600x500")
        st = scrolledtext.ScrolledText(win, bg=SURFACE, fg=FG,
                                        font=("Consolas",9))
        st.pack(fill="both", expand=True, padx=8, pady=8)
        help_text = """ASSEMBLY PROMPT GUIDE
==================================================

BASIC INSERTION:
  insert screw into middle hole
  insert fastener into edge hole
  insert shaft into small hole

MULTIPLE PARTS:
  insert screw into middle hole, insert fastener into edge hole
  insert fastener into middle hole, insert screw into edge hole

WITH DEPTH:
  insert screw 15mm into middle hole
  insert fastener 20mm deep into edge hole

BY DIAMETER:
  insert screw into 10mm hole
  insert pin into small hole
  insert shaft into large bore

CROSS-AXIS (Knuckle Joint):
  rotate knuckle joint part 90 degrees around z, insert into fork end
  insert knuckle joint part into side hole of fork end

SLOT/GROOVE:
  insert key into keyway slot
  insert plate into slot of housing

KEYWORDS SUPPORTED:
  Hole positions:  middle, center, top, edge, side, small, large, bore
  Depth:           Xmm, Xmm deep, X millimeters into
  Rotation:        rotate X degrees around z/y/x
  Parts:           use words from filename (e.g. "screw" for screw_m8.step)
=================================================="""
        st.insert("1.0", help_text)
        st.config(state="disabled")

    def _clear_all(self):
        self.file_paths = []
        self.parts_cache = []
        self.file_list.delete(0,"end")
        self.engine = AssemblyEnginePro()
        for box in [self.results_box, self.bom_box,
                    self.seq_box, self.tol_box, self.export_log]:
            self._set_text(box, "")
        self.constr_list.delete(0,"end")
        self.status_var.set("Cleared — load new STEP files")


def main():
    root = tk.Tk()
    try:
        root.iconbitmap("")
    except Exception:
        pass
    app = IndustrialCADApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()