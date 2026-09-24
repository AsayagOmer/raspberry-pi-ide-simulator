# Components Reference

`src/components/`

## Overview

The simulator uses a modular component architecture. Each visual hardware element inherits from **`BaseComponent`**, which provides common functionality such as drawing, dragging, rotating, and interaction with the Tkinter canvas.

---

## `BaseComponent`

| Attribute / Method | Description |
|--------------------|-------------|
| `canvas` | Tkinter canvas the component draws on. |
| `x`, `y` | Top‑left position of the component (canvas coordinates). |
| `rotation` | Current rotation in degrees (0, 90, 180, 270). |
| `draw()` | Abstract – subclasses implement their visual representation. |
| `setup_draggable()` | Binds mouse events for drag‑and‑drop and right‑click rotation. |
| `snap_port_to(port_name, target_x, target_y)` | Called by the connection manager to snap a specific port to a target location. |
| `get_ports()` | Returns a list of port dictionaries `{name, direction, x, y}`. Sub‑classes override to expose their connection points. |
| `rotate(event=None)` | Rotates the component by 90° and redraws it. |
| `delete()` | Removes all canvas items and deregisters the component from the app. |

---

## Concrete Components

### `RaspberryPi`
*File: `raspberry_pi.py`*

- Represents the Raspberry Pi 4 board.
- Implements `draw()` to render the board, GPIO header, USB ports, Ethernet, power, and other connectors.
- Exposes three ports via `get_ports()`:
  * `gpio_header` (in) – centre of the GPIO header.
  * `usb2_port` (in) – centre of the USB 2.0 block.
  * `usb3_port` (in) – centre of the USB 3.0 block.
- Updates port coordinates on drag/rotate via `update_ports()`.

### `PirateAudio`
*File: `pirate_audio.py`*

- Simulates the Pirate Audio HAT with buttons **A, B, X, Y**, an LCD‑style screen, and a microphone.
- Implements custom `draw()` to render the HAT shape, buttons, and screen text.
- Provides a single port `gpio_header` (out) for snapping onto the Pi’s GPIO header.
- Offers helper methods `display_text`, `clear_screen`, and `is_pressed` used by `HardwareAPI`.

### `USBSpeaker`
*File: `usb_speaker.py`*

- Visualises a USB speaker with a detachable plug.
- Two logical parts: the speaker body and the plug (`plug_tag`).
- Exposes `usb_port` (out) for connection to the Pi’s USB ports.
- Handles cable stretching with a Bezier curve when the plug is dragged.

---

## Connection Management

The **`ConnectionManager`** (`src/components/connection.py`) automatically discovers compatible ports and creates a `Connection` object linking a source component’s *out* port to a target component’s *in* port. Connections are visualised as thin lines on the canvas and are re‑established whenever the hardware state is loaded.

---

## Extending the Library

To add a new device:
1. Subclass `BaseComponent`.
2. Implement `draw()` and optionally override `get_ports()`.
3. Register the component in `src/components/__init__.py` using the `@register_component("Display Name", color="#hex")` decorator.
4. The new component will automatically appear in the **Component Library** tab of the IDE.

[Back to top](#components-reference)
