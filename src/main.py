import tkinter as tk
from tkinter import ttk, filedialog
import pygame
import threading
import re

from components import COMPONENT_REGISTRY
from hardware_api import HardwareAPI

class IDEApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Professional Raspberry Pi IDE")
        self.geometry("1200x800")
        self.configure(bg="#2b2b2b")
        
        self.components = []
        self.button_states = {'A': False, 'B': False, 'X': False, 'Y': False}
        self.current_file = None

        pygame.mixer.init()

        self.setup_styles()
        self.setup_ui()
        self.log_event("IDE started with a clear board.")

    def log_event(self, text):
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("event.log", "a") as f:
            f.write(f"[{timestamp}] {text}\n")

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TNotebook", background="#2b2b2b", borderwidth=0)
        style.configure("TNotebook.Tab", background="#3c3f41", foreground="white", padding=[10, 5], font=("Segoe UI", 10))
        style.map("TNotebook.Tab", background=[("selected", "#1e1e1e")])
        style.configure("TFrame", background="#2b2b2b")

    def setup_ui(self):
        self.toolbar = tk.Frame(self, bg="#3c3f41", bd=1, relief=tk.RAISED)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)
        btn_open = tk.Button(self.toolbar, text="📂 Open File", bg="#555", fg="white", command=self.open_file, relief=tk.FLAT)
        btn_open.pack(side=tk.LEFT, padx=5, pady=2)
        btn_save = tk.Button(self.toolbar, text="💾 Save", bg="#555", fg="white", command=self.save_file, relief=tk.FLAT)
        btn_save.pack(side=tk.LEFT, padx=5, pady=2)

        self.paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left Canvas
        self.left_frame = tk.Frame(self.paned, bg="#3c3f41", bd=2, relief=tk.SUNKEN)
        self.paned.add(self.left_frame, weight=1)
        tk.Label(self.left_frame, text="Hardware Workspace", font=("Segoe UI", 14, "bold"), bg="#3c3f41", fg="white").pack(pady=5)
        self.canvas = tk.Canvas(self.left_frame, bg="#2b2b2b", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Right Notebook
        self.right_notebook = ttk.Notebook(self.paned)
        self.paned.add(self.right_notebook, weight=1)

        self.code_tab = ttk.Frame(self.right_notebook)
        self.right_notebook.add(self.code_tab, text="💻 Code Editor")
        self.setup_code_tab()

        self.comp_tab = ttk.Frame(self.right_notebook)
        self.right_notebook.add(self.comp_tab, text="🔌 Component Library")
        self.setup_components_tab()

        self.bind("<Delete>", self.delete_hovered_component)
        self.bind("<BackSpace>", self.delete_hovered_component)

    def delete_hovered_component(self, event=None):
        # Don't delete components if the user is typing in the code editor!
        if isinstance(self.focus_get(), tk.Text):
            return
        comp = getattr(self, 'hovered_component', None)
        if comp:
            self.log_event(f"Component erased from workspace: {comp.__class__.__name__}")
            comp.delete()

    def setup_components_tab(self):
        lbl = tk.Label(self.comp_tab, text="Click to add components to workspace:", font=("Segoe UI", 12), bg="#2b2b2b", fg="white")
        lbl.pack(pady=10)
        
        for name, data in COMPONENT_REGISTRY.items():
            btn = tk.Button(
                self.comp_tab, 
                text=f"Add {name}", 
                font=("Segoe UI", 11), 
                bg=data["color"], 
                fg="white", 
                command=lambda n=name: self.add_component(n)
            )
            btn.pack(fill=tk.X, padx=20, pady=5)

    def add_component(self, name):
        if name not in COMPONENT_REGISTRY: return
        offset = len(self.components) * 20
        cls = COMPONENT_REGISTRY[name]["class"]
        
        # Default layout positions based on type
        if "Raspberry" in name:
            c = cls(self.canvas, 50 + offset, 150 + offset)
        elif "Pirate" in name:
            c = cls(self.canvas, 50 + offset, 20 + offset)
        else:
            c = cls(self.canvas, 250 + offset, 20 + offset)
            
        self.components.append(c)
        self.log_event(f"Component added to workspace: {name}")

    def setup_code_tab(self):
        toolbar = tk.Frame(self.code_tab, bg="#3c3f41")
        toolbar.pack(fill=tk.X)
        btn_run = tk.Button(toolbar, text="▶ Run Code", font=("Segoe UI", 10, "bold"), bg="#4CAF50", fg="white", command=self.run_code, padx=10)
        btn_run.pack(side=tk.RIGHT, padx=5, pady=5)
        btn_stop = tk.Button(toolbar, text="■ Stop", font=("Segoe UI", 10, "bold"), bg="#f44336", fg="white", command=self.stop_audio, padx=10)
        btn_stop.pack(side=tk.RIGHT, padx=5, pady=5)

        self.file_notebook = ttk.Notebook(self.code_tab)
        self.file_notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        self.editors = {}
        
        default_code = '''# Professional Raspberry Pi IDE
import time

hardware.clear_screen()
hardware.display_text("Testing Hardware...", color="cyan")

print("1. Testing Audio Output...")
if hardware.play_audio("C:/Windows/Media/tada.wav"):
    print("Success: Speaker is connected and played sound!")
else:
    print("Failed: Please connect the USB Speaker to the Pi!")

time.sleep(2)

print("\\n2. Testing Microphone Input...")
if hardware.record_audio("test_mic.wav", duration=3):
    print("Success: Audio recorded via Pirate Audio Mic!")
    print("Playing it back...")
    hardware.play_audio("test_mic.wav")
else:
    print("Failed: Please snap the Pirate Audio onto the RPi GPIO Header!")
'''
        self.add_file_tab("main.py", default_code)

        tk.Label(self.code_tab, text="Console Output", font=("Segoe UI", 10, "bold"), bg="#2b2b2b", fg="#aaa").pack(anchor=tk.W)
        self.console = tk.Text(self.code_tab, height=8, font=("Consolas", 10), bg="#0d0d0d", fg="#4CAF50", state=tk.DISABLED, bd=0)
        self.console.pack(fill=tk.X)

    def add_file_tab(self, filename, content=""):
        frame = tk.Frame(self.file_notebook, bg="#1e1e1e")
        self.file_notebook.add(frame, text=filename)
        editor = tk.Text(frame, font=("Consolas", 12), bg="#1e1e1e", fg="#d4d4d4", insertbackground="white", undo=True, maxundo=50)
        editor.pack(fill=tk.BOTH, expand=True)
        editor.insert(tk.END, content)
        
        # Explicitly handle shortcut keys robustly
        def safe_undo(event):
            try: event.widget.edit_undo()
            except tk.TclError: pass
            return "break"
        
        def safe_redo(event):
            try: event.widget.edit_redo()
            except tk.TclError: pass
            return "break"
            
        editor.bind("<Control-z>", safe_undo)
        editor.bind("<Control-y>", safe_redo)
        # Default tk bindings handle Ctrl+C/V/X out of the box natively, but binding just to guarantee behavior
        editor.bind("<Control-c>", lambda e: e.widget.event_generate("<<Copy>>"))
        editor.bind("<Control-x>", lambda e: e.widget.event_generate("<<Cut>>"))
        editor.bind("<Control-v>", lambda e: e.widget.event_generate("<<Paste>>"))
        
        editor.bind("<KeyRelease>", lambda e: self.highlight_syntax(editor))
        
        editor.tag_configure("keyword", foreground="#569cd6")
        editor.tag_configure("string", foreground="#ce9178")
        editor.tag_configure("comment", foreground="#6a9955")
        editor.tag_configure("builtin", foreground="#4ec9b0")
        self.highlight_syntax(editor)
        
        tab_id = self.file_notebook.tabs()[-1]
        self.editors[tab_id] = editor

    def highlight_syntax(self, editor):
        for tag in ["keyword", "string", "comment", "builtin"]: editor.tag_remove(tag, "1.0", tk.END)
        for kw in ["import", "from", "for", "in", "if", "elif", "else", "while", "def", "class", "return", "True", "False"]:
            self._search_and_tag(editor, rf"\\b{kw}\\b", "keyword")
        for b in ["print", "range", "time"]: self._search_and_tag(editor, rf"\\b{b}\\b", "builtin")
        self._search_and_tag(editor, r"\\#.*", "comment")
        self._search_and_tag(editor, r"\\'.*?\\'", "string")
        self._search_and_tag(editor, r"\\\".*?\\\"", "string")

    def _search_and_tag(self, editor, pattern, tag):
        for match in re.finditer(pattern, editor.get("1.0", tk.END)):
            editor.tag_add(tag, f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")

    def open_file(self):
        filepath = filedialog.askopenfilename(defaultextension=".py")
        if filepath:
            with open(filepath, "r") as f: content = f.read()
            current_tab_id = self.file_notebook.select()
            if current_tab_id:
                editor = self.editors[current_tab_id]
                editor.delete("1.0", tk.END)
                editor.insert(tk.END, content)
                self.highlight_syntax(editor)
            self.current_file = filepath
            self.log_event(f"Opened file: {filepath}")

    def save_file(self):
        current_tab_id = self.file_notebook.select()
        if not current_tab_id: return
        editor = self.editors[current_tab_id]
        if self.current_file:
            with open(self.current_file, "w") as f: f.write(editor.get("1.0", tk.END))
            self.log_event(f"Saved file: {self.current_file}")
        else:
            filepath = filedialog.asksaveasfilename(defaultextension=".py")
            if filepath:
                self.current_file = filepath
                with open(self.current_file, "w") as f: f.write(editor.get("1.0", tk.END))
                self.log_event(f"Saved file: {self.current_file}")

    def log_console(self, text):
        self.console.config(state=tk.NORMAL)
        self.console.insert(tk.END, text + "\n")
        self.console.see(tk.END)
        self.console.config(state=tk.DISABLED)

    def stop_audio(self):
        pygame.mixer.music.stop()
        self.log_console("Audio stopped.")
        self.log_event("Audio playback stopped manually.")

    def run_code(self):
        current_tab_id = self.file_notebook.select()
        if not current_tab_id: return
        code = self.editors[current_tab_id].get("1.0", tk.END)
        tab_name = self.file_notebook.tab(current_tab_id, 'text')
        
        self.console.config(state=tk.NORMAL)
        self.console.delete("1.0", tk.END)
        self.console.config(state=tk.DISABLED)
        self.log_console(f"--- Running {tab_name} ---")
        self.log_event(f"Started executing code: {tab_name}")

        api = HardwareAPI(self)
        
        def execute():
            import io, sys
            from contextlib import redirect_stdout
            redirected_output = io.StringIO()
            try:
                with redirect_stdout(redirected_output):
                    exec(code, {}, {'hardware': api, 'time': __import__('time')})
            except Exception as e:
                self.after(0, lambda err=e: self.log_console(f"Error: {err}"))
                self.after(0, lambda err=e: self.log_event(f"Code execution error: {err}"))
            finally:
                output = redirected_output.getvalue()
                if output: self.after(0, lambda out=output: self.log_console(out.strip()))
                self.after(0, lambda: self.log_console("--- Execution Finished ---"))
                self.after(0, lambda: self.log_event("Code execution finished."))
                
        threading.Thread(target=execute, daemon=True).start()

if __name__ == "__main__":
    app = IDEApp()
    app.mainloop()
