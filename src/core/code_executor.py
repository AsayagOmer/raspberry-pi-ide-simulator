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
        self.active_procs = []
        self.active_apis = []

    def stop(self):
        """Stop all running user scripts, emulators, and audio streams."""
        for api in list(self.active_apis):
            api.stop_requested = True
            try:
                api.display_text("Stopped", color="red")
            except Exception:
                pass
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass
        for proc in list(self.active_procs):
            try:
                if proc and proc.poll() is None:
                    proc.terminate()
            except Exception:
                pass
        self.active_procs.clear()
        self.active_apis.clear()

    def run(self, code: str, tab_name: str, rpi):
        # Stop any previously running loop before starting a new run
        self.stop()

        self.app.console.config(state="normal")
        self.app.console.delete("1.0", "end")
        self.app.console.config(state="disabled")
        
        self.app.log_console(f"--- Running {tab_name} on RPi ({id(rpi)}) ---")
        log_event(f"Started executing code: {tab_name} on RPi ({id(rpi)})")

        api = HardwareAPI(self.app, rpi)
        self.active_apis.append(api)
        
        def execute():
            # --- Auto-Install Isolated Dependencies ---
            raw_modules = []
            try:
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for n in node.names: raw_modules.append(n.name.split('.')[0])
                    elif isinstance(node, ast.ImportFrom):
                        if node.module: raw_modules.append(node.module.split('.')[0])
                raw_modules = list(set([m for m in raw_modules if m not in sys.stdlib_module_names and m != 'hardware']))
            except Exception:
                pass
                
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            deps_dir = os.path.join(project_root, f'.sim_env_{id(rpi)}')
            os.makedirs(deps_dir, exist_ok=True)

            pkg_map = {"edge_tts": "edge-tts"}
            missing_pkgs = [
                pkg_map.get(m, m)
                for m in raw_modules
                if not (
                    os.path.exists(os.path.join(deps_dir, m))
                    or os.path.exists(os.path.join(deps_dir, f"{m}.py"))
                )
            ]

            if missing_pkgs:
                self.app.after(0, lambda: self.app.log_console(f"Setting up isolated environment for: {', '.join(missing_pkgs)}..."))
                installed = False
                try:
                    subprocess.run(
                        [sys.executable, "-m", "uv", "pip", "install", "--target", deps_dir] + missing_pkgs,
                        check=True, capture_output=True, text=True
                    )
                    installed = True
                except Exception:
                    pass

                if not installed:
                    try:
                        subprocess.run(
                            [sys.executable, "-m", "pip", "install", "--target", deps_dir] + missing_pkgs,
                            check=True, capture_output=True, text=True
                        )
                        installed = True
                    except subprocess.CalledProcessError as e:
                        self.app.after(0, lambda err=e.stderr: self.app.log_console(f"Warning: Some packages couldn't be installed:\n{err}"))

                if installed:
                    self.app.after(0, lambda: self.app.log_console("Isolated environment ready!"))

            if api.stop_requested:
                return

            # Write hardware proxy
            proxy_code = """
import sys
def _send_cmd(cmd, *args):
    arg_str = "|".join(str(a) for a in args)
    print(f"HW_CMD:{cmd}:{arg_str}", flush=True)
    return sys.stdin.readline().strip() == "True"

def clear_screen(): _send_cmd("clear_screen")
def display_text(text, color="white"): _send_cmd("display_text", text, color)
def is_pressed(btn): return _send_cmd("is_pressed", btn)
def play_audio(filepath): return _send_cmd("play_audio", filepath)
def record_audio(filepath, duration=4, fs=16000): return _send_cmd("record_audio", filepath, duration, fs)
"""
            with open(os.path.join(deps_dir, "hardware.py"), "w") as f:
                f.write(proxy_code.strip())
            
            # Write main code
            with open(os.path.join(deps_dir, "main_script.py"), "w", encoding="utf-8") as f:
                f.write("import hardware\n" + code)

            # Start the true hardware emulator side-by-side
            emu_script = os.path.join(project_root, "run_emulator.py")
            emu_proc = None
            if os.path.exists(emu_script):
                emu_env = os.environ.copy()
                emu_env["PYTHONIOENCODING"] = "utf-8"
                emu_proc = subprocess.Popen([sys.executable, emu_script, "--test", "uart"], 
                                            cwd=project_root,
                                            env=emu_env,
                                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                            text=True, encoding="utf-8", errors="replace")
                self.active_procs.append(emu_proc)
                def read_emu():
                    for eline in emu_proc.stdout:
                        eline = eline.strip()
                        if eline: self.app.after(0, lambda l=eline: self.app.log_console(f"[ARM64 Emulator] {l}"))
                threading.Thread(target=read_emu, daemon=True).start()

            # Start the isolated Python process
            script_env = os.environ.copy()
            script_env["PYTHONIOENCODING"] = "utf-8"
            env_file = os.path.join(project_root, ".env")
            if os.path.exists(env_file):
                try:
                    with open(env_file, "r", encoding="utf-8") as ef:
                        for eline in ef:
                            eline = eline.strip()
                            if eline and not eline.startswith("#") and "=" in eline:
                                k, v = eline.split("=", 1)
                                script_env.setdefault(k.strip(), v.strip())
                except Exception:
                    pass
            proc = subprocess.Popen([sys.executable, "-u", "main_script.py"], cwd=deps_dir,
                                    env=script_env,
                                    stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                    text=True, encoding="utf-8", errors="replace", bufsize=1)
            self.active_procs.append(proc)
            
            try:
                for line in proc.stdout:
                    if api.stop_requested:
                        break
                    line = line.strip()
                    if not line: continue
                    if line.startswith("HW_CMD:"):
                        parts = line.split(":", 2)
                        cmd = parts[1]
                        args = parts[2].split("|") if len(parts) > 2 and parts[2] else []
                        
                        res = False
                        if cmd == "clear_screen": api.clear_screen(); res = True
                        elif cmd == "display_text": api.display_text(args[0], args[1] if len(args) > 1 else "white"); res = True
                        elif cmd == "is_pressed": res = api.is_pressed(args[0])
                        elif cmd == "play_audio":
                            fpath = args[0] if os.path.isabs(args[0]) else os.path.join(deps_dir, args[0])
                            res = api.play_audio(fpath)
                        elif cmd == "record_audio":
                            fpath = args[0] if os.path.isabs(args[0]) else os.path.join(deps_dir, args[0])
                            res = api.record_audio(fpath, float(args[1]), int(args[2]))
                        
                        if proc.poll() is None and proc.stdin:
                            proc.stdin.write(("True\n" if res else "False\n"))
                            proc.stdin.flush()
                    else:
                        out_text = line
                        if "\\u" in out_text:
                            try:
                                out_text = out_text.encode('utf-8').decode('unicode_escape')
                            except Exception:
                                pass
                        self.app.after(0, lambda l=out_text: self.app.log_console(l))
            except Exception as e:
                if not api.stop_requested:
                    self.app.after(0, lambda err=e: self.app.log_console(f"Error reading from script: {err}"))
            
            try:
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            # allow emulator to finish printing
            if emu_proc:
                try:
                    emu_proc.wait(timeout=2)
                except Exception:
                    try:
                        emu_proc.kill()
                    except Exception:
                        pass 
            
            self.app.after(0, lambda: self.app.log_console("--- Execution Finished ---"))
            self.app.after(0, lambda: log_event("Code execution finished."))

        threading.Thread(target=execute, daemon=True).start()
