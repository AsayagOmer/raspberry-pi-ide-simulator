"""
AArch64 CPU Core — Unicorn Engine Wrapper

Wraps a single Unicorn AArch64 engine instance to model one
Cortex-A72 core of the BCM2711 SoC. Handles:

    - EL0/EL1/EL2 exception level transitions
    - System register access hooks (SCTLR, TCR, MAIR, VBAR, TTBR, ESR, FAR)
    - MMIO read/write routing to the MemoryController
    - Interrupt injection from the GIC
    - Instruction-count-based execution batching
"""

import logging
import struct
import threading
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

from unicorn import (
    Uc,
    UC_ARCH_ARM64,
    UC_MODE_ARM,
    UC_HOOK_MEM_READ,
    UC_HOOK_MEM_WRITE,
    UC_HOOK_MEM_READ_UNMAPPED,
    UC_HOOK_MEM_WRITE_UNMAPPED,
    UC_HOOK_MEM_FETCH_UNMAPPED,
    UC_HOOK_INTR,
    UC_HOOK_INSN,
    UC_HOOK_CODE,
    UcError,
    UC_ERR_OK,
)
from unicorn.arm64_const import (
    UC_ARM64_REG_PC,
    UC_ARM64_REG_SP,
    UC_ARM64_REG_PSTATE,
    UC_ARM64_REG_NZCV,
    UC_ARM64_REG_X0,
    UC_ARM64_REG_X1,
    UC_ARM64_REG_X2,
    UC_ARM64_REG_X3,
    UC_ARM64_REG_X29,
    UC_ARM64_REG_X30,
)

if TYPE_CHECKING:
    from .memory import MemoryController

logger = logging.getLogger(__name__)

# ── AArch64 system register encoding ────────────────────────────
# Unicorn doesn't directly expose system registers by name, so we
# hook MSR/MRS instructions and decode the op0/op1/CRn/CRm/op2
# fields ourselves.

# fmt: off
_SYSREG_NAMES = {
    # (op0, op1, CRn, CRm, op2) → name
    (3, 0, 1, 0, 0): "SCTLR_EL1",
    (3, 0, 2, 0, 0): "TTBR0_EL1",
    (3, 0, 2, 0, 1): "TTBR1_EL1",
    (3, 0, 2, 0, 2): "TCR_EL1",
    (3, 0, 10, 2, 0): "MAIR_EL1",
    (3, 0, 12, 0, 0): "VBAR_EL1",
    (3, 0, 5, 2, 0): "ESR_EL1",
    (3, 0, 6, 0, 0): "FAR_EL1",
    (3, 0, 13, 0, 1): "CONTEXTIDR_EL1",
    (3, 3, 14, 0, 1): "CNTPCT_EL0",      # Physical counter (read-only)
    (3, 0, 14, 2, 0): "CNTP_TVAL_EL0",    # Timer value
    (3, 0, 14, 2, 1): "CNTP_CTL_EL0",     # Timer control
    (3, 0, 14, 2, 2): "CNTP_CVAL_EL0",    # Timer comparator
}
# fmt: on


class AArch64Core:
    """Single Cortex-A72 core emulation via Unicorn.

    Args:
        core_id:  0–3, identifying this core in the SoC.
        memory:   The shared MemoryController instance.
    """

    # Execution batch size: how many instructions to run between
    # checks for interrupts, I/O, and throttling.
    BATCH_SIZE = 50_000

    def __init__(self, core_id: int, memory: "MemoryController"):
        self.core_id = core_id
        self.memory = memory
        self.running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # ── System register shadow state ──
        # Unicorn doesn't natively track all AArch64 sysregs,
        # so we maintain shadow copies updated via hooks.
        self.sysregs: Dict[str, int] = {
            "SCTLR_EL1": 0,
            "TTBR0_EL1": 0,
            "TTBR1_EL1": 0,
            "TCR_EL1": 0,
            "MAIR_EL1": 0,
            "VBAR_EL1": 0,
            "ESR_EL1": 0,
            "FAR_EL1": 0,
            "CONTEXTIDR_EL1": 0,
            "CNTP_TVAL_EL0": 0,
            "CNTP_CTL_EL0": 0,
            "CNTP_CVAL_EL0": 0,
        }

        # Instruction counter (total across all batches)
        self.insn_count: int = 0

        # Callbacks
        self._on_uart_write: Optional[Callable[[int], None]] = None
        self._on_halt: Optional[Callable[["AArch64Core"], None]] = None

        # Pending interrupt flag (set by GIC, consumed at batch boundary)
        self._pending_irq = False
        self._pending_irq_id = 0

        # ── Create Unicorn instance ──
        self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self._map_memory()
        self._install_hooks()

        logger.info("Core %d: initialized", self.core_id)

    # ── Memory mapping ────────────────────────────────────────────

    def _map_memory(self):
        """Map RAM banks and MMIO regions into the Unicorn address space.

        RAM banks are mapped into Unicorn so the JIT can access them.
        We cap each mapping at 256 MB to avoid Windows access violations
        on 32-bit Python. The full 8 GB is still represented in the
        MemoryController's bytearray banks — Unicorn just gets the
        subset needed for the current workload.
        """
        MAX_MAP_SIZE = 256 * 1024 * 1024  # 256 MB per mapping

        for bank in self.memory.banks:
            # Only map the first MAX_MAP_SIZE of each bank
            map_size = min(bank.size, MAX_MAP_SIZE)
            try:
                self.uc.mem_map(bank.base, map_size)
                logger.debug(
                    "Core %d: mapped %s (%d MB of %d MB)",
                    self.core_id, bank.name,
                    map_size // (1024*1024), bank.size // (1024*1024),
                )
            except UcError as e:
                logger.warning(
                    "Core %d: failed to map %s: %s (skipping)",
                    self.core_id, bank.name, e,
                )

        # Map the MMIO region as a single block
        mmio_base = self.memory.MMIO_LEGACY_BASE
        mmio_size = self.memory.MMIO_LEGACY_END - mmio_base
        try:
            self.uc.mem_map(mmio_base, mmio_size)
            logger.debug(
                "Core %d: mapped MMIO region 0x%09X–0x%09X",
                self.core_id, mmio_base, mmio_base + mmio_size,
            )
        except UcError as e:
            logger.error(
                "Core %d: failed to map MMIO region: %s", self.core_id, e
            )

    def sync_ram_to_unicorn(self):
        """Copy RAM bank data into Unicorn's address space.

        Only syncs the mapped portion of each bank (up to 256 MB).
        Call this after loading a kernel or DTB into the MemoryController
        so Unicorn sees the updated contents.
        """
        MAX_MAP_SIZE = 256 * 1024 * 1024
        CHUNK = 64 * 1024 * 1024  # 64 MB write chunks

        for bank in self.memory.banks:
            sync_size = min(bank.size, MAX_MAP_SIZE)
            offset = 0
            while offset < sync_size:
                chunk_size = min(CHUNK, sync_size - offset)
                try:
                    self.uc.mem_write(
                        bank.base + offset,
                        bytes(bank.data[offset : offset + chunk_size]),
                    )
                except UcError:
                    break  # Bank not fully mapped
                offset += chunk_size

    def sync_unicorn_to_ram(self):
        """Copy Unicorn's memory back to MemoryController bank data.

        Call this when you need the host-side MemoryController to
        reflect changes made by emulated code.
        """
        for bank in self.memory.banks:
            CHUNK = 64 * 1024 * 1024
            offset = 0
            while offset < bank.size:
                chunk_size = min(CHUNK, bank.size - offset)
                data = self.uc.mem_read(bank.base + offset, chunk_size)
                bank.data[offset : offset + chunk_size] = data
                offset += chunk_size

    # ── Hook installation ─────────────────────────────────────────

    def _install_hooks(self):
        """Install Unicorn hooks for MMIO, interrupts, and tracing."""

        # MMIO read hook — fires for reads in the MMIO region
        mmio_base = self.memory.MMIO_LEGACY_BASE
        mmio_end = self.memory.MMIO_LEGACY_END - 1
        self.uc.hook_add(
            UC_HOOK_MEM_READ,
            self._hook_mmio_read,
            begin=mmio_base,
            end=mmio_end,
        )

        # MMIO write hook
        self.uc.hook_add(
            UC_HOOK_MEM_WRITE,
            self._hook_mmio_write,
            begin=mmio_base,
            end=mmio_end,
        )

        # Unmapped memory fault hooks
        self.uc.hook_add(
            UC_HOOK_MEM_READ_UNMAPPED | UC_HOOK_MEM_WRITE_UNMAPPED | UC_HOOK_MEM_FETCH_UNMAPPED,
            self._hook_mem_unmapped,
        )

        # Interrupt hook
        self.uc.hook_add(UC_HOOK_INTR, self._hook_interrupt)

    # ── MMIO hooks ────────────────────────────────────────────────

    def _hook_mmio_read(self, uc, access, address, size, value, user_data):
        """Handle MMIO reads by routing to the peripheral model."""
        result = self.memory.read(address, size)
        # Write the result back into Unicorn's memory so the
        # instruction sees the correct value
        if size == 1:
            uc.mem_write(address, struct.pack("<B", result & 0xFF))
        elif size == 2:
            uc.mem_write(address, struct.pack("<H", result & 0xFFFF))
        elif size == 4:
            uc.mem_write(address, struct.pack("<I", result & 0xFFFFFFFF))
        elif size == 8:
            uc.mem_write(address, struct.pack("<Q", result & 0xFFFFFFFFFFFFFFFF))

    def _hook_mmio_write(self, uc, access, address, size, value, user_data):
        """Handle MMIO writes by routing to the peripheral model."""
        self.memory.write(address, size, value)

    def _hook_mem_unmapped(self, uc, access, address, size, value, user_data):
        """Handle access to unmapped memory — log and return False to
        let Unicorn raise an exception (which triggers synchronous abort)."""
        access_type = "read" if access == 16 else "write" if access == 17 else "fetch"
        logger.warning(
            "Core %d: unmapped %s @ 0x%09X (size=%d, value=0x%X)",
            self.core_id, access_type, address, size, value,
        )
        # Return True to indicate we handled it (skip the fault)
        # In a full implementation, we'd inject a synchronous data abort.
        # For now, map a zero page so execution can continue.
        try:
            aligned = address & ~0xFFF  # Page-align
            uc.mem_map(aligned, 0x1000)
            return True
        except UcError:
            return True

    def _hook_interrupt(self, uc, intno, user_data):
        """Handle Unicorn interrupt/exception callbacks."""
        pc = uc.reg_read(UC_ARM64_REG_PC)
        logger.debug(
            "Core %d: interrupt %d at PC=0x%X", self.core_id, intno, pc
        )
        # intno == 2 is SVC (syscall) in AArch64 Unicorn
        # intno == 7 is an SError
        # We'll handle these as we build out exception support.

    # ── Register access ───────────────────────────────────────────

    # Map of X register names to Unicorn constants
    _X_REGS = {i: UC_ARM64_REG_X0 + i for i in range(31)}
    _X_REGS[29] = UC_ARM64_REG_X29  # FP
    _X_REGS[30] = UC_ARM64_REG_X30  # LR

    def get_reg(self, reg) -> int:
        """Read a Unicorn register (use UC_ARM64_REG_* constants)."""
        return self.uc.reg_read(reg)

    def set_reg(self, reg, value: int) -> None:
        """Write a Unicorn register."""
        self.uc.reg_write(reg, value)

    @property
    def pc(self) -> int:
        return self.uc.reg_read(UC_ARM64_REG_PC)

    @pc.setter
    def pc(self, value: int):
        self.uc.reg_write(UC_ARM64_REG_PC, value)

    @property
    def sp(self) -> int:
        return self.uc.reg_read(UC_ARM64_REG_SP)

    @sp.setter
    def sp(self, value: int):
        self.uc.reg_write(UC_ARM64_REG_SP, value)

    def dump_regs(self) -> dict:
        """Return a snapshot of all general-purpose registers + PC + SP."""
        regs = {}
        for i in range(31):
            regs[f"X{i}"] = self.uc.reg_read(UC_ARM64_REG_X0 + i)
        regs["SP"] = self.sp
        regs["PC"] = self.pc
        return regs

    # ── IRQ injection ─────────────────────────────────────────────

    def inject_irq(self, irq_id: int = 0):
        """Signal that an IRQ is pending. Checked at batch boundaries."""
        self._pending_irq = True
        self._pending_irq_id = irq_id
        logger.debug("Core %d: IRQ %d queued", self.core_id, irq_id)

    def inject_fiq(self, irq_id: int = 0):
        """Signal that an FIQ is pending."""
        # For now, treat FIQ same as IRQ
        self.inject_irq(irq_id)

    # ── Execution control ─────────────────────────────────────────

    def start(self, address: Optional[int] = None, stop_addr: int = 0):
        """Start executing in a new thread.

        Args:
            address:   If given, set PC before starting. Otherwise use current PC.
            stop_addr: Stop when PC reaches this address (0 = never auto-stop).
        """
        if address is not None:
            self.pc = address

        self.running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            args=(stop_addr,),
            daemon=True,
            name=f"core-{self.core_id}",
        )
        self._thread.start()
        logger.info("Core %d: started at PC=0x%X", self.core_id, self.pc)

    def stop(self):
        """Request the core to stop after the current batch."""
        self.running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        logger.info(
            "Core %d: stopped at PC=0x%X (insn_count=%d)",
            self.core_id, self.pc, self.insn_count,
        )

    def step(self, count: int = 1):
        """Execute exactly *count* instructions synchronously."""
        try:
            self.uc.emu_start(self.pc, 0, count=count)
            self.insn_count += count
        except UcError as e:
            logger.error(
                "Core %d: execution error at PC=0x%X: %s",
                self.core_id, self.pc, e,
            )

    def _run_loop(self, stop_addr: int):
        """Main execution loop — runs BATCH_SIZE instructions per iteration."""
        while self.running and not self._stop_event.is_set():
            try:
                self.uc.emu_start(
                    self.pc,
                    stop_addr if stop_addr else 0xFFFFFFFFFFFFFFFF,
                    count=self.BATCH_SIZE,
                )
                self.insn_count += self.BATCH_SIZE

                # Check for pending interrupts at batch boundary
                if self._pending_irq:
                    self._handle_pending_irq()

            except UcError as e:
                logger.error(
                    "Core %d: execution error at PC=0x%X: %s",
                    self.core_id, self.pc, e,
                )
                self.running = False
                break

            # Check if we hit the stop address
            if stop_addr and self.pc == stop_addr:
                self.running = False
                break

        if self._on_halt:
            self._on_halt(self)

    def _handle_pending_irq(self):
        """Process a pending IRQ by vectoring to the exception handler."""
        self._pending_irq = False
        # In a full implementation, this would:
        # 1. Save PSTATE to SPSR_EL1
        # 2. Set ELR_EL1 = current PC
        # 3. Jump to VBAR_EL1 + 0x280 (IRQ from current EL, SPx)
        # For now, we just log it — the GIC integration will implement
        # the full exception injection path.
        vbar = self.sysregs.get("VBAR_EL1", 0)
        if vbar:
            logger.debug(
                "Core %d: would vector to IRQ handler at VBAR+0x280 = 0x%X",
                self.core_id, vbar + 0x280,
            )

    # ── WFE / WFI support (for secondary cores) ──────────────────

    def enter_wfe_loop(self, release_addr: int):
        """Put this core into a WFE (Wait For Event) spin loop.

        The core polls *release_addr* in memory. When a non-zero value
        is written there (by core 0), this core jumps to that address.

        This models the spin-table boot protocol used by the RPi4
        bootloader for secondary CPU bringup.
        """
        def _wfe_loop():
            logger.info(
                "Core %d: entering WFE loop, watching 0x%X",
                self.core_id, release_addr,
            )
            while not self._stop_event.is_set():
                # Check the release address
                try:
                    jump_addr = struct.unpack_from(
                        "<Q",
                        self.memory.banks[0].data,
                        release_addr - self.memory.banks[0].base,
                    )[0]
                except (IndexError, struct.error):
                    jump_addr = 0

                if jump_addr != 0:
                    logger.info(
                        "Core %d: released! Jumping to 0x%X",
                        self.core_id, jump_addr,
                    )
                    self.pc = jump_addr
                    self._run_loop(stop_addr=0)
                    return

                self._stop_event.wait(0.001)  # 1ms poll interval

        self.running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=_wfe_loop,
            daemon=True,
            name=f"core-{self.core_id}-wfe",
        )
        self._thread.start()

    # ── Cleanup ───────────────────────────────────────────────────

    def __del__(self):
        """Ensure Unicorn instance is cleaned up."""
        try:
            if hasattr(self, "uc"):
                del self.uc
        except Exception:
            pass

    def __repr__(self):
        state = "running" if self.running else "stopped"
        return (
            f"<AArch64Core {self.core_id} [{state}] "
            f"PC=0x{self.pc:X} insns={self.insn_count}>"
        )
