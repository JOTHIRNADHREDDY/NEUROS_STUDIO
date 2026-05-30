"""
NEUROS V2 — Configuration Loader

Loads YAML config files from the config/ directory, merges them into a single
typed ``NeurosConfig`` dataclass tree, and applies environment-variable overrides
using the ``NEUROS_`` prefix convention.

Environment override format
----------------------------
``NEUROS_<SECTION>_<KEY>=<value>``

Examples::

    NEUROS_RUNTIME_PORT=9000          -> runtime.port = 9000
    NEUROS_SAFETY_ENABLED=false       -> safety.enabled = False
    NEUROS_AI_MODEL=gpt-4o-mini       -> ai.model = "gpt-4o-mini"

Nested keys beyond two levels are separated by underscores.  Because YAML
keys are lowercase, the environment variable name is lowered before lookup.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Section dataclasses
# ---------------------------------------------------------------------------

# ---- robot.yaml -----------------------------------------------------------

@dataclass
class RobotConfig:
    """Identity metadata for the physical (or simulated) robot."""
    id: str = "neuros-default"
    name: str = "My Robot"
    type: str = "rover"
    description: str = "Default NEUROS robot configuration"


@dataclass
class HardwareConfig:
    """Low-level board / serial connection parameters."""
    board: str = "simulator"
    port: str | None = None
    baudrate: int = 115200


# ---- runtime.yaml ---------------------------------------------------------

@dataclass
class RuntimeConfig:
    """HTTP / tick-loop runtime settings."""
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    max_workers: int = 4
    tick_rate_hz: int = 50


@dataclass
class DatabaseConfig:
    """Persistence backend configuration."""
    engine: str = "sqlite"
    path: str = "data/neuros.db"


@dataclass
class WebSocketConfig:
    """WebSocket gateway settings."""
    enabled: bool = True
    max_connections: int = 50


# ---- safety.yaml ----------------------------------------------------------

@dataclass
class SafetyConfig:
    """Global safety switches."""
    enabled: bool = True
    emergency_stop_priority: int = 0


@dataclass
class MotorLimits:
    """Motor output clamps."""
    max_pwm: int = 200
    max_speed_ms: float = 1.5


@dataclass
class ServoLimits:
    """Servo angle clamps."""
    min_angle: int = 0
    max_angle: int = 180


@dataclass
class BatteryLimits:
    """Battery voltage thresholds."""
    min_voltage: float = 10.5
    critical_voltage: float = 9.5


@dataclass
class TemperatureLimits:
    """Thermal protection thresholds (°C)."""
    max_celsius: float = 75.0
    warning_celsius: float = 65.0


@dataclass
class WorkspaceLimits:
    """Maximum workspace envelope (metres)."""
    max_x: float = 10.0
    max_y: float = 10.0
    max_z: float = 5.0


@dataclass
class LimitsConfig:
    """Aggregated hardware & environment limits."""
    motor: MotorLimits = field(default_factory=MotorLimits)
    servo: ServoLimits = field(default_factory=ServoLimits)
    battery: BatteryLimits = field(default_factory=BatteryLimits)
    temperature: TemperatureLimits = field(default_factory=TemperatureLimits)
    workspace: WorkspaceLimits = field(default_factory=WorkspaceLimits)


# ---- ai.yaml --------------------------------------------------------------

@dataclass
class AIConfig:
    """LLM / inference provider settings."""
    provider: str = "openai"
    model: str = "gpt-4o"
    temperature: float = 0.2
    max_tokens: int = 2048
    timeout_seconds: int = 30


@dataclass
class AgentToggle:
    """Per-agent on/off switch."""
    enabled: bool = True


@dataclass
class AgentsConfig:
    """Registry of toggleable agent modules."""
    planner: AgentToggle = field(default_factory=AgentToggle)
    robotics: AgentToggle = field(default_factory=AgentToggle)
    vision: AgentToggle = field(default_factory=AgentToggle)
    memory: AgentToggle = field(default_factory=AgentToggle)
    code: AgentToggle = field(default_factory=lambda: AgentToggle(enabled=False))


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------

@dataclass
class NeurosConfig:
    """Complete, merged NEUROS runtime configuration.

    Every field has a sane default so the system can boot even when config
    files are missing.
    """

    # robot.yaml
    robot: RobotConfig = field(default_factory=RobotConfig)
    hardware: HardwareConfig = field(default_factory=HardwareConfig)

    # runtime.yaml
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    websocket: WebSocketConfig = field(default_factory=WebSocketConfig)

    # safety.yaml
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    limits: LimitsConfig = field(default_factory=LimitsConfig)

    # ai.yaml
    ai: AIConfig = field(default_factory=AIConfig)
    agents: AgentsConfig = field(default_factory=AgentsConfig)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_YAML_FILES: list[str] = [
    "robot.yaml",
    "runtime.yaml",
    "safety.yaml",
    "ai.yaml",
]

_ENV_PREFIX = "NEUROS_"


def _coerce(value: str, target_type: type) -> Any:
    """Best-effort coercion of a string env-var value to *target_type*."""
    if target_type is bool:
        return value.lower() in ("1", "true", "yes", "on")
    if target_type is int:
        return int(value)
    if target_type is float:
        return float(value)
    if target_type is type(None) or target_type is (str | None):
        return value if value.lower() not in ("null", "none", "") else None
    return value


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *override* into *base* (mutates *base*)."""
    for key, val in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val
    return base


def _populate_dataclass(cls: type, data: dict[str, Any]) -> Any:
    """Recursively instantiate a dataclass *cls* from a plain dict."""
    if not data:
        return cls()

    kwargs: dict[str, Any] = {}
    for fld in fields(cls):
        if fld.name not in data:
            continue
        raw = data[fld.name]
        # If the field is itself a dataclass, recurse
        if hasattr(fld.type, "__dataclass_fields__"):
            kwargs[fld.name] = _populate_dataclass(fld.type, raw if isinstance(raw, dict) else {})
        else:
            kwargs[fld.name] = raw

    return cls(**kwargs)


def _apply_env_overrides(merged: dict[str, Any]) -> None:
    """Scan ``os.environ`` for ``NEUROS_*`` keys and patch *merged* in-place."""
    for env_key, env_val in os.environ.items():
        if not env_key.startswith(_ENV_PREFIX):
            continue

        # Strip prefix and split into path segments (lowercase)
        parts = env_key[len(_ENV_PREFIX):].lower().split("_")
        if not parts:
            continue

        # Walk into the nested dict, creating intermediate dicts as needed
        node = merged
        for part in parts[:-1]:
            if part not in node:
                node[part] = {}
            target = node[part]
            if not isinstance(target, dict):
                # The env override targets a deeper path than the YAML had;
                # we can't descend into a scalar, so skip.
                break
            node = target
        else:
            leaf_key = parts[-1]
            # Coerce to the same type as the existing value (if present)
            existing = node.get(leaf_key)
            if existing is not None:
                try:
                    env_val = _coerce(env_val, type(existing))  # type: ignore[assignment]
                except (ValueError, TypeError):
                    pass  # keep as string
            node[leaf_key] = env_val
            logger.debug("ENV override: %s -> %s.%s = %r", env_key, ".".join(parts[:-1]), leaf_key, env_val)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_config(config_dir: str | Path | None = None) -> NeurosConfig:
    """Load, merge, and return the complete NEUROS configuration.

    Parameters
    ----------
    config_dir:
        Path to the directory containing the YAML files.  Defaults to the
        ``config/`` directory next to this module.

    Returns
    -------
    NeurosConfig
        Fully-populated, typed configuration object.
    """
    if config_dir is None:
        config_dir = Path(__file__).resolve().parent
    else:
        config_dir = Path(config_dir)

    merged: dict[str, Any] = {}

    for filename in _YAML_FILES:
        filepath = config_dir / filename
        if not filepath.exists():
            logger.warning("Config file not found, skipping: %s", filepath)
            continue
        with open(filepath, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if isinstance(data, dict):
            _deep_merge(merged, data)
            logger.info("Loaded config: %s", filepath)

    # Environment variable overrides
    _apply_env_overrides(merged)

    # Build typed config tree
    config = _populate_dataclass(NeurosConfig, merged)
    assert isinstance(config, NeurosConfig)

    logger.info(
        "NEUROS config ready — robot=%s  runtime=%s:%d  safety=%s",
        config.robot.id,
        config.runtime.host,
        config.runtime.port,
        "ON" if config.safety.enabled else "OFF",
    )
    return config
