"""
Base class for all BCM2711 memory-mapped peripheral devices.

Every peripheral model (GIC-400, PL011, Timers, etc.) inherits from
BasePeripheral and implements read/write handlers for its MMIO register
space. The MemoryController routes accesses by address to the correct
peripheral instance.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class BasePeripheral:
    """Abstract base for a memory-mapped I/O peripheral.

    Subclasses MUST define:
        NAME       – human-readable device name (e.g. "PL011 UART")
        BASE_ADDR  – MMIO base address in the physical address space
        SIZE       – size in bytes of the register window

    Subclasses MUST implement:
        read(offset, size)            – returns int
        write(offset, size, value)    – returns None
    """

    NAME: str = "Unnamed Peripheral"
    BASE_ADDR: int = 0
    SIZE: int = 0

    def __init__(self):
        self._irq_callback = None
        self.reset()

    def reset(self):
        """Reset the peripheral to its power-on state.

        Override in subclasses to initialise registers.
        """
        pass

    def read(self, offset: int, size: int) -> int:
        """Read *size* bytes from register at *offset*.

        Args:
            offset: Byte offset from BASE_ADDR (0-based).
            size:   Access width in bytes (1, 2, or 4).

        Returns:
            The register value as an unsigned integer.
        """
        logger.warning(
            "%s: unhandled read  @ offset 0x%03X (size=%d)",
            self.NAME, offset, size,
        )
        return 0

    def write(self, offset: int, size: int, value: int) -> None:
        """Write *value* (of *size* bytes) to register at *offset*.

        Args:
            offset: Byte offset from BASE_ADDR (0-based).
            size:   Access width in bytes (1, 2, or 4).
            value:  The value to write.
        """
        logger.warning(
            "%s: unhandled write @ offset 0x%03X ← 0x%X (size=%d)",
            self.NAME, offset, value, size,
        )

    # ── IRQ plumbing ──────────────────────────────────────────────

    def set_irq_callback(self, callback):
        """Register a callback: callback(peripheral, irq_id, level).

        Called by the peripheral when it wants to assert/deassert an
        interrupt line.  The MemoryController or SoC wires this to the
        GIC distributor.
        """
        self._irq_callback = callback

    def assert_irq(self, irq_id: int, level: int = 1):
        """Assert (level=1) or deassert (level=0) an interrupt line."""
        if self._irq_callback:
            self._irq_callback(self, irq_id, level)
        else:
            logger.debug(
                "%s: IRQ %d asserted but no callback registered",
                self.NAME, irq_id,
            )

    # ── Helpers ───────────────────────────────────────────────────

    def contains(self, address: int) -> bool:
        """Return True if *address* falls within this peripheral's window."""
        return self.BASE_ADDR <= address < self.BASE_ADDR + self.SIZE

    def __repr__(self):
        return (
            f"<{self.NAME} @ 0x{self.BASE_ADDR:09X}"
            f" size=0x{self.SIZE:X}>"
        )
