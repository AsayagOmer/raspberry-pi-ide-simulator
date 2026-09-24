import io
import sys
import ast
import subprocess
import os
import threading
from contextlib import redirect_stdout
from core.hardware_api import HardwareAPI
from core.logger import log_event

class CodeExecutor:
    """Handles parsing, dependency installation, and thread-safe execution of user code."""
    
    def __init__(self, app):
        self.app = app

    def run(self, code: str, tab_name: str):
        self.app.console.config(state="normal")
        self.app.console.delete("1.0", "end")
        self.app.console.config(state="disabled")
        
        self.app.log_console(f"--- Running {tab_name} ---")
        log_event(f"Started executing code: {tab_name}")

        api = HardwareAPI(self.app)
        
        def execute():
            # --- Auto-Install Isolated Dependencies ---
            third_party = []
            try:
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for n in node.names:
                            third_party.append(n.name.split('.')[0])
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            third_party.append(node.module.split('.')[0])
                
                # Filter out stdlib and the injected 'hardware' object
                third_party = list(set([m for m in third_party if m not in sys.stdlib_module_names and m != 'hardware']))
            except Exception:
                pass
                
            if third_party:
                deps_dir = os.path.join(os.getcwd(), '.sim_env')
                os.makedirs(deps_dir, exist_ok=True)
                if deps_dir not in sys.path:
                    sys.path.insert(0, deps_dir)
                    
                self.app.after(0, lambda: self.app.log_console(f"Setting up isolated environment for: {', '.join(third_party)}..."))
                try:
                    subprocess.run(
                        ["uv", "pip", "install", "--target", deps_dir] + third_party,
                        check=True, capture_output=True, text=True
                    )
                    self.app.after(0, lambda: self.app.log_console("Isolated environment ready!"))
                except subprocess.CalledProcessError as e:
                    self.app.after(0, lambda err=e.stderr: self.app.log_console(f"Warning: Some packages couldn't be installed:\n{err}"))
            # ----------------------------------------
            
            redirected_output = io.StringIO()
            try:
                with redirect_stdout(redirected_output):
                    # Allow any imports by using the default builtins dictionary
                    safe_globals = {
                        "__builtins__": __builtins__,
                        "hardware": api,
                        "time": __import__("time"),
                    }
                    exec(code, safe_globals, {})
            except Exception as e:
                self.app.after(0, lambda err=e: self.app.log_console(f"Error: {err}"))
                self.app.after(0, lambda err=e: log_event(f"Code execution error: {err}"))
            finally:
                output = redirected_output.getvalue()
                if output: 
                    self.app.after(0, lambda out=output: self.app.log_console(out.strip()))
                self.app.after(0, lambda: self.app.log_console("--- Execution Finished ---"))
                self.app.after(0, lambda: log_event("Code execution finished."))
                
        threading.Thread(target=execute, daemon=True).start()
