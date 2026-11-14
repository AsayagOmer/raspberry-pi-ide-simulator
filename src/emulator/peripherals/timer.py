from .base_peripheral import BasePeripheral

class ARMGenericTimer(BasePeripheral):
    """
    ARM Generic Timer model.
    Accessed via system registers, not memory-mapped MMIO.
    """
    NAME = 'ARM Generic Timer'
    BASE_ADDR = 0
    SIZE = 0
    
    def __init__(self):
        super().__init__()
        self.reset()
        
    def reset(self):
        """Reset the timer to its initial state."""
        self.cntpct = 0
        self.cntp_cval = 0
        self.cntp_ctl = 0
        
    def tick(self, elapsed_ns: int):
        """Advance the counter by the elapsed nanoseconds."""
        # 54 MHz = 54 ticks per microsecond = 0.054 ticks per nanosecond
        # Using integer math to avoid drift: (ns * 54) / 1000
        ticks = (elapsed_ns * 54) // 1000
        self.cntpct += ticks
        self.check_interrupt()
        
    def check_interrupt(self):
        """Check if an interrupt should be asserted."""
        enable = self.cntp_ctl & 1
        imask = (self.cntp_ctl >> 1) & 1
        
        condition_met = self.cntpct >= self.cntp_cval
        
        if condition_met:
            self.cntp_ctl |= (1 << 2)  # Set ISTATUS
        else:
            self.cntp_ctl &= ~(1 << 2) # Clear ISTATUS
            
        if condition_met and enable and not imask:
            self.assert_irq(30, 1)  # PPI interrupt 30
        else:
            self.assert_irq(30, 0)
            
    def read_sysreg(self, name: str) -> int:
        """Read a system register by name."""
        if name == 'CNTPCT':
            return self.cntpct
        elif name == 'CNTP_CVAL':
            return self.cntp_cval
        elif name == 'CNTP_CTL':
            return self.cntp_ctl
        elif name == 'CNTP_TVAL':
            return max(0, self.cntp_cval - self.cntpct)
        return 0
        
    def write_sysreg(self, name: str, value: int) -> None:
        """Write a value to a system register by name."""
        if name == 'CNTP_CVAL':
            self.cntp_cval = value
            self.check_interrupt()
        elif name == 'CNTP_CTL':
            # Preserve reserved bits, only update ENABLE and IMASK
            self.cntp_ctl = (self.cntp_ctl & ~(3)) | (value & 3)
            self.check_interrupt()
        elif name == 'CNTP_TVAL':
            self.cntp_cval = self.cntpct + value
            self.check_interrupt()
            
    def read(self, offset: int, size: int) -> int:
        """MMIO read (not applicable)."""
        return 0
        
    def write(self, offset: int, size: int, value: int) -> None:
        """MMIO write (not applicable)."""
        pass
