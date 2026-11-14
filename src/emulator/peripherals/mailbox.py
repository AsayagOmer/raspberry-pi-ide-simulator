import struct
from .base_peripheral import BasePeripheral

class Mailbox(BasePeripheral):
    """
    VideoCore Firmware Mailbox model.
    """
    NAME = "VideoCore Firmware Mailbox"
    BASE_ADDR = 0xFE00B880
    SIZE = 0x40

    def __init__(self):
        super().__init__()
        self.memory_read_callback = None
        self.memory_write_callback = None
        self.reset()

    def reset(self):
        """Reset the Mailbox to its initial state."""
        self.mbox_read = 0
        self.mbox_peek = 0
        self.mbox_sender = 0
        self.mbox_status = 0x40000000  # EMPTY (bit 30), FULL (bit 31)=0
        self.mbox_config = 0
        self.responses = []

        self.fb_width = 0
        self.fb_height = 0
        self.fb_depth = 0
        self.fb_x_offset = 0
        self.fb_y_offset = 0

    def read(self, offset: int, size: int) -> int:
        """Read a value from the specified offset."""
        if offset == 0x00:
            if self.responses:
                val = self.responses.pop(0)
                if not self.responses:
                    self.mbox_status |= 0x40000000  # EMPTY
                return val
            return 0
        elif offset == 0x10:
            if self.responses:
                return self.responses[0]
            return 0
        elif offset == 0x14:
            return self.mbox_sender
        elif offset == 0x18:
            return self.mbox_status
        elif offset == 0x1C:
            return self.mbox_config
        return 0

    def write(self, offset: int, size: int, value: int) -> None:
        """Write a value to the specified offset."""
        if offset == 0x20:
            channel = value & 0xF
            data = value & ~0xF
            
            if channel == 8:
                self.process_property_tags(data)
                
            self.responses.append(value)
            self.mbox_status &= ~0x40000000  # Not EMPTY
        elif offset == 0x1C:
            self.mbox_config = value

    def read_mem32(self, addr: int) -> int:
        """Helper to read 32-bit value from physical memory."""
        if self.memory_read_callback:
            data = self.memory_read_callback(addr, 4)
            return struct.unpack('<I', data)[0]
        return 0

    def write_mem32(self, addr: int, val: int) -> None:
        """Helper to write 32-bit value to physical memory."""
        if self.memory_write_callback:
            self.memory_write_callback(addr, struct.pack('<I', val & 0xFFFFFFFF))

    def process_property_tags(self, paddr: int):
        """Process property tags at the given physical address."""
        buf_size = self.read_mem32(paddr)
        req_code = self.read_mem32(paddr + 4)
        
        offset = 8
        while offset < buf_size:
            tag_id = self.read_mem32(paddr + offset)
            if tag_id == 0:
                break
                
            val_buf_size = self.read_mem32(paddr + offset + 4)
            req_resp = self.read_mem32(paddr + offset + 8)
            
            # Process specific tags
            val_addr = paddr + offset + 12
            self.handle_tag(tag_id, val_buf_size, val_addr)
            
            # Write response success bit to req/resp field (bit 31)
            self.write_mem32(paddr + offset + 8, (1 << 31) | val_buf_size)
            
            # Move to next tag (padding to 4 bytes alignment)
            offset += 12 + ((val_buf_size + 3) & ~3)
            
        # Write overall success
        self.write_mem32(paddr + 4, 0x80000000)

    def handle_tag(self, tag_id: int, size: int, addr: int):
        """Handle an individual property tag."""
        if tag_id == 0x00010001:  # Get Board Model
            self.write_mem32(addr, 0x00000011)
        elif tag_id == 0x00010002:  # Get Board Revision
            self.write_mem32(addr, 0x00D03114)
        elif tag_id == 0x00010003:  # Get Board MAC Address
            self.write_mem32(addr, 0x0132A6DC)  # DC:A6:32:01
            self.write_mem32(addr + 4, 0x00000302) # :02:03
        elif tag_id == 0x00010004:  # Get Board Serial
            self.write_mem32(addr, 0x90ABCDEF)
            self.write_mem32(addr + 4, 0x12345678)
        elif tag_id == 0x00030001:  # Get Clock State
            clock_id = self.read_mem32(addr)
            self.write_mem32(addr, clock_id)
            self.write_mem32(addr + 4, 1) # on
        elif tag_id == 0x00030002:  # Get Clock Rate
            clock_id = self.read_mem32(addr)
            rate = 0
            if clock_id == 1: rate = 200000000  # EMMC
            elif clock_id == 2: rate = 48000000  # UART
            elif clock_id == 3: rate = 1500000000  # ARM
            elif clock_id == 4: rate = 500000000  # CORE
            else: rate = 500000000
            
            self.write_mem32(addr, clock_id)
            self.write_mem32(addr + 4, rate)
        elif tag_id == 0x00010005:  # Get ARM Memory
            self.write_mem32(addr, 0x00000000)
            self.write_mem32(addr + 4, 0x3B400000)
        elif tag_id == 0x00010006:  # Get VC Memory
            self.write_mem32(addr, 0x3B400000)
            self.write_mem32(addr + 4, 0x04C00000)
        elif tag_id == 0x00040001:  # Allocate Buffer
            self.write_mem32(addr, 0x3E000000)
            self.write_mem32(addr + 4, 0)
        elif tag_id == 0x00048003:  # Set Physical Display Size
            self.fb_width = self.read_mem32(addr)
            self.fb_height = self.read_mem32(addr + 4)
        elif tag_id == 0x00048004:  # Set Virtual Display Size
            self.fb_width = self.read_mem32(addr)
            self.fb_height = self.read_mem32(addr + 4)
        elif tag_id == 0x00048005:  # Set Depth
            self.fb_depth = self.read_mem32(addr)
        elif tag_id == 0x00048009:  # Set Virtual Offset
            self.fb_x_offset = self.read_mem32(addr)
            self.fb_y_offset = self.read_mem32(addr + 4)
