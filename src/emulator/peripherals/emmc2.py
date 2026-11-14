import os
import logging
from typing import Optional
from .base_peripheral import BasePeripheral

logger = logging.getLogger(__name__)

class eMMC2(BasePeripheral):
    """
    eMMC2 / SDHCI controller (Arasan SD Host Controller)
    Base: 0xFE340000, Size: 0x100
    """
    NAME = "eMMC2"
    BASE_ADDR = 0xFE340000
    SIZE = 0x100
    IRQ_ID = 158  # SPI 126

    # States
    STATE_IDLE = 0
    STATE_READY = 1
    STATE_IDENT = 2
    STATE_STBY = 3
    STATE_TRAN = 4

    def __init__(self, disk_image_path: Optional[str] = None):
        self.disk_image_path = disk_image_path
        self.disk_file = None
        self.card_state = self.STATE_IDLE
        self.card_detect = False
        
        self.sdma_addr = 0
        self.block_size = 512
        self.block_count = 0
        self.arg1 = 0
        self.cmdtm = 0
        self.resp = [0, 0, 0, 0]
        self.status = 0
        self.control0 = 0
        self.control1 = 0
        self.interrupt = 0
        self.irpt_mask = 0
        self.irpt_en = 0
        self.control2 = 0
        
        self.data_fifo = bytearray()
        self.fifo_offset = 0

        super().__init__()
        self.setup_disk()

    def setup_disk(self):
        if self.disk_image_path and os.path.exists(self.disk_image_path):
            self.disk_file = open(self.disk_image_path, "r+b")
            self.card_detect = True
            self.status |= (1 << 20)  # CARD_DETECT
        else:
            self.card_detect = False
            self.status &= ~(1 << 20)

    def reset(self):
        self.sdma_addr = 0
        self.block_size = 512
        self.block_count = 0
        self.arg1 = 0
        self.cmdtm = 0
        self.resp = [0, 0, 0, 0]
        self.control0 = 0
        self.control1 = 0
        self.interrupt = 0
        self.irpt_mask = 0
        self.irpt_en = 0
        self.control2 = 0
        self.data_fifo.clear()
        self.fifo_offset = 0
        self.card_state = self.STATE_IDLE if self.card_detect else self.STATE_IDLE
        
        # Bits 0, 1 = CMD/DAT INHIBIT off initially
        self.status &= ~0x03

    def _update_interrupts(self):
        # Assert IRQ if any unmasked interrupt is active
        active_ints = self.interrupt & self.irpt_mask
        if active_ints != 0:
            self.assert_irq(self.IRQ_ID, 1)
        else:
            self.assert_irq(self.IRQ_ID, 0)

    def _handle_command(self):
        cmd_idx = (self.cmdtm >> 24) & 0x3F
        is_acmd = (self.card_state == self.STATE_TRAN and cmd_idx == 55) # Simplified ACMD tracking
        
        self.interrupt |= (1 << 0) # CMD_DONE
        
        if not self.card_detect:
            self.interrupt |= (1 << 16) # CTO_ERR (Timeout)
            self._update_interrupts()
            return

        if cmd_idx == 0: # GO_IDLE_STATE
            self.card_state = self.STATE_IDLE
            
        elif cmd_idx == 2: # ALL_SEND_CID
            self.card_state = self.STATE_IDENT
            self.resp[0] = 0x12345678 # Dummy CID
            self.resp[1] = 0x12345678
            self.resp[2] = 0x12345678
            self.resp[3] = 0x12345678
            
        elif cmd_idx == 3: # SEND_RELATIVE_ADDR
            self.card_state = self.STATE_STBY
            self.resp[0] = 0x12340000 # RCA = 0x1234
            
        elif cmd_idx == 7: # SELECT/DESELECT_CARD
            if self.arg1 == 0:
                self.card_state = self.STATE_STBY
            else:
                self.card_state = self.STATE_TRAN
                
        elif cmd_idx == 8: # SEND_IF_COND
            # Echo back check pattern
            self.resp[0] = self.arg1 & 0xFFF
            
        elif cmd_idx == 17: # READ_SINGLE_BLOCK
            if self.disk_file:
                sector = self.arg1
                self.disk_file.seek(sector * 512)
                data = self.disk_file.read(512)
                self.data_fifo = bytearray(data)
                self.fifo_offset = 0
                self.interrupt |= (1 << 5) # READ_RDY
                self.status |= (1 << 9) # READ_TRANSFER
                
        elif cmd_idx == 18: # READ_MULTIPLE_BLOCK
            if self.disk_file:
                sector = self.arg1
                self.disk_file.seek(sector * 512)
                data = self.disk_file.read(512 * self.block_count)
                self.data_fifo = bytearray(data)
                self.fifo_offset = 0
                self.interrupt |= (1 << 5) # READ_RDY
                self.status |= (1 << 9) # READ_TRANSFER
                
        elif cmd_idx == 24 or cmd_idx == 25: # WRITE_BLOCK(S)
            if self.disk_file:
                self.data_fifo = bytearray(512 * (self.block_count if cmd_idx == 25 else 1))
                self.fifo_offset = 0
                self.interrupt |= (1 << 4) # WRITE_RDY
                self.status |= (1 << 8) # WRITE_TRANSFER
                
        elif cmd_idx == 41: # ACMD41 SD_SEND_OP_COND
            self.resp[0] = 0x80000000 | 0x40000000 | 0x00FF8000 # Ready, SDHC, Voltage
            self.card_state = self.STATE_READY
            
        elif cmd_idx == 51: # ACMD51 SEND_SCR
            pass
            
        elif cmd_idx == 6: # ACMD6 SET_BUS_WIDTH
            pass
            
        self._update_interrupts()

    def read(self, offset: int, size: int) -> int:
        if offset == 0x00: return self.sdma_addr
        elif offset == 0x04: return (self.block_count << 16) | self.block_size
        elif offset == 0x08: return self.arg1
        elif offset == 0x0C: return self.cmdtm
        elif offset == 0x10: return self.resp[0]
        elif offset == 0x14: return self.resp[1]
        elif offset == 0x18: return self.resp[2]
        elif offset == 0x1C: return self.resp[3]
        elif offset == 0x20:
            # Data port read
            val = 0
            if self.fifo_offset + 4 <= len(self.data_fifo):
                val = int.from_bytes(self.data_fifo[self.fifo_offset:self.fifo_offset+4], byteorder='little')
                self.fifo_offset += 4
                
                if self.fifo_offset >= len(self.data_fifo):
                    self.status &= ~(1 << 9) # Clear READ_TRANSFER
                    self.interrupt |= (1 << 1) # DATA_DONE
                    self._update_interrupts()
            return val
        elif offset == 0x24: return self.status
        elif offset == 0x28: return self.control0
        elif offset == 0x2C: return self.control1
        elif offset == 0x30: return self.interrupt
        elif offset == 0x34: return self.irpt_mask
        elif offset == 0x38: return self.irpt_en
        elif offset == 0x3C: return self.control2
        elif offset == 0xFC: return 0x01020002 # SLOTISR_VER
        
        logger.debug(f"eMMC2 Unhandled read offset {hex(offset)}")
        return 0

    def write(self, offset: int, size: int, value: int) -> None:
        if offset == 0x00: self.sdma_addr = value
        elif offset == 0x04:
            self.block_size = value & 0xFFFF
            self.block_count = (value >> 16) & 0xFFFF
        elif offset == 0x08: self.arg1 = value
        elif offset == 0x0C:
            self.cmdtm = value
            self._handle_command()
        elif offset == 0x20:
            # Data port write
            if self.fifo_offset + 4 <= len(self.data_fifo):
                self.data_fifo[self.fifo_offset:self.fifo_offset+4] = value.to_bytes(4, byteorder='little')
                self.fifo_offset += 4
                
                if self.fifo_offset >= len(self.data_fifo):
                    if self.disk_file:
                        sector = self.arg1
                        self.disk_file.seek(sector * 512)
                        self.disk_file.write(self.data_fifo)
                    self.status &= ~(1 << 8) # Clear WRITE_TRANSFER
                    self.interrupt |= (1 << 1) # DATA_DONE
                    self._update_interrupts()
        elif offset == 0x28: self.control0 = value
        elif offset == 0x2C:
            self.control1 = value
            if value & (1 << 24): # SRST_HC
                self.reset()
        elif offset == 0x30:
            # W1C (write 1 to clear)
            self.interrupt &= ~value
            self._update_interrupts()
        elif offset == 0x34:
            self.irpt_mask = value
            self._update_interrupts()
        elif offset == 0x38: self.irpt_en = value
        elif offset == 0x3C: self.control2 = value
        else:
            logger.debug(f"eMMC2 Unhandled write offset {hex(offset)} = {hex(value)}")
