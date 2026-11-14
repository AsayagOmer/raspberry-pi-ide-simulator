import logging
from typing import Callable, Optional, Tuple, List
from .base_peripheral import BasePeripheral

logger = logging.getLogger(__name__)

class GICDistributor(BasePeripheral):
    NAME = "GICD"
    BASE_ADDR = 0xFF841000
    SIZE = 0x1000

    def __init__(self, gic_controller):
        super().__init__()
        self.gic = gic_controller

    def reset(self):
        pass

    def read(self, offset: int, size: int) -> int:
        return self.gic._read_gicd(offset, size)

    def write(self, offset: int, size: int, value: int) -> None:
        self.gic._write_gicd(offset, size, value)


class GICCPUInterface(BasePeripheral):
    NAME = "GICC"
    BASE_ADDR = 0xFF842000
    SIZE = 0x2000

    def __init__(self, gic_controller):
        super().__init__()
        self.gic = gic_controller
        self.cpu_id = 0  # Assuming single core or primary interface for now

    def reset(self):
        pass

    def read(self, offset: int, size: int) -> int:
        return self.gic._read_gicc(self.cpu_id, offset, size)

    def write(self, offset: int, size: int, value: int) -> None:
        self.gic._write_gicc(self.cpu_id, offset, size, value)


class GIC400:
    """
    ARM GIC-400 (Generic Interrupt Controller v2)
    Coordinates GICD (Distributor) and GICC (CPU Interface).
    Supports 320 interrupts:
    - 0-15: SGI (Software Generated Interrupts)
    - 16-31: PPI (Private Peripheral Interrupts)
    - 32-319: SPI (Shared Peripheral Interrupts)
    """
    NUM_IRQS = 320
    NUM_CPUS = 4

    def __init__(self):
        self.distributor = GICDistributor(self)
        self.cpu_interface = GICCPUInterface(self)
        
        # State arrays
        self.enabled = [False] * self.NUM_IRQS
        self.pending = [False] * self.NUM_IRQS
        self.active = [False] * self.NUM_IRQS
        self.priorities = [0] * self.NUM_IRQS
        self.targets = [0] * self.NUM_IRQS
        self.config = [0] * self.NUM_IRQS
        self.group = [0] * self.NUM_IRQS

        # Global GICD state
        self.gicd_ctlr = 0

        # CPU state
        self.gicc_ctlr = [0] * self.NUM_CPUS
        self.gicc_pmr = [0] * self.NUM_CPUS
        self.gicc_bpr = [0] * self.NUM_CPUS

        self.reset()

    def reset(self):
        self.enabled = [False] * self.NUM_IRQS
        self.pending = [False] * self.NUM_IRQS
        self.active = [False] * self.NUM_IRQS
        self.priorities = [0xA0] * self.NUM_IRQS
        
        # Default target CPU 0
        for i in range(self.NUM_IRQS):
            if i < 32:
                # PPI/SGI are banked per CPU, target is implicitly the current CPU
                self.targets[i] = 0b1111 # all CPUs
            else:
                self.targets[i] = 1 # CPU 0

        self.config = [0] * self.NUM_IRQS
        self.group = [0] * self.NUM_IRQS

        self.gicd_ctlr = 0
        self.gicc_ctlr = [0] * self.NUM_CPUS
        self.gicc_pmr = [0xF0] * self.NUM_CPUS
        self.gicc_bpr = [0] * self.NUM_CPUS

    def set_pending(self, irq_id: int):
        if 0 <= irq_id < self.NUM_IRQS:
            self.pending[irq_id] = True

    def clear_pending(self, irq_id: int):
        if 0 <= irq_id < self.NUM_IRQS:
            self.pending[irq_id] = False

    def generate_sgi(self, source_cpu: int, target_filter: int, target_list: int, sgi_id: int):
        targets = []
        if target_filter == 0:
            for i in range(self.NUM_CPUS):
                if (target_list & (1 << i)):
                    targets.append(i)
        elif target_filter == 1:
            for i in range(self.NUM_CPUS):
                if i != source_cpu:
                    targets.append(i)
        elif target_filter == 2:
            targets.append(source_cpu)

        for cpu in targets:
            self.set_pending(sgi_id) # For proper modeling, SGI pending should be banked per CPU

    def check_pending(self, cpu_id: int) -> bool:
        if not (self.gicd_ctlr & 1) or not (self.gicc_ctlr[cpu_id] & 1):
            return False

        for irq in range(self.NUM_IRQS):
            if self.pending[irq] and self.enabled[irq]:
                if self.targets[irq] & (1 << cpu_id):
                    if self.priorities[irq] < self.gicc_pmr[cpu_id]:
                        return True
        return False

    def acknowledge(self, cpu_id: int) -> int:
        best_irq = 1023
        best_prio = 0x100

        if not (self.gicd_ctlr & 1) or not (self.gicc_ctlr[cpu_id] & 1):
            return best_irq

        for irq in range(self.NUM_IRQS):
            if self.pending[irq] and self.enabled[irq] and not self.active[irq]:
                if self.targets[irq] & (1 << cpu_id):
                    prio = self.priorities[irq]
                    if prio < self.gicc_pmr[cpu_id] and prio < best_prio:
                        best_prio = prio
                        best_irq = irq

        if best_irq != 1023:
            self.pending[best_irq] = False
            self.active[best_irq] = True

        return best_irq

    def complete(self, cpu_id: int, irq_id: int):
        if 0 <= irq_id < self.NUM_IRQS:
            self.active[irq_id] = False

    def _read_gicd(self, offset: int, size: int) -> int:
        if offset == 0x000: # GICD_CTLR
            return self.gicd_ctlr
        elif offset == 0x004: # GICD_TYPER
            it_lines_num = (self.NUM_IRQS // 32) - 1
            cpu_num = self.NUM_CPUS - 1
            return (cpu_num << 5) | it_lines_num
        elif offset == 0x008: # GICD_IIDR
            return 0x0200143B
        
        # Helper for reading banked/array registers
        def read_array_reg(base_offset, item_size_bits, data_array):
            index = (offset - base_offset) // (item_size_bits // 8)
            if item_size_bits == 32:
                idx = index * 32
                val = 0
                for i in range(32):
                    if idx + i < self.NUM_IRQS and data_array[idx + i]:
                        val |= (1 << i)
                return val
            elif item_size_bits == 8:
                val = 0
                idx = index * 4
                for i in range(4):
                    if idx + i < self.NUM_IRQS:
                        val |= (data_array[idx + i] & 0xFF) << (i * 8)
                return val
            elif item_size_bits == 2:
                val = 0
                idx = index * 16
                for i in range(16):
                    if idx + i < self.NUM_IRQS:
                        val |= (data_array[idx + i] & 0x3) << (i * 2)
                return val
            return 0

        if 0x080 <= offset <= 0x0BF: return read_array_reg(0x080, 32, self.group)
        elif 0x100 <= offset <= 0x13F: return read_array_reg(0x100, 32, self.enabled)
        elif 0x180 <= offset <= 0x1BF: return read_array_reg(0x180, 32, self.enabled)
        elif 0x200 <= offset <= 0x23F: return read_array_reg(0x200, 32, self.pending)
        elif 0x280 <= offset <= 0x2BF: return read_array_reg(0x280, 32, self.pending)
        elif 0x300 <= offset <= 0x33F: return read_array_reg(0x300, 32, self.active)
        elif 0x380 <= offset <= 0x3BF: return read_array_reg(0x380, 32, self.active)
        elif 0x400 <= offset <= 0x4FF: return read_array_reg(0x400, 8, self.priorities)
        elif 0x800 <= offset <= 0x8FF: return read_array_reg(0x800, 8, self.targets)
        elif 0xC00 <= offset <= 0xC3F: return read_array_reg(0xC00, 2, self.config)
        
        logger.debug(f"GICD Unhandled read offset {hex(offset)}")
        return 0

    def _write_gicd(self, offset: int, size: int, value: int) -> None:
        if offset == 0x000: # GICD_CTLR
            self.gicd_ctlr = value
            return
        elif offset == 0xF00: # GICD_SGIR
            sgi_id = value & 0xF
            target_list = (value >> 16) & 0xFF
            filter_mode = (value >> 24) & 0x3
            self.generate_sgi(0, filter_mode, target_list, sgi_id) # Using cpu 0 as source
            return

        def write_array_reg(base_offset, item_size_bits, data_array, mode="set"):
            index = (offset - base_offset) // (item_size_bits // 8)
            if item_size_bits == 32:
                idx = index * 32
                for i in range(32):
                    if idx + i < self.NUM_IRQS:
                        bit = (value >> i) & 1
                        if mode == "set_enable" and bit: data_array[idx + i] = True
                        elif mode == "clear_enable" and bit: data_array[idx + i] = False
                        elif mode == "set_pending" and bit: self.set_pending(idx + i)
                        elif mode == "clear_pending" and bit: self.clear_pending(idx + i)
                        elif mode == "set_active" and bit: data_array[idx + i] = True
                        elif mode == "clear_active" and bit: data_array[idx + i] = False
                        elif mode == "set_group": data_array[idx + i] = bit
            elif item_size_bits == 8:
                idx = index * 4
                for i in range(4):
                    if idx + i < self.NUM_IRQS:
                        data_array[idx + i] = (value >> (i * 8)) & 0xFF
            elif item_size_bits == 2:
                idx = index * 16
                for i in range(16):
                    if idx + i < self.NUM_IRQS:
                        data_array[idx + i] = (value >> (i * 2)) & 0x3

        if 0x080 <= offset <= 0x0BF: write_array_reg(0x080, 32, self.group, "set_group")
        elif 0x100 <= offset <= 0x13F: write_array_reg(0x100, 32, self.enabled, "set_enable")
        elif 0x180 <= offset <= 0x1BF: write_array_reg(0x180, 32, self.enabled, "clear_enable")
        elif 0x200 <= offset <= 0x23F: write_array_reg(0x200, 32, self.pending, "set_pending")
        elif 0x280 <= offset <= 0x2BF: write_array_reg(0x280, 32, self.pending, "clear_pending")
        elif 0x300 <= offset <= 0x33F: write_array_reg(0x300, 32, self.active, "set_active")
        elif 0x380 <= offset <= 0x3BF: write_array_reg(0x380, 32, self.active, "clear_active")
        elif 0x400 <= offset <= 0x4FF: write_array_reg(0x400, 8, self.priorities)
        elif 0x800 <= offset <= 0x8FF: write_array_reg(0x800, 8, self.targets)
        elif 0xC00 <= offset <= 0xC3F: write_array_reg(0xC00, 2, self.config)
        else:
            logger.debug(f"GICD Unhandled write offset {hex(offset)} = {hex(value)}")

    def _read_gicc(self, cpu_id: int, offset: int, size: int) -> int:
        if offset == 0x000: # GICC_CTLR
            return self.gicc_ctlr[cpu_id]
        elif offset == 0x004: # GICC_PMR
            return self.gicc_pmr[cpu_id]
        elif offset == 0x008: # GICC_BPR
            return self.gicc_bpr[cpu_id]
        elif offset == 0x00C: # GICC_IAR
            return self.acknowledge(cpu_id)
        elif offset == 0x014: # GICC_RPR
            return 0 # simplification
        elif offset == 0x018: # GICC_HPPIR
            # Find best priority but don't acknowledge
            best_irq = 1023
            best_prio = 0x100
            for irq in range(self.NUM_IRQS):
                if self.pending[irq] and self.enabled[irq]:
                    if self.targets[irq] & (1 << cpu_id):
                        if self.priorities[irq] < best_prio:
                            best_prio = self.priorities[irq]
                            best_irq = irq
            return best_irq
        logger.debug(f"GICC Unhandled read offset {hex(offset)}")
        return 0

    def _write_gicc(self, cpu_id: int, offset: int, size: int, value: int) -> None:
        if offset == 0x000: # GICC_CTLR
            self.gicc_ctlr[cpu_id] = value
        elif offset == 0x004: # GICC_PMR
            self.gicc_pmr[cpu_id] = value
        elif offset == 0x008: # GICC_BPR
            self.gicc_bpr[cpu_id] = value
        elif offset == 0x010: # GICC_EOIR
            self.complete(cpu_id, value & 0x3FF)
        else:
            logger.debug(f"GICC Unhandled write offset {hex(offset)} = {hex(value)}")
