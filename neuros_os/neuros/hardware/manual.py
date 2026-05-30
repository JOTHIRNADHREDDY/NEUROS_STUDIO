"""
NEUROS OS — Manual Hardware Addition
Add any board that wasn't auto-detected. Validates input, persists to registry.
"""

import json
import time
import uuid
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

from neuros.hardware.detector import DetectedDevice, METHOD_MANUAL
from neuros.hardware.boards import (
    BOARD_REGISTRY, get_board,
    TIER_BASIC, TIER_INTER, TIER_ADVANCED, TIER_EXPERT, TIER_CRITICAL,
)

# ── Connection types NEUROS supports ────────────────────────────
CONNECTION_TYPES = {
    "usb":      {"label": "USB Serial",   "icon": "🔌", "port_hint": "/dev/ttyUSB0  or  COM3"},
    "wifi":     {"label": "WiFi",         "icon": "📶", "port_hint": "192.168.1.x"},
    "i2c":      {"label": "I²C",          "icon": "🔗", "port_hint": "0x3C  (hex address)"},
    "spi":      {"label": "SPI",          "icon": "⚡", "port_hint": "/dev/spidev0.0"},
    "can":      {"label": "CAN Bus",      "icon": "🏭", "port_hint": "can0"},
    "modbus":   {"label": "Modbus RTU",   "icon": "⚙️", "port_hint": "/dev/ttyUSB0 @ 9600"},
    "bluetooth":{"label": "Bluetooth",    "icon": "🔷", "port_hint": "AA:BB:CC:DD:EE:FF"},
    "ethernet": {"label": "Ethernet",     "icon": "🌐", "port_hint": "192.168.1.x"},
    "gpio":     {"label": "GPIO (direct)","icon": "📌", "port_hint": "Pin 18 (BCM)"},
    "uart":     {"label": "UART (TTL)",   "icon": "〰️", "port_hint": "/dev/ttyAMA0"},
}

TIER_OPTIONS = {
    "1": TIER_BASIC,
    "2": TIER_INTER,
    "3": TIER_ADVANCED,
    "4": TIER_EXPERT,
    "5": TIER_CRITICAL,
}

BAUD_RATES = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]

CAPABILITY_LIST = [
    "GPIO", "UART", "I2C", "SPI", "PWM", "ADC", "DAC",
    "WiFi", "Bluetooth", "CAN", "Ethernet", "Camera", "GPU",
]

# ── Storage path ─────────────────────────────────────────────────
REGISTRY_PATH = Path.home() / ".neuros" / "hardware_registry.json"


@dataclass
class ManualHardwareSpec:
    """Everything a user provides when manually adding hardware."""
    name:         str
    board_type:   str
    connection:   str
    port:         str
    tier:         str         = TIER_BASIC
    baud_rate:    int         = 115200
    firmware:     str         = ""
    capabilities: list        = field(default_factory=list)
    notes:        str         = ""
    ip_address:   str         = ""

    def validate(self) -> list[str]:
        """Return list of validation errors (empty = valid)."""
        errors = []
        if not self.name.strip():
            errors.append("Device name cannot be empty.")
        if len(self.name) > 64:
            errors.append("Device name must be under 64 characters.")
        if not self.board_type:
            errors.append("Board type must be selected.")
        if self.connection not in CONNECTION_TYPES:
            errors.append(f"Unknown connection type '{self.connection}'. "
                          f"Choose from: {', '.join(CONNECTION_TYPES)}")
        if self.connection == "usb" and self.port:
            # basic port sanity on Linux
            p = Path(self.port)
            if not str(self.port).startswith("COM") and not str(self.port).startswith("/dev/"):
                errors.append(f"Port '{self.port}' looks wrong for USB. "
                              f"Expected /dev/ttyUSBx or COMx.")
        if self.baud_rate not in BAUD_RATES:
            errors.append(f"Baud rate must be one of: {BAUD_RATES}")
        return errors

    def to_detected_device(self) -> DetectedDevice:
        """Convert to DetectedDevice so it integrates with the rest of NEUROS."""
        board_def = get_board(self.board_type)
        caps = {c: (c in self.capabilities) for c in CAPABILITY_LIST}

        # Override caps from board registry if known board
        if board_def:
            bc = board_def.caps
            caps.update({
                "GPIO":      bc.gpio,
                "UART":      bc.uart,
                "I2C":       bc.i2c,
                "SPI":       bc.spi,
                "PWM":       bc.pwm_pins > 0,
                "ADC":       bc.adc,
                "DAC":       bc.dac,
                "WiFi":      bc.wifi,
                "Bluetooth": bc.bluetooth,
                "CAN":       bc.can,
                "GPU":       bc.gpu_cores > 0,
            })
            # User can override with their checkboxes
            for c in self.capabilities:
                caps[c] = True

        return DetectedDevice(
            id=f"manual_{uuid.uuid4().hex[:8]}",
            name=self.name,
            port=self.port or self.ip_address or CONNECTION_TYPES[self.connection]["port_hint"],
            tier=self.tier,
            status="online",
            method=METHOD_MANUAL,
            driver=board_def.driver if board_def else "neuros.drivers.generic_serial",
            fw_version=self.firmware or "user-specified",
            chip=board_def.chip if board_def else self.board_type,
            flash=f"{board_def.caps.flash_kb}KB" if board_def else "?",
            ram=f"{board_def.caps.ram_kb}KB" if board_def and board_def.caps.ram_kb else "?",
            freq=f"{board_def.caps.freq_mhz}MHz" if board_def else "?",
            capabilities=caps,
            source="manual",
            notes=self.notes,
        )


# ── Persistent Hardware Registry ────────────────────────────────

class HardwareRegistry:
    """
    Persists all detected + manually added hardware to disk.
    Lives at ~/.neuros/hardware_registry.json
    """

    def __init__(self, path: Path = REGISTRY_PATH):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._devices: dict[str, dict] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                self._devices = json.loads(self.path.read_text())
            except Exception:
                self._devices = {}

    def _save(self):
        self.path.write_text(json.dumps(self._devices, indent=2))

    def add(self, device: DetectedDevice, overwrite: bool = False) -> bool:
        """Add device to registry. Returns False if already exists and overwrite=False."""
        if device.id in self._devices and not overwrite:
            return False
        self._devices[device.id] = device.to_dict()
        self._save()
        return True

    def remove(self, device_id: str) -> bool:
        if device_id in self._devices:
            del self._devices[device_id]
            self._save()
            return True
        return False

    def get(self, device_id: str) -> Optional[DetectedDevice]:
        d = self._devices.get(device_id)
        return DetectedDevice.from_dict(d) if d else None

    def all(self) -> list[DetectedDevice]:
        return [DetectedDevice.from_dict(d) for d in self._devices.values()]

    def manual_devices(self) -> list[DetectedDevice]:
        return [DetectedDevice.from_dict(d) for d in self._devices.values()
                if d.get("source") == "manual"]

    def auto_devices(self) -> list[DetectedDevice]:
        return [DetectedDevice.from_dict(d) for d in self._devices.values()
                if d.get("source") == "auto"]

    def count(self) -> int:
        return len(self._devices)

    def clear_auto(self):
        """Remove all auto-detected entries (re-scan will repopulate)."""
        self._devices = {k: v for k, v in self._devices.items()
                         if v.get("source") == "manual"}
        self._save()


# ── Interactive manual-add wizard (CLI mode) ─────────────────────

class ManualAddWizard:
    """
    Step-by-step CLI wizard for adding hardware manually.
    Called from the NEUROS CLI when user runs: neuros hardware add
    """

    def __init__(self, registry: HardwareRegistry):
        self.registry = registry

    def run(self) -> Optional[DetectedDevice]:
        from rich.console import Console
        from rich.prompt import Prompt, Confirm
        from rich.panel import Panel
        from rich.columns import Columns
        from rich import box
        from rich.table import Table

        console = Console()
        console.print()
        console.print(Panel(
            "[bold cyan]NEUROS Hardware — Manual Add Wizard[/bold cyan]\n"
            "[dim]Add any board that wasn't auto-detected[/dim]",
            border_style="cyan", padding=(0, 2)
        ))
        console.print()

        # ── Step 1: Device name ──────────────────────────────────
        name = Prompt.ask("[yellow]Device name[/yellow] [dim](e.g. My Arduino Mega)[/dim]")

        # ── Step 2: Board type ───────────────────────────────────
        console.print("\n[cyan]Known boards (press ENTER to skip and type custom):[/cyan]")
        families: dict[str, list[str]] = {}
        for bname, bdef in BOARD_REGISTRY.items():
            families.setdefault(bdef.family, []).append(bname)

        table = Table(box=box.SIMPLE, show_header=True, header_style="dim")
        table.add_column("#", style="dim", width=4)
        table.add_column("Board", style="white")
        table.add_column("Family", style="cyan")
        table.add_column("Chip", style="dim")
        table.add_column("Tier", style="yellow")

        board_list = list(BOARD_REGISTRY.keys())
        for i, bname in enumerate(board_list, 1):
            bd = BOARD_REGISTRY[bname]
            table.add_row(str(i), bname, bd.family, bd.chip[:28], bd.tier)
        console.print(table)

        board_input = Prompt.ask(
            "[yellow]Board type[/yellow] [dim](number, name, or custom)[/dim]",
            default=""
        )
        if board_input.isdigit():
            idx = int(board_input) - 1
            board_type = board_list[idx] if 0 <= idx < len(board_list) else board_input
        elif board_input in BOARD_REGISTRY:
            board_type = board_input
        else:
            board_type = board_input or "Custom Board"

        # ── Step 3: Connection type ──────────────────────────────
        console.print("\n[cyan]Connection type:[/cyan]")
        conn_list = list(CONNECTION_TYPES.keys())
        for i, (key, info) in enumerate(CONNECTION_TYPES.items(), 1):
            console.print(f"  [dim]{i}.[/dim] {info['icon']} [white]{info['label']}[/white] "
                          f"[dim]— e.g. {info['port_hint']}[/dim]")
        conn_input = Prompt.ask("\n[yellow]Connection[/yellow] [dim](number or key)[/dim]", default="1")
        if conn_input.isdigit():
            conn_key = conn_list[int(conn_input) - 1] if 1 <= int(conn_input) <= len(conn_list) else "usb"
        else:
            conn_key = conn_input if conn_input in CONNECTION_TYPES else "usb"

        # ── Step 4: Port / address ───────────────────────────────
        hint = CONNECTION_TYPES[conn_key]["port_hint"]
        port = Prompt.ask(f"[yellow]Port / address[/yellow] [dim](e.g. {hint})[/dim]", default="")

        # ── Step 5: Baud rate (only for serial connections) ──────
        baud = 115200
        if conn_key in ("usb", "uart", "modbus"):
            baud_str = Prompt.ask(
                "[yellow]Baud rate[/yellow]",
                choices=[str(b) for b in BAUD_RATES],
                default="115200"
            )
            baud = int(baud_str)

        # ── Step 6: Tier ─────────────────────────────────────────
        console.print("\n[cyan]Tier:[/cyan]")
        tier_display = {
            "1": ("Basic",        "yellow", "Arduino, ESP, Pico — beginner boards"),
            "2": ("Intermediate", "green",  "Raspberry Pi, ESP32-CAM, SBCs"),
            "3": ("Advanced",     "blue",   "Jetson, STM32, Teensy, ROS2"),
            "4": ("Expert",       "magenta","Industrial, Jetson AGX, heavy RT"),
            "5": ("Critical",     "red",    "Medical, space, safety-critical"),
        }
        for k, (label, color, desc) in tier_display.items():
            console.print(f"  [dim]{k}.[/dim] [{color}]{label}[/{color}] [dim]— {desc}[/dim]")
        tier_in = Prompt.ask("[yellow]Tier[/yellow]", choices=list(TIER_OPTIONS), default="1")
        tier = TIER_OPTIONS[tier_in]

        # ── Step 7: Capabilities ─────────────────────────────────
        console.print("\n[cyan]Capabilities[/cyan] [dim](space-separated, e.g. GPIO UART I2C WiFi):[/dim]")
        console.print(f"  [dim]Available: {', '.join(CAPABILITY_LIST)}[/dim]")
        caps_input = Prompt.ask("[yellow]Capabilities[/yellow]", default="GPIO UART I2C SPI")
        caps = [c.upper() for c in caps_input.split() if c.upper() in CAPABILITY_LIST]

        # ── Step 8: Optional fields ──────────────────────────────
        firmware = Prompt.ask("[yellow]Firmware / OS[/yellow] [dim](optional)[/dim]", default="")
        notes    = Prompt.ask("[yellow]Notes[/yellow] [dim](optional)[/dim]",         default="")

        # ── Build spec, validate, convert ────────────────────────
        spec = ManualHardwareSpec(
            name=name, board_type=board_type, connection=conn_key,
            port=port, tier=tier, baud_rate=baud,
            firmware=firmware, capabilities=caps, notes=notes,
        )

        errors = spec.validate()
        if errors:
            console.print()
            for err in errors:
                console.print(f"[red]✗ {err}[/red]")
            if not Confirm.ask("\nContinue anyway?", default=False):
                return None

        device = spec.to_detected_device()

        # ── Confirm ───────────────────────────────────────────────
        console.print()
        summary = Table(box=box.SIMPLE, show_header=False)
        summary.add_column("Key",   style="dim")
        summary.add_column("Value", style="white")
        summary.add_row("Name",   device.name)
        summary.add_row("Board",  device.chip)
        summary.add_row("Port",   device.port)
        summary.add_row("Tier",   device.tier.upper())
        summary.add_row("Driver", device.driver)
        summary.add_row("Caps",   ", ".join(k for k, v in device.capabilities.items() if v))
        console.print(Panel(summary, title="[cyan]Hardware Summary[/cyan]",
                            border_style="cyan", padding=(0,1)))

        if Confirm.ask("\n[green]Add this hardware to NEUROS?[/green]", default=True):
            self.registry.add(device, overwrite=True)
            console.print(f"\n[bold green]✓ {device.name} added to Neural Bus[/bold green]")
            console.print(f"[dim]  ID: {device.id}  ·  Registry: {REGISTRY_PATH}[/dim]")
            return device

        return None
