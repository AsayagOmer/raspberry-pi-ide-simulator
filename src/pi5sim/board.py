"""Raspberry Pi 5 Model B (16 GB) facts used by the shell, the backend and the webview."""

MODEL = "Raspberry Pi 5 Model B Rev 1.1"
REVISION = "e04171"  # 16 GB, BCM2712 D0 stepping
SERIAL = "f3a1c0de5e9d7b21"
SOC = "BCM2712"
CORES = 4
ARM_FREQ_MHZ = 2400
ARM_IDLE_MHZ = 1500
MEM_TOTAL_KB = 16_219_256  # what `free` reports on a 16 GB board (firmware/GPU carve-outs removed)
KERNEL = "6.12.25+rpt-rpi-2712"
UNAME_A = (f"Linux raspberrypi {KERNEL} #1 SMP PREEMPT Debian 1:6.12.25-1+rpt1 (2025-04-30) "
           "aarch64 GNU/Linux")

SPECS = {
    "SoC": "Broadcom BCM2712 D0, 4x Arm Cortex-A76 @ 2.4 GHz, 512 KB L2 per core, 2 MB shared L3",
    "GPU": "VideoCore VII @ 800 MHz, OpenGL ES 3.1, Vulkan 1.2, 4Kp60 HEVC decode",
    "Memory": "16 GB LPDDR4X-4267 SDRAM",
    "I/O": "RP1 southbridge over PCIe 2.0 x4 (USB, Ethernet, MIPI, GPIO)",
    "Power": "5 V / 5 A USB-C PD (USB ports limited to 600 mA on a 3 A supply)",
}

# Ports a peripheral can attach to. Keys match the webview's port ids.
PORTS = {
    "gpio_header": "40-pin GPIO header (J8)",
    "usb2_0": "USB 2.0 (top)", "usb2_1": "USB 2.0 (bottom)",
    "usb3_0": "USB 3.0 (top)", "usb3_1": "USB 3.0 (bottom)",
    "cam0": "CAM/DISP 0 (22-pin MIPI)", "cam1": "CAM/DISP 1 (22-pin MIPI)",
    "hdmi0": "micro-HDMI 0", "hdmi1": "micro-HDMI 1",
    "eth": "Gigabit Ethernet (RJ45)", "pcie": "PCIe 2.0 x1 FPC", "fan": "4-pin fan",
    "usbc": "USB-C power", "uart": "3-pin UART debug", "rtc": "RTC battery",
}

# Peripheral id -> (display name, ports it may plug into)
PERIPHERALS = {
    "pirate_audio": ("Pirate Audio (Mic)", ["gpio_header"]),
    "usb_speaker": ("Mini USB 2.0 external speaker", ["usb2_0", "usb2_1", "usb3_0", "usb3_1"]),
    "imx519": ("Arducam IMX519 16MP Autofocus", ["cam0", "cam1"]),
}

# J8 header: physical pin -> (name, function). Odd pins inner row, even pins board edge.
J8 = {
    1: ("3V3", "power"), 2: ("5V", "power"), 3: ("GPIO2", "SDA1"), 4: ("5V", "power"),
    5: ("GPIO3", "SCL1"), 6: ("GND", "ground"), 7: ("GPIO4", "GPCLK0"), 8: ("GPIO14", "TXD0"),
    9: ("GND", "ground"), 10: ("GPIO15", "RXD0"), 11: ("GPIO17", ""), 12: ("GPIO18", "PCM_CLK"),
    13: ("GPIO27", ""), 14: ("GND", "ground"), 15: ("GPIO22", ""), 16: ("GPIO23", ""),
    17: ("3V3", "power"), 18: ("GPIO24", ""), 19: ("GPIO10", "SPI0_MOSI"), 20: ("GND", "ground"),
    21: ("GPIO9", "SPI0_MISO"), 22: ("GPIO25", ""), 23: ("GPIO11", "SPI0_SCLK"), 24: ("GPIO8", "SPI0_CE0"),
    25: ("GND", "ground"), 26: ("GPIO7", "SPI0_CE1"), 27: ("GPIO0", "ID_SD"), 28: ("GPIO1", "ID_SC"),
    29: ("GPIO5", ""), 30: ("GND", "ground"), 31: ("GPIO6", ""), 32: ("GPIO12", "PWM0"),
    33: ("GPIO13", "PWM1"), 34: ("GND", "ground"), 35: ("GPIO19", "PCM_FS"), 36: ("GPIO16", ""),
    37: ("GPIO26", ""), 38: ("GPIO20", "PCM_DIN"), 39: ("GND", "ground"), 40: ("GPIO21", "PCM_DOUT"),
}
GPIO_NUMBERS = sorted(int(n[4:]) for n, _ in J8.values() if n.startswith("GPIO"))


def cpuinfo() -> str:
    core = ("processor\t: {i}\nBogoMIPS\t: 108.00\n"
            "Features\t: fp asimd evtstrm aes pmull sha1 sha2 crc32 atomics fphp asimdhp cpuid "
            "asimdrdm lrcpc dcpop asimddp\nCPU implementer\t: 0x41\nCPU architecture: 8\n"
            "CPU variant\t: 0x4\nCPU part\t: 0xd0b\nCPU revision\t: 1\n\n")
    return ("".join(core.format(i=i) for i in range(CORES))
            + f"Revision\t: {REVISION}\nSerial\t\t: {SERIAL}\nModel\t\t: {MODEL}\n")


def meminfo(used_kb: int) -> str:
    free = MEM_TOTAL_KB - used_kb
    return (f"MemTotal:       {MEM_TOTAL_KB} kB\nMemFree:        {free} kB\n"
            f"MemAvailable:   {free} kB\nSwapTotal:        524272 kB\nSwapFree:         524272 kB\n")


def os_release() -> str:
    return ('PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"\nNAME="Debian GNU/Linux"\nVERSION_ID="12"\n'
            'VERSION="12 (bookworm)"\nVERSION_CODENAME=bookworm\nID=debian\n')
