import tkinter as tk
from tkinter import ttk, filedialog
import pygame
import threading
import re
import math

from components import COMPONENT_REGISTRY
from components.raspberry_pi import RaspberryPi
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
        
        self.hardware_history = []
        self.history_index = -1
        self.copied_component = None
        self.zoom_factor = 1.0

        pygame.mixer.init()

        self.setup_styles()
        self.setup_ui()
        self.log_event("IDE started with a clear board.")
        self.save_hardware_state()

    def log_event(self, text):
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("event.log", "a") as f:
            f.write(f"[{timestamp}] {text}\n")

    def save_hardware_state(self):
        state = []
        for c in self.components:
            name = next((n for n, d in COMPONENT_REGISTRY.items() if d["class"] == c.__class__), None)
            if name:
                comp_state = {
                    "name": name,
                    "x": c.x,
                    "y": c.y,
                    "rotation": getattr(c, 'rotation', 0),
                    "plug_x": getattr(c, 'plug_x', None),
                    "plug_y": getattr(c, 'plug_y', None)
                }
                state.append(comp_state)
        self.history_index += 1
        self.hardware_history = self.hardware_history[:self.history_index]
        self.hardware_history.append(state)

    def load_hardware_state(self, state):
        for c in list(self.components):
            c.connected_to = None # Prevent disconnect logs during load
            c.delete()
        self.components = []
        
        for comp_state in state:
            name = comp_state["name"]
            if name in COMPONENT_REGISTRY:
                c = COMPONENT_REGISTRY[name]["class"](self.canvas, comp_state["x"], comp_state["y"])
                c.rotation = comp_state["rotation"]
                c.redraw()
                if comp_state.get("plug_x") is not None and getattr(c, 'plug_x', None) is not None:
                    dx = comp_state["plug_x"] - c.plug_x
                    dy = comp_state["plug_y"] - c.plug_y
                    c.canvas.move(c.plug_tag, dx, dy)
                    c.plug_x = comp_state["plug_x"]
                    c.plug_y = comp_state["plug_y"]
                    if hasattr(c, 'update_cable'):
                        c.update_cable()
                self.components.append(c)
                
        # Silently re-establish connections based on distances
        threshold = 40 * self.zoom_factor
        for c in self.components:
            if getattr(c, 'socket_x', None) is not None:
                for comp in self.components:
                    if isinstance(comp, RaspberryPi) and math.hypot(c.socket_x - comp.gpio_x, c.socket_y - comp.gpio_y) < threshold:
                        c.connected_to = comp
                        break
            if getattr(c, 'plug_x', None) is not None:
                for comp in self.components:
                    if isinstance(comp, RaspberryPi) and math.hypot(c.plug_x - comp.usb2_x, c.plug_y - comp.usb2_y) < threshold:
                        c.connected_to = comp
                        break

    def hw_undo(self, event=None):
        if isinstance(self.focus_get(), tk.Text): return
        if self.history_index > 0:
            self.history_index -= 1
            self.load_hardware_state(self.hardware_history[self.history_index])
            self.log_event("Hardware undo performed.")
        return "break"

    def hw_redo(self, event=None):
        if isinstance(self.focus_get(), tk.Text): return
        if self.history_index < len(self.hardware_history) - 1:
            self.history_index += 1
            self.load_hardware_state(self.hardware_history[self.history_index])
            self.log_event("Hardware redo performed.")
        return "break"

    def hw_copy(self, event=None):
        if isinstance(self.focus_get(), tk.Text): return
        comp = getattr(self, 'hovered_component', None)
        if comp: self.copied_component = next((n for n, d in COMPONENT_REGISTRY.items() if d["class"] == comp.__class__), None)
        return "break"

    def hw_cut(self, event=None):
        if isinstance(self.focus_get(), tk.Text): return
        self.hw_copy()
        self.delete_hovered_component()
        return "break"

    def hw_paste(self, event=None):
        if isinstance(self.focus_get(), tk.Text): return
        if self.copied_component:
            # We don't have event mouse coordinates globally accessible in paste without an event object.
            # Using center canvas coordinates as default if event is missing.
            if event and hasattr(event, 'x_root'):
                x, y = event.x_root - self.canvas.winfo_rootx(), event.y_root - self.canvas.winfo_rooty()
            else:
                x, y = 150, 150
            if x < 0 or y < 0 or x > self.canvas.winfo_width() or y > self.canvas.winfo_height(): x, y = 50, 50
            c = COMPONENT_REGISTRY[self.copied_component]["class"](self.canvas, x, y)
            self.components.append(c)
            self.save_hardware_state()
        return "break"

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

        self.paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=6, sashrelief=tk.RAISED, bg="#3c3f41")
        self.paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left Canvas
        self.left_frame = tk.Frame(self.paned, bg="#3c3f41", bd=2, relief=tk.SUNKEN)
        self.paned.add(self.left_frame, stretch="always")
        tk.Label(self.left_frame, text="Hardware Workspace", font=("Segoe UI", 14, "bold"), bg="#3c3f41", fg="white").pack(pady=5)
        
        # Upper Hardware Toolbar (Undo/Redo & Zoom)
        self.hw_toolbar = tk.Frame(self.left_frame, bg="#3c3f41")
        self.hw_toolbar.pack(fill=tk.X, padx=5, pady=2)
        tk.Button(self.hw_toolbar, text="↩ Undo", bg="#555", fg="white", command=self.hw_undo, relief=tk.FLAT).pack(side=tk.LEFT, padx=5)
        tk.Button(self.hw_toolbar, text="↪ Redo", bg="#555", fg="white", command=self.hw_redo, relief=tk.FLAT).pack(side=tk.LEFT, padx=5)

        # Zoom Controls
        self.zoom_frame = tk.Frame(self.hw_toolbar, bg="#3c3f41")
        self.zoom_frame.pack(side=tk.RIGHT, padx=5)
        tk.Button(self.zoom_frame, text=" - ", bg="#555", fg="white", command=lambda: self.set_zoom(self.zoom_factor - 0.1), relief=tk.FLAT).pack(side=tk.LEFT, padx=2)
        self.zoom_label = tk.Label(self.zoom_frame, text="100%", bg="#3c3f41", fg="white", width=5)
        self.zoom_label.pack(side=tk.LEFT, padx=2)
        tk.Button(self.zoom_frame, text=" + ", bg="#555", fg="white", command=lambda: self.set_zoom(self.zoom_factor + 0.1), relief=tk.FLAT).pack(side=tk.LEFT, padx=2)
        tk.Button(self.zoom_frame, text=" ⛶ ", bg="#555", fg="white", command=lambda: self.set_zoom(1.0), relief=tk.FLAT).pack(side=tk.LEFT, padx=5)

        # Coordinate label at bottom
        self.coord_label = tk.Label(self.left_frame, text="X: 0, Y: 0", font=("Consolas", 10), bg="#3c3f41", fg="#aaa")
        self.coord_label.pack(side=tk.BOTTOM, anchor=tk.E, padx=5, pady=2)

        self.canvas = tk.Canvas(self.left_frame, bg="#f0f0f0", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.canvas.bind("<Configure>", self._draw_graph_paper)
        self.canvas.bind("<ButtonPress-1>", lambda e: self.canvas.focus_set())
        self.canvas.bind("<Motion>", self._update_coords)

        # Right Notebook
        self.right_notebook = ttk.Notebook(self.paned)
        self.paned.add(self.right_notebook, stretch="always")

        self.code_tab = ttk.Frame(self.right_notebook)
        self.right_notebook.add(self.code_tab, text="💻 Code Editor")
        self.setup_code_tab()

        self.comp_tab = ttk.Frame(self.right_notebook)
        self.right_notebook.add(self.comp_tab, text="🔌 Component Library")
        self.setup_components_tab()

        # Keyboard Bindings
        self.bind("<Delete>", self.delete_hovered_component)
        self.bind("<BackSpace>", self.delete_hovered_component)
        
        self.bind("<Control-c>", self.hw_copy)
        self.bind("<Control-C>", self.hw_copy)
        self.bind("<Control-v>", self.hw_paste)
        self.bind("<Control-V>", self.hw_paste)
        self.bind("<Control-x>", self.hw_cut)
        self.bind("<Control-X>", self.hw_cut)
        
        self.bind("<Control-z>", self.hw_undo)
        self.bind("<Control-Z>", self.hw_undo)
        
        # Redo bindings explicitly include Shift+Z and Y
        self.bind("<Control-y>", self.hw_redo)
        self.bind("<Control-Y>", self.hw_redo)
        self.bind("<Control-Shift-Z>", self.hw_redo)
        self.bind("<Control-Shift-z>", self.hw_redo)

    def set_zoom(self, new_zoom):
        old_zoom = self.zoom_factor
        self.zoom_factor = max(0.2, min(3.0, round(new_zoom, 2)))
        if self.zoom_factor == old_zoom: return
        
        ratio = self.zoom_factor / old_zoom
        cx = self.canvas.winfo_width() / 2
        cy = self.canvas.winfo_height() / 2
        
        self.zoom_label.config(text=f"{int(self.zoom_factor * 100)}%")
        
        for comp in self.components:
            comp.x = cx + (comp.x - cx) * ratio
            comp.y = cy + (comp.y - cy) * ratio
            if hasattr(comp, 'socket_x'):
                comp.socket_x = cx + (comp.socket_x - cx) * ratio
                comp.socket_y = cy + (comp.socket_y - cy) * ratio
            if hasattr(comp, 'plug_x'):
                comp.plug_x = cx + (comp.plug_x - cx) * ratio
                comp.plug_y = cy + (comp.plug_y - cy) * ratio
            if hasattr(comp, 'gpio_x'):
                comp.gpio_x = cx + (comp.gpio_x - cx) * ratio
                comp.gpio_y = cy + (comp.gpio_y - cy) * ratio
            if hasattr(comp, 'usb2_x'):
                comp.usb2_x = cx + (comp.usb2_x - cx) * ratio
                comp.usb2_y = cy + (comp.usb2_y - cy) * ratio
            if hasattr(comp, 'usb3_x'):
                comp.usb3_x = cx + (comp.usb3_x - cx) * ratio
                comp.usb3_y = cy + (comp.usb3_y - cy) * ratio
            comp.redraw()
            
        self._draw_graph_paper()

    def _update_coords(self, event):
        cx = self.canvas.winfo_width() // 2
        cy = self.canvas.winfo_height() // 2
        # Reverse zoom scaling to show real model coords
        rel_x = int((event.x - cx) / self.zoom_factor)
        rel_y = int((event.y - cy) / self.zoom_factor)
        self.coord_label.config(text=f"X: {rel_x}, Y: {rel_y}")

    def _draw_graph_paper(self, event=None):
        self.canvas.delete("grid_line")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        cx = w // 2
        cy = h // 2
        
        step_minor = max(5, int(20 * self.zoom_factor))
        step_major = max(25, int(100 * self.zoom_factor))
        
        for x in range(cx % step_minor, w, step_minor):
            self.canvas.create_line(x, 0, x, h, fill="#d6d6d6", width=1, tags="grid_line")
        for y in range(cy % step_minor, h, step_minor):
            self.canvas.create_line(0, y, w, y, fill="#d6d6d6", width=1, tags="grid_line")
            
        for x in range(cx % step_major, w, step_major):
            self.canvas.create_line(x, 0, x, h, fill="#c0c0c0", width=1, tags="grid_line")
        for y in range(cy % step_major, h, step_major):
            self.canvas.create_line(0, y, w, y, fill="#c0c0c0", width=1, tags="grid_line")
            
        self.canvas.create_line(cx, 0, cx, h, fill="#888888", width=2, tags="grid_line")
        self.canvas.create_line(0, cy, w, cy, fill="#888888", width=2, tags="grid_line")
        
        self.canvas.tag_lower("grid_line")

    def delete_hovered_component(self, event=None):
        if isinstance(self.focus_get(), tk.Text): return
        comp = getattr(self, 'hovered_component', None)
        if comp:
            self.log_event(f"Component erased from workspace: {comp.__class__.__name__}")
            comp.delete()
            self.save_hardware_state()

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
        
        cx = self.canvas.winfo_width() // 2
        cy = self.canvas.winfo_height() // 2
        
        if "Raspberry" in name:
            c = cls(self.canvas, cx - 200 + offset, cy - 100 + offset)
        elif "Pirate" in name:
            c = cls(self.canvas, cx - 200 + offset, cy - 250 + offset)
        else:
            c = cls(self.canvas, cx + 50 + offset, cy - 250 + offset)
            
        self.components.append(c)
        self.log_event(f"Component added to workspace: {name}")
        self.save_hardware_state()

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
        editor = tk.Text(frame, font=("Consolas", 12), bg="#1e1e1e", fg="#d4d4d4", insertbackground="white", undo=True, maxundo=50, autoseparators=True)
        editor.pack(fill=tk.BOTH, expand=True)
        editor.insert(tk.END, content)
        editor.edit_reset()
        editor.edit_modified(False)
        
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
