import re
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from tkinter.colorchooser import askcolor
import json
import os

# ---------------------------------------------------------
#  KONFIG
# ---------------------------------------------------------
version = "260605A"
RECENT_PATH = "_internal\\recent_files.json"
MAX_RECENT = 5

# ---------------------------------------------------------
#  HÄMTA SENASTE ANVÄNDA ST-FILER
# ---------------------------------------------------------
def load_recent_files():
    if os.path.exists(RECENT_PATH):
        try:
            with open(RECENT_PATH, "r") as f:
                return json.load(f)
        except:
            return []
    return []

def save_recent_files(files):
    os.makedirs(os.path.dirname(RECENT_PATH), exist_ok=True)
    with open(RECENT_PATH, "w") as f:
        json.dump(files, f, indent=2)

def add_recent_file(path):
    files = load_recent_files()
    if path in files:
        files.remove(path)
    files.insert(0, path)
    files = files[:MAX_RECENT]
    save_recent_files(files)

# ---------------------------------------------------------
#  PARSER
# ---------------------------------------------------------
def parse_st_file(path):
    traces = {}
    current_trace = None
    in_measurements = False

    number_regex = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"

    with open(path, encoding="latin-1") as f:
        for raw in f:
            line = raw.strip()

            if line.startswith("@Parameter Trace:"):
                current_trace = int(line.split(":")[1])
                traces[current_trace] = {"params": {}, "idx": [], "val": []}
                in_measurements = False

            elif line.startswith("@Messwerte Trace:"):
                current_trace = int(line.split(":")[1])
                in_measurements = True

            elif line.startswith("P ") and ":" in line and not in_measurements:
                m = re.match(rf"P\s+(\d+):\s*({number_regex}|.+)", line)
                if m:
                    p_no = int(m.group(1))
                    val_raw = m.group(2).strip()
                    try:
                        val = float(val_raw.replace(",", "."))
                    except ValueError:
                        val = val_raw
                    traces[current_trace]["params"][p_no] = val

            elif in_measurements and line.startswith("M "):
                m = re.match(rf"M\s+(\d+):\s*({number_regex})", line)
                if m:
                    idx = int(m.group(1))
                    val = float(m.group(2))
                    traces[current_trace]["idx"].append(idx)
                    traces[current_trace]["val"].append(val)

    for tr in traces.values():
        if tr["idx"]:
            arr = np.array(sorted(zip(tr["idx"], tr["val"])))
            tr["idx"] = arr[:, 0].astype(int)
            tr["val"] = arr[:, 1].astype(float)
        else:
            tr["idx"] = np.array([], dtype=int)
            tr["val"] = np.array([], dtype=float)

    return traces

# ---------------------------------------------------------
#  GUI
# ---------------------------------------------------------
class TraceViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Servotrace Viewer (840D PL) -- Skapad av Filip Haverinen")
        self.geometry("1460x830")
        self.minsize(width=1460, height=830)
        self.state("zoomed")
        self.traces_a = {}
        self.traces_b = {}
        self.trace_vars = {}
        self.colors = {}
        self.iconbitmap("_internal\\Servotrace.ico")

        style = ttk.Style()
        style.configure("Big.TCheckbutton", font=("Segoe UI", 14))
        self.suppress_log = False
        self.create_widgets()
        self.create_menubar()

    # ---------------------------------------------------------
    #  MENYBAR
    # ---------------------------------------------------------
    def create_menubar(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Öppna Trace-fil 1", command=lambda: self.open_file("A"))
        file_menu.add_command(label="Öppna Trace-fil 2", command=lambda: self.open_file("B"))
        file_menu.add_separator()
        file_menu.add_command(label="Exportera graf", command=self.export_png)
        file_menu.add_separator()

        self.recent_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_cascade(label="Senaste filerna", menu=self.recent_menu)
        self.update_recent_menu()

        file_menu.add_separator()
        file_menu.add_command(label="Avsluta", command=self.quit)
        menubar.add_cascade(label="Fil", menu=file_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Stäng Trace-fil 1", command=lambda: self.close_file("A"))
        view_menu.add_command(label="Stäng Trace-fil 2", command=lambda: self.close_file("B"))
        view_menu.add_command(label="Stäng båda trace-filerna", command=self.close_all)
        menubar.add_cascade(label="Visa", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Om programmet", command=self.show_about)
        menubar.add_cascade(label="Hjälp", menu=help_menu)

        self.config(menu=menubar)

    # ---------------------------------------------------------
    #  ABOUT
    # ---------------------------------------------------------
    def show_about(self):
        messagebox.showinfo(
            "Om programmet",
            f"Servotrace Viewer (840D PL)\n"
            f"Skapad av Filip Haverinen\n\n"
            f"Vid förbättringar eller buggfixar kontakta Filip Haverinen.\n\n"
            f"Telefon: 0728624550\n"
            f"E-post: filip.haverinen@volvo.com"
        )

    # ---------------------------------------------------------
    #  EXPORT PNG
    # ---------------------------------------------------------
    def export_png(self):
        fig = plt.Figure(figsize=(12, 6), dpi=100)
        ax = fig.add_subplot(111)

        for (label, trace_no), var in self.trace_vars.items():
            if var.get():
                tr = self.traces_a.get(trace_no) if label == "A" else self.traces_b.get(trace_no)
                if tr:
                    self.plot_trace(ax, tr, trace_no, label, self.colors[(label, trace_no)])

        ax.grid(True)
        ax.legend()

        filepath = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG-bild", "*.png")],
            title="Spara graf som PNG"
        )

        if filepath:
            fig.savefig(filepath)
            messagebox.showinfo("Sparad", f"Grafen sparades som:\n{filepath}")
            self.log(f"Grafen sparades under: {filepath}")

    # ---------------------------------------------------------
    #  RECENT FILES
    # ---------------------------------------------------------
    def update_recent_menu(self):
        self.recent_menu.delete(0, "end")
        files = load_recent_files()

        if not files:
            self.recent_menu.add_command(label="(Inga senaste filer)", state="disabled")
            return

        for fpath in files:
            if os.path.exists(fpath):
                self.recent_menu.add_command(
                    label=fpath,
                    command=lambda p=fpath: self.open_recent_file(p)
                )

    def open_recent_file(self, filepath):
        if not os.path.exists(filepath):
            messagebox.showerror("Fel", "Filen finns inte längre.")
            return

        self.log(f"Läser fil (senaste): {filepath}")
        self.traces_a = parse_st_file(filepath)

        add_recent_file(filepath)
        self.update_recent_menu()
        self.update_checkboxes()
        self.update_plot()

    # ---------------------------------------------------------
    #  UI SETUP
    # ---------------------------------------------------------
    def create_widgets(self):
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True)

        self.left_panel = ttk.Frame(main_frame, width=300)
        self.left_panel.pack(side="left", fill="y")
        self.left_panel.pack_propagate(False)

        self.plot_frame = ttk.Frame(main_frame)
        self.plot_frame.pack(side="right", fill="both", expand=True)

        terminal_frame = ttk.Frame(self)
        terminal_frame.pack(fill="x", padx=10, pady=5)

        scrollbar = ttk.Scrollbar(terminal_frame)
        scrollbar.pack(side="right", fill="y")
        
        self.text_output = tk.Text(
            terminal_frame,
            height=10,
            bg="#111",
            fg="#0f0",
            font=("Consolas", 16),
            yscrollcommand=scrollbar.set
        )
        self.text_output.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.text_output.yview)
        self.text_output.bind("<MouseWheel>", self._on_mousewheel)
    
        self.clear_terminal = ttk.Button(text="Rensa terminalen", command=self.clear_log)
        self.clear_terminal.pack(side="left", padx=5, pady=5)
        self.label = ttk.Label(text=f"Aktuell Version: {version}")
        self.label.pack(side="right", padx=5, pady=5)

        self.update_checkboxes()
        self.update_plot()
        
    def _on_mousewheel(self, event):
            self.text_output.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def log(self, msg):
        self.text_output.insert("end", msg + "\n")
        self.text_output.see("end")

    def clear_log(self):
        self.text_output.delete("1.0", tk.END)
        self.log(f"Terminalen rensad")
        self.after(2000, lambda: self.text_output.delete("1.0", tk.END))

    # ---------------------------------------------------------
    #  Öppna fil
    # ---------------------------------------------------------
    def open_file(self, label):
        self.suppress_log = False
        filepath = filedialog.askopenfilename(
            title=f"Välj ST-fil {label}",
            filetypes=[("ST filer", "*.ST1 *.ST2"), ("Alla filer", "*.*")]
        )
        if not filepath:
            return

        self.log(f"Läser fil {label}: {filepath}")

        if label == "A":
            self.traces_a = parse_st_file(filepath)
        else:
            self.traces_b = parse_st_file(filepath)

        add_recent_file(filepath)
        self.update_recent_menu()
        self.update_checkboxes()
        self.update_plot()

    # ---------------------------------------------------------
    #  Stäng enskild trace
    # ---------------------------------------------------------
    def close_single_trace(self, label, trace_no):
        if label == "A" and trace_no in self.traces_a:
            del self.traces_a[trace_no]
            self.log(f"Stängde A: Trace {trace_no}")

        if label == "B" and trace_no in self.traces_b:
            del self.traces_b[trace_no]
            self.log(f"Stängde B: Trace {trace_no}")

        self.update_checkboxes()
        self.update_plot()
        self.after(2000, lambda: self.text_output.delete("1.0", tk.END))

    # ---------------------------------------------------------
    #  Stäng alla i en fil
    # ---------------------------------------------------------
    def close_file(self, label):
        if label == "A":
            self.traces_a = {}
            self.log("Stängde alla A-traces.")
        else:
            self.traces_b = {}
            self.log("Stängde alla B-traces.")

        self.update_checkboxes()
        self.update_plot()
        self.after(2000, lambda: self.text_output.delete("1.0", tk.END))

    # ---------------------------------------------------------
    #  Stäng ALLT
    # ---------------------------------------------------------
    def close_all(self):
        self.traces_a = {}
        self.traces_b = {}
        self.log("Stängde ALLA traces.")
        self.update_checkboxes()
        self.update_plot()
        self.after(2000, lambda: self.text_output.delete("1.0", tk.END))

    # ---------------------------------------------------------
    #  Checkbox-lista
    # ---------------------------------------------------------
    def update_checkboxes(self):
        for widget in self.left_panel.winfo_children():
            widget.destroy()

        title = ttk.Label(self.left_panel, text="AKTUELLA FILER", font=("Segoe UI", 16, "bold"))
        title.pack(anchor="n", padx=10, pady=(5, 10))

        self.trace_vars.clear()

        all_traces = []

        for tr in sorted(self.traces_a.keys()):
            all_traces.append(("A", tr, self.traces_a[tr]))

        for tr in sorted(self.traces_b.keys()):
            all_traces.append(("B", tr, self.traces_b[tr]))

        for i, (label, trace_no, tr) in enumerate(all_traces):

            # Defaultfärg i HEX
            if (label, trace_no) not in self.colors:
                palette_A = ["#0070ff", "#ff0000"]
                palette_B = ["#00cc00", "#9900ff"]

                if label == "A":
                    palette = palette_A
                else:
                    palette = palette_B
                
                self.colors[(label, trace_no)] = palette[i % 2]

            row = ttk.Frame(self.left_panel)
            row.pack(anchor="w", padx=10, pady=3, fill="x")

            var = tk.BooleanVar(value=True)

            cb = ttk.Checkbutton(
                row,
                text=f"{label}: Trace {trace_no}",
                variable=var,
                command=lambda L=label, T=trace_no: self.on_checkbox_toggle(L, T),
                style="Big.TCheckbutton"
            )
            cb.pack(side="left")

            # --- Färgknapp ---
            color_btn = tk.Button(
                row,
                width=2,
                bg=self.colors[(label, trace_no)],
                command=lambda L=label, T=trace_no: self.change_color(L, T)
            )
            color_btn.pack(side="right", padx=5)

            # --- X-knapp ---
            btn = ttk.Button(
                row,
                text="X",
                width=3,
                command=lambda L=label, T=trace_no: self.close_single_trace(L, T)
            )
            btn.pack(side="right", padx=5)

            self.trace_vars[(label, trace_no)] = var

    def on_checkbox_toggle(self, label, trace_no):
        self.suppress_log = True
        self.update_plot()

    # ---------------------------------------------------------
    #  Färgbyte
    # ---------------------------------------------------------
    def update_plot(self):
        for widget in self.plot_frame.winfo_children():
            widget.destroy()

        fig = plt.Figure(figsize=(12, 6), dpi=100)
        ax_left = fig.add_subplot(111)
        ax_right = ax_left.twinx()

        # Samla alla aktiva traces
        active = []  # (label, trace_no, tr, mean, rng)

        for label, traces in [("A", self.traces_a), ("B", self.traces_b)]:
            for trace_no, tr in traces.items():
                key = (label, trace_no)
                if key in self.trace_vars and self.trace_vars[key].get():
                    vals = np.array(tr["val"])
                    if len(vals) == 0:
                        continue
                    mean = np.mean(vals)
                    rng = max(abs(vals.min() - mean), abs(vals.max() - mean))
                    active.append((label, trace_no, tr, mean, rng))

        if not active:
            canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)
            return

        # Sortera efter range
        active.sort(key=lambda x: x[4], reverse=True)

        # Gruppindelning:
        # Största signalen definierar vänster-gruppen
        # Näst största definierar höger-gruppen
        left_group = []
        right_group = []

        if len(active) == 1:
            left_group = active
        else:
            # Första = vänster
            left_group.append(active[0])

            # Andra = höger
            right_group.append(active[1])

            # Övriga: välj grupp baserat på vilken mean de ligger närmast
            left_mean = active[0][3]
            right_mean = active[1][3]

            for item in active[2:]:
                _, _, _, mean, _ = item
                if abs(mean - left_mean) < abs(mean - right_mean):
                    left_group.append(item)
                else:
                    right_group.append(item)

        # Rita vänster grupp
        for label, trace_no, tr, mean, rng in left_group:
            self.plot_trace(ax_left, tr, trace_no, label, self.colors[(label, trace_no)])

        # Rita höger grupp
        for label, trace_no, tr, mean, rng in right_group:
            self.plot_trace(ax_right, tr, trace_no, label, self.colors[(label, trace_no)])

        # Grid
        ax_left.grid(True)

        # Legend
        handles_left, labels_left = ax_left.get_legend_handles_labels()
        handles_right, labels_right = ax_right.get_legend_handles_labels()
        ax_left.legend(handles_left + handles_right, labels_left + labels_right, loc="upper right")

        # Synka axlar
        if left_group and right_group:
            left_mean = left_group[0][3]
            left_range = left_group[0][4]

            right_mean = right_group[0][3]
            right_range = right_group[0][4]

            common_range = max(left_range, right_range)

            ax_left.set_ylim(left_mean - common_range, left_mean + common_range)
            ax_right.set_ylim(right_mean - common_range, right_mean + common_range)

        elif left_group:
            mean = left_group[0][3]
            rng = left_group[0][4]
            ax_left.set_ylim(mean - rng, mean + rng)

        elif right_group:
            mean = right_group[0][3]
            rng = right_group[0][4]
            ax_right.set_ylim(mean - rng, mean + rng)

        # Rendera
        canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        toolbar = NavigationToolbar2Tk(canvas, self.plot_frame)
        toolbar.update()
        toolbar.pack(side="bottom", fill="x")

    # ---------------------------------------------------------
    #  Rita en trace
    # ---------------------------------------------------------
    def change_color(self, label, trace_no):
        # Öppna färgväljaren
        color = askcolor(title="Välj färg")[1]
        if not color:
            return

        # Spara färgen
        self.colors[(label, trace_no)] = color

        self.suppress_log = True

        # Uppdatera checkbox-listan så färgknappen byter färg
        self.update_checkboxes()

        # Rita om grafen
        self.update_plot()

        self.suppress_log = False

    def plot_trace(self, ax, tr, trace_no, label, color):
        params = tr["params"]
        val = tr["val"]

        if len(val) == 0:
            return

        p_keys = [k for k in params.keys() if isinstance(k, int)]
        block = (min(p_keys) // 100) * 100

        axis_id = params.get(block + 2, "N/A")
        ymax    = params.get(block + 8, None)
        ymin    = params.get(block + 9, None)
        unit    = params.get(block + 10, "")

        total_ms = params.get(block + 13, len(val))
        Ts_ms = total_ms / len(val)
        Ts_s = Ts_ms / 1000.0
        t = np.arange(len(val)) * Ts_s

        ax.plot(
            t, val,
            label=f"{label}: Trace {trace_no} – {axis_id} [{unit}]",
            color=color
        )

        if not self.suppress_log:
            self.log(
                f"{label}: Trace {trace_no} | Axel={axis_id} | Enhet={unit} | "
                f"Ymin={ymin} | Ymax={ymax} | Samples={len(val)} | Ts={Ts_ms:.6f} ms"
            )

if __name__ == "__main__":
    app = TraceViewer()
    app.mainloop()