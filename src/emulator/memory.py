"""
BCM2711 Memory Controller — 35-bit Physical Address Space

Models the full 8 GB RAM + MMIO routing for the Raspberry Pi 4 Model B.

Physical Memory Map (BCM2711):
    0x0_0000_0000 – 0x0_3FFF_FFFF   1 GB   Low RAM (ZONE_DMA)
    0x0_4000_0000 – 0x0_BFFF_FFFF   2 GB   Mid RAM
    0x0_C000_0000 – 0x0_FBFF_FFFF   ~960 MB RAM (below MMIO gap)
    0x0_FC00_0000 – 0x0_FFFF_FFFF   64 MB  Peripherals + GIC (MMIO)
    0x1_0000_0000 – 0x1_FFFF_FFFF   4 GB   High RAM (above 4 GB)

The legacy 32-bit MMIO window starts at 0xFE00_0000.
In native 64-bit mode, peripherals also appear at 0x4_7E00_0000
(we map the legacy window only, since Linux on Pi4 uses the legacy
addresses via the device tree).

Design:
    - RAM is backed by Python bytearray objects (split into banks to
      avoid a single 8 GB allocation).
    - MMIO regions are routed to registered BasePeripheral instances.
    - The Unicorn engine maps the same RAM buffers so reads/writes
      from emulated code and from the host API share the same data.
"""

import logging
import struct
from typing import Dict, List, Optional, Tuple

from .peripherals.base_peripheral import BasePeripheral

logger = logging.getLogger(__name__)


class MemoryBank:
    """A contiguous region of RAM backed by a bytearray."""

    __slots__ = ("base", "size", "data", "name")

    def __init__(self, name: str, base: int, size: int):
        self.name = name
        self.base = base
        self.size = size
        self.data = bytearray(size)

    def contains(self, addr: int) -> bool:
        return self.base <= addr < self.base + self.size

    def read(self, addr: int, size: int) -> int:
        offset = addr - self.base
        if size == 1:
            return self.data[offset]
        elif size == 2:
            return struct.unpack_from("<H", self.data, offset)[0]
        elif size == 4:
            return struct.unpack_from("<I", self.data, offset)[0]
        elif size == 8:
            return struct.unpack_from("<Q", self.data, offset)[0]
        else:
            raise ValueError(f"Unsupported read size: {size}")

    def write(self, addr: int, size: int, value: int) -> None:
        offset = addr - self.base
        if size == 1:
            self.data[offset] = value & 0xFF
        elif size == 2:
            struct.pack_into("<H", self.data, offset, value & 0xFFFF)
        elif size == 4:
            struct.pack_into("<I", self.data, offset, value & 0xFFFFFFFF)
        elif size == 8:
            struct.pack_into("<Q", self.data, offset, value & 0xFFFFFFFFFFFFFFFF)
        else:
            raise ValueError(f"Unsupported write size: {size}")

    def read_bytes(self, addr: int, length: int) -> bytes:
        """Bulk read *length* bytes starting at *addr*."""
        offset = addr - self.base
        return bytes(self.data[offset : offset + length])

    def write_bytes(self, addr: int, data: bytes) -> None:
        """Bulk write *data* starting at *addr*."""
        offset = addr - self.base
        self.data[offset : offset + len(data)] = data

    def __repr__(self):
        return (
            f"<MemoryBank '{self.name}' "
            f"0x{self.base:09X}–0x{self.base + self.size - 1:09X} "
            f"({self.size // (1024*1024)} MB)>"
        )


class MemoryController:
    """BCM2711 35-bit physical address space controller.

    Routes memory accesses to RAM banks or MMIO peripherals.

    Args:
        ram_size_bytes: Total RAM in bytes. Default 8 GB.
        bank_size_bytes: Maximum size of each RAM bank. Default 1 GB.
                         Splitting avoids a single huge allocation.
    """

    # ── BCM2711 MMIO windows ──────────────────────────────────────
    MMIO_LEGACY_BASE = 0x0_FC00_0000
    MMIO_LEGACY_END  = 0x1_0000_0000  # exclusive

    # The total physical address space is 35 bits = 32 GB
    PA_BITS = 35
    PA_MAX  = 1 << PA_BITS  # 0x8_0000_0000

    def __init__(
        self,
        ram_size_bytes: int = 8 * 1024 * 1024 * 1024,  # 8 GB
        bank_size_bytes: int = 1 * 1024 * 1024 * 1024,  # 1 GB banks
    ):
        self.ram_size = ram_size_bytes
        self.bank_size = bank_size_bytes
        self.banks: List[MemoryBank] = []
        self.peripherals: List[BasePeripheral] = []
        self._peripheral_map: Dict[Tuple[int, int], BasePeripheral] = {}

        self._create_ram_banks()

    # ── RAM bank layout ───────────────────────────────────────────

    def _create_ram_banks(self):
        """Allocate RAM banks, leaving a hole for the MMIO window.

        BCM2711 physical RAM layout for 8 GB:
            Bank 0:  0x0_0000_0000 – 0x0_3FFF_FFFF  (1 GB)
            Bank 1:  0x0_4000_0000 – 0x0_7FFF_FFFF  (1 GB)
            Bank 2:  0x0_8000_0000 – 0x0_BFFF_FFFF  (1 GB)
            Bank 3:  0x0_C000_0000 – 0x0_FBFF_FFFF  (960 MB, stops before MMIO)
            -- MMIO hole: 0x0_FC00_0000 – 0x0_FFFF_FFFF --
            Bank 4:  0x1_0000_0000 – 0x1_3FFF_FFFF  (1 GB)
            Bank 5:  0x1_4000_0000 – 0x1_7FFF_FFFF  (1 GB)
            Bank 6:  0x1_8000_0000 – 0x1_BFFF_FFFF  (1 GB)
            Bank 7:  0x1_C000_0000 – 0x1_FFFF_FFFF  (1 GB)
            Total RAM: ~7.9375 GB usable (MMIO hole eats 64 MB)
        """
        allocated = 0
        bank_id = 0
        addr = 0

        while allocated < self.ram_size and addr < self.PA_MAX:
            # Skip the MMIO hole
            if addr >= self.MMIO_LEGACY_BASE and addr < self.MMIO_LEGACY_END:
                addr = self.MMIO_LEGACY_END
                continue

            # How much can we allocate before hitting the MMIO hole or exhausting RAM?
            remaining = self.ram_size - allocated
            space_to_mmio = (self.MMIO_LEGACY_BASE - addr) if addr < self.MMIO_LEGACY_BASE else self.bank_size
            chunk = min(self.bank_size, remaining, space_to_mmio)

            if chunk <= 0:
                addr += self.bank_size
                continue

            bank = MemoryBank(f"RAM_{bank_id}", addr, chunk)
            self.banks.append(bank)
            logger.info("Created %s", bank)
            allocated += chunk
            addr += chunk
            bank_id += 1

        logger.info(
            "Memory controller: %d banks, %d MB total RAM",
            len(self.banks),
            allocated // (1024 * 1024),
        )

    # ── Peripheral registration ───────────────────────────────────

    def register_peripheral(self, peripheral: BasePeripheral) -> None:
        """Register a peripheral for MMIO routing."""
        self.peripherals.append(peripheral)
        key = (peripheral.BASE_ADDR, peripheral.BASE_ADDR + peripheral.SIZE)
        self._peripheral_map[key] = peripheral
        logger.info("Registered %s", peripheral)

    def _find_peripheral(self, addr: int) -> Optional[BasePeripheral]:
        """Find the peripheral that owns *addr*, or None."""
        for (base, end), periph in self._peripheral_map.items():
            if base <= addr < end:
                return periph
        return None

    # ── Unified read/write interface ──────────────────────────────

    def read(self, addr: int, size: int) -> int:
        """Read *size* bytes from physical address *addr*.

        Routes to RAM banks or MMIO peripherals as appropriate.
        """
        # Check MMIO first (smaller search space)
        if self.MMIO_LEGACY_BASE <= addr < self.MMIO_LEGACY_END:
            periph = self._find_peripheral(addr)
            if periph:
                offset = addr - periph.BASE_ADDR
                return periph.read(offset, size)
            logger.warning(
                "MMIO read from unmapped address 0x%09X (size=%d)", addr, size
            )
            return 0

        # RAM access
        for bank in self.banks:
            if bank.contains(addr):
                return bank.read(addr, size)

        logger.warning(
            "Read from unmapped physical address 0x%09X (size=%d)", addr, size
        )
        return 0

    def write(self, addr: int, size: int, value: int) -> None:
        """Write *value* (*size* bytes) to physical address *addr*."""
        # Check MMIO first
        if self.MMIO_LEGACY_BASE <= addr < self.MMIO_LEGACY_END:
            periph = self._find_peripheral(addr)
            if periph:
                offset = addr - periph.BASE_ADDR
                periph.write(offset, size, value)
                return
            logger.warning(
                "MMIO write to unmapped address 0x%09X ← 0x%X (size=%d)",
                addr, value, size,
            )
            return

        # RAM access
        for bank in self.banks:
            if bank.contains(addr):
                bank.write(addr, size, value)
                return

        logger.warning(
            "Write to unmapped physical address 0x%09X ← 0x%X (size=%d)",
            addr, value, size,
        )

    # ── Bulk access (for loading kernels, DTBs, etc.) ─────────────

    def write_bytes(self, addr: int, data: bytes) -> None:
        """Write a block of bytes starting at *addr*.

        Handles cross-bank boundaries.
        """
        remaining = data
        current_addr = addr

        while remaining:
            for bank in self.banks:
                if bank.contains(current_addr):
                    bank_end = bank.base + bank.size
                    space = bank_end - current_addr
                    chunk_len = min(space, len(remaining))
                    bank.write_bytes(current_addr, remaining[:chunk_len])
                    remaining = remaining[chunk_len:]
                    current_addr += chunk_len
                    break
            else:
                logger.error(
                    "write_bytes: address 0x%09X not in any RAM bank",
                    current_addr,
                )
                break

    def read_bytes(self, addr: int, length: int) -> bytes:
        """Read *length* bytes starting at *addr*."""
        result = bytearray()
        current_addr = addr
        remaining = length

        while remaining > 0:
            for bank in self.banks:
                if bank.contains(current_addr):
                    bank_end = bank.base + bank.size
                    space = bank_end - current_addr
                    chunk_len = min(space, remaining)
                    result.extend(bank.read_bytes(current_addr, chunk_len))
                    current_addr += chunk_len
                    remaining -= chunk_len
                    break
            else:
                logger.error(
                    "read_bytes: address 0x%09X not in any RAM bank",
                    current_addr,
                )
                break

        return bytes(result)

    # ── Info / Debug ──────────────────────────────────────────────

    def get_ram_info(self) -> dict:
        """Return a summary of the RAM layout."""
        total = sum(b.size for b in self.banks)
        return {
            "total_bytes": total,
            "total_mb": total // (1024 * 1024),
            "bank_count": len(self.banks),
            "banks": [
                {
                    "name": b.name,
                    "base": f"0x{b.base:09X}",
                    "size_mb": b.size // (1024 * 1024),
                }
                for b in self.banks
            ],
            "peripheral_count": len(self.peripherals),
            "peripherals": [repr(p) for p in self.peripherals],
        }
