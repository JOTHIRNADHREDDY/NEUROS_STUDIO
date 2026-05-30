"""
NEUROS V2 — Configuration Package

Quick start::

    from neuros.config import load_config, NeurosConfig

    cfg: NeurosConfig = load_config()
    print(cfg.runtime.port)        # 8000
    print(cfg.safety.enabled)      # True
"""

from neuros.config.loader import (
    AgentsConfig,
    AgentToggle,
    AIConfig,
    BatteryLimits,
    DatabaseConfig,
    HardwareConfig,
    LimitsConfig,
    MotorLimits,
    NeurosConfig,
    RobotConfig,
    RuntimeConfig,
    SafetyConfig,
    ServoLimits,
    TemperatureLimits,
    WebSocketConfig,
    WorkspaceLimits,
    load_config,
)

__all__: list[str] = [
    "load_config",
    "NeurosConfig",
    "RobotConfig",
    "HardwareConfig",
    "RuntimeConfig",
    "DatabaseConfig",
    "WebSocketConfig",
    "SafetyConfig",
    "LimitsConfig",
    "MotorLimits",
    "ServoLimits",
    "BatteryLimits",
    "TemperatureLimits",
    "WorkspaceLimits",
    "AIConfig",
    "AgentsConfig",
    "AgentToggle",
]
