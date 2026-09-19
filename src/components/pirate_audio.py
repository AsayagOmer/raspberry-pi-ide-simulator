import tkinter as tk
import math
from .base_component import BaseComponent
from .raspberry_pi import RaspberryPi

class PirateAudio(BaseComponent):
    def __init__(self, canvas, x, y, app):
        self.app = app
        super().__init__(canvas, x, y)
        self.draw()
        self.setup_draggable()

    def draw(self):
        # Board (Scale: ~4x, 65mm x 30mm -> 260x120 pHAT)
        self.w, self.h = 260, 120
        self.items.append(self.canvas.create_rectangle(self.x, self.y, self.x+self.w, self.y+self.h, fill="#1c3b57", outline="#ffffff", width=2, tags=self.tag))
        self.items.append(self.canvas.create_text(self.x+130, self.y+15, text="Pirate Audio (pHAT)", fill="white", font=("Segoe UI", 9, "bold"), tags=self.tag))
        
        # Screen (1.3" IPS -> ~90x90 square in the center)
        self.screen_rect = self.canvas.create_rectangle(self.x+85, self.y+20, self.x+175, self.y+110, fill="black", outline="#444", width=4, tags=self.tag)
        self.items.append(self.screen_rect)
        
        self.screen_text = self.canvas.create_text(self.x+130, self.y+65, text="Off", fill="white", font=("Segoe UI", 12), tags=self.tag)
        self.items.append(self.screen_text)

        # Buttons (A, B on Left. X, Y on Right of screen)
        self._add_btn(self.x+10, self.y+20, "A")
        self._add_btn(self.x+10, self.y+80, "B")
        self._add_btn(self.x+210, self.y+20, "X")
        self._add_btn(self.x+210, self.y+80, "Y")
        
        # Line-out Jack (Bottom edge, near right)
        self.items.append(self.canvas.create_rectangle(self.x+180, self.y+115, self.x+200, self.y+130, fill="gold", tags=self.tag))
        self.items.append(self.canvas.create_text(self.x+190, self.y+122, text="AUX", fill="black", font=("Arial", 6), tags=self.tag))

        # GPIO Socket (Header aligns with Pi's GPIO, top edge underneath)
        self.items.append(self.canvas.create_rectangle(self.x+30, self.y-5, self.x+230, self.y+5, fill="black", tags=self.tag))
        self.items.append(self.canvas.create_text(self.x+130, self.y, text="GPIO Socket (Underside)", fill="white", font=("Arial", 6), tags=self.tag))
        self.socket_x, self.socket_y = self.x + 130, self.y

    def _add_btn(self, bx, by, key):
        btn = tk.Button(self.canvas, text=key, font=("Segoe UI", 7, "bold"), width=2, height=1, bg="#d3d3d3", cursor="hand2")
        self.items.append(self.canvas.create_window(bx, by, anchor=tk.NW, window=btn, tags=self.tag))
        btn.bind("<ButtonPress-1>", lambda e: self.app.button_states.update({key: True}))
        btn.bind("<ButtonRelease-1>", lambda e: self.app.button_states.update({key: False}))

    def on_drag_motion(self, event):
        super().on_drag_motion(event)
        self.socket_x, self.socket_y = self.x + 130, self.y
        self.connected_to = None

    def on_drag_stop(self, event):
        # Snap to RPi GPIO
        for comp in self.app.components:
            if isinstance(comp, RaspberryPi):
                if math.hypot(self.socket_x - comp.gpio_x, self.socket_y - comp.gpio_y) < 40:
                    dx = comp.gpio_x - self.socket_x
                    dy = comp.gpio_y - self.socket_y
                    self.canvas.move(self.tag, dx, dy)
                    self.x += dx; self.y += dy
                    self.socket_x += dx; self.socket_y += dy
                    self.connected_to = comp
                    break
