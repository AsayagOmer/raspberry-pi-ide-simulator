import tkinter as tk
from .base_component import BaseComponent
from . import register_component

@register_component("Raspberry Pi 4", color="#006400")
class RaspberryPi(BaseComponent):
    def __init__(self, canvas, x, y):
        super().__init__(canvas, x, y)
        self.draw()
        self.setup_draggable()
        self.components_attached = []

    def draw(self):
        # Board dimensions scaled to match the reference diagram proportions
        # Real RPi4: 85mm x 56mm → scaled ~5x → 425 x 280
        self.w, self.h = 425, 280

        # === PCB Board ===
        self._rect(0, 0, self.w, self.h, fill="#2E8B2E", outline="#1B5E1B", width=4)

        # === Mounting Holes (4 corners, gold circles) ===
        hole_r = 8
        # Top-left
        self._oval(12, 12, hole_r * 2, hole_r * 2, fill="#C8B560", outline="#A08830", width=2)
        self._oval(16, 16, hole_r, hole_r, fill="#2E8B2E", outline="#1B5E1B")
        # Top-right
        self._oval(self.w - 12 - hole_r * 2, 12, hole_r * 2, hole_r * 2, fill="#C8B560", outline="#A08830", width=2)
        self._oval(self.w - 12 - hole_r * 2 + 4, 16, hole_r, hole_r, fill="#2E8B2E", outline="#1B5E1B")
        # Bottom-left
        self._oval(12, self.h - 12 - hole_r * 2, hole_r * 2, hole_r * 2, fill="#C8B560", outline="#A08830", width=2)
        self._oval(16, self.h - 12 - hole_r * 2 + 4, hole_r, hole_r, fill="#2E8B2E", outline="#1B5E1B")
        # Bottom-right
        self._oval(self.w - 12 - hole_r * 2, self.h - 12 - hole_r * 2, hole_r * 2, hole_r * 2, fill="#C8B560", outline="#A08830", width=2)
        self._oval(self.w - 12 - hole_r * 2 + 4, self.h - 12 - hole_r * 2 + 4, hole_r, hole_r, fill="#2E8B2E", outline="#1B5E1B")

        # === GPIO Header (40-pin, 2x20, top edge, spans left-center) ===
        gpio_x, gpio_y = 60, -4
        gpio_w, gpio_h = 230, 22
        self._rect(gpio_x, gpio_y, gpio_w, gpio_h, fill="#1a1a1a", outline="#333")
        # Draw pin dots (2 rows of 20)
        for col in range(20):
            for row in range(2):
                px = gpio_x + 8 + col * 11
                py = gpio_y + 5 + row * 10
                self._oval(px, py, 4, 4, fill="#C8B560")
        # GPIO Label
        self._rect(gpio_x + 5, gpio_y + gpio_h + 2, 40, 14, fill="#E8E0C0", outline="#999")
        self._text(gpio_x + 25, gpio_y + gpio_h + 9, text="GPIO", fill="black", font=("Arial", 6, "bold"))

        # === Board Title Text ===
        self._text(250, 42, text="Raspberry Pi 4 Model B", fill="white", font=("Segoe UI", 10, "bold"))
        self._text(250, 56, text="© Raspberry Pi 2018", fill="white", font=("Segoe UI", 7))

        # === PoE Header (J14, top-right area) ===
        poe_x, poe_y = 340, 30
        self._rect(poe_x, poe_y, 24, 24, fill="#1a1a1a", outline="#555")
        for pr in range(2):
            for pc in range(2):
                self._oval(poe_x + 4 + pc * 12, poe_y + 4 + pr * 12, 6, 6, fill="#C8B560")
        self._text(poe_x + 12, poe_y - 6, text="PoE", fill="white", font=("Arial", 5))
        self._text(poe_x + 12, poe_y + 30, text="J14", fill="white", font=("Arial", 5))

        # === Ethernet Port (top-right, extends past board edge) ===
        eth_x, eth_y = 375, 10
        eth_w, eth_h = 55, 60
        self._rect(eth_x, eth_y, eth_w, eth_h, fill="#C0C0C0", outline="#888", width=2)
        self._rect(eth_x + 5, eth_y + 5, eth_w - 10, eth_h - 15, fill="#A0A0A0", outline="#777")
        self._text(eth_x + eth_w // 2, eth_y - 6, text="Ethernet", fill="white", font=("Arial", 7, "bold"))

        # === USB 3.0 Ports (right side, stacked, blue interior) ===
        usb3_x, usb3_y = 375, 85
        usb3_w, usb3_h = 55, 60
        # USB 3.0 housing
        self._rect(usb3_x, usb3_y, usb3_w, usb3_h, fill="#C0C0C0", outline="#888", width=2)
        # Top USB 3.0 slot
        self._rect(usb3_x + 8, usb3_y + 6, usb3_w - 16, 20, fill="#2050A0")
        # Bottom USB 3.0 slot
        self._rect(usb3_x + 8, usb3_y + 32, usb3_w - 16, 20, fill="#2050A0")
        self._text(usb3_x + usb3_w + 3, usb3_y + usb3_h // 2, text="USB3", fill="white", font=("Arial", 6, "bold"), angle=270)

        # === USB 2.0 Ports (right side, below USB 3.0, black interior) ===
        usb2_x, usb2_y = 375, 160
        usb2_w, usb2_h = 55, 60
        # USB 2.0 housing
        self._rect(usb2_x, usb2_y, usb2_w, usb2_h, fill="#C0C0C0", outline="#888", width=2)
        # Top USB 2.0 slot
        self._rect(usb2_x + 8, usb2_y + 6, usb2_w - 16, 20, fill="#1a1a1a")
        # Bottom USB 2.0 slot
        self._rect(usb2_x + 8, usb2_y + 32, usb2_w - 16, 20, fill="#1a1a1a")
        self._text(usb2_x + usb2_w + 3, usb2_y + usb2_h // 2, text="USB2", fill="white", font=("Arial", 6, "bold"), angle=270)

        # === SoC / CPU (large silver-bordered chip, center-left) ===
        cpu_x, cpu_y = 135, 90
        cpu_sz = 65
        self._rect(cpu_x - 4, cpu_y - 4, cpu_sz + 8, cpu_sz + 8, fill="#B0B0B0", outline="#888", width=2)
        self._rect(cpu_x, cpu_y, cpu_sz, cpu_sz, fill="#808080")

        # === RAM chip (black, right of CPU) ===
        self._rect(230, 95, 55, 45, fill="#1a1a1a")

        # === Wireless/Bluetooth chip (smaller, center-right) ===
        self._rect(305, 90, 35, 35, fill="#1a1a1a")

        # === Small black chip (bottom-left, near power) ===
        self._rect(40, 220, 22, 22, fill="#1a1a1a")

        # === Raspberry Pi Logo (text representation, left-center) ===
        self._text(95, 150, text="🍓", fill="white", font=("Segoe UI", 18))
        self._text(95, 175, text="Raspberry Pi", fill="white", font=("Arial", 6))

        # === DISPLAY (DSI) Connector (left edge, vertical black strip) ===
        dsi_x, dsi_y = -5, 75
        self._rect(dsi_x, dsi_y, 14, 80, fill="#1a1a1a", outline="#333")
        self._text(dsi_x + 7, dsi_y + 40, text="DISPLAY", fill="white", font=("Arial", 5), angle=90)

        # === RUN / GLOBAL_EN Headers (J2, left side, below DSI) ===
        j2_x, j2_y = 40, 192
        self._rect(j2_x, j2_y, 50, 12, fill="#CC6633", outline="#995522")
        # Small dots for pads
        for i in range(5):
            self._oval(j2_x + 4 + i * 9, j2_y + 2, 6, 6, fill="#DD8844")
        self._text(j2_x, j2_y - 7, text="RUN", fill="white", font=("Arial", 5))
        self._text(j2_x + 35, j2_y - 7, text="GLOBAL_EN", fill="white", font=("Arial", 5))
        self._text(j2_x + 25, j2_y + 18, text="J2", fill="white", font=("Arial", 5))

        # === CAMERA (CSI) Connector (center-bottom, vertical strip) ===
        csi_x, csi_y = 260, 200
        self._rect(csi_x, csi_y, 14, 55, fill="#1a1a1a", outline="#333")
        self._text(csi_x + 7, csi_y + 27, text="CAMERA", fill="white", font=("Arial", 5), angle=90)

        # === "HDMI" large label (center-bottom) ===
        self._text(210, 235, text="HDMI", fill="white", font=("Segoe UI", 20, "bold"))

        # === Bottom Edge Ports ===

        # USB-C Power In (bottom-left)
        pwr_x, pwr_y = 55, self.h - 18
        self._rect(pwr_x, pwr_y, 28, 22, fill="#C0C0C0", outline="#888")
        self._text(pwr_x + 14, pwr_y - 7, text="Power in", fill="white", font=("Arial", 5))

        # Micro HDMI 0
        hdmi0_x, hdmi0_y = 120, self.h - 16
        self._rect(hdmi0_x, hdmi0_y, 18, 18, fill="#C0C0C0", outline="#888")
        self._rect(hdmi0_x + 5, hdmi0_y + 18, 8, 6, fill="#C0C0C0")
        self._text(hdmi0_x + 9, hdmi0_y - 7, text="HDMI 0", fill="white", font=("Arial", 5))

        # Micro HDMI 1
        hdmi1_x, hdmi1_y = 170, self.h - 16
        self._rect(hdmi1_x, hdmi1_y, 18, 18, fill="#C0C0C0", outline="#888")
        self._rect(hdmi1_x + 5, hdmi1_y + 18, 8, 6, fill="#C0C0C0")
        self._text(hdmi1_x + 9, hdmi1_y - 7, text="HDMI 1", fill="white", font=("Arial", 5))

        # AV (3.5mm Audio/Video Jack)
        av_x, av_y = 290, self.h - 18
        self._rect(av_x, av_y, 22, 22, fill="#C0C0C0", outline="#888")
        self._oval(av_x + 5, av_y + 5, 12, 12, fill="#888888")
        self._text(av_x + 11, av_y - 7, text="AV", fill="white", font=("Arial", 5))

        self.update_ports()

    def update_ports(self):
        # GPIO connection point: center of the GPIO header
        gx, gy = self._rot_pt(175, 8)
        self.gpio_x, self.gpio_y = self.x + gx, self.y + gy
        # USB 3.0 connection point: center of USB 3.0 block
        u3x, u3y = self._rot_pt(402, 115)
        self.usb3_x, self.usb3_y = self.x + u3x, self.y + u3y
        # USB 2.0 connection point: center of USB 2.0 block
        u2x, u2y = self._rot_pt(402, 190)
        self.usb2_x, self.usb2_y = self.x + u2x, self.y + u2y

    def on_drag_motion(self, event):
        super().on_drag_motion(event)
        self.update_ports()
