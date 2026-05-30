"""
NEUROS OS — Board Database
All known boards with their VID:PID, capabilities, and tier mapping.
"""

from dataclasses import dataclass, field
from typing import Optional

# ── Tier constants ──────────────────────────────────────────────
TIER_BASIC    = "basic"
TIER_INTER    = "intermediate"
TIER_ADVANCED = "advanced"
TIER_EXPERT   = "expert"
TIER_CRITICAL = "critical"

TIER_COLORS = {
    TIER_BASIC:    "yellow",
    TIER_INTER:    "green",
    TIER_ADVANCED: "blue",
    TIER_EXPERT:   "magenta",
    TIER_CRITICAL: "red",
}

@dataclass
class BoardCapabilities:
    digital_pins: int = 0
    analog_pins:  int = 0
    pwm_pins:     int = 0
    flash_kb:     int = 0
    ram_kb:       int = 0
    freq_mhz:     float = 0
    uart:         bool = False
    i2c:          bool = False
    spi:          bool = False
    wifi:         bool = False
    bluetooth:    bool = False
    can:          bool = False
    usb_native:   bool = False
    gpio:         bool = False
    adc:          bool = False
    dac:          bool = False
    gpu_cores:    int = 0
    ram_mb:       int = 0   # for Linux SBCs

@dataclass
class BoardDef:
    name:         str
    family:       str
    tier:         str
    chip:         str
    caps:         BoardCapabilities
    driver:       str
    vid:          Optional[int] = None
    pid:          Optional[int] = None
    max_baud:     int = 115200
    description:  str = ""
    aliases:      list = field(default_factory=list)

# ── VID:PID lookup table ─────────────────────────────────────────
VID_PID_MAP: dict[tuple, str] = {
    # Arduino genuine
    (0x2341, 0x0043): "Arduino Uno R3",
    (0x2341, 0x0001): "Arduino Uno R1/R2",
    (0x2341, 0x0010): "Arduino Mega 2560",
    (0x2341, 0x003E): "Arduino Mega 2560 R3",
    (0x2341, 0x0036): "Arduino Leonardo",
    (0x2341, 0x003D): "Arduino Leonardo",
    (0x2341, 0x003B): "Arduino Nano Every",
    (0x2341, 0x0058): "Arduino Nano 33 IoT",
    (0x2341, 0x805A): "Arduino MKR WiFi 1010",
    (0x2341, 0x804E): "Arduino Zero",
    (0x2341, 0x003C): "Arduino Due",
    # Arduino clones (CH340 chip)
    (0x1A86, 0x7523): "Arduino Nano (clone/CH340)",
    (0x1A86, 0x5523): "Arduino Uno (clone/CH340)",
    # ESP32 family (CP2102/CP2104 bridge)
    (0x10C4, 0xEA60): "ESP32 (CP2102)",
    (0x10C4, 0xEA70): "ESP32-S3 (CP2104)",
    # ESP32 family (CH340 bridge)
    (0x1A86, 0x55D4): "ESP32-C3 (CH343)",
    # FTDI-based boards
    (0x0403, 0x6001): "FTDI-based board (FT232R)",
    (0x0403, 0x6010): "FTDI-based board (FT2232)",
    # Teensy
    (0x16C0, 0x0483): "Teensy (PJRC)",
    (0x16C0, 0x0487): "Teensy 4.x (PJRC)",
    # STM32
    (0x0483, 0x5740): "STM32 (ST-Link/VCP)",
    (0x0483, 0x374B): "STM32 Nucleo (ST-Link)",
    # Adafruit
    (0x239A, 0x800B): "Adafruit Feather M0",
    (0x239A, 0x8022): "Adafruit Metro M4",
    (0x239A, None):   "Adafruit board (generic)",
    # Raspberry Pi
    (0x2E8A, 0x0005): "Raspberry Pi Pico",
    (0x2E8A, 0x000A): "Raspberry Pi Pico W",
    # Seeed
    (0x2886, 0x802F): "Seeed XIAO SAMD21",
    (0x2886, 0x8056): "Seeed XIAO ESP32-S3",
}

# ── Full board registry ──────────────────────────────────────────
BOARD_REGISTRY: dict[str, BoardDef] = {

    # ── ARDUINO FAMILY ──────────────────────────────
    "Arduino Uno R3": BoardDef(
        name="Arduino Uno R3", family="Arduino", tier=TIER_BASIC,
        chip="ATmega328P", vid=0x2341, pid=0x0043,
        driver="neuros.drivers.arduino_serial",
        max_baud=115200,
        description="The classic beginner board. 14 digital I/O, 6 analog, 32KB flash.",
        caps=BoardCapabilities(digital_pins=14,analog_pins=6,pwm_pins=6,
            flash_kb=32,ram_kb=2,freq_mhz=16,uart=True,i2c=True,spi=True,gpio=True,adc=True),
    ),
    "Arduino Mega 2560": BoardDef(
        name="Arduino Mega 2560", family="Arduino", tier=TIER_BASIC,
        chip="ATmega2560", vid=0x2341, pid=0x0010,
        driver="neuros.drivers.arduino_serial",
        description="54 digital I/O, 16 analog. Best for projects needing many pins.",
        caps=BoardCapabilities(digital_pins=54,analog_pins=16,pwm_pins=15,
            flash_kb=256,ram_kb=8,freq_mhz=16,uart=True,i2c=True,spi=True,gpio=True,adc=True),
    ),
    "Arduino Nano": BoardDef(
        name="Arduino Nano", family="Arduino", tier=TIER_BASIC,
        chip="ATmega328P", vid=0x1A86, pid=0x7523,
        driver="neuros.drivers.arduino_serial",
        description="Compact Uno-compatible. Popular for embedded builds.",
        caps=BoardCapabilities(digital_pins=14,analog_pins=8,pwm_pins=6,
            flash_kb=32,ram_kb=2,freq_mhz=16,uart=True,i2c=True,spi=True,gpio=True,adc=True),
    ),
    "Arduino Nano Every": BoardDef(
        name="Arduino Nano Every", family="Arduino", tier=TIER_BASIC,
        chip="ATmega4809", vid=0x2341, pid=0x003B,
        driver="neuros.drivers.arduino_serial",
        description="Upgraded Nano with more flash/RAM. Drop-in replacement.",
        caps=BoardCapabilities(digital_pins=14,analog_pins=8,pwm_pins=5,
            flash_kb=48,ram_kb=6,freq_mhz=20,uart=True,i2c=True,spi=True,gpio=True,adc=True),
    ),
    "Arduino Leonardo": BoardDef(
        name="Arduino Leonardo", family="Arduino", tier=TIER_BASIC,
        chip="ATmega32U4", vid=0x2341, pid=0x0036,
        driver="neuros.drivers.arduino_serial",
        description="Built-in USB HID. Can act as keyboard/mouse.",
        caps=BoardCapabilities(digital_pins=20,analog_pins=12,pwm_pins=7,
            flash_kb=32,ram_kb=2,freq_mhz=16,uart=True,i2c=True,spi=True,gpio=True,adc=True,usb_native=True),
    ),
    "Arduino Due": BoardDef(
        name="Arduino Due", family="Arduino", tier=TIER_INTER,
        chip="SAM3X8E (ARM Cortex-M3)", vid=0x2341, pid=0x003C,
        driver="neuros.drivers.arduino_serial",
        description="First Arduino with 32-bit ARM. 96KB RAM, 84MHz.",
        caps=BoardCapabilities(digital_pins=54,analog_pins=12,pwm_pins=12,
            flash_kb=512,ram_kb=96,freq_mhz=84,uart=True,i2c=True,spi=True,gpio=True,adc=True,dac=True),
    ),
    "Arduino Zero": BoardDef(
        name="Arduino Zero", family="Arduino", tier=TIER_INTER,
        chip="ATSAMD21G18 (ARM Cortex-M0+)", vid=0x2341, pid=0x804E,
        driver="neuros.drivers.arduino_serial",
        description="32-bit ARM M0+. Native USB, 256KB flash.",
        caps=BoardCapabilities(digital_pins=14,analog_pins=6,pwm_pins=10,
            flash_kb=256,ram_kb=32,freq_mhz=48,uart=True,i2c=True,spi=True,gpio=True,adc=True,dac=True,usb_native=True),
    ),
    "Arduino MKR WiFi 1010": BoardDef(
        name="Arduino MKR WiFi 1010", family="Arduino", tier=TIER_INTER,
        chip="SAMD21 + U-blox NINA-W10", vid=0x2341, pid=0x805A,
        driver="neuros.drivers.arduino_wifi",
        description="IoT board with built-in WiFi + BLE. Battery connector.",
        caps=BoardCapabilities(digital_pins=8,analog_pins=7,pwm_pins=13,
            flash_kb=256,ram_kb=32,freq_mhz=48,uart=True,i2c=True,spi=True,
            wifi=True,bluetooth=True,gpio=True,adc=True,usb_native=True),
    ),

    # ── ESP FAMILY ──────────────────────────────────
    "ESP32": BoardDef(
        name="ESP32", family="ESP", tier=TIER_BASIC,
        chip="Xtensa LX6 Dual-Core", vid=0x10C4, pid=0xEA60,
        driver="neuros.drivers.esp32_serial",
        max_baud=921600,
        description="Dual-core, WiFi+BT, 34 GPIO. The workhorse of IoT robotics.",
        caps=BoardCapabilities(digital_pins=34,analog_pins=18,pwm_pins=16,
            flash_kb=4096,ram_kb=520,freq_mhz=240,uart=True,i2c=True,spi=True,
            wifi=True,bluetooth=True,gpio=True,adc=True,dac=True),
    ),
    "ESP32-S3": BoardDef(
        name="ESP32-S3", family="ESP", tier=TIER_BASIC,
        chip="Xtensa LX7 Dual-Core", vid=0x10C4, pid=0xEA70,
        driver="neuros.drivers.esp32_serial",
        description="Faster LX7 cores, AI acceleration, USB OTG, 8MB PSRAM option.",
        caps=BoardCapabilities(digital_pins=45,analog_pins=20,pwm_pins=8,
            flash_kb=8192,ram_kb=512,freq_mhz=240,uart=True,i2c=True,spi=True,
            wifi=True,bluetooth=True,gpio=True,adc=True,usb_native=True),
    ),
    "ESP32-C3": BoardDef(
        name="ESP32-C3", family="ESP", tier=TIER_BASIC,
        chip="RISC-V 32-bit Single-Core", vid=0x1A86, pid=0x55D4,
        driver="neuros.drivers.esp32_serial",
        description="RISC-V core. Ultra-low power. WiFi+BLE. Smaller/cheaper.",
        caps=BoardCapabilities(digital_pins=22,analog_pins=6,pwm_pins=6,
            flash_kb=4096,ram_kb=400,freq_mhz=160,uart=True,i2c=True,spi=True,
            wifi=True,bluetooth=True,gpio=True,adc=True),
    ),
    "ESP32-CAM": BoardDef(
        name="ESP32-CAM", family="ESP", tier=TIER_INTER,
        chip="ESP32 + OV2640 Camera", vid=0x10C4, pid=0xEA60,
        driver="neuros.drivers.esp32_cam",
        description="ESP32 with onboard OV2640 camera. Vision + WiFi robot brain.",
        caps=BoardCapabilities(digital_pins=10,flash_kb=4096,ram_kb=520,
            freq_mhz=240,uart=True,i2c=True,spi=True,wifi=True,gpio=True),
    ),
    "ESP8266 NodeMCU": BoardDef(
        name="ESP8266 NodeMCU", family="ESP", tier=TIER_BASIC,
        chip="Tensilica L106 80MHz",
        driver="neuros.drivers.esp8266_serial",
        description="Original WiFi microcontroller. 80KB RAM, Lua/C/Python support.",
        caps=BoardCapabilities(digital_pins=11,analog_pins=1,flash_kb=4096,
            ram_kb=80,freq_mhz=80,uart=True,i2c=True,spi=True,wifi=True,gpio=True,adc=True),
    ),

    # ── RASPBERRY PI FAMILY ──────────────────────────
    "Raspberry Pi Pico": BoardDef(
        name="Raspberry Pi Pico", family="Raspberry Pi", tier=TIER_BASIC,
        chip="RP2040 (ARM Cortex-M0+ Dual)", vid=0x2E8A, pid=0x0005,
        driver="neuros.drivers.rpi_pico",
        description="Microcontroller Pi. Dual M0+, PIO, 264KB RAM. MicroPython friendly.",
        caps=BoardCapabilities(digital_pins=26,analog_pins=3,pwm_pins=16,
            flash_kb=2048,ram_kb=264,freq_mhz=133,uart=True,i2c=True,spi=True,gpio=True,adc=True),
    ),
    "Raspberry Pi Pico W": BoardDef(
        name="Raspberry Pi Pico W", family="Raspberry Pi", tier=TIER_BASIC,
        chip="RP2040 + CYW43439", vid=0x2E8A, pid=0x000A,
        driver="neuros.drivers.rpi_pico",
        description="Pico with WiFi + BLE via CYW43439. Same pinout.",
        caps=BoardCapabilities(digital_pins=26,analog_pins=3,pwm_pins=16,
            flash_kb=2048,ram_kb=264,freq_mhz=133,uart=True,i2c=True,spi=True,
            wifi=True,bluetooth=True,gpio=True,adc=True),
    ),
    "Raspberry Pi 4B": BoardDef(
        name="Raspberry Pi 4B", family="Raspberry Pi", tier=TIER_INTER,
        chip="BCM2711 (ARM Cortex-A72 Quad)",
        driver="neuros.drivers.rpi_hal",
        description="Full Linux SBC. 4GB RAM, USB3, Gigabit Ethernet, 40-pin GPIO.",
        caps=BoardCapabilities(digital_pins=40,freq_mhz=1800,
            uart=True,i2c=True,spi=True,wifi=True,bluetooth=True,gpio=True,ram_mb=4096),
    ),
    "Raspberry Pi 5": BoardDef(
        name="Raspberry Pi 5", family="Raspberry Pi", tier=TIER_INTER,
        chip="BCM2712 (ARM Cortex-A76 Quad)",
        driver="neuros.drivers.rpi_hal",
        description="2.4GHz quad-core A76. PCIe 2.0, RTC, 2x MIPI camera.",
        caps=BoardCapabilities(digital_pins=40,freq_mhz=2400,
            uart=True,i2c=True,spi=True,wifi=True,bluetooth=True,gpio=True,ram_mb=8192),
    ),
    "Raspberry Pi Zero W": BoardDef(
        name="Raspberry Pi Zero W", family="Raspberry Pi", tier=TIER_INTER,
        chip="BCM2835 (ARM Cortex-A7)",
        driver="neuros.drivers.rpi_hal",
        description="Tiny $15 Linux SBC with WiFi. 512MB RAM, 40-pin GPIO.",
        caps=BoardCapabilities(digital_pins=40,freq_mhz=1000,
            uart=True,i2c=True,spi=True,wifi=True,bluetooth=True,gpio=True,ram_mb=512),
    ),

    # ── JETSON / AI FAMILY ───────────────────────────
    "Jetson Nano": BoardDef(
        name="Jetson Nano", family="Jetson", tier=TIER_ADVANCED,
        chip="Maxwell GPU (128 CUDA) + ARM A57",
        driver="neuros.drivers.jetson_hal",
        description="128 CUDA cores. 4GB RAM. NVIDIA's entry AI compute module.",
        caps=BoardCapabilities(digital_pins=40,freq_mhz=1430,
            uart=True,i2c=True,spi=True,wifi=False,gpio=True,ram_mb=4096,gpu_cores=128),
    ),
    "Jetson Xavier NX": BoardDef(
        name="Jetson Xavier NX", family="Jetson", tier=TIER_ADVANCED,
        chip="Volta GPU (384 CUDA) + ARM Carmel",
        driver="neuros.drivers.jetson_hal",
        description="21 TOPS AI. 8GB RAM. ROS2 + deep learning workloads.",
        caps=BoardCapabilities(digital_pins=40,freq_mhz=1900,
            uart=True,i2c=True,spi=True,gpio=True,ram_mb=8192,gpu_cores=384),
    ),
    "Jetson AGX Orin": BoardDef(
        name="Jetson AGX Orin", family="Jetson", tier=TIER_EXPERT,
        chip="Ampere GPU (2048 CUDA) + ARM Cortex-A78",
        driver="neuros.drivers.jetson_hal",
        description="275 TOPS AI. 64GB RAM. Autonomous vehicles, humanoid robots.",
        caps=BoardCapabilities(digital_pins=40,freq_mhz=2200,
            uart=True,i2c=True,spi=True,can=True,gpio=True,ram_mb=65536,gpu_cores=2048),
    ),

    # ── STM32 FAMILY ─────────────────────────────────
    "STM32 Nucleo-F401RE": BoardDef(
        name="STM32 Nucleo-F401RE", family="STM32", tier=TIER_ADVANCED,
        chip="STM32F401RE (ARM Cortex-M4)", vid=0x0483, pid=0x374B,
        driver="neuros.drivers.stm32_serial",
        description="84MHz M4 with FPU. ST-Link onboard. 512KB flash, 96KB RAM.",
        caps=BoardCapabilities(digital_pins=76,analog_pins=16,pwm_pins=20,
            flash_kb=512,ram_kb=96,freq_mhz=84,uart=True,i2c=True,spi=True,
            can=True,gpio=True,adc=True,dac=True),
    ),
    "STM32 Nucleo-H743ZI": BoardDef(
        name="STM32 Nucleo-H743ZI", family="STM32", tier=TIER_EXPERT,
        chip="STM32H743ZI (ARM Cortex-M7)", vid=0x0483, pid=0x374B,
        driver="neuros.drivers.stm32_serial",
        description="480MHz M7, 1MB RAM, Ethernet, CAN. Real-time control beast.",
        caps=BoardCapabilities(digital_pins=114,analog_pins=16,pwm_pins=30,
            flash_kb=2048,ram_kb=1024,freq_mhz=480,uart=True,i2c=True,spi=True,
            can=True,gpio=True,adc=True,dac=True),
    ),
    "STM32 Blue Pill": BoardDef(
        name="STM32 Blue Pill", family="STM32", tier=TIER_INTER,
        chip="STM32F103C8T6 (ARM Cortex-M3)",
        driver="neuros.drivers.stm32_serial",
        description="$2 ARM board. 72MHz M3, 64KB flash. Popular PX4 flight controller.",
        caps=BoardCapabilities(digital_pins=37,analog_pins=10,pwm_pins=10,
            flash_kb=64,ram_kb=20,freq_mhz=72,uart=True,i2c=True,spi=True,
            can=True,gpio=True,adc=True),
    ),

    # ── TEENSY FAMILY ────────────────────────────────
    "Teensy 4.1": BoardDef(
        name="Teensy 4.1", family="Teensy", tier=TIER_ADVANCED,
        chip="IMXRT1062 (ARM Cortex-M7)", vid=0x16C0, pid=0x0487,
        driver="neuros.drivers.teensy_serial",
        description="600MHz M7. 8MB flash, 1MB RAM. Ethernet, SD. Top of class.",
        caps=BoardCapabilities(digital_pins=42,analog_pins=18,pwm_pins=35,
            flash_kb=8192,ram_kb=1024,freq_mhz=600,uart=True,i2c=True,spi=True,
            can=True,gpio=True,adc=True,dac=True,usb_native=True),
    ),
    "Teensy 4.0": BoardDef(
        name="Teensy 4.0", family="Teensy", tier=TIER_ADVANCED,
        chip="IMXRT1062 (ARM Cortex-M7)", vid=0x16C0, pid=0x0487,
        driver="neuros.drivers.teensy_serial",
        description="600MHz M7 in compact form. Identical CPU to Teensy 4.1.",
        caps=BoardCapabilities(digital_pins=24,analog_pins=14,pwm_pins=24,
            flash_kb=2048,ram_kb=1024,freq_mhz=600,uart=True,i2c=True,spi=True,
            can=True,gpio=True,adc=True,dac=True,usb_native=True),
    ),

    # ── ADAFRUIT FAMILY ──────────────────────────────
    "Adafruit Feather M0": BoardDef(
        name="Adafruit Feather M0", family="Adafruit", tier=TIER_BASIC,
        chip="ATSAMD21G18 (ARM Cortex-M0+)", vid=0x239A, pid=0x800B,
        driver="neuros.drivers.arduino_serial",
        description="Feather ecosystem. LiPo charging, 256KB flash, native USB.",
        caps=BoardCapabilities(digital_pins=20,analog_pins=6,pwm_pins=14,
            flash_kb=256,ram_kb=32,freq_mhz=48,uart=True,i2c=True,spi=True,
            gpio=True,adc=True,dac=True,usb_native=True),
    ),
    "Adafruit Metro M4": BoardDef(
        name="Adafruit Metro M4", family="Adafruit", tier=TIER_INTER,
        chip="ATSAMD51J19 (ARM Cortex-M4)", vid=0x239A, pid=0x8022,
        driver="neuros.drivers.arduino_serial",
        description="120MHz M4 in Uno form factor. 512KB flash, 192KB RAM.",
        caps=BoardCapabilities(digital_pins=25,analog_pins=6,pwm_pins=18,
            flash_kb=512,ram_kb=192,freq_mhz=120,uart=True,i2c=True,spi=True,
            gpio=True,adc=True,dac=True,usb_native=True),
    ),

    # ── SEEED STUDIO ─────────────────────────────────
    "Seeed XIAO SAMD21": BoardDef(
        name="Seeed XIAO SAMD21", family="Seeed Studio", tier=TIER_BASIC,
        chip="ATSAMD21G18 (ARM Cortex-M0+)", vid=0x2886, pid=0x802F,
        driver="neuros.drivers.arduino_serial",
        description="Thumb-sized Arduino-compat. 11 pins, USB-C. Tiny robot brains.",
        caps=BoardCapabilities(digital_pins=11,analog_pins=11,pwm_pins=10,
            flash_kb=256,ram_kb=32,freq_mhz=48,uart=True,i2c=True,spi=True,
            gpio=True,adc=True,dac=True,usb_native=True),
    ),
    "Seeed XIAO ESP32-S3": BoardDef(
        name="Seeed XIAO ESP32-S3", family="Seeed Studio", tier=TIER_INTER,
        chip="ESP32-S3 Dual-Core LX7", vid=0x2886, pid=0x8056,
        driver="neuros.drivers.esp32_serial",
        description="Thumb-sized ESP32-S3. WiFi+BLE+camera connector. 8MB flash.",
        caps=BoardCapabilities(digital_pins=11,analog_pins=9,
            flash_kb=8192,ram_kb=512,freq_mhz=240,uart=True,i2c=True,spi=True,
            wifi=True,bluetooth=True,gpio=True,adc=True,usb_native=True),
    ),

    # ── BEAGLEBONE ───────────────────────────────────
    "BeagleBone Black": BoardDef(
        name="BeagleBone Black", family="BeagleBone", tier=TIER_INTER,
        chip="AM3358 (ARM Cortex-A8)",
        driver="neuros.drivers.rpi_hal",
        description="Linux SBC with 2x PRU real-time cores. 92 GPIO pins.",
        caps=BoardCapabilities(digital_pins=92,analog_pins=7,pwm_pins=8,
            freq_mhz=1000,uart=True,i2c=True,spi=True,can=True,gpio=True,adc=True,ram_mb=512),
    ),
}

def lookup_by_vid_pid(vid: int, pid: int) -> Optional[str]:
    """Return board name from VID:PID, checking exact then vendor-only matches."""
    exact = VID_PID_MAP.get((vid, pid))
    if exact:
        return exact
    vendor = VID_PID_MAP.get((vid, None))
    return vendor

def get_board(name: str) -> Optional[BoardDef]:
    return BOARD_REGISTRY.get(name)

def all_boards() -> list[BoardDef]:
    return list(BOARD_REGISTRY.values())

def boards_by_family(family: str) -> list[BoardDef]:
    return [b for b in BOARD_REGISTRY.values() if b.family.lower() == family.lower()]

def boards_by_tier(tier: str) -> list[BoardDef]:
    return [b for b in BOARD_REGISTRY.values() if b.tier == tier]
