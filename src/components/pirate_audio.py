import tkinter as tk
import math
from .base_component import BaseComponent
from .raspberry_pi import RaspberryPi
from . import register_component

@register_component("Pirate Audio (Mic)", color="#1a1a1a")
class PirateAudio(BaseComponent):
    def __init__(self, canvas, x, y):
        super().__init__(canvas, x, y)
        self.draw()
        self.setup_draggable()

    def draw(self):
        # Board: Pirate Audio Dual Mic pHAT
        # Real: 65mm x 30mm → scaled ~4.5x → 290 x 135
        self.w, self.h = 290, 135

        # === Black PCB Board ===
        self._rect(0, 0, self.w, self.h, fill="#1a1a1a", outline="#333333", width=3)

        # === Mounting Holes (4 corners, gold rings) ===
        hole_r = 7
        corners = [(8, 8), (self.w - 8 - hole_r * 2, 8),
                   (8, self.h - 8 - hole_r * 2), (self.w - 8 - hole_r * 2, self.h - 8 - hole_r * 2)]
        for cx, cy in corners:
            self._oval(cx, cy, hole_r * 2, hole_r * 2, fill="#C8B560", outline="#A08830", width=2)
            self._oval(cx + 3, cy + 3, hole_r * 2 - 6, hole_r * 2 - 6, fill="#1a1a1a")

        # === "Pirate" text (white, script/italic, left side) ===
        self._text(65, 42, text="Pirate", fill="white", font=("Georgia", 18, "bold italic"))

        # === "audio" text (gold, below "Pirate") ===
        self._text(72, 68, text="audio", fill="#C8B560", font=("Georgia", 14, "italic"))

        # === Bottom labels: I2S, DUAL MIC, LCD (white rounded rects) ===
        # I2S label
        self._rect(18, 103, 25, 12, fill="#333", outline="white", width=1)
        self._text(30, 109, text="I2S", fill="white", font=("Arial", 5, "bold"))
        # DUAL MIC label
        self._rect(48, 103, 42, 12, fill="#333", outline="white", width=1)
        self._text(69, 109, text="DUAL MIC", fill="white", font=("Arial", 5, "bold"))
        # LCD label
        self._rect(95, 103, 25, 12, fill="#333", outline="white", width=1)
        self._text(107, 109, text="LCD", fill="white", font=("Arial", 5, "bold"))

        # === LCD Screen (1.3" IPS, right side of board) ===
        # Screen housing (dark border)
        self._rect(170, 8, 105, 105, fill="#111111", outline="#333", width=3)
        # Screen inner display area
        self.screen_rect = self._rect(175, 13, 95, 95, fill="black", outline="#222", width=2)
        self.screen_text = self._text(222, 60, text="Off", fill="white", font=("Segoe UI", 9), width=88)

        # === Buttons A, B (left of screen), X, Y (right of screen) ===
        # Button A - top center-left (between text area and screen)
        self._add_btn(148, 12, "A")
        # Button B - bottom center-left
        self._add_btn(148, 95, "B")
        # Button X - top right
        self._add_btn(258, 12, "X")
        # Button Y - bottom right
        self._add_btn(258, 95, "Y")

        # === MIC L (left edge, gold pad with label) ===
        self._rect(-4, 75, 22, 18, fill="#C8B560", outline="#A08830", width=1)
        self._text(7, 84, text="MIC", fill="black", font=("Arial", 5, "bold"))
        self._text(7, 70, text="L", fill="white", font=("Arial", 6, "bold"))

        # === MIC R (right edge, gold pad with label) ===
        self._rect(self.w - 18, 75, 22, 18, fill="#C8B560", outline="#A08830", width=1)
        self._text(self.w - 7, 84, text="MIC", fill="black", font=("Arial", 5, "bold"))
        self._text(self.w - 7, 70, text="R", fill="white", font=("Arial", 6, "bold"))

        # === GPIO Socket (underside, along bottom edge — hidden connector) ===
        self._rect(30, self.h - 4, 230, 8, fill="#1a1a1a", outline="#444")

        self.update_ports()

    def update_ports(self):
        gx, gy = self._rot_pt(145, self.h)
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
