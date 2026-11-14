# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Repo: https://github.com/AsayagOmer/raspberry-pi-ide-simulator

## Commands

```bash
# Install (Python >=3.10, tkinter required; uv.lock present)
pip install -r requirements.txt        # includes emulator deps: unicorn, capstone, keystone-engine

# Launch the Tkinter IDE
python main.py

# ARM64 (BCM2711) emulator CLI
python run_emulator.py --test uart|memory|multicore|all
python run_emulator.py --binary firmware/test.bin --addr 0x80000
python run_emulator.py --unittest      # = pytest src/emulator/tests/ -v --tb=short

# Tests
python -m pytest tests
python -m pytest tests/test_components.py::TestClassName::test_name

# VS Code extension (Raspberry Pi 5 shell + board panel)
code --extensionDevelopmentPath=vscode-extension .
cd vscode-extension && npm run package # bundles src/core + src/pi5sim into a .vsix
python -m pytest tests/test_pi5_shell.py tests/test_imx519.py tests/test_perf.py

# Docker (Windows via WSL2 + WSLg, no Docker Desktop)
launch_isolated.bat                    # wraps run_simulator.ps1: installs docker.io in WSL, builds pi-ide-sim, runs it
```

Known state: `tests/test_hardware_api.py` and `tests/test_connections.py` fail to collect — they `from hardware_api import HardwareAPI`, but the module is now `core.hardware_api`. `src/emulator/tests` needs `unicorn` installed (not in `.venv` by default).

## Imports

`src/` is put on `sys.path` by each entry point (`main.py`, `run_emulator.py`, tests), so code imports top-level packages: `from core.event_bus import EventBus`, `from ui.code_editor import CodeEditor`, `from components.raspberry_pi import RaspberryPi`, `from emulator.soc import BCM2711SoC`. Never `from src....`.

## Architecture

Subsystems:

**1. IDE (`src/ui/`, MVC on Tkinter).** `ide_app.IDEApp` is the controller gluing `hardware_workspace.HardwareWorkspace` (canvas, drag/snap of components, connections) and `code_editor.CodeEditor` (tabs, highlighting). Tkinter is not thread-safe: background work must reach widgets only via `app.after(0, ...)`.

**2. Hardware components (`src/components/`, plugin registry).** `components/__init__.py` auto-imports every `.py` file in the folder (except `base_component.py`, `connection.py`); each class registers itself with `@register_component("Name", color=...)` into `COMPONENT_REGISTRY`. Adding a device = drop one file subclassing `BaseComponent`. `connection.py` holds `Connection`/`ConnectionManager` for port wiring.

**3. Code execution (`src/core/`).** `HardwareAPI` (`hardware_api.py`) implements device actions (display, buttons, `play_audio` via pygame, `record_audio` via sounddevice) against connected components and publishes UI updates through `EventBus` (`event_bus.py`, simple pub/sub, e.g. `"LOG_CONSOLE"`).

`CodeExecutor.run` (`code_executor.py`). `docs/ARCHITECTURE.md` still describes an in-thread sandbox, but code actually runs in a separate process. Shared by the Tk IDE and the Pi 5 backend:
- **Dependencies:** AST-scans user imports. Packages that are neither importable on the host nor already in `.sim_env/` (project root, a gitignored cache) get installed there with `uv pip install --target`, falling back to `pip`.
- **Running:** writes the `hardware.py` proxy (`PROXY_CODE`) plus any `extra_files` into `.sim_env/`. Then it runs either `main_script.py` (with `import hardware` prepended, Tk mode) or `script_path` directly (shell mode), with `PYTHONPATH=.sim_env` and `.env` vars merged in.
- **Proxy protocol over stdio:**
  - The child prints `HW_CMD:<cmd>:<arg1>|<arg2>`.
  - The parent replies `\x01HW:<result>` on stdin. The tag lets the proxy's stdin wrapper keep `input()` working.
  - Built-in commands live in `dispatch()`, and callers add their own with `extra_commands={name: fn(args, cwd)}`.
  - Output is streamed unbuffered through `on_output`. By default that is line-wise `app.log_console`.
- `spawn_emulator=True` (the Tk default) also runs `run_emulator.py --test uart` and shows its output as `[ARM64 Emulator]` lines.

**4. Raspberry Pi 5 backend (`src/pi5sim/`) + VS Code extension (`vscode-extension/`).**
- The extension (`extension.js`, plain JS with no build step) spawns `python -m pi5sim <workspace>` with `PYTHONPATH` set to `../src`, or to `python/` in a packaged `.vsix`. It talks JSON lines over stdio; message types are documented at the top of `backend.py`.
- **The terminal:** a Pseudoterminal that forwards raw keystrokes. `shell.py` handles line editing itself and maps `~` and `/home/pi` onto the workspace. Add a command by putting it in `Shell.commands`. A command that returns `"async"` must print the prompt itself; use `run_async`.
- **The side panel:** a WebviewView, `media/board.*`. Port ids and geometry are hardcoded in `board.js`; port compatibility comes from `board.PERIPHERALS`. Components are added from the search bar, which lists one result per (component, free compatible port); search keywords live in `KEYWORDS` in `board.js`.
- **`backend.HeadlessApp`:** stands in for the Tk app. `HardwareAPI` finds peripherals by class name (`PirateAudio`, `USBSpeaker`) and checks `connected_to is rpi`, so the backend creates stub objects with those names.
- **`perf.Pacer`:** paces the user process to Pi 5 speed by suspending and resuming it. It must act on the whole process tree, because on Windows the venv `python.exe` is only a launcher.
- **`camera.attach`:** registers the `cam_*` HW_CMDs, writes the `picamera2.py`/`libcamera.py` shims, adds the `rpicam-*` commands and runs the preview stream. `PI5SIM_WEBCAM=0` forces the test pattern.
- **Tests:** `tests/test_pi5_shell.py`, `test_imx519.py` and `test_perf.py`. Note that `tests/` is gitignored.
- **Packaging:** `cd vscode-extension && npm run package`. This runs `scripts/bundle-python.js` and then vsce.

**5. BCM2711 emulator (`src/emulator/`).** Unicorn-based ARMv8-A emulator: `soc.BCM2711SoC` wires `cpu.py` (cores), `memory.py` (map, 8 GB boundary), `boot.py` (kernel/DTB/spin-table load), `throttle.py`, and MMIO `peripherals/` (`pl011` UART, `gic400`, `mailbox`, `timer`, `emmc2`, all on `base_peripheral.py`).

## Other top-level files

- `voice_assistant_client.py`: standalone EcoCare voice client (VAD recording, HTTP keep-alive to a server, Hebrew TTS via edge-tts). Not imported by the IDE; often run as user code inside the simulator.
- `ecocare_hardware_test.py`, `ecocare_rpi_hardware_tests.ipynb`: real-Pi hardware checks.
- Docs: `docs/hardware_api.md` (user-script API), `docs/components.md`, `docs/Getting-Started.md`.
