"""A bash-like shell that behaves like Raspberry Pi OS on a Pi 5 (pi@raspberrypi)."""
import datetime
import os
import shlex
import shutil
import threading
import time

import psutil

from core.code_executor import install_packages
from pi5sim import board

GREEN, BLUE, RESET = "\x1b[1;32m", "\x1b[1;34m", "\x1b[0m"
BOOT_TIME = time.time()


class Shell:
    def __init__(self, backend, home: str):
        self.b = backend
        self.home = os.path.abspath(home)
        self.cwd = self.home
        self.line = ""
        self.history, self.hpos = [], 0
        self.running = False
        self.busy, self.cancel = False, threading.Event()
        self.commands = {
            "help": self.c_help, "ls": self.c_ls, "cd": self.c_cd, "pwd": self.c_pwd, "cat": self.c_cat,
            "echo": self.c_echo, "clear": self.c_clear, "mkdir": self.c_mkdir, "rm": self.c_rm,
            "touch": self.c_touch, "whoami": lambda a: self.out("pi\n"),
            "hostname": lambda a: self.out("raspberrypi\n"), "uname": self.c_uname, "date": self.c_date,
            "uptime": self.c_uptime, "free": self.c_free, "lscpu": self.c_lscpu, "nproc": lambda a: self.out(f"{board.CORES}\n"),
            "python": self.c_python, "python3": self.c_python, "pip": self.c_pip, "pip3": self.c_pip,
            "vcgencmd": self.c_vcgencmd, "pinout": self.c_pinout, "pinctrl": self.c_pinctrl,
            "sudo": self.c_sudo, "exit": lambda a: self.out("logout\n"),
        }

    # ---------- terminal I/O ----------
    def out(self, text: str):
        self.b.write(text.replace("\r\n", "\n").replace("\n", "\r\n"))

    def prompt(self):
        self.out(f"{GREEN}pi@raspberrypi{RESET}:{BLUE}{self.display(self.cwd)}{RESET} $ ")

    def display(self, path: str) -> str:
        rel = os.path.relpath(path, self.home)
        return "~" if rel == "." else ("~/" + rel.replace("\\", "/") if not rel.startswith("..") else path)

    def resolve(self, p: str) -> str:
        """Map Pi paths (~, /home/pi) onto the workspace folder."""
        if p in ("~", "/home/pi"):
            return self.home
        for pre in ("~/", "/home/pi/"):
            if p.startswith(pre):
                return os.path.abspath(os.path.join(self.home, p[len(pre):]))
        return os.path.abspath(os.path.join(self.cwd, p))

    def run_async(self, job):
        """Run job(cancel_event) off the input thread; the prompt returns when it finishes."""
        self.cancel, self.busy = threading.Event(), True

        def go():
            try:
                job(self.cancel)
            except Exception as e:
                self.out(f"ERROR: {e}\n")
            finally:
                self.busy = False
                self.prompt()
        threading.Thread(target=go, daemon=True).start()
        return "async"

    def feed(self, data: str):
        """Handle raw keystrokes from the terminal."""
        if self.running:
            return self._feed_script(data)
        if self.busy:
            if "\x03" in data:
                self.out("^C\r\n")
                self.cancel.set()
            return
        i = 0
        while i < len(data):
            ch = data[i]
            if data.startswith("\x1b[A", i) or data.startswith("\x1b[B", i):
                self._history(-1 if data[i + 2] == "A" else 1)
                i += 3
                continue
            if ch == "\x1b":  # ignore other escape sequences (arrows left/right, etc.)
                i += 3
                continue
            if ch == "\r":
                self.out("\r\n")
                line, self.line = self.line.strip(), ""
                if line:
                    self.history.append(line)
                self.hpos = len(self.history)
                self.execute(line)
            elif ch in ("\x7f", "\b"):
                if self.line:
                    self.line = self.line[:-1]
                    self.out("\b \b")
            elif ch == "\x03":
                self.line = ""
                self.out("^C\r\n")
                self.prompt()
            elif ch == "\x0c":
                self.out("\x1b[2J\x1b[H")
                self.prompt()
                self.out(self.line)
            elif ch >= " ":
                self.line += ch
                self.out(ch)
            i += 1

    def _history(self, step: int):
        if not self.history:
            return
        self.hpos = max(0, min(len(self.history), self.hpos + step))
        new = self.history[self.hpos] if self.hpos < len(self.history) else ""
        self.out("\b \b" * len(self.line) + new)
        self.line = new

    def _feed_script(self, data: str):
        """While a script runs: local echo, line editing, Enter sends the line, Ctrl+C stops it."""
        for ch in data:
            if ch == "\x03":
                self.out("^C\r\nKeyboardInterrupt\r\n")
                self.b.stop_script()
                self.line = ""
            elif ch == "\r":
                self.out("\r\n")
                self.b.executor.send_input(self.line + "\n")
                self.line = ""
            elif ch in ("\x7f", "\b"):
                if self.line:
                    self.line = self.line[:-1]
                    self.out("\b \b")
            elif ch >= " ":
                self.line += ch
                self.out(ch)

    # ---------- command dispatch ----------
    def execute(self, line: str):
        if not line:
            return self.prompt()
        try:
            argv = shlex.split(line)
        except ValueError as e:
            self.out(f"bash: {e}\n")
            return self.prompt()
        fn = self.commands.get(argv[0])
        if fn is None:
            self.out(f"bash: {argv[0]}: command not found\n")
            return self.prompt()
        try:
            if fn(argv[1:]) == "async":
                return  # the command prints the prompt when it finishes
        except Exception as e:
            self.out(f"{argv[0]}: {e}\n")
        self.prompt()

    # ---------- commands ----------
    def c_help(self, a):
        self.out("Raspberry Pi 5 simulator shell. Commands:\n  " + " ".join(sorted(self.commands)) + "\n")

    def c_ls(self, a):
        flags = "".join(x[1:] for x in a if x.startswith("-"))
        paths = [x for x in a if not x.startswith("-")] or ["."]
        for p in paths:
            full = self.resolve(p)
            if not os.path.exists(full):
                self.out(f"ls: cannot access '{p}': No such file or directory\n")
                continue
            names = sorted(os.listdir(full)) if os.path.isdir(full) else [p]
            if "a" not in flags:
                names = [n for n in names if not n.startswith(".")]
            if "l" in flags:
                for n in names:
                    st = os.stat(os.path.join(full, n) if os.path.isdir(full) else full)
                    kind = "d" if os.path.isdir(os.path.join(full, n)) else "-"
                    ts = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%b %d %H:%M")
                    self.out(f"{kind}rw-r--r-- 1 pi pi {st.st_size:>8} {ts} {n}\n")
            elif names:
                self.out("  ".join(BLUE + n + RESET if os.path.isdir(os.path.join(full, n)) else n for n in names) + "\n")

    def c_cd(self, a):
        target = self.resolve(a[0] if a else "~")
        if not os.path.isdir(target):
            return self.out(f"bash: cd: {a[0]}: No such file or directory\n")
        self.cwd = target

    def c_pwd(self, a):
        rel = os.path.relpath(self.cwd, self.home).replace("\\", "/")
        self.out("/home/pi" + ("" if rel == "." else "/" + rel) + "\n")

    VIRTUAL = {
        "/proc/cpuinfo": lambda s: board.cpuinfo(),
        "/proc/meminfo": lambda s: board.meminfo(s.b.used_kb()),
        "/etc/os-release": lambda s: board.os_release(),
        "/proc/device-tree/model": lambda s: board.MODEL + "\n",
        "/sys/firmware/devicetree/base/model": lambda s: board.MODEL + "\n",
    }

    def c_cat(self, a):
        for p in a:
            if p in self.VIRTUAL:
                self.out(self.VIRTUAL[p](self))
                continue
            full = self.resolve(p)
            if os.path.isdir(full):
                self.out(f"cat: {p}: Is a directory\n")
            elif not os.path.exists(full):
                self.out(f"cat: {p}: No such file or directory\n")
            else:
                with open(full, encoding="utf-8", errors="replace") as f:
                    self.out(f.read())

    def c_echo(self, a):
        self.out(" ".join(a) + "\n")

    def c_clear(self, a):
        self.out("\x1b[2J\x1b[3J\x1b[H")

    def c_mkdir(self, a):
        for p in (x for x in a if not x.startswith("-")):
            os.makedirs(self.resolve(p), exist_ok="-p" in a)

    def c_rm(self, a):
        recursive = any(x.startswith("-") and "r" in x for x in a)
        for p in (x for x in a if not x.startswith("-")):
            full = self.resolve(p)
            if os.path.isdir(full):
                if not recursive:
                    self.out(f"rm: cannot remove '{p}': Is a directory\n")
                    continue
                shutil.rmtree(full)
            elif os.path.exists(full):
                os.remove(full)
            else:
                self.out(f"rm: cannot remove '{p}': No such file or directory\n")

    def c_touch(self, a):
        for p in a:
            with open(self.resolve(p), "a"):
                pass

    def c_uname(self, a):
        self.out((board.UNAME_A if "-a" in a else "aarch64" if "-m" in a else "Linux") + "\n")

    def c_date(self, a):
        self.out(time.strftime("%a %d %b %H:%M:%S %Z %Y") + "\n")

    def c_uptime(self, a):
        up = int(time.time() - BOOT_TIME)
        self.out(f" {time.strftime('%H:%M:%S')} up {up // 60} min,  1 user,  load average: "
                 f"{psutil.getloadavg()[0]:.2f}, 0.00, 0.00\n")

    def c_free(self, a):
        total, used = board.MEM_TOTAL_KB, self.b.used_kb()
        if "-h" in a:
            gi = lambda kb: f"{kb / 1024 / 1024:.1f}Gi" if kb >= 1024 * 1024 else f"{kb // 1024}Mi"
            row = (gi(total), gi(used), gi(total - used), "1.0Mi", "0Mi", gi(total - used))
            swap = ("511Mi", "0B", "511Mi")
        else:
            row = (total, used, total - used, 1024, 0, total - used)
            swap = (524272, 0, 524272)
        self.out("               total        used        free      shared  buff/cache   available\n"
                 "Mem:   " + "".join(f"{v:>12}" for v in row) + "\n"
                 "Swap:  " + "".join(f"{v:>12}" for v in swap) + "\n")

    def c_lscpu(self, a):
        self.out(f"Architecture:        aarch64\nCPU(s):              {board.CORES}\nVendor ID:           ARM\n"
                 f"Model name:          Cortex-A76\nThread(s) per core:  1\nCore(s) per cluster: {board.CORES}\n"
                 f"CPU max MHz:         {board.ARM_FREQ_MHZ}.0000\nCPU min MHz:         {board.ARM_IDLE_MHZ}.0000\n"
                 "L1d:                 256 KiB (4 instances)\nL2:                  2 MiB (4 instances)\n"
                 "L3:                  2 MiB (1 instance)\n")

    def c_python(self, a):
        if not a or a[0] in ("-V", "--version"):
            if a:
                return self.out("Python 3.11.2\n")
            return self.out("Interactive Python is not supported here; run a file: python3 script.py\n")
        path = self.resolve(a[0])
        if not os.path.isfile(path):
            return self.out(f"python3: can't open file '{a[0]}': [Errno 2] No such file or directory\n")
        self.running = True
        self.b.run_script(path, a[1:], self.cwd, on_exit=self._script_done)
        return "async"

    def _script_done(self, rc):
        self.running = False
        self.line = ""
        self.prompt()

    def c_pip(self, a):
        if not a or a[0] != "install":
            return self.out("usage: pip install <package> ...\n")
        pkgs = [x for x in a[1:] if not x.startswith("-")]
        self.out(f"Installing {' '.join(pkgs)} into the simulator environment...\n")
        ok, err = install_packages(pkgs)
        self.out(f"Successfully installed {' '.join(pkgs)}\n" if ok else err + "\n")

    def c_vcgencmd(self, a):
        cmd = a[0] if a else ""
        busy = self.running
        if cmd == "measure_temp":
            self.out(f"temp={(62.0 if busy else 48.5) + psutil.cpu_percent() * 0.1:.1f}'C\n")
        elif cmd == "measure_clock":
            mhz = board.ARM_FREQ_MHZ if busy else board.ARM_IDLE_MHZ
            self.out(f"frequency(0)={mhz * 1_000_000}\n")
        elif cmd == "get_config" and a[1:] == ["arm_freq"]:
            self.out(f"arm_freq={board.ARM_FREQ_MHZ}\n")
        elif cmd == "get_throttled":
            self.out("throttled=0x0\n")
        elif cmd == "measure_volts":
            self.out("volt=0.8650V\n" if busy else "volt=0.7200V\n")
        elif cmd == "get_mem":
            self.out("arm=16384M\n" if a[1:] == ["arm"] else "gpu=4M\n")
        else:
            self.out("Commands: measure_temp measure_clock arm get_config arm_freq get_throttled measure_volts get_mem arm\n")

    def c_pinout(self, a):
        self.out(f"{GREEN}{board.MODEL}{RESET}\n" + "".join(f"{k}: {v}\n" for k, v in board.SPECS.items()) + "\nJ8:\n")
        for pin in range(1, 41, 2):
            (ln, _), (rn, _) = board.J8[pin], board.J8[pin + 1]
            self.out(f"{ln:>9} ({pin:>2}) ({pin + 1:>2}) {rn}\n")
        attached = [board.PERIPHERALS[p][0] + " -> " + board.PORTS[port] for p, port in self.b.links.items() if port]
        self.out("\nAttached:\n" + ("".join(f"  {x}\n" for x in attached) or "  (none)\n"))

    def c_pinctrl(self, a):
        if a and a[0] == "set" and len(a) >= 3:
            pin = int(a[1])
            if pin not in board.GPIO_NUMBERS:
                return self.out(f"Unknown GPIO \"{a[1]}\"\n")
            opts = a[2:]
            self.b.gpio[pin] = {"mode": "op" if "op" in opts else "ip" if "ip" in opts else self.b.gpio.get(pin, {}).get("mode", "ip"),
                                "level": 1 if "dh" in opts else 0 if "dl" in opts else self.b.gpio.get(pin, {}).get("level", 0)}
            self.b.send_state()
            return
        pins = [int(x) for x in a[1:]] if a[:1] == ["get"] and len(a) > 1 else board.GPIO_NUMBERS
        for pin in pins:
            st = self.b.gpio.get(pin, {"mode": "ip", "level": 0})
            self.out(f"{pin:>2}: {st['mode']}    pd | {'hi' if st['level'] else 'lo'} // GPIO{pin} = "
                     f"{'output' if st['mode'] == 'op' else 'input'}\n")

    def c_sudo(self, a):
        if not a:
            return self.out("usage: sudo command\n")
        fn = self.commands.get(a[0])
        if fn is None:
            return self.out(f"sudo: {a[0]}: command not found\n")
        return fn(a[1:])
