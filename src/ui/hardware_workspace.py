import tkinter as tk
from components import COMPONENT_REGISTRY
from core.logger import log_event

class HardwareWorkspace:
    """Manages the visual hardware canvas, components drag-and-drop, zoom, and history."""
    
    def __init__(self, parent_frame, app):
        self.app = app
        self.parent_frame = parent_frame
        
        self.app.zoom_factor = 1.0
        self.app.hardware_history = []
        self.app.history_index = -1
        self.app.copied_component = None
        self.app.hovered_component = None
        self.app.components = []
        from components.connection import ConnectionManager
        self.app.connection_manager = ConnectionManager()

        self._setup_ui()
        self._bind_events()

    def _setup_ui(self):
        tk.Label(self.parent_frame, text="Hardware Workspace", font=("Segoe UI", 14, "bold"), bg="#3c3f41", fg="white").pack(pady=5)
        
        # Upper Hardware Toolbar (Undo/Redo & Zoom)
        self.hw_toolbar = tk.Frame(self.parent_frame, bg="#3c3f41")
        self.hw_toolbar.pack(fill=tk.X, padx=5, pady=2)
        tk.Button(self.hw_toolbar, text="↩ Undo", bg="#555", fg="white", command=self.undo, relief=tk.FLAT).pack(side=tk.LEFT, padx=5)
        tk.Button(self.hw_toolbar, text="↪ Redo", bg="#555", fg="white", command=self.redo, relief=tk.FLAT).pack(side=tk.LEFT, padx=5)

        # Zoom Controls
        self.zoom_frame = tk.Frame(self.hw_toolbar, bg="#3c3f41")
        self.zoom_frame.pack(side=tk.RIGHT, padx=5)
        tk.Button(self.zoom_frame, text=" - ", bg="#555", fg="white", command=lambda: self.set_zoom(self.app.zoom_factor - 0.1), relief=tk.FLAT).pack(side=tk.LEFT, padx=2)
        self.zoom_label = tk.Label(self.zoom_frame, text="100%", bg="#3c3f41", fg="white", width=5)
        self.zoom_label.pack(side=tk.LEFT, padx=2)
        tk.Button(self.zoom_frame, text=" + ", bg="#555", fg="white", command=lambda: self.set_zoom(self.app.zoom_factor + 0.1), relief=tk.FLAT).pack(side=tk.LEFT, padx=2)

        # Coordinate label at bottom
        self.coord_label = tk.Label(self.parent_frame, text="X: 0, Y: 0", font=("Consolas", 10), bg="#3c3f41", fg="#aaa")
        self.coord_label.pack(side=tk.BOTTOM, anchor=tk.E, padx=5, pady=2)

        self.app.canvas = tk.Canvas(self.parent_frame, bg="#f0f0f0", highlightthickness=0)
        self.app.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.app.canvas.bind("<Configure>", self.draw_graph_paper)
        self.app.canvas.bind("<ButtonPress-1>", lambda e: self.app.canvas.focus_set())
        self.app.canvas.bind("<Motion>", self.update_coords)

    def _bind_events(self):
        self.app.bind("<Delete>", self.delete_hovered)
        self.app.bind("<BackSpace>", self.delete_hovered)
        self.app.bind("<Control-c>", self.copy)
        self.app.bind("<Control-C>", self.copy)
        self.app.bind("<Control-v>", self.paste)
        self.app.bind("<Control-V>", self.paste)
        self.app.bind("<Control-x>", self.cut)
        self.app.bind("<Control-X>", self.cut)
        self.app.bind("<Control-z>", self.undo)
        self.app.bind("<Control-Z>", self.undo)
        self.app.bind("<Control-y>", self.redo)
        self.app.bind("<Control-Y>", self.redo)
        self.app.bind("<Control-Shift-Z>", self.redo)
        self.app.bind("<Control-Shift-z>", self.redo)

    def set_zoom(self, new_zoom):
        old_zoom = self.app.zoom_factor
        self.app.zoom_factor = max(0.2, min(3.0, round(new_zoom, 2)))
        if self.app.zoom_factor == old_zoom: return
        
        ratio = self.app.zoom_factor / old_zoom
        cx = self.app.canvas.winfo_width() / 2
        cy = self.app.canvas.winfo_height() / 2
        
        self.zoom_label.config(text=f"{int(self.app.zoom_factor * 100)}%")
        
        for comp in self.app.components:
            comp.x = cx + (comp.x - cx) * ratio
            comp.y = cy + (comp.y - cy) * ratio
            if hasattr(comp, 'socket_x'):
                comp.socket_x = cx + (comp.socket_x - cx) * ratio
                comp.socket_y = cy + (comp.socket_y - cy) * ratio
            if hasattr(comp, 'plug_x'):
                comp.plug_x = cx + (comp.plug_x - cx) * ratio
                comp.plug_y = cy + (comp.plug_y - cy) * ratio
            if hasattr(comp, 'gpio_x'):
                comp.gpio_x = cx + (comp.gpio_x - cx) * ratio
                comp.gpio_y = cy + (comp.gpio_y - cy) * ratio
            if hasattr(comp, 'usb2_x'):
                comp.usb2_x = cx + (comp.usb2_x - cx) * ratio
                comp.usb2_y = cy + (comp.usb2_y - cy) * ratio
            if hasattr(comp, 'usb3_x'):
                comp.usb3_x = cx + (comp.usb3_x - cx) * ratio
                comp.usb3_y = cy + (comp.usb3_y - cy) * ratio
            comp.redraw()
            
        self.draw_graph_paper()

    def update_coords(self, event):
        cx = self.app.canvas.winfo_width() // 2
        cy = self.app.canvas.winfo_height() // 2
        rel_x = int((event.x - cx) / self.app.zoom_factor)
        rel_y = int((event.y - cy) / self.app.zoom_factor)
        self.coord_label.config(text=f"X: {rel_x}, Y: {rel_y}")

    def draw_graph_paper(self, event=None):
        self.app.canvas.delete("grid_line")
        w = self.app.canvas.winfo_width()
        h = self.app.canvas.winfo_height()
        cx = w // 2
        cy = h // 2
        
        step_minor = max(5, int(20 * self.app.zoom_factor))
        step_major = max(25, int(100 * self.app.zoom_factor))
        
        for x in range(cx % step_minor, w, step_minor):
            self.app.canvas.create_line(x, 0, x, h, fill="#d6d6d6", width=1, tags="grid_line")
        for y in range(cy % step_minor, h, step_minor):
            self.app.canvas.create_line(0, y, w, y, fill="#d6d6d6", width=1, tags="grid_line")
            
        for x in range(cx % step_major, w, step_major):
            self.app.canvas.create_line(x, 0, x, h, fill="#c0c0c0", width=1, tags="grid_line")
        for y in range(cy % step_major, h, step_major):
            self.app.canvas.create_line(0, y, w, y, fill="#c0c0c0", width=1, tags="grid_line")
            
        self.app.canvas.create_line(cx, 0, cx, h, fill="#888888", width=2, tags="grid_line")
        self.app.canvas.create_line(0, cy, w, cy, fill="#888888", width=2, tags="grid_line")
        
        self.app.canvas.tag_lower("grid_line")

    def add_component(self, name):
        if name not in COMPONENT_REGISTRY: return
        offset = len(self.app.components) * 20
        cls = COMPONENT_REGISTRY[name]["class"]
        
        cx = self.app.canvas.winfo_width() // 2
        cy = self.app.canvas.winfo_height() // 2
        
        if "Raspberry" in name:
            c = cls(self.app.canvas, cx - 200 + offset, cy - 100 + offset)
        elif "Pirate" in name:
            c = cls(self.app.canvas, cx - 200 + offset, cy - 250 + offset)
        else:
            c = cls(self.app.canvas, cx + 50 + offset, cy - 250 + offset)
            
        self.app.components.append(c)
        log_event(f"Component added to workspace: {name}")
        self.save_state()

    def delete_hovered(self, event=None):
        if isinstance(self.app.focus_get(), tk.Text): return
        comp = self.app.hovered_component
        if comp:
            log_event(f"Component erased from workspace: {comp.__class__.__name__}")
            comp.delete()
            self.save_state()

    def save_state(self):
        state = []
        for c in self.app.components:
            name = next((n for n, d in COMPONENT_REGISTRY.items() if d["class"] == c.__class__), None)
            if name:
                comp_state = {
                    "name": name,
                    "x": c.x,
                    "y": c.y,
                    "rotation": getattr(c, 'rotation', 0),
                    "plug_x": getattr(c, 'plug_x', None),
                    "plug_y": getattr(c, 'plug_y', None)
                }
                state.append(comp_state)
        self.app.history_index += 1
        self.app.hardware_history = self.app.hardware_history[:self.app.history_index]
        self.app.hardware_history.append(state)

    def load_state(self, state):
        self.app.connection_manager.clear_all()
        for c in list(self.app.components):
            c.connected_to = None
            c.delete()
        self.app.components = []
        
        for comp_state in state:
            name = comp_state["name"]
            if name in COMPONENT_REGISTRY:
                c = COMPONENT_REGISTRY[name]["class"](self.app.canvas, comp_state["x"], comp_state["y"])
                c.rotation = comp_state["rotation"]
                c.redraw()
                if comp_state.get("plug_x") is not None and getattr(c, 'plug_x', None) is not None:
                    dx = comp_state["plug_x"] - c.plug_x
                    dy = comp_state["plug_y"] - c.plug_y
                    c.canvas.move(c.plug_tag, dx, dy)
                    c.plug_x = comp_state["plug_x"]
                    c.plug_y = comp_state["plug_y"]
                    if hasattr(c, 'update_cable'):
                        c.update_cable()
                self.app.components.append(c)
                
        self.app.connection_manager.reconnect_by_position(self.app.components, threshold=40 * self.app.zoom_factor)

    def undo(self, event=None):
        if isinstance(self.app.focus_get(), tk.Text): return
        if self.app.history_index > 0:
            self.app.history_index -= 1
            self.load_state(self.app.hardware_history[self.app.history_index])
            log_event("Hardware undo performed.")
        return "break"

    def redo(self, event=None):
        if isinstance(self.app.focus_get(), tk.Text): return
        if self.app.history_index < len(self.app.hardware_history) - 1:
            self.app.history_index += 1
            self.load_state(self.app.hardware_history[self.app.history_index])
            log_event("Hardware redo performed.")
        return "break"

    def copy(self, event=None):
        if isinstance(self.app.focus_get(), tk.Text): return
        comp = self.app.hovered_component
        if comp: self.app.copied_component = next((n for n, d in COMPONENT_REGISTRY.items() if d["class"] == comp.__class__), None)
        return "break"

    def cut(self, event=None):
        if isinstance(self.app.focus_get(), tk.Text): return
        self.copy()
        self.delete_hovered()
        return "break"

    def paste(self, event=None):
        if isinstance(self.app.focus_get(), tk.Text): return
        if self.app.copied_component:
            if event and hasattr(event, 'x_root'):
                x, y = event.x_root - self.app.canvas.winfo_rootx(), event.y_root - self.app.canvas.winfo_rooty()
            else:
                x, y = 150, 150
            if x < 0 or y < 0 or x > self.app.canvas.winfo_width() or y > self.app.canvas.winfo_height(): x, y = 50, 50
            c = COMPONENT_REGISTRY[self.app.copied_component]["class"](self.app.canvas, x, y)
            self.app.components.append(c)
            self.save_state()
        return "break"
