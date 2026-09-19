# Professional Raspberry Pi IDE Simulator

Welcome to the Professional IDE Simulator for Raspberry Pi! This application provides a seamless, interactive virtual workspace to develop, test, and debug Python scripts meant for Raspberry Pi hardware setups.

## 🚀 Key Features

*   **Interactive Visual Hardware Workspace:** Drag and drop components around the canvas. Components realistically "snap" onto appropriate ports (e.g., Pirate Audio snaps onto the Pi's GPIO header, USB Speaker cable snaps into the Pi's USB port).
*   **Split-Pane Interface with Tabs:** 
    *   **Code Editor:** Supports multiple open script tabs. Features syntax highlighting (VSCode dark theme colors) and **Ctrl+Z (Undo) / Ctrl+Y (Redo)** support.
    *   **Component Palette:** A dedicated tab allowing you to spawn additional hardware components into the workspace.
*   **Role-Specific Hardware Audio:**
    *   **Pirate Audio HAT (Microphone):** The HAT has been configured to act as your audio input device. It will record actual audio from your computer's microphone if properly attached to the Pi's GPIO header.
    *   **Mini USB Speaker (Playback):** Strictly acts as the audio output device. It will only play back `.wav` or `.mp3` files if its USB cable is plugged into the Pi.
*   **Thread-Safe Execution Engine:** When you click "Run Code", your script is executed in a background thread. `sys.stdout` is carefully redirected using `contextlib` so your `print()` statements stream directly into the IDE Console without freezing the GUI.

## 🧠 Code Architecture & Design

The codebase (`professional_ide.py`) has been refactored into a scalable Object-Oriented design to ensure maintainability and readability.

### 1. `BaseComponent` Class
The foundation of the visual workspace. It encapsulates common logic for rendering, tracking coordinates, and handling `tkinter` drag-and-drop mouse events (`<ButtonPress-1>`, `<B1-Motion>`). Every physical device inherits from this class.

### 2. Hardware Implementations
*   `RaspberryPi(BaseComponent)`: Defines the main board, establishing the physical coordinates for the `gpio_x, gpio_y` and `usb_x, usb_y` connection ports.
*   `PirateAudio(BaseComponent)`: Includes interactive UI buttons (`A, B, X, Y`) and an LCD screen. Its drag release event calculates the euclidean distance (`math.hypot`) to any Raspberry Pi on the canvas. If within the threshold, it snaps to the GPIO header.
*   `USBSpeaker(BaseComponent)`: A complex component that separates the drag logic of its "Body" from its "USB Plug". Dragging the plug recalculates a Bezier curve to visually stretch the cable, snapping only to valid USB ports.

### 3. `IDEApp` Class
Inherits from `tk.Tk` and orchestrates the layout using `ttk.PanedWindow` and `ttk.Notebook`. It maintains a list of instantiated `components` and maps `tab_ids` to their respective `tk.Text` editors.

### 4. `HardwareAPI` Class
An abstraction layer injected dynamically into the user's script environment during execution. 
*   **State Checking:** Before playing or recording audio, it queries the IDE state to find if `isinstance(comp.connected_to, RaspberryPi)` is True for the required component.
*   **Thread-Safety:** All visual updates requested by the user's script (like `hardware.display_text`) are wrapped in `self.app.after(0, ...)` to ensure Tkinter's main loop safely handles the GUI update across thread boundaries.

## 📝 Getting Started
1. Run `python professional_ide.py`.
2. Ensure the **Pirate Audio HAT** is dragged directly onto the top edge (GPIO Header) of the Raspberry Pi.
3. Ensure the **USB Speaker's blue plug** is dragged onto the right edge (USB Port) of the Raspberry Pi.
4. Open the **Code Editor** tab and click **▶ Run Active Code**.
