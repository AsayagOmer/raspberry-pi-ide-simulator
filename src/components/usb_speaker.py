import math
from .base_component import BaseComponent
from .raspberry_pi import RaspberryPi

class USBSpeaker(BaseComponent):
    def __init__(self, canvas, x, y, app):
        self.app = app
        self.plug_tag = f"plug_{id(self)}"
        self.cable_id = None
        super().__init__(canvas, x, y)
        self.draw()
        self.setup_draggable()
        self.setup_draggable(specific_tag=self.plug_tag) # Make plug draggable separately

    def draw(self):
        self.w, self.h = 120, 150
        # Speaker Body
        self._rect(0, 0, self.w, self.h, fill="#333", outline="#555", width=2)
        self._oval(20, 45, 80, 80, fill="#111")
        self._text(60, 20, text="Mini USB 2.0 external speaker", fill="white", font=("Segoe UI", 7, "bold"), width=110, justify="center")
        
        # USB Cable & Plug
        cx, cy = self._rot_pt(0, 75)
        self.plug_x, self.plug_y = self.x + cx - 100, self.y + cy
        self.cable_id = self.canvas.create_line(self.x+cx, self.y+cy, self.plug_x, self.plug_y, fill="#00bfff", width=4, smooth=True, tags=self.tag)
        self.items.append(self.cable_id)
        
        # Plug rect drawn statically (doesn't rotate with speaker since it's loose)
        self.plug_rect = self.canvas.create_rectangle(self.plug_x-10, self.plug_y-15, self.plug_x+10, self.plug_y+15, fill="#00bfff", tags=self.plug_tag)
        self.items.append(self.plug_rect)

    def update_cable(self):
        cx, cy = self._rot_pt(0, 75)
        self.canvas.coords(self.cable_id, self.x+cx, self.y+cy, self.x+cx-50, self.plug_y+50, self.plug_x, self.plug_y)

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
