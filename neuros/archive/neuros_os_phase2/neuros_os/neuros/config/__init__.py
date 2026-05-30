"""
neuros.config
=============
NEUROS Configuration System — Phase 1.

Provides a centralised, type-safe config store that nodes can read at
startup and subscribe to for live parameter updates.

Config sources (priority order — highest wins)
-----------------------------------------------
  1. Runtime overrides  (set via config.set())
  2. Environment vars   (NEUROS_<SECTION>_<KEY>=value)
  3. Project file       (.neuros/config.yaml or config.json)
  4. Defaults           (built-in defaults below)

Live parameter updates
-----------------------
Nodes can subscribe to config changes:
  config.watch("motor.max_speed", on_max_speed_change)

This lets you tune PID gains, LED patterns, sensor thresholds etc.
at runtime without restarting the robot.

Usage
-----
    from neuros.config import Config

    cfg = Config()
    cfg.load("config.yaml")

    speed = cfg.get("motor.max_speed", default=0.8)
    cfg.set("led.pattern", "blink")
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("neuros.config")

# ── Built-in defaults ──────────────────────────────────────────────────────
_DEFAULTS: Dict[str, Any] = {
    # Kernel
    "kernel.domain":        "A",
    "kernel.hz":            1000,
    "kernel.watchdog_s":    2.0,
    "kernel.max_restarts":  3,

    # Neural Bus
    "bus.qos_default":      "best_effort",

    # Motors
    "motor.max_speed":      1.0,
    "motor.default_hz":     100,
    "motor.pid.kp":         1.0,
    "motor.pid.ki":         0.05,
    "motor.pid.kd":         0.01,

    # Servos
    "servo.duty_min":       0.025,
    "servo.duty_max":       0.125,
    "servo.hz":             50,

    # Safety
    "safety.battery_crit_v": 3.0,
    "safety.battery_low_v":  3.3,
    "safety.overcurrent_a":  2.0,
    "safety.hz":             50,

    # LED
    "led.default_brightness": 1.0,
    "led.blink_hz":          2.0,

    # IMU
    "imu.hz":           100,
    "imu.alpha":        0.96,
    "imu.i2c_address":  0x68,

    # Ultrasonic
    "sonar.hz":         10,
    "sonar.max_retries": 3,

    # Encoder
    "encoder.ticks_per_rev": 360,
    "encoder.wheel_dia_m":   0.065,
    "encoder.hz":            500,

    # Line follower
    "line.hz":      100,
    "line.invert":  True,

    # AI / LLM
    "ai.enabled":   False,       # Phase 3 activates
    "ai.model":     "stub",
}


class Config:
    """
    NEUROS configuration store.

    Keys use dot notation: "motor.pid.kp"

    Example
    -------
        cfg = Config()
        cfg.load("my_robot_config.json")

        speed = cfg.get("motor.max_speed")
        cfg.set("led.blink_hz", 4.0)
        cfg.watch("motor.max_speed", lambda old, new: print(f"Speed: {old}→{new}"))
    """

    def __init__(self) -> None:
        self._store:    Dict[str, Any]              = dict(_DEFAULTS)
        self._watchers: Dict[str, List[Callable]]   = {}
        self._load_env()

    # ── Load ────────────────────────────────────────────────────────────────
    def load(self, path: str) -> None:
        """Load config from a JSON or simple KEY=VALUE file."""
        try:
            with open(path) as f:
                if path.endswith(".json"):
                    data = json.load(f)
                    self._update_flat(data)
                else:
                    # KEY=VALUE format
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, _, v = line.partition("=")
                            self._store[k.strip()] = self._coerce(v.strip())
            logger.info("[CONFIG] loaded %s", path)
        except FileNotFoundError:
            logger.debug("[CONFIG] no config file at %s — using defaults", path)
        except Exception as e:
            logger.warning("[CONFIG] error loading %s: %s", path, e)

    def _update_flat(self, data: dict, prefix: str = "") -> None:
        """Recursively flatten nested dict into dot-notation keys."""
        for k, v in data.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                self._update_flat(v, full_key)
            else:
                self._store[full_key] = v

    def _load_env(self) -> None:
        """Load NEUROS_* environment variables."""
        for key, val in os.environ.items():
            if key.startswith("NEUROS_"):
                cfg_key = key[7:].lower().replace("__", ".").replace("_", ".")
                self._store[cfg_key] = self._coerce(val)

    @staticmethod
    def _coerce(val: str) -> Any:
        """Try to coerce string value to int, float, or bool."""
        if val.lower() in ("true", "yes"):  return True
        if val.lower() in ("false", "no"):  return False
        try: return int(val)
        except ValueError: pass
        try: return float(val)
        except ValueError: pass
        return val

    # ── Get / Set ──────────────────────────────────────────────────────────
    def get(self, key: str, *, default: Any = None) -> Any:
        return self._store.get(key, default)

    def set(self, key: str, value: Any) -> None:
        old = self._store.get(key)
        self._store[key] = value
        if old != value:
            for cb in self._watchers.get(key, []):
                try:
                    cb(old, value)
                except Exception as e:
                    logger.error("[CONFIG] watcher error for '%s': %s", key, e)

    def watch(self, key: str, callback: Callable[[Any, Any], None]) -> None:
        """Register a callback: cb(old_value, new_value) on key change."""
        self._watchers.setdefault(key, []).append(callback)

    def dump(self) -> Dict[str, Any]:
        return dict(self._store)

    def __repr__(self) -> str:
        return f"<Config keys={len(self._store)}>"


# ── Singleton ───────────────────────────────────────────────────────────────
_global_config: Optional[Config] = None


def get_config() -> Config:
    """Return the global NEUROS config singleton."""
    global _global_config
    if _global_config is None:
        _global_config = Config()
    return _global_config
