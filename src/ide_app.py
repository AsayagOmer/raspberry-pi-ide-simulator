import tkinter as tk
from tkinter import ttk
import pygame

from hardware_workspace import HardwareWorkspace
from code_editor import CodeEditor
from logger import log_event

class IDEApp(tk.Tk):
    """Main Application coordinating the Hardware Workspace and Code Editor."""
    
    def __init__(self):
        super().__init__()
        self.title("Professional Raspberry Pi IDE")
        self.geometry("1200x800")
        self.configure(bg="#2b2b2b")
        
        self.button_states = {'A': False, 'B': False, 'X': False, 'Y': False}
        pygame.mixer.init()

        self._setup_styles()
        self._setup_ui()
        
        log_event("IDE started with a clear board.")
        self.workspace.save_state()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TNotebook", background="#2b2b2b", borderwidth=0)
        style.configure("TNotebook.Tab", background="#3c3f41", foreground="white", padding=[10, 5], font=("Segoe UI", 10))
        style.map("TNotebook.Tab", background=[("selected", "#1e1e1e")])
        style.configure("TFrame", background="#2b2b2b")

    def _setup_ui(self):
        # Global Toolbar
        self.toolbar = tk.Frame(self, bg="#3c3f41", bd=1, relief=tk.RAISED)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)
        
        # Paned Window separates Hardware (left) and Code (right)
        self.paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=6, sashrelief=tk.RAISED, bg="#3c3f41")
        self.paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 1. Left Frame: Hardware Workspace
        self.left_frame = tk.Frame(self.paned, bg="#3c3f41", bd=2, relief=tk.SUNKEN)
        self.paned.add(self.left_frame, stretch="always")
        self.workspace = HardwareWorkspace(self.left_frame, self)

        # 2. Right Notebook: Code Editor & Component Library
        self.right_notebook = ttk.Notebook(self.paned)
        self.paned.add(self.right_notebook, stretch="always")
        
        self.editor = CodeEditor(self.right_notebook, self)

        # Attach global toolbar buttons to editor methods
        btn_open = tk.Button(self.toolbar, text="📂 Open File", bg="#555", fg="white", command=self.editor.open_file, relief=tk.FLAT)
        btn_open.pack(side=tk.LEFT, padx=5, pady=2)
        btn_save = tk.Button(self.toolbar, text="💾 Save", bg="#555", fg="white", command=self.editor.save_file, relief=tk.FLAT)
        btn_save.pack(side=tk.LEFT, padx=5, pady=2)

        # Component Library Tab
        self.comp_tab = ttk.Frame(self.right_notebook)
        self.right_notebook.add(self.comp_tab, text="🔌 Component Library")
        self._setup_components_tab()

    def _setup_components_tab(self):
        from components import COMPONENT_REGISTRY
        lbl = tk.Label(self.comp_tab, text="Click to add components to workspace:", font=("Segoe UI", 12), bg="#2b2b2b", fg="white")
        lbl.pack(pady=10)
        for name, data in COMPONENT_REGISTRY.items():
            btn = tk.Button(
                self.comp_tab, 
                text=f"Add {name}", 
                font=("Segoe UI", 11), 
                bg=data["color"], 
                fg="white", 
                command=lambda n=name: self.workspace.add_component(n)
            )
            btn.pack(fill=tk.X, padx=20, pady=5)

    def log_console(self, text):
        """Proxy to CodeEditor console for components that expect app.log_console"""
        if hasattr(self, 'editor'):
            self.editor.log_console(text)

    def save_hardware_state(self):
        """Proxy for components that call app.save_hardware_state()"""
        if hasattr(self, 'workspace'):
            self.workspace.save_state()
