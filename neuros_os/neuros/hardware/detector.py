"""
NEUROS OS — Hardware Auto-Detection Engine
Parallel scanning: USB Serial · I²C · SPI · WiFi/mDNS · Host self-identification
"""

import os
import sys
import time
import json
import socket
import platform
import subprocess
import threading
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

from neuros.hardware.boards import (
    lookup_by_vid_pid, get_board, BOARD_REGISTRY,
    TIER_BASIC, TIER_INTER, TIER_ADVANCED
)

# ── Detection method labels ──────────────────────────────────────
METHOD_VID_PID    = "VID:PID match"
METHOD_HANDSHAKE  = "NEUROS handshake"
METHOD_AT_PROBE   = "AT command probe"
METHOD_HOST_SELF  = "Host self-identification"
METHOD_I2C_PROBE  = "I²C WHO_AM_I probe"
METHOD_MDNS       = "mDNS discovery"
METHOD_MANUAL     = "Manual (user-added)"

# ── Known I2C device addresses ───────────────────────────────────
I2C_ADDRESS_MAP = {
    0x3C: "SSD1306 OLED Display (128x64)",
    0x3D: "SSD1306 OLED Display (128x32)",
    0x48: "ADS1115 ADC / TMP102 Temp Sensor",
    0x68: "MPU-6050 IMU / DS3231 RTC",
    0x69: "MPU-6050 IMU (alt address)",
    0x76: "BME280 Temp/Humidity/Pressure",
    0x77: "BME280 / BMP180 Pressure Sensor",
    0x1E: "HMC5883L / QMC5883 Compass",
    0x29: "VL53L0X ToF Distance Sensor",
    0x40: "INA219 Current Sensor / PCA9685 PWM",
    0x70: "PCA9685 PWM Driver (default)",
    0x20: "PCF8574 GPIO Expander",
    0x27: "PCF8574A / LCD I2C Backpack",
    0x53: "ADXL345 Accelerometer",
    0x1D: "ADXL345 Accelerometer (alt)",
    0x5A: "MPR121 Capacitive Touch",
    0x60: "SI5351 Clock Generator",
    0x08: "AS5600 Magnetic Encoder",
}

@dataclass
class DetectedDevice:
    id:           str
    name:         str
    port:         str
    tier:         str
    status:       str          # online / partial / offline
    method:       str
    driver:       str
    fw_version:   str = "unknown"
    chip:         str = "unknown"
    vid:          Optional[int] = None
    pid:          Optional[int] = None
    flash:        str = "?"
    ram:          str = "?"
    freq:         str = "?"
    capabilities: dict = field(default_factory=dict)
    silicon_class: str = "unknown"  # microcontroller / microprocessor / peripheral / unknown
    source:       str = "auto"  # auto / manual
    added_at:     float = field(default_factory=time.time)
    notes:        str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "DetectedDevice":
        return cls(**d)


class HardwareDetector:
    """
    Parallel hardware detector for NEUROS OS.
    Scans USB serial, host GPIO, I²C bus, and network simultaneously.
    """

    NEUROS_PROBE  = b'\xEE\x01\x00\x00'   # NEUROS proprietary probe packet
    NEUROS_ACK    = b'\xEE\x02'           # Expected ACK prefix
    PROBE_TIMEOUT = 0.6                   # seconds per probe attempt
    AT_TIMEOUT    = 0.8

    def __init__(self):
        self._results: list[DetectedDevice] = []
        self._lock    = threading.Lock()
        self._errors: list[str] = []

    # ── PUBLIC API ─────────────────────────────────────────────────

    def scan(self) -> tuple[list[DetectedDevice], float, list[str]]:
        """Run full parallel detection. Returns tuple of (devices, elapsed_time, errors)."""
        self._results = []
        self._errors  = []
        start = time.time()

        threads = [
            threading.Thread(target=self._scan_usb_serial,   name="usb"),
            threading.Thread(target=self._detect_host,       name="host"),
            threading.Thread(target=self._scan_i2c_bus,      name="i2c"),
            threading.Thread(target=self._scan_network,      name="net"),
        ]

        for t in threads:
            t.daemon = True
            t.start()
        for t in threads:
            t.join(timeout=5.0)   # hard cap: 5 seconds total

        elapsed = time.time() - start
        return self._results, elapsed, self._errors

    # ── STAGE 1: HOST SELF-IDENTIFICATION ─────────────────────────

    def _detect_host(self):
        """Detect the machine NEUROS is running on."""
        try:
            dev = self._identify_host()
            if dev:
                with self._lock:
                    self._results.append(dev)
        except Exception as e:
            self._errors.append(f"Host detection: {e}")

    def _identify_host(self) -> Optional[DetectedDevice]:
        model_path = Path("/proc/device-tree/model")
        if model_path.exists():
            try:
                model = model_path.read_bytes().rstrip(b'\x00').decode()
            except Exception:
                model = "Unknown SBC"

            if "Raspberry Pi 5" in model:
                return self._make_host_device("Raspberry Pi 5", model, TIER_INTER,
                    "neuros.drivers.rpi_hal", "BCM2712 ARM Cortex-A76", "SD card", "8GB", "2.4GHz")
            elif "Raspberry Pi 4" in model:
                return self._make_host_device("Raspberry Pi 4B", model, TIER_INTER,
                    "neuros.drivers.rpi_hal", "BCM2711 ARM Cortex-A72", "SD card", _rpi_ram(), "1.8GHz")
            elif "Raspberry Pi 3" in model:
                return self._make_host_device("Raspberry Pi 3B+", model, TIER_INTER,
                    "neuros.drivers.rpi_hal", "BCM2837 ARM Cortex-A53", "SD card", "1GB", "1.4GHz")
            elif "Raspberry Pi Zero" in model:
                return self._make_host_device("Raspberry Pi Zero W", model, TIER_INTER,
                    "neuros.drivers.rpi_hal", "BCM2835 ARM Cortex-A7", "SD card", "512MB", "1.0GHz")
            elif "Jetson" in model:
                name = "Jetson Nano" if "Nano" in model else "Jetson Xavier NX" if "Xavier" in model else "Jetson AGX Orin"
                return self._make_host_device(name, model, TIER_ADVANCED,
                    "neuros.drivers.jetson_hal", model, "16GB eMMC", "4-64GB", "1.4-2.2GHz")
            elif "BeagleBone" in model:
                return self._make_host_device("BeagleBone Black", model, TIER_INTER,
                    "neuros.drivers.rpi_hal", "AM3358 ARM Cortex-A8", "4GB eMMC", "512MB", "1.0GHz")
            else:
                return self._make_host_device("Embedded Linux SBC", model, TIER_INTER,
                    "neuros.drivers.generic_linux", model, "?", _rpi_ram(), "?")

        # Check for Jetson via tegra-chip-id
        if Path("/sys/module/tegra_fuse/parameters/tegra_chip_id").exists():
            return self._make_host_device("NVIDIA Jetson", "Jetson (tegra)", TIER_ADVANCED,
                "neuros.drivers.jetson_hal", "Tegra SoC", "eMMC", "GB", "GHz")

        # Generic Linux PC
        if platform.system() == "Linux":
            cpu = _cpu_model()
            ram = _total_ram_str()
            return self._make_host_device(
                f"Linux PC ({platform.node()})",
                f"Linux {platform.release()} · {cpu}",
                TIER_ADVANCED, "neuros.drivers.pc_linux",
                cpu, "HDD/SSD", ram, f"{_cpu_freq()}"
            )

        # macOS
        if platform.system() == "Darwin":
            return self._make_host_device(
                "macOS Host", f"macOS {platform.mac_ver()[0]}",
                TIER_ADVANCED, "neuros.drivers.pc_macos",
                platform.processor(), "SSD", _total_ram_str(), "GHz"
            )

        # Windows PC
        if platform.system() == "Windows":
            cpu = _cpu_model()
            return self._make_host_device(
                f"Windows Host ({platform.node()})",
                f"Windows {platform.release()} · {cpu}",
                TIER_ADVANCED, "neuros.drivers.pc_windows",
                cpu, "HDD/SSD", _total_ram_str(), _cpu_freq()
            )

        return None

    def _make_host_device(self, name, description, tier, driver, chip, flash, ram, freq) -> DetectedDevice:
        return DetectedDevice(
            id=f"host_{name.lower().replace(' ','_')}",
            name=name, port="HOST (self-identified)",
            tier=tier, status="online",
            method=METHOD_HOST_SELF, driver=driver,
            fw_version=f"Linux {platform.release()}" if platform.system()=="Linux" else platform.system(),
            chip=chip, flash=flash, ram=ram, freq=freq,
            capabilities=_host_caps(name),
            silicon_class="microprocessor",
            source="auto",
        )

    # ── STAGE 2: USB SERIAL SCANNING ──────────────────────────────

    def _scan_usb_serial(self):
        """Scan all USB serial ports, fingerprint each device."""
        if not SERIAL_AVAILABLE:
            self._errors.append("pyserial not installed — USB scan skipped")
            return
        try:
            ports = list(serial.tools.list_ports.comports())
        except Exception as e:
            self._errors.append(f"Port list error: {e}")
            return

        probe_threads = []
        for port in ports:
            t = threading.Thread(
                target=self._probe_serial_port,
                args=(port,), daemon=True
            )
            probe_threads.append(t)
            t.start()
        for t in probe_threads:
            t.join(timeout=3.0)

    def _probe_serial_port(self, port_info):
        """Probe a single serial port: VID:PID → NEUROS handshake → AT probe."""
        port    = port_info.device
        vid     = port_info.vid
        pid     = port_info.pid
        desc    = port_info.description or ""
        hwid    = port_info.hwid or ""

        board_name = None
        method     = METHOD_VID_PID
        status     = "partial"
        fw_ver     = "unknown"

        # ① VID:PID lookup (instant, no I/O)
        if vid and pid:
            board_name = lookup_by_vid_pid(vid, pid)

        if not board_name:
            board_name = _guess_from_description(desc, hwid)

        # ② NEUROS handshake probe
        neuros_ok = self._neuros_handshake(port)
        if neuros_ok:
            method = f"{METHOD_VID_PID} + {METHOD_HANDSHAKE}"
            status = "online"
            fw_ver = neuros_ok.get("fw", "NEUROS fw detected")
        else:
            # ③ AT command probe for ESP boards
            if board_name and "ESP" in board_name:
                at_ok = self._at_probe(port)
                if at_ok:
                    method = f"{METHOD_VID_PID} + {METHOD_AT_PROBE}"
                    status = "partial"
                    fw_ver = at_ok

        board_def = get_board(board_name) if board_name else None
        dev = DetectedDevice(
            id=f"usb_{port.replace('/','_').replace('\\','_')}",
            name=board_name or f"Unknown board ({desc})",
            port=port,
            tier=board_def.tier if board_def else TIER_BASIC,
            status=status,
            method=method,
            driver=board_def.driver if board_def else "neuros.drivers.generic_serial",
            fw_version=fw_ver,
            chip=board_def.chip if board_def else "unknown",
            vid=vid, pid=pid,
            flash=f"{board_def.caps.flash_kb}KB" if board_def else "?",
            ram=f"{board_def.caps.ram_kb}KB" if board_def else "?",
            freq=f"{board_def.caps.freq_mhz}MHz" if board_def else "?",
            capabilities=_caps_dict(board_def),
            silicon_class=_silicon_class(board_def, board_name),
            source="auto",
        )
        with self._lock:
            self._results.append(dev)

    def _neuros_handshake(self, port: str) -> Optional[dict]:
        """Send NEUROS probe packet, expect NEUROS ACK. Returns info dict or None."""
        if not SERIAL_AVAILABLE:
            return None
        try:
            with serial.Serial(port, 115200, timeout=self.PROBE_TIMEOUT) as ser:
                ser.reset_input_buffer()
                ser.write(self.NEUROS_PROBE)
                resp = ser.read(32)
                if resp and resp[:2] == self.NEUROS_ACK:
                    # Parse simple TLV response
                    return {"fw": resp[2:18].decode(errors="ignore").strip('\x00')}
        except Exception:
            pass
        return None

    def _at_probe(self, port: str) -> Optional[str]:
        """Send ESP AT commands, return firmware string or None."""
        if not SERIAL_AVAILABLE:
            return None
        for baud in (115200, 9600):
            try:
                with serial.Serial(port, baud, timeout=self.AT_TIMEOUT) as ser:
                    ser.reset_input_buffer()
                    ser.write(b'AT+GMR\r\n')
                    time.sleep(0.3)
                    resp = ser.read(200).decode(errors="ignore")
                    if "AT version" in resp or "IDF" in resp or "OK" in resp:
                        lines = [l.strip() for l in resp.splitlines() if l.strip()]
                        return lines[0] if lines else "ESP-AT detected"
            except Exception:
                pass
        return None

    # ── STAGE 3: I²C BUS SCAN ─────────────────────────────────────

    def _scan_i2c_bus(self):
        """Scan all I²C buses (Linux only via /dev/i2c-*)."""
        if platform.system() != "Linux":
            return
        i2c_buses = list(Path("/dev").glob("i2c-*"))
        for bus_path in i2c_buses:
            self._probe_i2c_bus(bus_path)

    def _probe_i2c_bus(self, bus_path: Path):
        """Probe all 128 I²C addresses on a bus via i2cdetect."""
        try:
            result = subprocess.run(
                ["i2cdetect", "-y", "-r", bus_path.name.split("-")[1]],
                capture_output=True, text=True, timeout=3
            )
            output = result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # i2cdetect not available — try direct /dev access
            output = self._i2c_raw_scan(bus_path)
            if not output:
                return

        # Parse i2cdetect output for device addresses
        for line in output.splitlines():
            parts = line.split()
            if not parts or not parts[0].endswith(":"):
                continue
            row_offset = int(parts[0].rstrip(":"), 16)
            for col_idx, cell in enumerate(parts[1:]):
                if cell not in ("--", "UU", "") and len(cell) == 2:
                    try:
                        addr = row_offset + col_idx
                        device_name = I2C_ADDRESS_MAP.get(addr, f"Unknown I²C device")
                        dev = DetectedDevice(
                            id=f"i2c_{bus_path.name}_0x{addr:02X}",
                            name=device_name,
                            port=f"{bus_path} @ 0x{addr:02X}",
                            tier=TIER_BASIC,
                            status="online",
                            method=METHOD_I2C_PROBE,
                            driver="neuros.drivers.i2c_generic",
                            chip=f"I²C addr 0x{addr:02X}",
                            capabilities={"I2C": True},
                            silicon_class="peripheral",
                            source="auto",
                        )
                        with self._lock:
                            self._results.append(dev)
                    except Exception:
                        pass

    def _i2c_raw_scan(self, bus_path: Path) -> Optional[str]:
        """Fallback: scan I2C via raw file I/O (requires r/w on /dev/i2c-*)."""
        try:
            import fcntl, struct  # type: ignore
            I2C_SLAVE = 0x0703
            found_hex = []
            with open(bus_path, "rb", buffering=0) as f:
                for addr in range(3, 120):
                    try:
                        getattr(fcntl, 'ioctl')(f, I2C_SLAVE, addr)
                        f.read(0)
                        found_hex.append(f"{addr:02X}")
                    except OSError:
                        pass
            # Format like i2cdetect output for parsing
            if found_hex:
                return "     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f\n" + \
                       "\n".join(f"{16*i:02x}: " + " ".join(found_hex) for i in range(8))
        except Exception:
            pass
        return None

    # ── STAGE 4: NETWORK SCAN ─────────────────────────────────────

    def _scan_network(self):
        """Scan local network for NEUROS devices broadcasting on mDNS / HTTP."""
        try:
            self._scan_mdns()
            self._scan_neuros_http()
        except Exception as e:
            self._errors.append(f"Network scan: {e}")

    def _scan_mdns(self):
        """Look for mDNS broadcasts from NEUROS-flashed WiFi boards."""
        try:
            # Try to resolve neuros-*.local via mDNS broadcast
            # Real impl would use zeroconf library; this is a stub
            pass
        except Exception:
            pass

    def _scan_neuros_http(self):
        """Probe local subnet for NEUROS HTTP bridge (port 8765)."""
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
            if local_ip.startswith("127."):
                return
            subnet = ".".join(local_ip.split(".")[:3])
            # Scan first 20 IPs quickly (won't block long)
            threads = []
            for last_octet in range(2, 22):
                ip = f"{subnet}.{last_octet}"
                if ip == local_ip:
                    continue
                t = threading.Thread(
                    target=self._probe_neuros_http,
                    args=(ip,), daemon=True
                )
                threads.append(t)
                t.start()
            for t in threads:
                t.join(timeout=1.0)
        except Exception:
            pass

    def _probe_neuros_http(self, ip: str):
        """Try to reach NEUROS HTTP bridge on a given IP."""
        try:
            s = socket.create_connection((ip, 8765), timeout=0.3)
            s.close()
            dev = DetectedDevice(
                id=f"net_{ip.replace('.','_')}",
                name=f"NEUROS WiFi Device ({ip})",
                port=f"WiFi · {ip}:8765",
                tier=TIER_BASIC,
                status="online",
                method=METHOD_MDNS,
                driver="neuros.drivers.wifi_bridge",
                chip="ESP32 (WiFi)",
                capabilities={"WiFi": True, "GPIO": True},
                silicon_class="microcontroller",
                source="auto",
            )
            with self._lock:
                self._results.append(dev)
        except Exception:
            pass


# ── Helper functions ─────────────────────────────────────────────

def _guess_from_description(desc: str, hwid: str) -> Optional[str]:
    """Guess board name from port description string."""
    desc_lower = (desc + hwid).lower()
    if "arduino uno"  in desc_lower: return "Arduino Uno R3"
    if "arduino mega" in desc_lower: return "Arduino Mega 2560"
    if "arduino nano" in desc_lower: return "Arduino Nano"
    if "arduino leon" in desc_lower: return "Arduino Leonardo"
    if "esp32"        in desc_lower: return "ESP32"
    if "esp8266"      in desc_lower: return "ESP8266 NodeMCU"
    if "cp210"        in desc_lower: return "ESP32"       # CP2102 = almost always ESP
    if "ch340"        in desc_lower: return "Arduino Nano (clone/CH340)"
    if "ftdi"         in desc_lower: return "FTDI-based board (FT232R)"
    if "teensy"       in desc_lower: return "Teensy 4.1"
    if "stm32"        in desc_lower: return "STM32 Nucleo-F401RE"
    return None

def _caps_dict(board_def) -> dict:
    if not board_def:
        return {}
    c = board_def.caps
    return {
        "GPIO":      c.gpio,
        "UART":      c.uart,
        "I2C":       c.i2c,
        "SPI":       c.spi,
        "PWM":       c.pwm_pins > 0,
        "ADC":       c.adc,
        "WiFi":      c.wifi,
        "Bluetooth": c.bluetooth,
        "CAN":       c.can,
        "DAC":       c.dac,
        "GPU":       c.gpu_cores > 0,
    }

def _silicon_class(board_def, board_name: Optional[str]) -> str:
    if not board_def:
        return "unknown"
    family = board_def.family.lower()
    name = (board_name or board_def.name).lower()
    chip = board_def.chip.lower()
    if any(token in family or token in name for token in ("raspberry pi", "jetson", "beaglebone")):
        if "pico" not in name:
            return "microprocessor"
    if board_def.caps.ram_mb > 0 or board_def.caps.gpu_cores > 0:
        return "microprocessor"
    if any(token in chip for token in ("cortex-a", "am335", "bcm", "tegra", "cuda")):
        return "microprocessor"
    return "microcontroller"

def _host_caps(name: str) -> dict:
    base = {"GPIO": False, "UART": True, "I2C": False, "SPI": False,
            "WiFi": False, "Bluetooth": False, "GPU": False}
    if "Pi" in name or "Jetson" in name or "BeagleBone" in name:
        base.update({"GPIO": True, "I2C": True, "SPI": True})
    if any(x in name for x in ("Pi 4","Pi 5","Pi 3","Zero W","Jetson","BeagleBone")):
        base.update({"WiFi": True, "Bluetooth": True})
    if "Jetson" in name or "GPU" in name:
        base["GPU"] = True
    return base

def _rpi_ram() -> str:
    try:
        mem = Path("/proc/meminfo").read_text()
        for line in mem.splitlines():
            if line.startswith("MemTotal:"):
                kb = int(line.split()[1])
                gb = round(kb / 1024 / 1024, 1)
                return f"{gb}GB"
    except Exception:
        pass
    return "?"

def _cpu_model() -> str:
    if platform.system() == "Windows":
        return platform.processor() or platform.machine() or "Unknown CPU"
    try:
        info = Path("/proc/cpuinfo").read_text()
        for line in info.splitlines():
            if "model name" in line.lower():
                return line.split(":")[1].strip()
    except Exception:
        pass
    return platform.processor() or "Unknown CPU"

def _total_ram_str() -> str:
    if platform.system() == "Windows":
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            mem = MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            gb = round(mem.ullTotalPhys / 1024 / 1024 / 1024, 1)
            return f"{gb}GB"
        except Exception:
            return "?"
    try:
        mem = Path("/proc/meminfo").read_text()
        for line in mem.splitlines():
            if line.startswith("MemTotal:"):
                kb = int(line.split()[1])
                gb = round(kb / 1024 / 1024, 1)
                return f"{gb}GB"
    except Exception:
        pass
    return "?"

def _cpu_freq() -> str:
    if platform.system() == "Windows":
        return "GHz"
    try:
        freq = Path("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq").read_text().strip()
        mhz = int(freq) // 1000
        return f"{mhz}MHz"
    except Exception:
        pass
    return "?"
