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
        # Speaker Body
        self.items.append(self.canvas.create_rectangle(self.x, self.y, self.x+120, self.y+150, fill="#333", outline="#555", width=2, tags=self.tag))
        self.items.append(self.canvas.create_oval(self.x+20, self.y+40, self.x+100, self.y+120, fill="#111", tags=self.tag))
        self.items.append(self.canvas.create_text(self.x+60, self.y+15, text="USB Speaker", fill="white", font=("Segoe UI", 9, "bold"), tags=self.tag))
        
        self.status_text = self.canvas.create_text(self.x+60, self.y+135, text="Disconnected", fill="red", font=("Segoe UI", 8, "bold"), tags=self.tag)
        self.items.append(self.status_text)
        
        # USB Cable & Plug
        self.plug_x, self.plug_y = self.x - 100, self.y + 75
        self.cable_id = self.canvas.create_line(self.x, self.y+75, self.plug_x, self.plug_y, fill="#00bfff", width=4, smooth=True)
        self.items.append(self.cable_id)
        
        self.plug_rect = self.canvas.create_rectangle(self.plug_x-10, self.plug_y-15, self.plug_x+10, self.plug_y+15, fill="#00bfff", tags=self.plug_tag)
        self.items.append(self.plug_rect)

    def update_cable(self):
        self.canvas.coords(self.cable_id, self.x, self.y+75, self.x-50, self.plug_y+50, self.plug_x, self.plug_y)

    def on_drag_motion(self, event):
        item = self.canvas.find_withtag("current")
        if item and self.plug_tag in self.canvas.gettags(item[0]):
            # Dragging Plug
            dx = event.x - self.plug_x
            dy = event.y - self.plug_y
            self.canvas.move(self.plug_tag, dx, dy)
            self.plug_x = event.x
            self.plug_y = event.y
            self.connected_to = None
            self.canvas.itemconfig(self.status_text, text="Disconnected", fill="red")
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
                    if math.hypot(self.plug_x - comp.usb_x, self.plug_y - comp.usb_y) < 40:
                        dx = comp.usb_x - self.plug_x
                        dy = comp.usb_y - self.plug_y
                        self.canvas.move(self.plug_tag, dx, dy)
                        self.plug_x += dx; self.plug_y += dy
                        self.connected_to = comp
                        self.canvas.itemconfig(self.status_text, text="Connected", fill="#888")
                        break
            self.update_cable()
