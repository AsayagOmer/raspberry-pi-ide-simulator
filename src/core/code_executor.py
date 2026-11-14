import sys
import ast
import codecs
import subprocess
import os
import threading
import importlib.util
from core.hardware_api import HardwareAPI
from core.logger import log_event

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SIM_ENV = os.path.join(PROJECT_ROOT, ".sim_env")
PKG_MAP = {"edge_tts": "edge-tts", "cv2": "opencv-python", "PIL": "pillow", "yaml": "pyyaml", "sklearn": "scikit-learn"}

# Replies to HW_CMD are tagged so the proxy can tell them apart from keyboard input meant for input().
HW_REPLY = "\x01HW:"

PROXY_CODE = r'''
import sys, threading
_real_stdin = sys.stdin
_pending = []
_lock = threading.Lock()

class _UserStdin:
    """Hands keyboard lines to input() while HW replies go to _send_cmd."""
    def readline(self, *a):
        with _lock:
            if _pending:
                return _pending.pop(0)
        while True:
            line = _real_stdin.readline()
            if not line.startswith("\x01HW:"):
                return line
    read = readline
    def __iter__(self):
        while True:
            line = self.readline()
            if not line:
                return
            yield line
    def __getattr__(self, name):
        return getattr(_real_stdin, name)

sys.stdin = _UserStdin()

def _send_cmd(cmd, *args):
    arg_str = "|".join(str(a) for a in args)
    print(f"HW_CMD:{cmd}:{arg_str}", flush=True)
    while True:
        line = _real_stdin.readline()
        if not line:
            return ""
        if line.startswith("\x01HW:"):
            return line[4:].rstrip("\n")
        with _lock:
            _pending.append(line)

def clear_screen(): _send_cmd("clear_screen")
def display_text(text, color="white"): _send_cmd("display_text", text, color)
def is_pressed(btn): return _send_cmd("is_pressed", btn) == "True"
def play_audio(filepath): return _send_cmd("play_audio", filepath) == "True"
def record_audio(filepath, duration=4, fs=16000): return _send_cmd("record_audio", filepath, duration, fs) == "True"
'''


def missing_packages(code: str, deps_dir: str = SIM_ENV):
    """Third-party top-level imports in `code` that are neither in deps_dir nor importable on the host."""
    mods = set()
    try:
        for node in ast.walk(ast.parse(code)):
            if isinstance(node, ast.Import):
                mods.update(n.name.split(".")[0] for n in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                mods.add(node.module.split(".")[0])
    except SyntaxError:
        return []
    out = []
    for m in sorted(mods - set(sys.stdlib_module_names) - {"hardware"}):
        if os.path.exists(os.path.join(deps_dir, m)) or os.path.exists(os.path.join(deps_dir, f"{m}.py")):
            continue
        if importlib.util.find_spec(m) is not None:
            continue
        out.append(PKG_MAP.get(m, m))
    return out


def install_packages(pkgs, deps_dir: str = SIM_ENV):
    """pip-install into the isolated env (uv first, pip fallback). Returns (ok, error_text)."""
    os.makedirs(deps_dir, exist_ok=True)
    err = ""
    for tool in (["-m", "uv", "pip", "install", "--target"], ["-m", "pip", "install", "--target"]):
        r = subprocess.run([sys.executable, *tool, deps_dir, *pkgs], capture_output=True, text=True)
        if r.returncode == 0:
            return True, ""
        err = r.stderr
    return False, err


class CodeExecutor:
    """Handles parsing, dependency installation, and isolated execution of user code."""

    def __init__(self, app):
        self.app = app
        self.active_procs = []
        self.active_apis = []
        self._stdin_lock = threading.Lock()

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

    def send_input(self, text: str):
        """Forward keyboard input to the running user script (for input())."""
        proc = self.active_procs[-1] if self.active_procs else None
        if proc and proc.poll() is None and proc.stdin:
            with self._stdin_lock:
                proc.stdin.write(text.encode("utf-8"))
                proc.stdin.flush()

    def run(self, code: str, tab_name: str, rpi, *, script_path=None, args=(), cwd=None,
            spawn_emulator=True, extra_files=None, extra_commands=None,
            on_output=None, on_start=None, on_exit=None, api=None):
        """Run user code in an isolated subprocess.

        script_path: run this file directly (shell mode) instead of `code` with `import hardware` prepended.
        extra_files: {filename: source} written into the isolated env (e.g. a picamera2 shim).
        extra_commands: {cmd: fn(args, cwd) -> reply} extra HW_CMD handlers.
        on_output(text): raw output stream; default is line-wise app.log_console.
        """
        # Stop any previously running loop before starting a new run
        self.stop()

        if hasattr(self.app, "console"):
            self.app.console.config(state="normal")
            self.app.console.delete("1.0", "end")
            self.app.console.config(state="disabled")
            self.app.log_console(f"--- Running {tab_name} on RPi ({id(rpi)}) ---")
        log_event(f"Started executing code: {tab_name} on RPi ({id(rpi)})")

        api = api or HardwareAPI(self.app, rpi)
        self.active_apis.append(api)
        deps_dir = SIM_ENV
        run_dir = cwd or deps_dir
        commands = extra_commands or {}

        if on_output is None:
            buf = [""]

            def on_output(text):
                buf[0] += text
                *lines, buf[0] = buf[0].split("\n")
                for line in lines:
                    line = line.strip()
                    if "\\u" in line:
                        try:
                            line = line.encode("utf-8").decode("unicode_escape")
                        except Exception:
                            pass
                    if line:
                        self.app.after(0, lambda l=line: self.app.log_console(l))

        def execute():
            os.makedirs(deps_dir, exist_ok=True)
            with open(os.path.join(deps_dir, "hardware.py"), "w", encoding="utf-8") as f:
                f.write(PROXY_CODE.strip())
            for name, src in (extra_files or {}).items():
                with open(os.path.join(deps_dir, name), "w", encoding="utf-8") as f:
                    f.write(src)

            # --- Auto-Install Isolated Dependencies ---
            missing_pkgs = missing_packages(code, deps_dir)
            if missing_pkgs:
                on_output(f"Setting up isolated environment for: {', '.join(missing_pkgs)}...\n")
                ok, err = install_packages(missing_pkgs, deps_dir)
                on_output("Isolated environment ready!\n" if ok else f"Warning: Some packages couldn't be installed:\n{err}\n")

            if api.stop_requested:
                return

            if script_path:
                target = os.path.abspath(script_path)
            else:
                target = os.path.join(deps_dir, "main_script.py")
                with open(target, "w", encoding="utf-8") as f:
                    f.write("import hardware\n" + code)

            # Start the Pi 4 bare-metal emulator demo side-by-side
            emu_script = os.path.join(PROJECT_ROOT, "run_emulator.py")
            emu_proc = None
            if spawn_emulator and os.path.exists(emu_script):
                emu_env = os.environ.copy()
                emu_env["PYTHONIOENCODING"] = "utf-8"
                emu_proc = subprocess.Popen([sys.executable, emu_script, "--test", "uart"],
                                            cwd=PROJECT_ROOT, env=emu_env,
                                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                            text=True, encoding="utf-8", errors="replace")
                self.active_procs.append(emu_proc)

                def read_emu():
                    for eline in emu_proc.stdout:
                        eline = eline.strip()
                        if eline:
                            on_output(f"[ARM64 Emulator] {eline}\n")
                threading.Thread(target=read_emu, daemon=True).start()

            # Start the isolated Python process
            script_env = os.environ.copy()
            script_env["PYTHONIOENCODING"] = "utf-8"
            script_env["PYTHONPATH"] = os.pathsep.join(p for p in (deps_dir, script_env.get("PYTHONPATH")) if p)
            env_file = os.path.join(PROJECT_ROOT, ".env")
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
            proc = subprocess.Popen([sys.executable, "-u", target, *args], cwd=run_dir, env=script_env,
                                    stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    bufsize=0)
            self.active_procs.append(proc)
            if on_start:
                on_start(proc)

            def resolve(p):
                return p if os.path.isabs(p) else os.path.join(run_dir, p)

            def dispatch(cmd, a):
                if cmd == "clear_screen": api.clear_screen(); return True
                if cmd == "display_text": api.display_text(a[0], a[1] if len(a) > 1 else "white"); return True
                if cmd == "is_pressed": return api.is_pressed(a[0])
                if cmd == "play_audio": return api.play_audio(resolve(a[0]))
                if cmd == "record_audio": return api.record_audio(resolve(a[0]), float(a[1]), int(a[2]))
                if cmd in commands: return commands[cmd](a, run_dir)
                return False

            def handle_hw(line):
                parts = line.split(":", 2)
                a = parts[2].split("|") if len(parts) > 2 and parts[2] else []
                try:
                    res = dispatch(parts[1], a)
                except Exception as e:
                    on_output(f"Hardware error ({parts[1]}): {e}\n")
                    res = False
                if proc.poll() is None and proc.stdin:
                    with self._stdin_lock:
                        proc.stdin.write(f"{HW_REPLY}{res}\n".encode("utf-8"))
                        proc.stdin.flush()

            # Stream output as it arrives (prompts without newline show up), but hold back
            # anything that could be the start of an HW_CMD line until it is complete.
            decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
            pending = ""
            try:
                while True:
                    chunk = proc.stdout.read(4096)  # unbuffered pipe: returns whatever is available
                    if not chunk or api.stop_requested:
                        break
                    pending += decoder.decode(chunk)
                    while "\n" in pending:
                        line, pending = pending.split("\n", 1)
                        if line.rstrip("\r").startswith("HW_CMD:"):
                            handle_hw(line.rstrip("\r"))
                        else:
                            on_output(line + "\n")
                    if pending and not ("HW_CMD:".startswith(pending) or pending.startswith("HW_CMD:")):
                        on_output(pending)
                        pending = ""
                if pending:
                    on_output(pending)
            except Exception as e:
                if not api.stop_requested:
                    on_output(f"Error reading from script: {e}\n")

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

            if hasattr(self.app, "console"):
                self.app.after(0, lambda: self.app.log_console("--- Execution Finished ---"))
            log_event("Code execution finished.")
            if on_exit:
                on_exit(proc.returncode)

        t = threading.Thread(target=execute, daemon=True)
        t.start()
        return t
