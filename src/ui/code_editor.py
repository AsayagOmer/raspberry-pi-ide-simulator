import tkinter as tk
from tkinter import ttk, filedialog
import re
import pygame
from core.logger import log_event
from core.code_executor import CodeExecutor

class CodeEditor:
    """Manages the multi-tab code editor, syntax highlighting, file IO, and console."""

    def __init__(self, parent_notebook, app):
        self.app = app
        self.parent_notebook = parent_notebook
        self.code_tab = ttk.Frame(self.parent_notebook)
        self.parent_notebook.add(self.code_tab, text="💻 Code Editor")
        
        self.editors = {}
        self.current_file = None
        self.executor = CodeExecutor(self.app)

        self._setup_ui()

    def _setup_ui(self):
        toolbar = tk.Frame(self.code_tab, bg="#3c3f41")
        toolbar.pack(fill=tk.X)
        btn_run = tk.Button(toolbar, text="▶ Run Code", font=("Segoe UI", 10, "bold"), bg="#4CAF50", fg="white", command=self.run_code, padx=10)
        btn_run.pack(side=tk.RIGHT, padx=5, pady=5)
        btn_stop = tk.Button(toolbar, text="■ Stop", font=("Segoe UI", 10, "bold"), bg="#f44336", fg="white", command=self.stop_audio, padx=10)
        btn_stop.pack(side=tk.RIGHT, padx=5, pady=5)

        self.file_notebook = ttk.Notebook(self.code_tab)
        self.file_notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        
        default_code = '''# Professional Raspberry Pi IDE\nimport time\n\nhardware.clear_screen()\nhardware.display_text("Testing Hardware...", color="cyan")\n\nprint("1. Testing Audio Output...")\nif hardware.play_audio("C:/Windows/Media/tada.wav"):\n    print("Success: Speaker is attached and played sound!")\nelse:\n    print("Failed: Please attach the USB Speaker to the Pi!")\n\ntime.sleep(2)\n\nprint("\\n2. Testing Microphone Input...")\nif hardware.record_audio("test_mic.wav", duration=3):\n    print("Success: Audio recorded via Pirate Audio Mic!")\n    print("Playing it back...")\n    hardware.play_audio("test_mic.wav")\nelse:\n    print("Failed: Please snap the Pirate Audio onto the RPi GPIO Header!")\n'''
        self.add_file_tab("main.py", default_code)

        tk.Label(self.code_tab, text="Console Output", font=("Segoe UI", 10, "bold"), bg="#2b2b2b", fg="#aaa").pack(anchor=tk.W)
        self.console = tk.Text(self.code_tab, height=8, font=("Consolas", 10), bg="#0d0d0d", fg="#4CAF50", state=tk.DISABLED, bd=0)
        self.console.pack(fill=tk.X)
        self.app.console = self.console # Attach console to app for executor access

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
        editor.bind("<Control-Z>", safe_undo)
        editor.bind("<Control-y>", safe_redo)
        editor.bind("<Control-Y>", safe_redo)
        editor.bind("<Control-Shift-Z>", safe_redo)
        editor.bind("<Control-Shift-z>", safe_redo)
        def safe_copy(e):
            e.widget.event_generate("<<Copy>>")
            return "break"
            
        def safe_cut(e):
            e.widget.event_generate("<<Cut>>")
            return "break"
            
        def safe_paste(e):
            e.widget.event_generate("<<Paste>>")
            return "break"

        editor.bind("<Control-c>", safe_copy)
        editor.bind("<Control-x>", safe_cut)
        editor.bind("<Control-v>", safe_paste)
        editor.bind("<KeyRelease>", lambda e: self.highlight_syntax(editor))
        
        editor.tag_configure("keyword", foreground="#569cd6")
        editor.tag_configure("string", foreground="#ce9178")
        editor.tag_configure("comment", foreground="#6a9955")
        editor.tag_configure("builtin", foreground="#4ec9b0")
        self.highlight_syntax(editor)
        
        tab_id = self.file_notebook.tabs()[-1]
        self.editors[tab_id] = editor

    def highlight_syntax(self, editor):
        for tag in ["keyword", "string", "comment", "builtin"]: 
            editor.tag_remove(tag, "1.0", tk.END)
        for kw in ["import", "from", "for", "in", "if", "elif", "else", "while", "def", "class", "return", "True", "False"]:
            self._search_and_tag(editor, rf"\b{kw}\b", "keyword")
        for b in ["print", "range", "time"]: 
            self._search_and_tag(editor, rf"\b{b}\b", "builtin")
        self._search_and_tag(editor, r"#.*", "comment")
        self._search_and_tag(editor, r"'.*?'", "string")
        self._search_and_tag(editor, r'\".*?\"', "string")

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
            log_event(f"Opened file: {filepath}")

    def save_file(self):
        current_tab_id = self.file_notebook.select()
        if not current_tab_id: return
        editor = self.editors[current_tab_id]
        
        if not self.current_file:
            self.current_file = filedialog.asksaveasfilename(defaultextension=".py")
            if not self.current_file: return
            
        with open(self.current_file, "w") as f: 
            f.write(editor.get("1.0", tk.END))
        log_event(f"Saved file: {self.current_file}")

    def log_console(self, text):
        self.console.config(state=tk.NORMAL)
        self.console.insert(tk.END, text + "\n")
        self.console.see(tk.END)
        self.console.config(state=tk.DISABLED)

    def stop_audio(self):
        pygame.mixer.music.stop()
        self.log_console("Audio stopped.")
        log_event("Audio playback stopped manually.")

    def run_code(self):
        current_tab_id = self.file_notebook.select()
        if not current_tab_id: return
        code = self.editors[current_tab_id].get("1.0", tk.END)
        tab_name = self.file_notebook.tab(current_tab_id, 'text')
        self.executor.run(code, tab_name)
