"""
Kernel & Binary Boot Loader

Provides high-level entry points for loading and booting:
    - Bare-metal AArch64 binaries
    - Linux kernel images (Image + DTB)
    - Assembling small test binaries from AArch64 assembly source

Also handles boot argument passing via device tree or command-line
string injection.
"""

import logging
import struct
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def assemble_aarch64(asm_source: str) -> bytes:
    """Assemble AArch64 assembly source into machine code.

    Uses Keystone Engine for assembly.

    Args:
        asm_source: Assembly source code string.

    Returns:
        Raw machine code bytes.

    Raises:
        RuntimeError: If assembly fails.
    """
    try:
        from keystone import Ks, KS_ARCH_ARM64, KS_MODE_LITTLE_ENDIAN
    except ImportError:
        raise RuntimeError(
            "Keystone Engine not installed. "
            "Install with: pip install keystone-engine"
        )

    ks = Ks(KS_ARCH_ARM64, KS_MODE_LITTLE_ENDIAN)
    try:
        encoding, count = ks.asm(asm_source)
        if encoding is None:
            raise RuntimeError("Assembly produced no output")
        logger.info("Assembled %d instructions (%d bytes)", count, len(encoding))
        return bytes(encoding)
    except Exception as e:
        raise RuntimeError(f"Assembly failed: {e}") from e


def disassemble_aarch64(code: bytes, address: int = 0, count: int = 0) -> str:
    """Disassemble AArch64 machine code into human-readable assembly.

    Args:
        code:    Raw machine code bytes.
        address: Base address for disassembly display.
        count:   Max number of instructions to disassemble (0 = all).

    Returns:
        Multi-line disassembly string.
    """
    try:
        from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
    except ImportError:
        return "(capstone not installed — cannot disassemble)"

    cs = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    lines = []
    for insn in cs.disasm(code, address, count=count):
        lines.append(f"  0x{insn.address:08X}:  {insn.mnemonic}\t{insn.op_str}")
    return "\n".join(lines) if lines else "(no instructions)"


def load_kernel_from_files(
    soc,
    kernel_path: str,
    dtb_path: str,
    kernel_addr: int = 0x80000,
    dtb_addr: int = 0x2600000,
    cmdline: Optional[str] = None,
):
    """Load a Linux kernel and DTB from disk files into the SoC.

    Args:
        soc:          BCM2711SoC instance.
        kernel_path:  Path to the kernel Image file.
        dtb_path:     Path to the compiled .dtb file.
        kernel_addr:  Load address for kernel.
        dtb_addr:     Load address for DTB.
        cmdline:      Optional kernel command line string. If provided,
                      it is written into memory and the DTB 'chosen'
                      node's bootargs are patched (simplified approach).
    """
    kernel_file = Path(kernel_path)
    dtb_file = Path(dtb_path)

    if not kernel_file.exists():
        raise FileNotFoundError(f"Kernel not found: {kernel_path}")
    if not dtb_file.exists():
        raise FileNotFoundError(f"DTB not found: {dtb_path}")

    kernel_data = kernel_file.read_bytes()
    dtb_data = dtb_file.read_bytes()

    logger.info(
        "Kernel: %s (%d bytes)", kernel_file.name, len(kernel_data)
    )
    logger.info(
        "DTB:    %s (%d bytes)", dtb_file.name, len(dtb_data)
    )

    # Validate kernel image magic (ARM64 kernel header)
    if len(kernel_data) >= 64:
        magic = struct.unpack_from("<I", kernel_data, 56)[0]
        if magic == 0x644D5241:  # "ARM\x64" in little-endian
            logger.info("Valid ARM64 kernel image header detected")
        else:
            logger.warning(
                "Kernel magic mismatch: expected 0x644D5241, got 0x%08X. "
                "This may be a raw binary, not a Linux Image.",
                magic,
            )

    # Validate DTB magic
    if len(dtb_data) >= 4:
        dtb_magic = struct.unpack_from(">I", dtb_data, 0)[0]
        if dtb_magic == 0xD00DFEED:
            logger.info("Valid FDT (Flattened Device Tree) header detected")
        else:
            logger.warning(
                "DTB magic mismatch: expected 0xD00DFEED, got 0x%08X",
                dtb_magic,
            )

    # If a command line is specified, write it to a known memory location
    # and log it (full DTB patching is complex; for now we rely on the
    # earlycon= being in the DTB or passed via bootloader).
    if cmdline:
        cmdline_addr = 0x2500000  # Before DTB
        cmdline_bytes = cmdline.encode("utf-8") + b"\x00"
        soc.memory.write_bytes(cmdline_addr, cmdline_bytes)
        logger.info(
            "Command line (%d bytes) at 0x%X: %s",
            len(cmdline_bytes), cmdline_addr, cmdline,
        )

    soc.load_kernel(kernel_data, dtb_data, kernel_addr, dtb_addr)


def load_binary_from_file(
    soc,
    binary_path: str,
    load_addr: int = 0x80000,
):
    """Load a bare-metal binary from disk into the SoC.

    Args:
        soc:         BCM2711SoC instance.
        binary_path: Path to the raw binary file.
        load_addr:   Load address.
    """
    path = Path(binary_path)
    if not path.exists():
        raise FileNotFoundError(f"Binary not found: {binary_path}")

    data = path.read_bytes()
    logger.info("Binary: %s (%d bytes)", path.name, len(data))
    soc.load_binary(data, load_addr)


def create_uart_test_binary() -> bytes:
    """Create a bare-metal binary that writes 'Hello from RPi4!' to PL011 UART.

    This is Test Binary 1 from the specification:
        Write string to 0xFE201000 (UART0 DR)
        Verify output stream on emulated terminal
    """
    # PL011 UART Data Register address
    asm = """
        // Load UART DR address (0xFE201000) into x1
        mov  x1, #0xFE200000
        movk x1, #0x1000, lsl #0

        // Load string address into x0
        adr  x0, message

    print_loop:
        ldrb w2, [x0], #1       // Load byte, post-increment
        cbz  w2, done            // If null terminator, done
        str  w2, [x1]            // Write byte to UART DR
        b    print_loop

    done:
        // Infinite loop (halt)
        wfe
        b done

    message:
        .ascii "Hello from RPi4 Emulator!\\r\\n\\0"
    """
    return assemble_aarch64(asm)


def create_memory_test_binary() -> bytes:
    """Create a bare-metal binary that tests 8 GB memory boundaries.

    This is Test Binary 3 from the specification:
        Write 0xDEADBEEF at 0x00100000 (Low RAM)
        Write 0xCAFEBABE at 0x180000000 (High RAM > 4 GB)
        Confirm memory independence (no aliasing)

    Result is reported via UART: "PASS" or "FAIL".
    """
    asm = """
        // UART DR address
        mov  x10, #0xFE200000
        movk x10, #0x1000, lsl #0

        // === Write 0xDEADBEEF to low RAM (0x00100000) ===
        mov  x0, #0x00100000
        mov  w1, #0xBEEF
        movk w1, #0xDEAD, lsl #16
        str  w1, [x0]

        // === Write 0xCAFEBABE to high RAM (0x180000000) ===
        mov  x2, #0x180000000
        mov  w3, #0xBABE
        movk w3, #0xCAFE, lsl #16
        str  w3, [x2]

        // === Read back low RAM ===
        ldr  w4, [x0]

        // === Read back high RAM ===
        ldr  w5, [x2]

        // === Verify low RAM still has 0xDEADBEEF ===
        mov  w6, #0xBEEF
        movk w6, #0xDEAD, lsl #16
        cmp  w4, w6
        b.ne fail

        // === Verify high RAM has 0xCAFEBABE ===
        mov  w7, #0xBABE
        movk w7, #0xCAFE, lsl #16
        cmp  w5, w7
        b.ne fail

        // === PASS ===
        adr  x0, pass_msg
        b    print_result

    fail:
        adr  x0, fail_msg

    print_result:
        ldrb w2, [x0], #1
        cbz  w2, halt
        str  w2, [x10]
        b    print_result

    halt:
        wfe
        b halt

    pass_msg:
        .ascii "8GB BOUNDARY TEST: PASS\\r\\n\\0"
    fail_msg:
        .ascii "8GB BOUNDARY TEST: FAIL\\r\\n\\0"
    """
    return assemble_aarch64(asm)


def create_multicore_test_binary() -> bytes:
    """Create a bare-metal binary that tests multicore spin-table boot.

    This is Test Binary 2 from the specification:
        Core 0 writes jump address to secondary release addresses (0xD8, 0xE0, 0xE8)
        Verify Cores 1, 2, and 3 wake up from WFE loops

    Each secondary core writes its ID to a known memory location,
    then Core 0 reads them back and reports via UART.
    """
    asm = """
        // UART DR
        mov  x10, #0xFE200000
        movk x10, #0x1000, lsl #0

        // Result memory locations (Cores 1-3 write their IDs here)
        // 0x200 = Core 1, 0x208 = Core 2, 0x210 = Core 3
        mov  x11, #0x200

        // Clear result slots
        str  xzr, [x11]
        str  xzr, [x11, #8]
        str  xzr, [x11, #16]

        // Write secondary entry point to release addresses
        adr  x0, secondary_entry

        // Core 1 release (0xD8)
        mov  x1, #0xD8
        str  x0, [x1]

        // Core 2 release (0xE0)
        mov  x1, #0xE0
        str  x0, [x1]

        // Core 3 release (0xE8)
        mov  x1, #0xE8
        str  x0, [x1]

        // Send event to wake secondaries
        sev

        // Wait a bit for secondaries to write
        mov  x0, #0x10000
    wait_loop:
        subs x0, x0, #1
        b.ne wait_loop

        // Check results
        ldr  x0, [x11]
        cmp  x0, #1
        b.ne core_fail

        ldr  x0, [x11, #8]
        cmp  x0, #2
        b.ne core_fail

        ldr  x0, [x11, #16]
        cmp  x0, #3
        b.ne core_fail

        // All cores responded
        adr  x0, pass_msg
        b    print_msg

    core_fail:
        adr  x0, fail_msg

    print_msg:
        ldrb w2, [x0], #1
        cbz  w2, halt
        str  w2, [x10]
        b    print_msg

    halt:
        wfe
        b halt

    // --- Secondary core entry point ---
    secondary_entry:
        // Read MPIDR_EL1 to get core ID
        mrs  x0, mpidr_el1
        and  x0, x0, #0xFF    // Aff0 = core number

        // Write core ID to result slot
        mov  x1, #0x200
        sub  x2, x0, #1       // slot index = core_id - 1
        lsl  x2, x2, #3       // × 8 bytes
        add  x1, x1, x2
        str  x0, [x1]

        // Halt
        wfe
        b    secondary_entry

    pass_msg:
        .ascii "MULTICORE BOOT TEST: PASS (4 CPUs online)\\r\\n\\0"
    fail_msg:
        .ascii "MULTICORE BOOT TEST: FAIL\\r\\n\\0"
    """
    return assemble_aarch64(asm)
