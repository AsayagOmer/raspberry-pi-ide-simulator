from collections import deque
from .base_peripheral import BasePeripheral

class PL011(BasePeripheral):
    """
    PL011 UART (ARM PrimeCell UART) model.
    """
    NAME = "PL011 UART"
    BASE_ADDR = 0xFE201000
    SIZE = 0x1000

    def __init__(self):
        super().__init__()
        self.output_callback = None
        self.input_buffer = deque()
        self.reset()

    def reset(self):
        """Reset the PL011 to its initial state."""
        self.uartdr = 0
        self.uartrsr = 0
        self.uartfr = 0x90  # TXFE (bit 7) and TXFF=0, RXFE=1 (bit 4)
        self.uartibrd = 0
        self.uartfbrd = 0
        self.uartlcr_h = 0
        self.uartcr = 0x0300
        self.uartifls = 0x12
        self.uartimsc = 0
        self.uartris = 0
        self.uartmis = 0
        self.uarticr = 0

    def inject_char(self, ch: int):
        """Inject a character into the receive buffer."""
        self.input_buffer.append(ch)
        self.update_flags()
        self.update_interrupts()

    def update_flags(self):
        """Update the UARTFR flag register based on current state."""
        # RX empty?
        if not self.input_buffer:
            self.uartfr |= (1 << 4)  # Set RXFE
        else:
            self.uartfr &= ~(1 << 4) # Clear RXFE
            
        self.uartfr |= (1 << 7)  # Set TXFE (always empty/ready)
        self.uartfr &= ~(1 << 5) # Clear TXFF
        
    def update_interrupts(self):
        """Update interrupt status and assert IRQ if necessary."""
        # RX RIS (bit 4)
        if not self.input_buffer:
            self.uartris &= ~(1 << 4)
        else:
            self.uartris |= (1 << 4)
            
        self.uartmis = self.uartris & self.uartimsc
        
        # SPI interrupt 57
        if self.uartmis:
            self.assert_irq(57, 1)
        else:
            self.assert_irq(57, 0)

    def read(self, offset: int, size: int) -> int:
        """Read a value from the specified offset."""
        if offset == 0x00:
            if self.input_buffer:
                val = self.input_buffer.popleft()
                self.update_flags()
                self.update_interrupts()
                return val
            return 0
        elif offset == 0x18:
            return self.uartfr
        elif offset == 0x24:
            return self.uartibrd
        elif offset == 0x28:
            return self.uartfbrd
        elif offset == 0x2C:
            return self.uartlcr_h
        elif offset == 0x30:
            return self.uartcr
        elif offset == 0x34:
            return self.uartifls
        elif offset == 0x38:
            return self.uartimsc
        elif offset == 0x3C:
            return self.uartris
        elif offset == 0x40:
            return self.uartmis
        return 0

    def write(self, offset: int, size: int, value: int) -> None:
        """Write a value to the specified offset."""
        if offset == 0x00:
            if self.output_callback:
                self.output_callback(value & 0xFF)
        elif offset == 0x24:
            self.uartibrd = value
        elif offset == 0x28:
            self.uartfbrd = value
        elif offset == 0x2C:
            self.uartlcr_h = value
        elif offset == 0x30:
            self.uartcr = value
        elif offset == 0x34:
            self.uartifls = value
        elif offset == 0x38:
            self.uartimsc = value
            self.update_interrupts()
        elif offset == 0x44:
            self.uarticr = value
            self.uartris &= ~value
            self.update_interrupts()
