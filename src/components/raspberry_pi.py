from .base_component import BaseComponent

class RaspberryPi(BaseComponent):
    def __init__(self, canvas, x, y):
        super().__init__(canvas, x, y)
        self.draw()
        self.setup_draggable()
        self.components_attached = []

    def draw(self):
        self.w, self.h = 340, 224
        # Main Board
        self._rect(0, 0, self.w, self.h, fill="#006400", outline="#004d00", width=4)
        self._text(170, 30, text="Raspberry Pi 4 Model B", fill="white", font=("Segoe UI", 10, "bold"))
        
        # CPU & RAM
        self._rect(140, 90, 50, 50, fill="#1a1a1a") # CPU
        self._rect(200, 90, 40, 40, fill="#1a1a1a") # RAM
        
        # GPIO Header (Top Edge, right-aligned)
        self._rect(100, 0, 230, 20, fill="black")
        self._text(215, 10, text="40-Pin GPIO", fill="gold", font=("Arial", 7, "bold"))
        
        # Ethernet (Right Edge, top)
        self._rect(310, 30, 50, 60, fill="silver")
        self._text(335, 60, text="ETH", fill="black", font=("Arial", 7, "bold"), angle=270)
        
        # USB Ports (Right Edge, below Ethernet)
        self._rect(310, 100, 50, 50, fill="silver") # USB 3.0 (blue)
        self._rect(310, 160, 50, 50, fill="silver") # USB 2.0 (black)
        self._text(335, 125, text="USB 3.0", fill="blue", font=("Arial", 7, "bold"), angle=270)
        self._text(335, 185, text="USB 2.0", fill="black", font=("Arial", 7, "bold"), angle=270)

        # Bottom Edge Ports (Power, HDMI, Audio)
        self._rect(20, 214, 30, 20, fill="silver") # USB-C Power
        self._text(35, 224, text="PWR", fill="black", font=("Arial", 6))
        
        self._rect(70, 214, 20, 20, fill="silver") # microHDMI 0
        self._text(80, 224, text="H0", fill="black", font=("Arial", 6))
        
        self._rect(105, 214, 20, 20, fill="silver") # microHDMI 1
        self._text(115, 224, text="H1", fill="black", font=("Arial", 6))

        self._rect(150, 214, 20, 20, fill="black") # Audio Jack
        self._text(160, 224, text="AUX", fill="white", font=("Arial", 6))
        
        self.update_ports()

    def update_ports(self):
        gx, gy = self._rot_pt(200, 10)
        self.gpio_x, self.gpio_y = self.x + gx, self.y + gy
        u3x, u3y = self._rot_pt(360, 125)
        self.usb3_x, self.usb3_y = self.x + u3x, self.y + u3y
        u2x, u2y = self._rot_pt(360, 185)
        self.usb2_x, self.usb2_y = self.x + u2x, self.y + u2y

    def on_drag_motion(self, event):
        super().on_drag_motion(event)
        self.update_ports()
