# Raspberry Pi 5 Simulator for VS Code

A simulated **Raspberry Pi 5 Model B (16 GB)** inside VS Code.

- **Terminal:** run *Pi Sim: Open Raspberry Pi 5 Terminal*, or pick **Raspberry Pi 5** from the terminal **+** menu. You get a `pi@raspberrypi:~ $` shell whose home is your workspace folder.
  - Run code with `python3 script.py` and install packages with `pip install`.
  - Inspect the board with `vcgencmd`, `pinout`, `pinctrl`, `cat /proc/cpuinfo` and `free -h`.
  - Use the camera with `rpicam-hello`, `rpicam-still` and `rpicam-vid`.
- **Performance:** scripts are paced to Pi 5 CPU speed (4× Cortex-A76 @ 2.4 GHz) and pinned to 4 cores. The pacing reference is an estimate. To calibrate it, run `python -m pi5sim.perf` on a real Pi 5 and set `PI5SIM_REF_SCORE` to the score it prints.
- **Camera:** an Arducam IMX519 16 MP autofocus camera.
  - Scripts can use `picamera2` and `libcamera.controls` as usual.
  - Frames come from your webcam. Set `piSim.useWebcam` to `false` to use a test pattern instead.

This is a simulator, not an emulator. Your Python runs on the host with Pi 5 hardware simulated around it. It does not boot Raspberry Pi OS.

## Requirements

Python 3.10+ with the simulator's dependencies installed:

```bash
pip install -r requirements.txt
```

By default the extension uses the workspace `.venv`. Set `piSim.pythonPath` to choose another interpreter.

## Development

```bash
code --extensionDevelopmentPath=vscode-extension .
```

## Packaging

Packaging copies the Python backend into `python/` and builds a `.vsix`:

```bash
cd vscode-extension && npm run package
```
