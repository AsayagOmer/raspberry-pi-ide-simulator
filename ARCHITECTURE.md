# Software Architecture of Raspberry Pi IDE Simulator

This document outlines the high-level architecture of the Raspberry Pi IDE Simulator. The system is designed to provide robust hardware simulation, safe code execution, and high extensibility.

## The Hybrid Architecture

The system employs a hybrid approach, mixing three distinct architectural patterns to solve specific domain challenges:

1. **Model-View-Controller (MVC)** for the IDE Frontend.
2. **Event-Driven Architecture (EDA)** for bridging background tasks (hardware execution) with the GUI thread.
3. **Microkernel / Plugin Pattern** for highly extensible hardware components.
*(Note: A future migration to Out-of-Process IPC Execution for the execution engine is planned to replace the current threading model for full sandboxing).*

### 1. MVC Frontend
The main IDE UI is split into strict responsibilities:
- `ide_app.py`: The main window controller that glues the system together.
- `hardware_workspace.py`: Manages the interactive canvas, zooming, component placement, and hardware state history.
- `code_editor.py`: Manages the text editing, file operations, and syntax highlighting.

### 2. Event-Driven Observer Pattern (State Sync)
Tkinter (like most GUI frameworks) is not thread-safe. Because user code runs in a background thread, the `HardwareAPI` must not manipulate UI widgets directly.
Instead, we use a central **EventBus** (`event_bus.py`).
- **Publishers:** The `HardwareAPI` publishes events (e.g., `EventBus.publish("LOG_CONSOLE", text="...")`).
- **Subscribers:** The IDE UI subscribes to these events at startup and schedules the UI updates on the main thread safely using `self.after(0, ...)`.

### 3. Microkernel / Plugin Registry
Hardware components shouldn't be hardcoded into the core IDE. We use a microkernel pattern in `components/__init__.py`.
- **Dynamic Loading:** The core system automatically discovers and imports all Python files in the `components/` directory.
- **Registration:** Components use the `@register_component("Name")` decorator to inject themselves into the `COMPONENT_REGISTRY`. This allows adding new hardware (like sensors or LEDs) simply by dropping a single file into the folder.

---

## Architectural Diagram

```mermaid
flowchart TD
    subgraph IDE_Process [Main IDE Process (Microkernel & MVC)]
        direction TB
        UI[Tkinter Views\n(Canvas, Code Tabs)]
        Ctrl[Controllers\n(Workspace, Editor)]
        State[(Hardware State Models)]
        
        UI <-->|User Input / Render| Ctrl
        Ctrl <-->|Update / Read| State
        
        PluginLoader[Plugin Registry] -.->|Dynamically Injects| UI
    end

    subgraph Event_System [Event Broker]
        EB((Event Bus\nPub/Sub))
    end

    subgraph Execution_Engine [Code Executor Thread]
        direction TB
        Runner[Execution Sandbox]
        UserCode(User's Python Script)
        HwAPI[Hardware API Proxy]
        
        Runner -->|Parses & Runs| UserCode
        UserCode <-->|Calls hardware.*| HwAPI
    end

    %% Connections
    Ctrl <-->|Subscribes to Events| EB
    HwAPI <-->|Publishes Events| EB
```
