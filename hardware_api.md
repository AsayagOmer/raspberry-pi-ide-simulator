# Hardware API Reference

`hardware_api.py`

## `HardwareAPI`

The `HardwareAPI` class provides a safe bridge between user scripts and the simulated hardware. It is instantiated with a reference to the running `IDEApp` instance and offers the following methods:

| Method | Description |
|--------|-------------|
| `clear_screen()` | Clears any text displayed on the attached Pirate Audio HAT screen. |
| `display_text(text: str, color: str = "white")` | Shows `text` on the HAT screen in the specified `color`. |
| `is_pressed(btn: str) -> bool` | Returns **True** if the button (`"A"`, `"B"`, `"X"`, `"Y"`) is currently pressed. |
| `play_audio(filepath: str) -> bool` | Plays an audio file **if** a USB speaker is connected. Logs an error and returns `False` when no speaker is present or the file is missing. |
| `record_audio(filepath: str, duration: int = 3, fs: int = 44100) -> bool` | Records from the Pirate Audio microphone for `duration` seconds into `filepath`. Requires the `sounddevice` and `soundfile` libraries and a connected microphone. |

All UI updates are dispatched via `self.app.after(0, ...)` to keep Tkinter thread‑safe.

**Typical usage in a user script**:

```python
from hardware_api import HardwareAPI
import time

def main(api: HardwareAPI):
    api.display_text("Hello Pi!")
    time.sleep(2)
    api.play_audio("assets/beep.wav")
    api.record_audio("recorded.wav", duration=3)
```

The simulator injects an instance named `hardware` (or `api` if you prefer) into the script’s globals before execution.
