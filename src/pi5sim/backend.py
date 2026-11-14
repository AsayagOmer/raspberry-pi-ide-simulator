"""Headless Pi 5 backend: talks JSON lines to the VS Code extension over stdin/stdout.

In:  {"t":"stdin","data":str} {"t":"wiring","links":{peripheral: port|null}} {"t":"button","btn":"A","down":bool}
Out: {"t":"term","data":str} {"t":"state",...} {"t":"screen","text":str,"color":str}
"""
import json
import os
import sys
import threading

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from core.code_executor import CodeExecutor
from core.event_bus import EventBus
from core.hardware_api import HardwareAPI
from pi5sim import board, perf
from pi5sim.shell import Shell


# HardwareAPI finds peripherals by class name and `connected_to is rpi`.
class PirateAudio:
    screen_text = "pirate_audio_screen"

    def __init__(self, rpi):
        self.connected_to = rpi


class USBSpeaker:
    def __init__(self, rpi):
        self.connected_to = rpi


class HeadlessApp:
    """The slice of the Tkinter IDEApp that HardwareAPI and CodeExecutor read."""

    def __init__(self):
        self.components = []
        self.button_states = {"A": False, "B": False, "X": False, "Y": False}

    def after(self, ms, fn):
        fn()


class Backend:
    def __init__(self, home: str, out=None):
        self._out = out or sys.stdout
        self._lock = threading.Lock()
        self.app = HeadlessApp()
        self.rpi = object()  # identity token for HardwareAPI's connected_to checks
        self.executor = CodeExecutor(self.app)
        self.links = {p: None for p in board.PERIPHERALS}
        self.gpio = {}
        self.pacer = None
        self.script_pid = None
        self._ratio = None
        self.extra_files = {}
        self.extra_commands = {}
        self.shell = Shell(self, home)
        EventBus.subscribe("UPDATE_CANVAS_TEXT", lambda item, text, color: self.send(t="screen", text=text, color=color))
        EventBus.subscribe("LOG_CONSOLE", lambda text: self.write(text + "\r\n"))

    # ---------- protocol ----------
    def send(self, **msg):
        with self._lock:
            self._out.write(json.dumps(msg) + "\n")
            self._out.flush()

    def write(self, text: str):
        self.send(t="term", data=text)

    def send_state(self):
        self.send(t="state", links=self.links, gpio={str(k): v for k, v in self.gpio.items()},
                  running=self.script_pid is not None, model=board.MODEL)

    def handle(self, msg: dict):
        t = msg.get("t")
        if t == "stdin":
            self.shell.feed(msg["data"])
        elif t == "wiring":
            for p, port in msg["links"].items():
                if p in self.links and (port is None or port in board.PERIPHERALS[p][1]):
                    self.links[p] = port
            self.app.components = ([PirateAudio(self.rpi)] if self.links["pirate_audio"] else []) + \
                                  ([USBSpeaker(self.rpi)] if self.links["usb_speaker"] else [])
            self.send_state()
        elif t == "button":
            self.app.button_states[msg["btn"]] = bool(msg["down"])

    def serve(self, stream=None):
        self.write(f"{board.MODEL} simulator - {board.SPECS['SoC']}, 16 GB\r\n"
                   "Type 'help' for commands.\r\n\r\n")
        self.send_state()
        self.shell.prompt()
        for line in stream or sys.stdin:
            line = line.strip()
            if line:
                try:
                    self.handle(json.loads(line))
                except Exception as e:
                    self.write(f"\r\n[backend error] {e}\r\n")

    # ---------- scripts ----------
    def used_kb(self) -> int:
        base = 412_000  # Raspberry Pi OS idle footprint
        if self.script_pid:
            try:
                import psutil
                return base + psutil.Process(self.script_pid).memory_info().rss // 1024
            except Exception:
                pass
        return base

    def ratio(self) -> float:
        if self._ratio is None:
            self._ratio = perf.speed_ratio(perf.bench(0.5))
        return self._ratio

    def run_script(self, path, args, cwd, on_exit):
        ratio = self.ratio()

        def started(proc):
            self.script_pid = proc.pid
            self.pacer = perf.Pacer(proc.pid, ratio, on_warning=self.write)
            self.send_state()

        def done(rc):
            if self.pacer:
                self.pacer.stop()
            self.pacer = self.script_pid = None
            self.send_state()
            on_exit(rc)

        with open(path, encoding="utf-8", errors="replace") as f:
            code = f.read()
        self.executor.run(code, os.path.basename(path), self.rpi, script_path=path, args=args, cwd=cwd,
                          spawn_emulator=False, extra_files=self.extra_files, extra_commands=self.extra_commands,
                          on_output=lambda s: self.write(s.replace("\r\n", "\n").replace("\n", "\r\n")),
                          on_start=started, on_exit=done, api=HardwareAPI(self.app, self.rpi))

    def stop_script(self):
        if self.pacer:
            self.pacer.stop()  # resumes the process so terminate() can land
        self.executor.stop()
