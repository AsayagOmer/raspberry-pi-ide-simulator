import os
from .base_component import BaseComponent
from . import register_component

@register_component("Mini USB 2.0 external speaker", color="#111111")
class USBSpeaker(BaseComponent):
    def __init__(self, canvas, x, y):
        self.plug_tag = f"plug_{id(self)}"
        self.cable_id = None
        super().__init__(canvas, x, y)
        self.draw()
        self.setup_draggable()
        self.setup_draggable(specific_tag=self.plug_tag)

    def draw(self):
        # Physically accurate proportions based on reference image: 
        # ~64mm wide x ~32mm high. Using 5x pixel scale: 320 x 160.
        self.w, self.h = 320, 160
        
        # Outer Black Shell (Pill shape)
        self._oval(0, 0, 160, 160, fill="#111111", outline="#333", width=2)
        self._oval(160, 0, 160, 160, fill="#111111", outline="#333", width=2)
        self._rect(80, 0, 160, 160, fill="#111111", outline="")
        self._rect(80, 0, 160, 160, outline="#333", width=2) # top/bottom borders
        self._rect(79, 2, 162, 156, fill="#111111", outline="") # clean up internal overlap
        
        # Inner Silver Grille (inset by 12)
        self._oval(12, 12, 136, 136, fill="#c0c0c0", outline="")
        self._oval(172, 12, 136, 136, fill="#c0c0c0", outline="")
        self._rect(80, 12, 160, 136, fill="#c0c0c0", outline="")
        
        # Dual Speaker Cones (inset by 12 more, diam = 112)
        self._oval(24, 24, 112, 112, fill="#1a1a1a", outline="#444", width=2)
        self._oval(184, 24, 112, 112, fill="#1a1a1a", outline="#444", width=2)
        
        # Inner cone details (size=36, centered)
        self._oval(62, 62, 36, 36, fill="#333")
        self._oval(222, 62, 36, 36, fill="#333")

        # Initialize plug position only if it doesn't exist
        z = getattr(self.app, 'zoom_factor', 1.0)
        if not hasattr(self, 'plug_x'):
            cx, cy = self._rot_pt(160, 0)
            self.plug_x, self.plug_y = self.x + cx*z - 60*z, self.y + cy*z + 120*z

        # Draw Cable
        self.cable_id = self.canvas.create_line(0, 0, 0, 0, fill="#111111", width=5, smooth=True, tags=self.tag)
        self.items.append(self.cable_id)

        # Draw enlarged USB Plug (to accurately fit into RPi's ~39x20 slots)
        px, py = self.plug_x, self.plug_y
        self.plug_metal = self.canvas.create_rectangle(
            px-17*z, py-25*z, px+17*z, py, 
            fill="#C0C0C0", tags=self.plug_tag
        )
        self.plug_body = self.canvas.create_rectangle(
            px-22*z, py, px+22*z, py+40*z, 
            fill="#111111", tags=self.plug_tag
        )
        self.items.extend([self.plug_metal, self.plug_body])
        
        self.update_cable()

    def update_cable(self):
        cx, cy = self._rot_pt(160, 0)
        z = getattr(self.app, 'zoom_factor', 1.0)
        # Bezier curve for the thicker cable
        self.canvas.coords(
            self.cable_id, 
            self.x + cx*z, self.y + cy*z, 
            self.x + cx*z - 80*z, self.y + cy*z - 100*z, 
            self.plug_x - 50*z, self.plug_y + 80*z, 
            self.plug_x, self.plug_y + 40*z
        )

    def get_ports(self):
        return [
            {"name": "usb_plug", "direction": "out", "x": self.plug_x, "y": self.plug_y},
        ]

    def snap_port_to(self, port_name, target_x, target_y):
        """Move only the USB plug so it lands at (target_x, target_y)."""
        if port_name == "usb_plug":
            dx = target_x - self.plug_x
            dy = target_y - self.plug_y
            self.canvas.move(self.plug_tag, dx, dy)
            self.plug_x = target_x
            self.plug_y = target_y
            self.update_cable()

    def delete(self):
        cm = getattr(self.app, 'connection_manager', None)
        if cm:
            cm.disconnect(self)
        elif self.connected_to is not None:
            with open(os.path.join("logs", "hardware.log"), "a") as f: f.write("Mini USB 2.0 external speaker is disconnected from USB 2.0 Port\n")
        super().delete()

    def on_drag_motion(self, event):
        item = self.canvas.find_withtag("current")
        if item and self.plug_tag in self.canvas.gettags(item[0]):
            # Dragging Plug
            dx = event.x - self.plug_x
            dy = event.y - self.plug_y
            self.canvas.move(self.plug_tag, dx, dy)
            self.plug_x = event.x
            self.plug_y = event.y
            if self.connected_to is not None:
                cm = getattr(self.app, 'connection_manager', None)
                if cm:
                    cm.disconnect(self)
                else:
                    self.connected_to = None
                    with open(os.path.join("logs", "hardware.log"), "a") as f: f.write("Mini USB 2.0 external speaker is disconnected from USB 2.0 Port\n")
        else:
            # Dragging Speaker Body
            dx = event.x - self.drag_x
            dy = event.y - self.drag_y
            
            # If the plug is not connected, drag it along with the speaker so it doesn't get left behind!
            if self.connected_to is None:
                self.canvas.move(self.plug_tag, dx, dy)
                self.plug_x += dx
                self.plug_y += dy
                
            super().on_drag_motion(event)
            
        self.update_cable()

    def on_drag_stop(self, event):
        item = self.canvas.find_withtag("current")
        if item and self.plug_tag in self.canvas.gettags(item[0]):
            cm = getattr(self.app, 'connection_manager', None)
            if cm:
                cm.try_connect(self, self.app.components,
                               snap_threshold=40,
                               zoom=getattr(self.app, 'zoom_factor', 1.0))
            self.update_cable()

