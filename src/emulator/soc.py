"""
BCM2711 System-on-Chip — Quad-Core Cortex-A72 Orchestrator

Wires together the four AArch64 CPU cores, the 8 GB memory controller,
and all BCM2711 peripheral models into a complete system. Manages:

    - Multi-core boot (spin-table protocol)
    - Peripheral registration and MMIO routing
    - GIC-400 ↔ CPU IRQ injection
    - Generic timer tick distribution
    - Instruction-rate throttling
    - Start/stop/reset lifecycle
"""

import logging
import time
import threading
from typing import Callable, Dict, List, Optional

from .cpu import AArch64Core
from .memory import MemoryController
from .throttle import ThrottleEngine
from .peripherals.gic400 import GIC400
from .peripherals.pl011 import PL011
from .peripherals.timer import ARMGenericTimer
from .peripherals.mailbox import Mailbox
from .peripherals.emmc2 import eMMC2

logger = logging.getLogger(__name__)


class BCM2711SoC:
    """Raspberry Pi 4 Model B — BCM2711 SoC emulation.

    Instantiates and wires together:
        - 4× AArch64Core (Cortex-A72)
        - MemoryController (8 GB, 35-bit PA)
        - GIC-400 (GICD + GICC)
        - PL011 UART
        - ARM Generic Timers (one per core)
        - VideoCore Firmware Mailbox
        - eMMC2 / SDHCI controller

    Args:
        ram_size_gb:     RAM size in GB (default 8).
        disk_image_path: Path to raw SD card image for eMMC2.
        uart_callback:   Called with each byte output by PL011 UART.
        throttle:        If True, throttle to ~1.5 GHz instruction rate.
    """

    # Spin-table release addresses (from RPi4 bootloader)
    SPIN_TABLE = {
        1: 0xD8,   # Core 1 release address
        2: 0xE0,   # Core 2 release address
        3: 0xE8,   # Core 3 release address
    }

    def __init__(
        self,
        ram_size_gb: int = 8,
        disk_image_path: Optional[str] = None,
        uart_callback: Optional[Callable[[int], None]] = None,
        throttle: bool = True,
    ):
        self.running = False
        self._timer_thread: Optional[threading.Thread] = None
        self._timer_stop = threading.Event()

        # ── Memory ────────────────────────────────────────────────
        ram_bytes = ram_size_gb * 1024 * 1024 * 1024
        self.memory = MemoryController(ram_size_bytes=ram_bytes)

        # ── Peripherals ───────────────────────────────────────────
        self.gic = GIC400()
        self.uart = PL011()
        self.timers: List[ARMGenericTimer] = [
            ARMGenericTimer() for _ in range(4)
        ]
        self.mailbox = Mailbox()
        self.emmc = eMMC2(disk_image_path=disk_image_path)

        # ── Wire UART output ──────────────────────────────────────
        self._uart_callback = uart_callback
        self.uart.output_callback = self._on_uart_output
        self._uart_buffer: List[int] = []

        # ── Wire Mailbox memory access ────────────────────────────
        self.mailbox.memory_read_callback = self._mailbox_mem_read
        self.mailbox.memory_write_callback = self._mailbox_mem_write

        # ── Wire IRQ callbacks ────────────────────────────────────
        self.uart.set_irq_callback(self._peripheral_irq)
        self.emmc.set_irq_callback(self._peripheral_irq)
        for timer in self.timers:
            timer.set_irq_callback(self._peripheral_irq)

        # ── Register peripherals with memory controller ───────────
        self.memory.register_peripheral(self.gic.distributor)
        self.memory.register_peripheral(self.gic.cpu_interface)
        self.memory.register_peripheral(self.uart)
        self.memory.register_peripheral(self.mailbox)
        self.memory.register_peripheral(self.emmc)

        # ── CPU cores ─────────────────────────────────────────────
        self.cores: List[AArch64Core] = []
        for i in range(4):
            core = AArch64Core(core_id=i, memory=self.memory)
            core._on_uart_write = self._on_uart_output
            self.cores.append(core)

        # ── Throttle engine (one per core) ────────────────────────
        self.throttle_enabled = throttle
        self.throttles: List[ThrottleEngine] = [
            ThrottleEngine(
                target_hz=1_500_000_000,
                batch_size=100_000,
                enabled=throttle,
            )
            for _ in range(4)
        ]

        logger.info(
            "BCM2711 SoC initialized: %d cores, %d GB RAM, "
            "disk=%s, throttle=%s",
            len(self.cores),
            ram_size_gb,
            disk_image_path or "none",
            throttle,
        )

    # ── UART output ───────────────────────────────────────────────

    def _on_uart_output(self, byte_val: int):
        """Called when the PL011 emits a byte."""
        self._uart_buffer.append(byte_val)
        if self._uart_callback:
            self._uart_callback(byte_val)

    def get_uart_output(self) -> str:
        """Return all UART output as a decoded string and clear the buffer."""
        text = bytes(self._uart_buffer).decode("utf-8", errors="replace")
        self._uart_buffer.clear()
        return text

    def peek_uart_output(self) -> str:
        """Return UART output without clearing."""
        return bytes(self._uart_buffer).decode("utf-8", errors="replace")

    # ── Mailbox memory access ─────────────────────────────────────

    def _mailbox_mem_read(self, addr: int, size: int) -> bytes:
        """Read bytes from physical memory for mailbox tag processing."""
        return self.memory.read_bytes(addr, size)

    def _mailbox_mem_write(self, addr: int, data: bytes):
        """Write bytes to physical memory for mailbox tag processing."""
        self.memory.write_bytes(addr, data)

    # ── IRQ routing ───────────────────────────────────────────────

    def _peripheral_irq(self, peripheral, irq_id: int, level: int):
        """Route a peripheral IRQ assertion to the GIC."""
        if level:
            self.gic.set_pending(irq_id)
        else:
            self.gic.clear_pending(irq_id)

        # Check if any core has a pending interrupt
        for core in self.cores:
            if core.running and self.gic.check_pending(core.core_id):
                core.inject_irq(irq_id)

    # ── Timer tick thread ─────────────────────────────────────────

    def _timer_tick_loop(self):
        """Background thread that advances the generic timers."""
        TICK_INTERVAL_NS = 1_000_000  # 1 ms
        last = time.perf_counter_ns()

        while not self._timer_stop.is_set():
            now = time.perf_counter_ns()
            elapsed = now - last
            last = now

            for timer in self.timers:
                timer.tick(elapsed)

            self._timer_stop.wait(TICK_INTERVAL_NS / 1e9)

    # ── Boot ──────────────────────────────────────────────────────

    def load_kernel(
        self,
        kernel_data: bytes,
        dtb_data: bytes,
        kernel_addr: int = 0x80000,
        dtb_addr: int = 0x2600000,
    ):
        """Load a kernel image and device tree blob into RAM.

        Args:
            kernel_data: Raw kernel Image bytes.
            dtb_data:    Compiled device tree blob bytes.
            kernel_addr: Load address for kernel (default 0x80000).
            dtb_addr:    Load address for DTB (default 0x2600000).
        """
        logger.info(
            "Loading kernel (%d bytes) at 0x%X, DTB (%d bytes) at 0x%X",
            len(kernel_data), kernel_addr,
            len(dtb_data), dtb_addr,
        )
        self.memory.write_bytes(kernel_addr, kernel_data)
        self.memory.write_bytes(dtb_addr, dtb_data)

        # Set up Core 0 registers per ARM64 Linux boot protocol
        core0 = self.cores[0]
        core0.set_reg(0x44, kernel_addr)  # PC (UC_ARM64_REG_PC = 0x44... we need to use the constant)
        # Actually use the proper import
        from unicorn.arm64_const import (
            UC_ARM64_REG_PC, UC_ARM64_REG_SP,
            UC_ARM64_REG_X0, UC_ARM64_REG_X1,
            UC_ARM64_REG_X2, UC_ARM64_REG_X3,
        )
        core0.set_reg(UC_ARM64_REG_X0, dtb_addr)    # x0 = DTB pointer
        core0.set_reg(UC_ARM64_REG_X1, 0)            # x1 = reserved
        core0.set_reg(UC_ARM64_REG_X2, 0)            # x2 = reserved
        core0.set_reg(UC_ARM64_REG_X3, 0)            # x3 = reserved
        core0.pc = kernel_addr
        core0.sp = 0x800000  # Initial stack pointer (8 MB)

        # Sync RAM to Unicorn so Core 0 sees the loaded data
        core0.sync_ram_to_unicorn()

        # Initialize spin-table release addresses to 0
        for core_id, addr in self.SPIN_TABLE.items():
            self.memory.write(addr, 8, 0)

        logger.info("Kernel loaded. Core 0 ready at PC=0x%X", kernel_addr)

    def load_binary(
        self,
        binary_data: bytes,
        load_addr: int = 0x80000,
    ):
        """Load a bare-metal binary into RAM.

        Args:
            binary_data: Raw binary bytes.
            load_addr:   Load address (default 0x80000).
        """
        logger.info(
            "Loading binary (%d bytes) at 0x%X",
            len(binary_data), load_addr,
        )
        self.memory.write_bytes(load_addr, binary_data)

        from unicorn.arm64_const import UC_ARM64_REG_SP
        core0 = self.cores[0]
        core0.pc = load_addr
        core0.set_reg(UC_ARM64_REG_SP, 0x800000)
        core0.sync_ram_to_unicorn()

        logger.info("Binary loaded. Core 0 ready at PC=0x%X", load_addr)

    # ── Start / Stop ──────────────────────────────────────────────

    def start(self, multicore: bool = True):
        """Start the emulation.

        Args:
            multicore: If True, set up spin-table for secondary cores.
        """
        self.running = True

        # Start timer tick thread
        self._timer_stop.clear()
        self._timer_thread = threading.Thread(
            target=self._timer_tick_loop,
            daemon=True,
            name="timer-tick",
        )
        self._timer_thread.start()

        # Start Core 0
        self.cores[0].start()

        # Set up secondary cores in WFE loops
        if multicore:
            for core_id, release_addr in self.SPIN_TABLE.items():
                self.cores[core_id].enter_wfe_loop(release_addr)

        logger.info("BCM2711 SoC started (multicore=%s)", multicore)

    def stop(self):
        """Stop all cores and the timer thread."""
        self.running = False

        # Stop timer thread
        self._timer_stop.set()
        if self._timer_thread:
            self._timer_thread.join(timeout=2.0)

        # Stop all cores
        for core in self.cores:
            core.stop()

        logger.info("BCM2711 SoC stopped")

    def reset(self):
        """Reset the entire SoC to power-on state."""
        self.stop()
        self.gic.reset()
        self.uart.reset()
        for timer in self.timers:
            timer.reset()
        self.mailbox.reset()
        self.emmc.reset()
        self._uart_buffer.clear()
        logger.info("BCM2711 SoC reset")

    # ── Status / Debug ────────────────────────────────────────────

    def get_status(self) -> dict:
        """Return a comprehensive status snapshot."""
        return {
            "running": self.running,
            "cores": [repr(c) for c in self.cores],
            "memory": self.memory.get_ram_info(),
            "throttle": [t.get_summary() for t in self.throttles],
            "uart_output_bytes": len(self._uart_buffer),
            "gic": {
                "distributor_enabled": bool(self.gic.gicd_ctlr & 1),
                "pending_count": sum(self.gic.pending),
                "active_count": sum(self.gic.active),
            },
            "emmc": {
                "card_detected": self.emmc.card_detect,
                "card_state": self.emmc.card_state,
            },
        }

    def __repr__(self):
        state = "running" if self.running else "stopped"
        return f"<BCM2711SoC [{state}] 4×Cortex-A72 8GB>"
