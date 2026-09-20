import tkinter as tk
import math
from .base_component import BaseComponent
from .raspberry_pi import RaspberryPi
from . import register_component

@register_component("Pirate Audio (Mic)", color="#1c3b57")
class PirateAudio(BaseComponent):
    def __init__(self, canvas, x, y):
        super().__init__(canvas, x, y)
        self.draw()
        self.setup_draggable()

    def draw(self):
        # Board (Scale: ~4x, 65mm x 30mm -> 260x120 pHAT)
        self.w, self.h = 260, 120
        self._rect(0, 0, self.w, self.h, fill="#1c3b57", outline="#ffffff", width=2)
        self._text(130, 10, text="Pirate Audio (pHAT)", fill="white", font=("Segoe UI", 7, "bold"))
        
        # Screen (1.3" IPS -> ~90x90 square in the center)
        self.screen_rect = self._rect(85, 20, 90, 90, fill="black", outline="#444", width=4)
        self.screen_text = self._text(130, 65, text="Off", fill="white", font=("Segoe UI", 8), width=85)

        # Buttons (A, B on Left. X, Y on Right of screen)
        self._add_btn(10, 20, "A")
        self._add_btn(10, 80, "B")
        self._add_btn(210, 20, "X")
        self._add_btn(210, 80, "Y")
        
        # Dual Mics (small gold circles)
        self._oval(60, 20, 10, 10, fill="gold")
        self._text(65, 15, text="MIC1", fill="gold", font=("Arial", 5))
        self._oval(190, 20, 10, 10, fill="gold")
        self._text(195, 15, text="MIC2", fill="gold", font=("Arial", 5))

        # GPIO Socket (Header aligns with Pi's GPIO, top edge underneath)
        self._rect(30, -5, 200, 10, fill="black")
        self._text(130, 0, text="GPIO Socket (Underside)", fill="white", font=("Arial", 6))
        
        self.update_ports()

    def update_ports(self):
        gx, gy = self._rot_pt(130, 0)
        self.socket_x, self.socket_y = self.x + gx, self.y + gy

    def delete(self):
        if self.connected_to is not None:
            with open("hardware.log", "a") as f: f.write("Pirate Audio is disconnected from GPIO Header\n")
        super().delete()

    def _add_btn(self, bx, by, key):
        btn = tk.Button(self.canvas, text=key, font=("Segoe UI", 7, "bold"), width=2, height=1, bg="#d3d3d3", cursor="hand2")
        self._window(bx, by, anchor=tk.NW, window=btn)
        btn.bind("<ButtonPress-1>", lambda e: self.app.button_states.update({key: True}))
        btn.bind("<ButtonRelease-1>", lambda e: self.app.button_states.update({key: False}))

    def on_drag_motion(self, event):
        super().on_drag_motion(event)
        self.update_ports()
        if self.connected_to is not None:
            self.connected_to = None
            with open("hardware.log", "a") as f: f.write("Pirate Audio is disconnected from GPIO Header\n")

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
                    if self.connected_to != comp:
                        self.connected_to = comp
                        with open("hardware.log", "a") as f: f.write("Pirate Audio is connected to GPIO Header\n")
                    break
