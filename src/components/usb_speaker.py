import math
from .base_component import BaseComponent
from .raspberry_pi import RaspberryPi
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
        self.w, self.h = 160, 60
        
        # Outer Black Shell (Pill shape = left circle + middle rect + right circle)
        self._oval(0, 0, 60, 60, fill="#111111", outline="#333", width=2)
        self._oval(100, 0, 60, 60, fill="#111111", outline="#333", width=2)
        self._rect(30, 0, 100, 60, fill="#111111", outline="")
        self._rect(30, 0, 100, 60, outline="#333", width=2) # top/bottom borders
        self._rect(29, 2, 102, 58, fill="#111111", outline="") # clean up internal overlap
        
        # Inner Silver Grille
        self._oval(5, 5, 50, 50, fill="#c0c0c0", outline="")
        self._oval(105, 5, 50, 50, fill="#c0c0c0", outline="")
        self._rect(30, 5, 100, 50, fill="#c0c0c0", outline="")
        
        # Dual Speaker Cones inside Grille
        self._oval(10, 10, 40, 40, fill="#1a1a1a", outline="#444", width=1)
        self._oval(110, 10, 40, 40, fill="#1a1a1a", outline="#444", width=1)
        
        # Inner cone details
        self._oval(23, 23, 14, 14, fill="#333")
        self._oval(123, 23, 14, 14, fill="#333")

        # Initialize plug position only if it doesn't exist (prevents reset on rotation)
        if not hasattr(self, 'plug_x'):
            cx, cy = self._rot_pt(80, 0)
            self.plug_x, self.plug_y = self.x - 40, self.y + 30

        # Draw Cable
        self.cable_id = self.canvas.create_line(0, 0, 0, 0, fill="#111111", width=3, smooth=True, tags=self.tag)
        self.items.append(self.cable_id)

        # Draw USB Plug
        self.plug_metal = self.canvas.create_rectangle(self.plug_x-6, self.plug_y-25, self.plug_x+6, self.plug_y-10, fill="#C0C0C0", tags=self.plug_tag)
        self.plug_body = self.canvas.create_rectangle(self.plug_x-10, self.plug_y-10, self.plug_x+10, self.plug_y+15, fill="#111111", tags=self.plug_tag)
        self.items.extend([self.plug_metal, self.plug_body])
        
        self.update_cable()

    def update_cable(self):
        cx, cy = self._rot_pt(80, 0)
        # Bezier curve for the cable
        self.canvas.coords(
            self.cable_id, 
            self.x + cx, self.y + cy, 
            self.x + cx - 50, self.y + cy - 60, 
            self.plug_x - 30, self.plug_y + 40, 
            self.plug_x, self.plug_y + 10
        )

    def delete(self):
        if self.connected_to is not None:
            with open("hardware.log", "a") as f: f.write("Mini USB 2.0 external speaker is disconnected from USB 2.0 Port\n")
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
                self.connected_to = None
                with open("hardware.log", "a") as f: f.write("Mini USB 2.0 external speaker is disconnected from USB 2.0 Port\n")
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
            # Snap plug to RPi USB
            for comp in self.app.components:
                if isinstance(comp, RaspberryPi):
                    if math.hypot(self.plug_x - comp.usb2_x, self.plug_y - comp.usb2_y) < 40:
                        dx = comp.usb2_x - self.plug_x
                        dy = comp.usb2_y - self.plug_y
                        self.canvas.move(self.plug_tag, dx, dy)
                        self.plug_x += dx; self.plug_y += dy
                        if self.connected_to != comp:
                            self.connected_to = comp
                            with open("hardware.log", "a") as f: f.write("Mini USB 2.0 external speaker is connected to USB 2.0 Port\n")
                        break
            self.update_cable()

