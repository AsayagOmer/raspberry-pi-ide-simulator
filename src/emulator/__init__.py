"""
BCM2711 (Raspberry Pi 4 Model B) Full-System Emulator

ARMv8-A (AArch64) quad-core Cortex-A72 emulation with BCM2711
peripheral models. Capable of running bare-metal binaries and
booting a Linux kernel.

Architecture:
    - CPU:         Unicorn Engine (AArch64) × 4 cores
    - Memory:      8 GB RAM + 35-bit physical address space
    - Peripherals: GIC-400, PL011 UART, Generic Timers,
                   VideoCore Mailbox, eMMC2/SDHCI, GPIO
"""

__version__ = "0.1.0"
