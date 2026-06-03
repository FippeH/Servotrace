import re
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import subprocess
import json
import os
import sys
import requests

# ---------------------------------------------------------
#  KONFIG
# ---------------------------------------------------------
path = "_internal\\version.json"
GITHUB_OWNER = "FippeH"
GITHUB_REPO = "Servotrace"
RECENT_PATH = "_internal\\recent_files.json"
MAX_RECENT = 5

# ---------------------------------------------------------
#  HJÄLPFUNKTION: KÖR VI SOM EXE?
# ---------------------------------------------------------
def running_as_exe():
    return getattr(sys, 'frozen', False)

# ---------------------------------------------------------
#  HÄMTA GIT-VERSION (PYTHON-LÄGE)
# ---------------------------------------------------------
def get_git_info():
    if running_as_exe():
        # EXE kan inte köra git → använd version.json
        return version, summary

    def run(cmd):
        return subprocess.check_output(cmd, encoding="utf-8").strip()

    try:
        version = run(["git", "describe", "--tags", "--always"])
        summary = run(["git", "log", "-1", "--pretty=%s"])
        return version, summary
    except Exception:
        return "unknown", "no summary"

# ---------------------------------------------------------
#  SPARA VERSION (PYTHON-LÄGE)
# ---------------------------------------------------------
def save_if_new():
    version, summary = get_git_info()

    os.makedirs(os.path.dirname(path), exist_ok=True)

    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump({"version": version, "summary": summary}, f)
        return True

    with open(path) as f:
        old = json.load(f)

    if old["summary"] != summary:
        with open(path, "w") as f:
            json.dump({"version": version, "summary": summary}, f)
        return True

    return False
 
# ---------------------------------------------------------
#  LÄS VERSION.JSON (PYTHON + EXE)
# ---------------------------------------------------------
def load_version_info():
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
            return data.get("version", "unknown"), data.get("summary", "no summary")
    return "unknown", "no summary"

version, summary = load_version_info()

# ---------------------------------------------------------
#  HÄMTA SENASTE VERSION FRÅN GITHUB
# ---------------------------------------------------------
def get_latest_github_version(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    response = requests.get(url, timeout=5)
    data = response.json()
    return data["name"], data["html_url"]

def check_for_update(local_version, owner, repo):
    try:
        latest, url = get_latest_github_version(owner, repo)
        return latest != local_version, latest, url
    except:
        return False, None, None

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

    # Ta bort om den redan finns
    if path in files:
        files.remove(path)

    # Lägg först i listan
    files.insert(0, path)

    # Begränsa antal
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

    # Sortera samples
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
        self.geometry("1500x900")
        self.traces_a = {}
        self.traces_b = {}
        self.trace_vars = {}
        self.colors = {}

        style = ttk.Style()
        style.configure("Big.TCheckbutton", font=("Segoe UI", 14))

        self.create_widgets()
        self.create_menubar()
  
    # ---------------------------------------------------------
    #  UI
    # ---------------------------------------------------------
    def create_menubar(self):
        menubar = tk.Menu(self)

        # --- Arkiv ---
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Öppna Trace-fil 1", command=lambda: self.open_file("A"))
        file_menu.add_command(label="Öppna Trace-fil 2", command=lambda: self.open_file("B"))
        file_menu.add_separator()
        file_menu.add_command(label="Exportera graf", command=self.export_png)
        file_menu.add_separator()
        self.config(menu=menubar)
        self.recent_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_cascade(label="Senaste filerna", menu=self.recent_menu)
        self.update_recent_menu()
        file_menu.add_separator()
        file_menu.add_command(label="Avsluta", command=self.quit)
        menubar.add_cascade(label="Fil", menu=file_menu)

        # --- Visa ---
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Stäng Trace-fil 1", command=lambda: self.close_file("A"))
        view_menu.add_command(label="Stäng Trace-fil 2", command=lambda: self.close_file("B"))
        view_menu.add_command(label="Stäng båda trace-filerna", command=self.close_all)
        menubar.add_cascade(label="Visa", menu=view_menu)

        # --- Hjälp ---
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Sök efter uppdatering", command=self.check_update_from_menu)
        help_menu.add_command(label="Om programmet", command=self.show_about)
        menubar.add_cascade(label="Hjälp", menu=help_menu)

    def show_about(self):
        messagebox.showinfo(
            "Om programmet",
            f"Servotrace Viewer (840D PL)\n"
            f"Skapad av Filip Haverinen\n\n"
            f"Lokal version: {version}\n"
            f"GitHub-version: {latest}\n"
        )

    def check_update_from_menu(self):
        update, latest_remote, url = check_for_update(version, GITHUB_OWNER, GITHUB_REPO)

        if update:
            if messagebox.askyesno(
                "Uppdatering finns!",
                f"Ny version finns på GitHub.\n\n"
                f"GitHub-version: {latest_remote}\n"
                f"Lokal version: {latest}\n\n"
                f"Vill du öppna nedladdningssidan?"
            ):
                import webbrowser
                webbrowser.open(url)
        else:
            messagebox.showinfo("Ingen uppdatering", "Du har redan den senaste versionen.")
    def export_png(self):
        # Skapa en ny figur med samma innehåll som den som visas
        fig = plt.Figure(figsize=(12, 6), dpi=100)
        ax = fig.add_subplot(111)

        # Rita om alla aktiva traces
        for (label, trace_no), var in self.trace_vars.items():
            if var.get():
                if label == "A":
                    tr = self.traces_a.get(trace_no)
                else:
                    tr = self.traces_b.get(trace_no)

                if tr:
                    self.plot_trace(ax, tr, trace_no, label, self.colors[(label, trace_no)])

        ax.grid(True)
        ax.legend()

        # Filväljare
        filepath = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG-bild", "*.png")],
            title="Spara graf som PNG"
        )

        if filepath:
            fig.savefig(filepath)
            messagebox.showinfo("Sparad", f"Grafen sparades som:\n{filepath}")
    
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
            else:
                # Ta bort filer som inte längre finns
                files.remove(fpath)
                save_recent_files(files)

    def open_recent_file(self, filepath):
        if not os.path.exists(filepath):
            messagebox.showerror("Fel", "Filen finns inte längre.")
            return

        label = "A" if filepath.endswith("A") else "B"  # eller välj automatiskt

        self.log(f"Läser fil (senaste): {filepath}")
        traces = parse_st_file(filepath)

        # Lägg in i A eller B beroende på vad du vill
        self.traces_a = traces

        add_recent_file(filepath)
        self.update_recent_menu()
        self.update_checkboxes()
        self.update_plot()

    def create_widgets(self):
        top = ttk.Frame(self)
        top.pack(fill="x", pady=5)

        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True)

        self.left_panel = ttk.Frame(main_frame, width=300)
        self.left_panel.pack(side="left", fill="y")

        self.plot_frame = ttk.Frame(main_frame)
        self.plot_frame.pack(side="right", fill="both", expand=True)

        self.text_output = tk.Text(self, height=10, bg="#111", fg="#0f0", font=("Consolas", 10))
        self.text_output.pack(fill="x", padx=10, pady=5)
        self.label = ttk.Label(text=f"Aktuell Version: {latest}")
        self.label.pack(side="right", padx=5, pady=5)

    def log(self, msg):
        self.text_output.insert("end", msg + "\n")
        self.text_output.see("end")

    # ---------------------------------------------------------
    #  Öppna fil
    # ---------------------------------------------------------
    def open_file(self, label):
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

        self.update_checkboxes()
        self.update_plot()
        add_recent_file(filepath)
        self.update_recent_menu()

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

    # ---------------------------------------------------------
    #  Stäng ALLT
    # ---------------------------------------------------------
    def close_all(self):
        self.traces_a = {}
        self.traces_b = {}
        self.log("Stängde ALLA traces.")
        self.update_checkboxes()
        self.update_plot()

    # ---------------------------------------------------------
    #  Checkbox-lista
    # ---------------------------------------------------------
    def update_checkboxes(self):
        for widget in self.left_panel.winfo_children():
            widget.destroy()

        self.trace_vars.clear()
        self.colors.clear()

        all_traces = []

        for tr in sorted(self.traces_a.keys()):
            all_traces.append(("A", tr, self.traces_a[tr]))

        for tr in sorted(self.traces_b.keys()):
            all_traces.append(("B", tr, self.traces_b[tr]))

        for i, (label, trace_no, tr) in enumerate(all_traces):
            row = ttk.Frame(self.left_panel)
            row.pack(anchor="w", padx=10, pady=3, fill="x")

            var = tk.BooleanVar(value=True)

            cb = ttk.Checkbutton(
                row,
                text=f"{label}: Trace {trace_no}",
                variable=var,
                command=self.update_plot,
                style="Big.TCheckbutton"
            )
            cb.pack(side="left")

            # X-knapp för att stänga en trace
            btn = ttk.Button(
                row,
                text="X",
                width=3,
                command=lambda L=label, T=trace_no: self.close_single_trace(L, T)
            )
            btn.pack(side="right", padx=5)

            self.trace_vars[(label, trace_no)] = var
            self.colors[(label, trace_no)] = plt.cm.tab20(i % 20)

    # ---------------------------------------------------------
    #  Rita graf
    # ---------------------------------------------------------
    def update_plot(self):
        for widget in self.plot_frame.winfo_children():
            widget.destroy()

        fig = plt.Figure(figsize=(12, 6), dpi=100)
        ax = fig.add_subplot(111)

        any_plotted = False

        # Rita A
        for trace_no, tr in self.traces_a.items():
            key = ("A", trace_no)
            if key in self.trace_vars and self.trace_vars[key].get():
                self.plot_trace(ax, tr, trace_no, "A", self.colors[key])
                any_plotted = True

        # Rita B
        for trace_no, tr in self.traces_b.items():
            key = ("B", trace_no)
            if key in self.trace_vars and self.trace_vars[key].get():
                self.plot_trace(ax, tr, trace_no, "B", self.colors[key])
                any_plotted = True

        if any_plotted:
            ax.grid(True)
            ax.legend()

        canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        toolbar = NavigationToolbar2Tk(canvas, self.plot_frame)
        toolbar.update()
        toolbar.pack(side="bottom", fill="x")

    # ---------------------------------------------------------
    #  Rita en trace
    # ---------------------------------------------------------
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

        self.log(
            f"{label}: Trace {trace_no} | Axel={axis_id} | Enhet={unit} | "
            f"Ymin={ymin} | Ymax={ymax} | Samples={len(val)} | Ts={Ts_ms:.6f} ms"
        )

if __name__ == "__main__":
    save_if_new()
    update, latest, url = check_for_update(version, GITHUB_OWNER, GITHUB_REPO)
    app = TraceViewer()
    if update:
        if messagebox.askyesno(
            title="Uppdatering finns!",
            message=f"Ny uppdatering finns på GitHub.\n\nNy version: {summary}\nAktuell version: {latest}\n\nVill du ladda ner den?"
        ):
            import webbrowser
            webbrowser.open(url)
    
    app.mainloop()