"""
NEUROS OS — CLI
Entry point for all hardware and library management commands.

Usage:
    neuros hardware scan          # auto-detect all hardware
    neuros hardware add           # manually add a board
    neuros hardware list          # show installed hardware
    neuros hardware remove <id>   # remove a device
    neuros hardware info <id>     # detailed device info
    neuros library list           # list all libraries
    neuros library search <q>     # search libraries
    neuros library install <name> # install a library
    neuros library remove <name>  # uninstall a library
    neuros library compat         # show libs for your hardware
"""

import click
import time
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.columns import Columns
from rich import box
from rich.text import Text
from rich.syntax import Syntax

from neuros.hardware.detector import HardwareDetector, DetectedDevice
from neuros.hardware.manual import HardwareRegistry, ManualAddWizard, REGISTRY_PATH
from neuros.hardware.manager import LibraryManager, CATEGORIES
from neuros.hardware.boards import TIER_COLORS, all_boards, boards_by_family

console = Console()

TIER_RICH_COLORS = {
    "basic":        "yellow",
    "intermediate": "green",
    "advanced":     "blue",
    "expert":       "magenta",
    "critical":     "red",
}

STATUS_COLORS = {
    "online":  "green",
    "partial": "yellow",
    "offline": "red",
}

# ── Shared instances ─────────────────────────────────────────────
registry = HardwareRegistry()
lib_mgr  = LibraryManager()


# ════════════════════════════════════════════════════════════════
#  ROOT
# ════════════════════════════════════════════════════════════════
@click.group()
def cli():
    """
    \b
    ███╗   ██╗███████╗██╗   ██╗██████╗  ██████╗ ███████╗
    ████╗  ██║██╔════╝██║   ██║██╔══██╗██╔═══██╗██╔════╝
    ██╔██╗ ██║█████╗  ██║   ██║██████╔╝██║   ██║███████╗
    ██║╚██╗██║██╔══╝  ██║   ██║██╔══██╗██║   ██║╚════██║
    ██║ ╚████║███████╗╚██████╔╝██║  ██║╚██████╔╝███████║
    ╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
    One OS. Every Robot. Zero Exceptions.
    """
    pass


# ════════════════════════════════════════════════════════════════
#  HARDWARE GROUP
# ════════════════════════════════════════════════════════════════
@cli.group()
def hardware():
    """Detect, add, list, and manage hardware devices."""
    pass


@hardware.command("scan")
@click.option("--save/--no-save", default=True, help="Save results to registry")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def hardware_scan(save, as_json):
    """Auto-detect all connected hardware (USB, I²C, WiFi, host)."""

    if not as_json:
        console.print()
        console.print(Panel(
            "[bold cyan]NEUROS Hardware Auto-Detection[/bold cyan]\n"
            "[dim]Scanning USB Serial · I²C Bus · WiFi/mDNS · Host[/dim]",
            border_style="cyan", padding=(0, 2)
        ))

    detector = HardwareDetector()

    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[cyan]{task.description}"),
        transient=True, console=console
    ) as prog:
        task = prog.add_task("Scanning all ports in parallel...", total=None)
        devices, elapsed, errors = detector.scan()
        prog.update(task, description=f"Done in {elapsed:.2f}s")

    if as_json:
        import json
        click.echo(json.dumps([d.to_dict() for d in devices], indent=2))
        return

    if not devices:
        console.print("[yellow]No hardware detected.[/yellow]")
        console.print("[dim]Tip: plug in a board, then run 'neuros hardware scan' again.[/dim]")
        console.print("[dim]Or use 'neuros hardware add' to add manually.[/dim]")
    else:
        console.print()
        _print_device_table(devices, elapsed)

    if errors:
        console.print()
        for e in errors:
            console.print(f"[dim red]⚠  {e}[/dim red]")

    if save and devices:
        registry.clear_auto()
        for d in devices:
            registry.add(d, overwrite=True)
        console.print(f"\n[dim]✓ {len(devices)} devices saved → {REGISTRY_PATH}[/dim]")

    console.print()


@hardware.command("add")
def hardware_add():
    """Manually add a board that wasn't auto-detected."""
    wizard = ManualAddWizard(registry)
    wizard.run()


@hardware.command("list")
@click.option("--auto-only",   is_flag=True, help="Show only auto-detected devices")
@click.option("--manual-only", is_flag=True, help="Show only manually added devices")
def hardware_list(auto_only, manual_only):
    """List all registered hardware devices."""
    devices = registry.all()

    if auto_only:
        devices = [d for d in devices if d.source == "auto"]
    elif manual_only:
        devices = [d for d in devices if d.source == "manual"]

    console.print()
    if not devices:
        console.print("[yellow]No hardware in registry.[/yellow]")
        console.print("[dim]Run 'neuros hardware scan' or 'neuros hardware add'[/dim]")
        return

    _print_device_table(devices)
    console.print(f"\n[dim]Registry: {REGISTRY_PATH}  ·  Total: {len(devices)} devices[/dim]\n")


@hardware.command("info")
@click.argument("device_id")
def hardware_info(device_id):
    """Show detailed info for a specific device."""
    device = registry.get(device_id)
    if not device:
        # Try searching by name
        all_devs = registry.all()
        matches = [d for d in all_devs if device_id.lower() in d.name.lower()]
        if len(matches) == 1:
            device = matches[0]
        elif len(matches) > 1:
            console.print(f"[yellow]Multiple matches:[/yellow]")
            for m in matches:
                console.print(f"  {m.id}  {m.name}")
            return
        else:
            console.print(f"[red]Device '{device_id}' not found in registry.[/red]")
            return

    _print_device_detail(device)


@hardware.command("remove")
@click.argument("device_id")
@click.confirmation_option(prompt="Remove this device from registry?")
def hardware_remove(device_id):
    """Remove a device from the registry."""
    if registry.remove(device_id):
        console.print(f"[green]✓ Removed {device_id}[/green]")
    else:
        console.print(f"[red]Device '{device_id}' not found.[/red]")


@hardware.command("boards")
@click.option("--family", default="", help="Filter by family (Arduino, ESP, etc.)")
@click.option("--tier",   default="", help="Filter by tier (basic, inter, etc.)")
def hardware_boards(family, tier):
    """List all boards in the NEUROS board registry."""
    boards = all_boards()
    if family:
        boards = [b for b in boards if family.lower() in b.family.lower()]
    if tier:
        boards = [b for b in boards if tier.lower() in b.tier.lower()]

    console.print()
    table = Table(
        title="[bold cyan]NEUROS Board Registry[/bold cyan]",
        box=box.SIMPLE_HEAVY, header_style="dim cyan",
        show_lines=False, padding=(0, 1)
    )
    table.add_column("Board",   style="white",  min_width=28)
    table.add_column("Family",  style="cyan",   min_width=12)
    table.add_column("Chip",    style="dim",    min_width=24)
    table.add_column("Flash",   style="yellow", min_width=7)
    table.add_column("RAM",     style="green",  min_width=6)
    table.add_column("Freq",    style="blue",   min_width=8)
    table.add_column("Tier",    min_width=12)
    table.add_column("WiFi",    min_width=4)
    table.add_column("BT",      min_width=4)
    table.add_column("CAN",     min_width=4)

    for b in boards:
        tc = TIER_RICH_COLORS.get(b.tier, "white")
        c  = b.caps
        table.add_row(
            b.name,
            b.family,
            b.chip[:26],
            f"{c.flash_kb}KB" if c.flash_kb else f"{c.ram_mb}MB" if not c.flash_kb else "?",
            f"{c.ram_kb}KB"   if c.ram_kb   else f"{c.ram_mb}MB" if c.ram_mb else "?",
            f"{c.freq_mhz}MHz" if c.freq_mhz else "?",
            f"[{tc}]{b.tier}[/{tc}]",
            "✓" if c.wifi      else "[dim]·[/dim]",
            "✓" if c.bluetooth else "[dim]·[/dim]",
            "✓" if c.can       else "[dim]·[/dim]",
        )

    console.print(table)
    console.print(f"[dim]  {len(boards)} boards listed[/dim]\n")


# ════════════════════════════════════════════════════════════════
#  LIBRARY GROUP
# ════════════════════════════════════════════════════════════════
@cli.group()
def library():
    """Discover, install, and manage NEUROS-compatible libraries."""
    pass


@library.command("list")
@click.option("--category", "-c", default="All",
              type=click.Choice(CATEGORIES, case_sensitive=False),
              help="Filter by category")
@click.option("--installed", "-i", is_flag=True, help="Show only installed libraries")
def library_list(category, installed):
    """List all available libraries."""
    libs = lib_mgr.by_category(category)
    if installed:
        libs = [l for l in libs if l.installed]

    console.print()
    table = Table(
        title=f"[bold yellow]NEUROS Library Manager[/bold yellow]"
              + (f" — [cyan]{category}[/cyan]" if category != "All" else ""),
        box=box.SIMPLE_HEAVY, header_style="dim yellow", padding=(0, 1)
    )
    table.add_column("Library",    style="white",  min_width=36)
    table.add_column("Category",   style="cyan",   min_width=20)
    table.add_column("Compatible", style="dim",    min_width=30)
    table.add_column("Version",    style="dim",    min_width=8)
    table.add_column("Status",     min_width=12)

    for lib in libs:
        compat = ", ".join(lib.compatible_families[:3])
        if len(lib.compatible_families) > 3:
            compat += f" +{len(lib.compatible_families)-3}"
        status = "[green]INSTALLED[/green]" if lib.installed else "[dim]available[/dim]"
        table.add_row(lib.name, lib.category, compat, f"v{lib.version}", status)

    console.print(table)
    inst_count = sum(1 for l in libs if l.installed)
    console.print(f"[dim]  {len(libs)} libraries  ·  {inst_count} installed[/dim]\n")


@library.command("search")
@click.argument("query")
def library_search(query):
    """Search libraries by name, description, or tag."""
    results = lib_mgr.search(query)
    console.print()
    if not results:
        console.print(f"[yellow]No results for '{query}'[/yellow]")
        return

    console.print(f"[cyan]{len(results)} results for '[bold]{query}[/bold]':[/cyan]\n")
    for lib in results:
        status = "[green]●[/green] INSTALLED" if lib.installed else "[dim]○ available[/dim]"
        console.print(f"  [bold white]{lib.name}[/bold white]  [dim]v{lib.version}[/dim]  {status}")
        console.print(f"  [dim]{lib.description[:80]}[/dim]")
        console.print(f"  [dim cyan]pip install {lib.pip_package}[/dim cyan]")
        console.print()


@library.command("info")
@click.argument("lib_name")
def library_info(lib_name):
    """Show detailed info and example code for a library."""
    lib = lib_mgr.get(lib_name)
    if not lib:
        results = lib_mgr.search(lib_name)
        if results:
            lib = results[0]
        else:
            console.print(f"[red]Library '{lib_name}' not found.[/red]")
            return

    console.print()
    status = "[bold green]INSTALLED[/bold green]" if lib.installed else "[dim]not installed[/dim]"
    console.print(Panel(
        f"[bold white]{lib.name}[/bold white]  v{lib.version}  {status}\n"
        f"[dim]by {lib.author} · {lib.category}[/dim]\n\n"
        f"{lib.description}\n\n"
        f"[dim]Compatible with:[/dim] {', '.join(lib.compatible_families)}\n"
        f"[dim]pip package:[/dim] [cyan]{lib.pip_package}[/cyan]\n"
        f"[dim]Tags:[/dim] {', '.join(lib.tags)}",
        title="[yellow]Library Info[/yellow]",
        border_style="yellow", padding=(1, 2)
    ))

    if lib.example:
        console.print("\n[dim]Example:[/dim]")
        console.print(Syntax(lib.example, "python",
                             theme="monokai", background_color="default",
                             padding=(1, 2)))

    if not lib.installed:
        console.print(f"\n[dim]Install:[/dim]  [cyan]neuros library install \"{lib.name}\"[/cyan]\n")
    else:
        console.print(f"\n[dim]Remove:[/dim]   [cyan]neuros library remove \"{lib.name}\"[/cyan]\n")


@library.command("install")
@click.argument("lib_name")
@click.option("--skip-pip", is_flag=True, help="Mark installed without pip (already on system)")
def library_install(lib_name, skip_pip):
    """Install a library via pip."""
    lib = lib_mgr.get(lib_name)
    if not lib:
        results = lib_mgr.search(lib_name)
        if results:
            lib = results[0]
            lib_name = lib.name
        else:
            console.print(f"[red]Library '{lib_name}' not found.[/red]")
            return

    if lib.installed:
        console.print(f"[green]'{lib_name}' is already installed (v{lib.installed_ver}).[/green]")
        return

    console.print(f"\nInstalling [bold white]{lib_name}[/bold white] v{lib.version}...")

    if skip_pip:
        lib_mgr.mark_installed(lib_name)
        console.print(f"[green]✓ Marked as installed.[/green]")
        return

    with Progress(
        SpinnerColumn(style="yellow"),
        TextColumn("[yellow]{task.description}"),
        transient=True, console=console
    ) as prog:
        task = prog.add_task(f"pip install {lib.pip_package}=={lib.version}", total=None)
        ok = lib_mgr.install(lib_name, console=None)

    if ok:
        console.print(f"[bold green]✓ Installed {lib_name} v{lib.version}[/bold green]")
        console.print(f"[dim]  To use:  {lib.example.splitlines()[0] if lib.example else ''}[/dim]")
    else:
        console.print(f"[red]✗ Install failed for '{lib_name}'.[/red]")
        console.print(f"[dim]  Try manually: pip install {lib.pip_package} --break-system-packages[/dim]")


@library.command("remove")
@click.argument("lib_name")
@click.confirmation_option(prompt="Uninstall this library?")
def library_remove(lib_name):
    """Uninstall a library."""
    lib = lib_mgr.get(lib_name)
    if not lib:
        console.print(f"[red]Library '{lib_name}' not found.[/red]")
        return
    if not lib.installed:
        console.print(f"[yellow]'{lib_name}' is not installed.[/yellow]")
        return

    ok = lib_mgr.uninstall(lib_name, console=console)
    if ok:
        console.print(f"[green]✓ Removed {lib_name}[/green]")
    else:
        console.print(f"[red]✗ Failed to remove '{lib_name}'.[/red]")


@library.command("compat")
def library_compat():
    """Show libraries compatible with your currently installed hardware."""
    hw_list = registry.all()
    if not hw_list:
        console.print("[yellow]No hardware in registry. Run 'neuros hardware scan' first.[/yellow]")
        return

    compatible = lib_mgr.compatible_with_hardware(hw_list)
    console.print()
    console.print(f"[cyan]Libraries compatible with your {len(hw_list)} registered device(s):[/cyan]\n")

    for cat in CATEGORIES:
        cat_libs = [l for l in compatible if l.category == cat]
        if not cat_libs:
            continue
        console.print(f"[bold dim]{cat}[/bold dim]")
        for lib in cat_libs:
            status = "[green]✓[/green]" if lib.installed else " [dim]○[/dim]"
            console.print(f"  {status} [white]{lib.name}[/white]  [dim]v{lib.version}[/dim]")
        console.print()


# ════════════════════════════════════════════════════════════════
#  PRETTY PRINTERS
# ════════════════════════════════════════════════════════════════

def _print_device_table(devices: list[DetectedDevice], elapsed: float | None = None):
    title = "[bold cyan]Detected Hardware[/bold cyan]"
    if elapsed is not None:
        title += f"  [dim]({elapsed:.2f}s · parallel scan)[/dim]"

    table = Table(title=title, box=box.SIMPLE_HEAVY,
                  header_style="dim cyan", padding=(0, 1))
    table.add_column("Status",  width=8)
    table.add_column("Name",    style="white",  min_width=26)
    table.add_column("Port",    style="cyan",   min_width=20)
    table.add_column("Tier",    min_width=13)
    table.add_column("Chip",    style="dim",    min_width=20)
    table.add_column("Source",  style="dim",    min_width=8)
    table.add_column("Method",  style="dim",    min_width=20)
    table.add_column("ID",      style="dim",    min_width=18)

    for d in devices:
        sc = STATUS_COLORS.get(d.status, "white")
        tc = TIER_RICH_COLORS.get(d.tier, "white")
        table.add_row(
            f"[{sc}]● {d.status.upper()[:7]}[/{sc}]",
            d.name,
            d.port[:22],
            f"[{tc}]{d.tier}[/{tc}]",
            (d.chip or "")[:22],
            d.source,
            d.method[:22],
            d.id[:18],
        )

    console.print(table)


def _print_device_detail(d: DetectedDevice):
    tc = TIER_RICH_COLORS.get(d.tier, "white")
    sc = STATUS_COLORS.get(d.status, "white")
    console.print()
    console.print(Panel(
        f"[bold white]{d.name}[/bold white]   "
        f"[{sc}]● {d.status.upper()}[/{sc}]   "
        f"[{tc}]{d.tier.upper()}[/{tc}]\n"
        f"[dim]ID: {d.id}  ·  Source: {d.source}  ·  Added: "
        f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(d.added_at))}[/dim]",
        title="[cyan]Device Info[/cyan]",
        border_style="cyan", padding=(0, 2)
    ))

    # Specs table
    specs = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    specs.add_column("Key",   style="dim")
    specs.add_column("Value", style="white")
    for k, v in [
        ("Port",       d.port),
        ("Chip",       d.chip),
        ("Driver",     d.driver),
        ("Firmware",   d.fw_version),
        ("Flash",      d.flash),
        ("RAM",        d.ram),
        ("Freq",       d.freq),
        ("Method",     d.method),
        ("Notes",      d.notes or "—"),
    ]:
        specs.add_row(k, v)
    console.print(specs)

    # Capabilities
    if d.capabilities:
        caps_on  = [k for k, v in d.capabilities.items() if v]
        caps_off = [k for k, v in d.capabilities.items() if not v]
        console.print(f"\n[dim]Capabilities:[/dim]")
        if caps_on:
            console.print("  [green]" + "  ".join(caps_on) + "[/green]")
        if caps_off:
            console.print("  [dim]" + "  ".join(caps_off) + "[/dim]")
    console.print()


# ── Entry point ──────────────────────────────────────────────────
if __name__ == "__main__":
    cli()
