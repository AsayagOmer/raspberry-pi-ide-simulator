# Raspberry Pi IDE Simulator

![Demo GIF](https://raw.githubusercontent.com/AsayagOmer/raspberry-pi-ide-simulator/main/docs/demo.gif)

## Overview

The **Raspberry Pi IDE Simulator** provides a full‑featured, graphical development environment that mimics a Raspberry Pi hardware setup.  It lets you drag‑and‑drop common peripherals (Pirate Audio HAT, USB speaker, etc.) onto a virtual Pi, write Python scripts, and execute them in a thread‑safe sandbox.  The simulator is ideal for learning, prototyping, and testing code that interacts with hardware without needing a physical device.

## Features

- Interactive visual workspace with snap‑to‑port behaviour
- Multi‑tab code editor with syntax highlighting
- Real‑time console output and error handling
- Thread‑safe `HardwareAPI` injected into user scripts
- Built‑in audio recording/playback emulation
- Extensible component architecture (add new devices easily)

## Recent Improvements

| # | Area | What was changed | Why it matters (new behavior) |
|---|------|------------------|--------------------------------|
| 1 | **Audio playback (`play_audio`)** | • Removed the *project‑root* whitelist check.<br>• Added a full‑path resolution (`os.path.abspath`).<br>• Wrapped `pygame` calls in a `try/except` block.<br>• Updated docstring to state **no path‑restriction**. | Allows any existing audio file (e.g., `C:/Windows/Media/tada.wav`) to be played, fixing the “outside the allowed directory” error. Errors during playback are now reported clearly. |
| 2 | **User feedback** | • Added explicit log messages for successful playback (`Playing audio: …`) and for any exception (`ERROR: Playback failed – …`). | Gives immediate, informative console output so you know exactly what succeeded or why it failed. |
| 3 | **Container launch script (`run_simulator.ps1`)** | • Automates WSL 2, Docker‑engine installation, image build, and container run.<br>• Mounts the project read‑only (`-v "${PWD}:/app:ro"`).<br>• Forwards the X server (`DISPLAY`).<br>• **Exposes the host audio device** (`--device /dev/snd`). | Provides a **single‑command** way to start the simulator without Docker Desktop. Audio recording now works because the container can access the host’s sound device. |
| 4 | **Isolation model** | • The container runs as a non‑root user (`appuser`).<br>• Only the project folder, the X server, and the audio device are exposed.<br>• Network can be disabled (`--network none`) if desired. | Keeps the simulator sandboxed from the rest of the Windows system while still permitting required GUI and audio functionality. |
| 5 | **Error handling for missing files** | • When the file does not exist, the method now logs `ERROR: Audio file '…' not found.` instead of silently failing. | Makes it easy to spot typos or missing assets during demos. |
| 6 | **Documentation comment** | Updated the method’s docstring to reflect the new unrestricted behavior. | Future developers (or you) will see the intended policy directly in the source. |

## Installation

```bash
# Clone the repository
git clone https://github.com/AsayagOmer/raspberry-pi-ide-simulator.git
cd raspberry-pi-ide-simulator

# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate   # on Windows use `.venv\Scripts\activate`

# Install dependencies
pip install -r requirements.txt
```

> **Note** – The project requires Python 3.10+ and the `tkinter` package (included with most Python installations).

## Launching the IDE

```bash
python professional_ide.py
```

The application window opens with two panes:
- **Component Palette** – drag components onto the canvas
- **Code Editor** – write or open Python files, then click **▶ Run Active Code**

## Getting Started

A concise step‑by‑step tutorial is available in the [Getting‑Started guide](Getting-Started.md).

## API Reference

- [`HardwareAPI`](hardware_api.md) – functions for audio I/O, display, and sensor simulation
- [`components`](components.md) – base classes for visual devices
- [`IDEApp`](IDEApp.md) – main application class handling layout and execution

See the individual markdown files for detailed signatures and usage examples.

## License & Citation

The project is released under the **MIT License** (see [LICENSE.md](LICENSE.md)).

If you use the simulator in academic work, please cite it as:

```
@software{Omer2026RaspberryPiIDE,
  author = {Asayag, Omer},
  title = {Raspberry Pi IDE Simulator},
  year = {2026},
  url = {https://github.com/AsayagOmer/raspberry-pi-ide-simulator},
  license = {MIT}
}
```
