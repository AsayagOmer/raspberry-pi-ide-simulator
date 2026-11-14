#!/usr/bin/env python3
"""
RPi4 Emulator — Command-Line Runner

Usage:
    # Run UART test (built-in)
    python run_emulator.py --test uart

    # Run memory boundary test (built-in)
    python run_emulator.py --test memory

    # Run multicore test (built-in)
    python run_emulator.py --test multicore

    # Load and run a bare-metal binary
    python run_emulator.py --binary firmware/test.bin --addr 0x80000

    # Boot a Linux kernel
    python run_emulator.py --kernel path/to/Image --dtb path/to/bcm2711-rpi-4-b.dtb \\
        --disk path/to/raspios.img --cmdline "earlycon=pl011,0xfe201000 console=ttyAMA0"

    # Run all built-in tests
    python run_emulator.py --test all

    # Run unit tests
    python run_emulator.py --unittest
"""

import argparse
import logging
import sys
import time
import os

# Ensure src/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from emulator.soc import BCM2711SoC
from emulator import __version__


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(name)-30s %(levelname)-5s %(message)s",
        datefmt="%H:%M:%S",
    )


def uart_output_handler(byte_val: int):
    """Print UART output to stdout in real-time."""
    ch = chr(byte_val) if 32 <= byte_val < 127 or byte_val in (10, 13) else '.'
    sys.stdout.write(ch)
    sys.stdout.flush()


def run_builtin_test(test_name: str, timeout: float = 5.0):
    """Run a built-in test binary and report results."""
    from emulator.boot import (
        create_uart_test_binary,
        create_memory_test_binary,
        create_multicore_test_binary,
        assemble_aarch64,
        disassemble_aarch64,
    )

    print(f"\n{'='*60}")
    print(f"  RPi4 Emulator — Test: {test_name}")
    print(f"{'='*60}\n")

    # Create SoC with small RAM for tests
    soc = BCM2711SoC(
        ram_size_gb=1,
        uart_callback=uart_output_handler,
        throttle=False,
    )

    try:
        if test_name == "uart":
            binary = create_uart_test_binary()
            print(f"Assembled UART test binary ({len(binary)} bytes)")
            print(f"Disassembly:\n{disassemble_aarch64(binary, 0x80000)}\n")
            print("--- UART Output ---")
            soc.load_binary(binary, 0x80000)
            soc.start(multicore=False)
            time.sleep(timeout)

        elif test_name == "memory":
            binary = create_memory_test_binary()
            print(f"Assembled memory test binary ({len(binary)} bytes)")
            print("--- Test Output ---")
            soc.load_binary(binary, 0x80000)
            soc.start(multicore=False)
            time.sleep(timeout)

        elif test_name == "multicore":
            binary = create_multicore_test_binary()
            print(f"Assembled multicore test binary ({len(binary)} bytes)")
            print("--- Test Output ---")
            soc.load_binary(binary, 0x80000)
            soc.start(multicore=True)
            time.sleep(timeout)

        else:
            print(f"Unknown test: {test_name}")
            return False

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        soc.stop()

    # Print results
    output = soc.peek_uart_output()
    print(f"\n\n--- Results ---")
    print(f"UART output: {repr(output)}")
    print(f"Core 0: {soc.cores[0]}")
    print(f"Status: {soc.get_status()['gic']}")

    return "PASS" in output or (test_name == "uart" and len(output) > 0)


def run_kernel(args):
    """Boot a Linux kernel."""
    from emulator.boot import load_kernel_from_files

    print(f"\n{'='*60}")
    print(f"  RPi4 Emulator — Linux Kernel Boot")
    print(f"{'='*60}\n")

    soc = BCM2711SoC(
        ram_size_gb=args.ram or 8,
        disk_image_path=args.disk,
        uart_callback=uart_output_handler,
        throttle=not args.no_throttle,
    )

    cmdline = args.cmdline or "earlycon=pl011,0xfe201000 console=ttyAMA0,115200"

    load_kernel_from_files(
        soc,
        kernel_path=args.kernel,
        dtb_path=args.dtb,
        cmdline=cmdline,
    )

    print(f"\nBooting kernel... (Ctrl+C to stop)\n")
    print("--- Console Output ---")

    soc.start(multicore=True)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping emulation...")
    finally:
        soc.stop()
        print(f"\nFull UART output ({len(soc._uart_buffer)} bytes):")
        print(soc.peek_uart_output()[:4096])


def run_binary(args):
    """Run a bare-metal binary."""
    from emulator.boot import load_binary_from_file

    print(f"\n{'='*60}")
    print(f"  RPi4 Emulator — Bare-Metal Binary")
    print(f"{'='*60}\n")

    addr = int(args.addr, 16) if args.addr else 0x80000

    soc = BCM2711SoC(
        ram_size_gb=1,
        uart_callback=uart_output_handler,
        throttle=not args.no_throttle,
    )

    load_binary_from_file(soc, args.binary, addr)

    print(f"\nRunning binary at 0x{addr:X}... (Ctrl+C to stop)\n")
    print("--- Console Output ---")

    soc.start(multicore=args.multicore)

    try:
        timeout = args.timeout or 10
        time.sleep(timeout)
    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        soc.stop()
        output = soc.peek_uart_output()
        if output:
            print(f"\nUART output: {output}")


def run_unittests():
    """Run the emulator unit test suite."""
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "src/emulator/tests/", "-v", "--tb=short"],
        cwd=os.path.dirname(__file__) or ".",
    )
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(
        description="Raspberry Pi 4 Model B (BCM2711) Emulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_emulator.py --test uart          Run UART output test
  python run_emulator.py --test memory        Run 8GB memory boundary test
  python run_emulator.py --test multicore     Run quad-core boot test
  python run_emulator.py --test all           Run all built-in tests
  python run_emulator.py --unittest           Run unit test suite
  python run_emulator.py --binary test.bin    Run a bare-metal binary
  python run_emulator.py --kernel Image --dtb bcm2711.dtb  Boot Linux kernel
        """,
    )

    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--test", choices=["uart", "memory", "multicore", "all"],
                       help="Run a built-in test")
    group.add_argument("--binary", type=str, help="Path to bare-metal binary")
    group.add_argument("--kernel", type=str, help="Path to Linux kernel Image")
    group.add_argument("--unittest", action="store_true", help="Run unit test suite")

    parser.add_argument("--dtb", type=str, help="Path to device tree blob (.dtb)")
    parser.add_argument("--disk", type=str, help="Path to SD card image (.img)")
    parser.add_argument("--addr", type=str, default="0x80000", help="Load address (hex)")
    parser.add_argument("--cmdline", type=str, help="Kernel command line")
    parser.add_argument("--ram", type=int, default=8, help="RAM size in GB")
    parser.add_argument("--timeout", type=float, default=10, help="Timeout in seconds")
    parser.add_argument("--no-throttle", action="store_true", help="Run at max speed")
    parser.add_argument("--multicore", action="store_true", help="Enable all 4 cores")

    args = parser.parse_args()
    setup_logging(args.verbose)

    print(f"🍓 Raspberry Pi 4 Model B Emulator v{__version__}")
    print(f"   BCM2711 | 4× Cortex-A72 @ 1.5 GHz | {args.ram} GB RAM")
    print()

    if args.unittest:
        success = run_unittests()
        sys.exit(0 if success else 1)

    elif args.test:
        if args.test == "all":
            results = {}
            for t in ["uart", "memory", "multicore"]:
                results[t] = run_builtin_test(t)
            print(f"\n{'='*60}")
            print("  Summary:")
            for t, passed in results.items():
                status = "✅ PASS" if passed else "❌ FAIL"
                print(f"    {t:20s} {status}")
            print(f"{'='*60}")
            sys.exit(0 if all(results.values()) else 1)
        else:
            success = run_builtin_test(args.test, args.timeout)
            sys.exit(0 if success else 1)

    elif args.kernel:
        if not args.dtb:
            parser.error("--kernel requires --dtb")
        run_kernel(args)

    elif args.binary:
        run_binary(args)


if __name__ == "__main__":
    main()
