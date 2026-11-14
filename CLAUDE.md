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

# Docker (Windows via WSL2 + WSLg, no Docker Desktop)
launch_isolated.bat                    # wraps run_simulator.ps1: installs docker.io in WSL, builds pi-ide-sim, runs it
```

Known state: `tests/test_hardware_api.py` and `tests/test_connections.py` fail to collect — they `from hardware_api import HardwareAPI`, but the module is now `core.hardware_api`. `src/emulator/tests` needs `unicorn` installed (not in `.venv` by default).

## Imports

`src/` is put on `sys.path` by each entry point (`main.py`, `run_emulator.py`, tests), so code imports top-level packages: `from core.event_bus import EventBus`, `from ui.code_editor import CodeEditor`, `from components.raspberry_pi import RaspberryPi`, `from emulator.soc import BCM2711SoC`. Never `from src....`.

## Architecture

Three subsystems:

**1. IDE (`src/ui/`, MVC on Tkinter).** `ide_app.IDEApp` is the controller gluing `hardware_workspace.HardwareWorkspace` (canvas, drag/snap of components, connections) and `code_editor.CodeEditor` (tabs, highlighting). Tkinter is not thread-safe: background work must reach widgets only via `app.after(0, ...)`.

**2. Hardware components (`src/components/`, plugin registry).** `components/__init__.py` auto-imports every `.py` file in the folder (except `base_component.py`, `connection.py`); each class registers itself with `@register_component("Name", color=...)` into `COMPONENT_REGISTRY`. Adding a device = drop one file subclassing `BaseComponent`. `connection.py` holds `Connection`/`ConnectionManager` for port wiring.

**3. Code execution (`src/core/`).** `HardwareAPI` (`hardware_api.py`) implements device actions (display, buttons, `play_audio` via pygame, `record_audio` via sounddevice) against connected components and publishes UI updates through `EventBus` (`event_bus.py`, simple pub/sub, e.g. `"LOG_CONSOLE"`).

`CodeExecutor.run` (`code_executor.py`) — note `docs/ARCHITECTURE.md` still describes an in-thread sandbox; the real flow is out-of-process:
- AST-scans user imports, `uv pip install --target` (fallback `pip`) missing non-stdlib packages into `.sim_env_<id(rpi)>/` at the project root (these dirs are per-run cache, safe to ignore).
- Writes a generated `hardware.py` proxy plus `main_script.py` (`import hardware` prepended) into that dir, runs it as a subprocess with `.env` vars merged in.
- Proxy protocol over stdio: child prints `HW_CMD:<cmd>:<arg1>|<arg2>`, parent dispatches to `HardwareAPI`, replies `True`/`False` on stdin. Adding a user-facing hardware function requires updating both the proxy string and the dispatch `if/elif` in `code_executor.py`, plus `HardwareAPI`.
- Also spawns `run_emulator.py --test uart` alongside and streams its output as `[ARM64 Emulator]` lines.

**4. BCM2711 emulator (`src/emulator/`, untracked/new).** Unicorn-based ARMv8-A emulator: `soc.BCM2711SoC` wires `cpu.py` (cores), `memory.py` (map, 8 GB boundary), `boot.py` (kernel/DTB/spin-table load), `throttle.py`, and MMIO `peripherals/` (`pl011` UART, `gic400`, `mailbox`, `timer`, `emmc2`, all on `base_peripheral.py`).

## Other top-level files

- `voice_assistant_client.py`: standalone EcoCare voice client (VAD recording, HTTP keep-alive to a server, Hebrew TTS via edge-tts). Not imported by the IDE; often run as user code inside the simulator.
- `ecocare_hardware_test.py`, `ecocare_rpi_hardware_tests.ipynb`: real-Pi hardware checks.
- Docs: `docs/hardware_api.md` (user-script API), `docs/components.md`, `docs/Getting-Started.md`.
