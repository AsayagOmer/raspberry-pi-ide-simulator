from .base_component import BaseComponent

class RaspberryPi(BaseComponent):
    def __init__(self, canvas, x, y):
        super().__init__(canvas, x, y)
        self.draw()
        self.setup_draggable()
        self.components_attached = []

    def draw(self):
        # Main Board (Scale: ~4x, 85mm x 56mm -> 340x224)
        self.w, self.h = 340, 224
        self.items.append(self.canvas.create_rectangle(self.x, self.y, self.x+self.w, self.y+self.h, fill="#006400", outline="#004d00", width=4, tags=self.tag))
        self.items.append(self.canvas.create_text(self.x+170, self.y+30, text="Raspberry Pi 4 Model B", fill="white", font=("Segoe UI", 10, "bold"), tags=self.tag))
        
        # CPU & RAM
        self.items.append(self.canvas.create_rectangle(self.x+140, self.y+90, self.x+190, self.y+140, fill="#1a1a1a", tags=self.tag)) # CPU
        self.items.append(self.canvas.create_rectangle(self.x+200, self.y+90, self.x+240, self.y+130, fill="#1a1a1a", tags=self.tag)) # RAM
        
        # GPIO Header (Top Edge, right-aligned)
        self.gpio_x, self.gpio_y = self.x + 200, self.y + 10
        self.items.append(self.canvas.create_rectangle(self.x+100, self.y, self.x+330, self.y+20, fill="black", tags=self.tag))
        self.items.append(self.canvas.create_text(self.x+215, self.y+10, text="40-Pin GPIO", fill="gold", font=("Arial", 7, "bold"), tags=self.tag))
        
        # Ethernet (Right Edge, top)
        self.items.append(self.canvas.create_rectangle(self.x+310, self.y+30, self.x+360, self.y+90, fill="silver", tags=self.tag))
        self.items.append(self.canvas.create_text(self.x+335, self.y+60, text="ETH", fill="black", font=("Arial", 7, "bold"), tags=self.tag))
        
        # USB Ports (Right Edge, below Ethernet)
        self.usb_x, self.usb_y = self.x + 360, self.y + 120
        self.items.append(self.canvas.create_rectangle(self.x+310, self.y+100, self.x+360, self.y+150, fill="silver", tags=self.tag)) # USB 3.0 (blue)
        self.items.append(self.canvas.create_rectangle(self.x+310, self.y+160, self.x+360, self.y+210, fill="silver", tags=self.tag)) # USB 2.0 (black)
        self.items.append(self.canvas.create_text(self.x+335, self.y+125, text="USB 3.0", fill="blue", font=("Arial", 7, "bold"), tags=self.tag))
        self.items.append(self.canvas.create_text(self.x+335, self.y+185, text="USB 2.0", fill="black", font=("Arial", 7, "bold"), tags=self.tag))

        # Bottom Edge Ports (Power, HDMI, Audio)
        self.items.append(self.canvas.create_rectangle(self.x+20, self.y+214, self.x+50, self.y+234, fill="silver", tags=self.tag)) # USB-C Power
        self.items.append(self.canvas.create_text(self.x+35, self.y+224, text="PWR", fill="black", font=("Arial", 6), tags=self.tag))
        
        self.items.append(self.canvas.create_rectangle(self.x+70, self.y+214, self.x+90, self.y+234, fill="silver", tags=self.tag)) # microHDMI 0
        self.items.append(self.canvas.create_text(self.x+80, self.y+224, text="H0", fill="black", font=("Arial", 6), tags=self.tag))
        
        self.items.append(self.canvas.create_rectangle(self.x+105, self.y+214, self.x+125, self.y+234, fill="silver", tags=self.tag)) # microHDMI 1
        self.items.append(self.canvas.create_text(self.x+115, self.y+224, text="H1", fill="black", font=("Arial", 6), tags=self.tag))

        self.items.append(self.canvas.create_rectangle(self.x+150, self.y+214, self.x+170, self.y+234, fill="black", tags=self.tag)) # Audio Jack
        self.items.append(self.canvas.create_text(self.x+160, self.y+224, text="AUX", fill="white", font=("Arial", 6), tags=self.tag))

    def on_drag_motion(self, event):
        super().on_drag_motion(event)
        self.gpio_x, self.gpio_y = self.x + 200, self.y + 10
        self.usb_x, self.usb_y = self.x + 360, self.y + 120
