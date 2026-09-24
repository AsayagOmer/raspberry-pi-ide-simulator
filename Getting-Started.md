# Getting Started

This guide walks you through the first steps to get the **Raspberry Pi IDE Simulator** up and running, and demonstrates a simple hardware‑interaction script.

## Prerequisites

- **Python 3.10+** (ensure `python --version` reports 3.10 or newer).
- **Tkinter** – typically bundled with the standard Python installer on Windows. If you get an import error, reinstall Python with the "tcl/tk and IDLE" option enabled.
- Optional but recommended: **Git** for cloning the repository.

## 1. Clone the repository

```bash
git clone https://github.com/AsayagOmer/raspberry-pi-ide-simulator.git
cd raspberry-pi-ide-simulator
```

## 2. Set up a virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate   # PowerShell: `.venv\Scripts\Activate.ps1`
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

> **Tip** – If you encounter permission errors on Windows, run the terminal as an administrator or add `--user` to the pip command.

## 4. Run the simulator

```bash
python professional_ide.py
```

The main window appears with two panes:
- **Component Palette** – drag the *Pirate Audio HAT* or *USB Speaker* onto the Raspberry Pi canvas.
- **Code Editor** – write or open a `.py` script.

## 5. Quick demo script

Create a file named `demo.py` in the project root with the following content:

```python
from hardware_api import HardwareAPI
import time

def main(api: HardwareAPI):
    # Display a welcome message on the Pirate Audio HAT screen
    api.display_text("Hello Pi!")
    time.sleep(2)
    # Play a short sound if a speaker is connected
    api.play_audio("assets/beep.wav")
    # Record 3 seconds of audio from the mic (if attached)
    api.record_audio("recorded.wav", duration=3)
```

1. Open `demo.py` in the **Code Editor** tab.
2. Click **▶ Run Active Code**.
3. Observe the on‑screen text, playback, and recording actions.

## 6. Exploring the API

- The full API reference is provided in the [API Reference section](API-Reference.md).
- For deeper dives, see the individual module docs: `hardware_api.md`, `components.md`, `IDEApp.md`.

Enjoy experimenting with virtual hardware!
