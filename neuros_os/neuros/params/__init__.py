"""
neuros.params
=============
Phase 2 — Parameter Manager.

ROS2 parameters become typed Python dataclasses.
Hot-reload without restarting nodes. YAML config that makes sense.

Usage
-----
    from neuros.params import ParameterManager, ParamGroup

    # Define a typed parameter group
    class DriveParams(ParamGroup):
        max_speed: float = 1.0
        turn_rate: float = 0.5
        wheel_base: float = 0.15
        pid_kp: float = 1.2
        pid_ki: float = 0.01
        pid_kd: float = 0.05

    # Create manager and register
    pm = ParameterManager()
    drive = pm.register("drive", DriveParams)

    # Access with dot notation
    print(drive.max_speed)   # → 1.0

    # Hot-reload from YAML
    pm.load_yaml("params.yaml")

    # Watch for changes
    pm.watch("drive.max_speed", lambda old, new: print(f"Speed changed: {old} → {new}"))

    # Set programmatically (triggers watchers)
    pm.set("drive.max_speed", 2.0)

    # Dump current values
    pm.save_yaml("params_snapshot.yaml")
"""

from __future__ import annotations

import copy
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field, fields, asdict
from pathlib import Path
from typing import (
    Any, Callable, Dict, Generic, List, Optional,
    Set, Tuple, Type, TypeVar, get_type_hints,
)

logger = logging.getLogger("neuros.params")

T = TypeVar("T")


# ── ParamGroup Base ───────────────────────────────────────────────────────

class ParamGroup:
    """
    Base class for typed parameter groups.

    Subclass and define fields with type annotations and defaults:

        class MotorParams(ParamGroup):
            max_speed: float = 1.0
            acceleration: float = 0.5
            reverse_enabled: bool = True
    """

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Collect annotations with defaults
        hints = {}
        for klass in reversed(cls.__mro__):
            if hasattr(klass, '__annotations__'):
                hints.update(klass.__annotations__)
        cls._param_fields = hints

    def __init__(self, **overrides):
        hints = getattr(self.__class__, '_param_fields', {})
        for name, typ in hints.items():
            if name.startswith('_'):
                continue
            if name in overrides:
                value = _coerce(overrides[name], typ)
            elif hasattr(self.__class__, name):
                value = copy.deepcopy(getattr(self.__class__, name))
            else:
                value = _default_for_type(typ)
            object.__setattr__(self, name, value)

    def to_dict(self) -> dict:
        """Serialize all parameters to a dict."""
        hints = getattr(self.__class__, '_param_fields', {})
        result = {}
        for name in hints:
            if name.startswith('_'):
                continue
            result[name] = getattr(self, name, None)
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "ParamGroup":
        """Create a ParamGroup from a dict."""
        return cls(**data)

    def update(self, data: dict) -> List[Tuple[str, Any, Any]]:
        """
        Update parameters from a dict.
        Returns list of (key, old_value, new_value) for changed params.
        """
        changes = []
        hints = getattr(self.__class__, '_param_fields', {})
        for key, value in data.items():
            if key in hints and not key.startswith('_'):
                old = getattr(self, key, None)
                new = _coerce(value, hints[key])
                if old != new:
                    object.__setattr__(self, key, new)
                    changes.append((key, old, new))
        return changes

    def __repr__(self):
        items = ', '.join(f'{k}={v!r}' for k, v in self.to_dict().items())
        return f"{self.__class__.__name__}({items})"


def _coerce(value: Any, typ: type) -> Any:
    """Coerce a value to the expected type."""
    if value is None:
        return value
    try:
        origin = getattr(typ, '__origin__', None)
        if origin is not None:
            return value  # Don't coerce generics
        if typ is bool:
            if isinstance(value, str):
                return value.lower() in ('true', 'yes', '1')
            return bool(value)
        if typ is int:
            return int(value)
        if typ is float:
            return float(value)
        if typ is str:
            return str(value)
        return value
    except (TypeError, ValueError):
        return value


def _default_for_type(typ: type) -> Any:
    """Return a sensible default for a type."""
    if typ is bool:
        return False
    if typ is int:
        return 0
    if typ is float:
        return 0.0
    if typ is str:
        return ""
    if typ is list or getattr(typ, '__origin__', None) is list:
        return []
    if typ is dict or getattr(typ, '__origin__', None) is dict:
        return {}
    return None


# ── Watcher ───────────────────────────────────────────────────────────────

@dataclass
class _Watcher:
    """A registered parameter change watcher."""
    pattern: str          # "group.key" or "group.*" or "*"
    callback: Callable    # fn(old_value, new_value) or fn(key, old_value, new_value)
    once: bool = False
    _nparams: int = -1    # cached callback arity (avoids inspect on every fire)

    def __post_init__(self):
        """Cache the callback arity at registration time."""
        if self._nparams < 0:
            try:
                import inspect
                sig = inspect.signature(self.callback)
                self._nparams = len(sig.parameters)
            except (ValueError, TypeError):
                self._nparams = 2  # default: (old, new)


# ── Parameter Manager ─────────────────────────────────────────────────────

class ParameterManager:
    """
    Central parameter manager for a NEUROS robot.

    Features:
    - Register typed ParamGroups
    - Load/save from YAML
    - Dot-notation access: pm.get("drive.max_speed")
    - Watch for changes with callbacks
    - Hot-reload from file (with file watcher)
    - Thread-safe
    """

    def __init__(self) -> None:
        self._groups: Dict[str, ParamGroup] = {}
        self._watchers: List[_Watcher] = []
        self._lock = threading.RLock()
        self._file_watcher: Optional[threading.Thread] = None
        self._watch_file: Optional[str] = None
        self._watch_running = False
        self._last_mtime: float = 0.0

    def register(self, name: str, group_cls: Type[ParamGroup],
                 **overrides) -> ParamGroup:
        """
        Register a typed parameter group.

        Parameters
        ----------
        name       : group name (e.g. "drive", "camera", "pid")
        group_cls  : ParamGroup subclass
        **overrides: initial value overrides

        Returns the instantiated ParamGroup.
        """
        with self._lock:
            instance = group_cls(**overrides)
            self._groups[name] = instance
            logger.info("[PARAMS] Registered group '%s' (%s) — %d params",
                        name, group_cls.__name__, len(instance.to_dict()))
            return instance

    def get_group(self, name: str) -> Optional[ParamGroup]:
        """Get a registered parameter group by name."""
        return self._groups.get(name)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a parameter value by dot-notation key.

        Example: pm.get("drive.max_speed") → 1.0
        """
        parts = key.split('.', 1)
        if len(parts) != 2:
            return default
        group_name, param_name = parts
        group = self._groups.get(group_name)
        if group is None:
            return default
        return getattr(group, param_name, default)

    def set(self, key: str, value: Any) -> bool:
        """
        Set a parameter value by dot-notation key.
        Triggers watchers if value changed.

        Returns True if value was changed.
        """
        parts = key.split('.', 1)
        if len(parts) != 2:
            logger.warning("[PARAMS] Invalid key format: '%s' (expected 'group.param')", key)
            return False

        group_name, param_name = parts
        with self._lock:
            group = self._groups.get(group_name)
            if group is None:
                logger.warning("[PARAMS] Unknown group: '%s'", group_name)
                return False

            old = getattr(group, param_name, None)
            hints = getattr(group.__class__, '_param_fields', {})
            if param_name not in hints:
                logger.warning("[PARAMS] Unknown param: '%s.%s'", group_name, param_name)
                return False

            new = _coerce(value, hints[param_name])
            if old == new:
                return False

            object.__setattr__(group, param_name, new)
            logger.debug("[PARAMS] %s = %r → %r", key, old, new)

            # Fire watchers
            self._fire_watchers(key, group_name, param_name, old, new)
            return True

    def set_many(self, updates: Dict[str, Any]) -> int:
        """Set multiple parameters at once. Returns count of changed params."""
        changed = 0
        for key, value in updates.items():
            if self.set(key, value):
                changed += 1
        return changed

    def watch(self, pattern: str, callback: Callable, *, once: bool = False) -> None:
        """
        Watch for parameter changes.

        Parameters
        ----------
        pattern  : "group.param" for specific, "group.*" for group, "*" for all
        callback : fn(old_value, new_value) or fn(key, old_value, new_value)
        once     : if True, fire only once then auto-unwatch
        """
        with self._lock:
            self._watchers.append(_Watcher(pattern=pattern, callback=callback, once=once))

    def unwatch(self, callback: Callable) -> None:
        """Remove a watcher by its callback reference."""
        with self._lock:
            self._watchers = [w for w in self._watchers if w.callback is not callback]

    def _fire_watchers(self, full_key: str, group: str, param: str,
                       old: Any, new: Any) -> None:
        """Fire matching watchers for a parameter change."""
        to_remove = []
        for i, w in enumerate(self._watchers):
            match = False
            if w.pattern == "*":
                match = True
            elif w.pattern == f"{group}.*":
                match = True
            elif w.pattern == full_key:
                match = True

            if match:
                try:
                    # Use cached arity (Fix #17 — no inspect.signature per call)
                    if w._nparams >= 3:
                        w.callback(full_key, old, new)
                    else:
                        w.callback(old, new)
                except Exception as e:
                    logger.error("[PARAMS] Watcher error for '%s': %s", w.pattern, e)
                if w.once:
                    to_remove.append(i)

        for i in reversed(to_remove):
            self._watchers.pop(i)

    # ── Serialization ─────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, dict]:
        """Serialize all parameter groups to a dict."""
        with self._lock:
            return {name: group.to_dict() for name, group in self._groups.items()}

    def load_dict(self, data: Dict[str, dict]) -> int:
        """
        Load parameter values from a dict.
        Only updates existing registered groups.
        Returns count of changed parameters.
        """
        changed = 0
        with self._lock:
            for group_name, params in data.items():
                if group_name in self._groups and isinstance(params, dict):
                    for key, value in params.items():
                        if self.set(f"{group_name}.{key}", value):
                            changed += 1
        return changed

    def load_yaml(self, path: str) -> int:
        """Load parameters from a YAML file. Returns count of changed params."""
        from neuros.launch import _parse_simple_yaml
        p = Path(path)
        if not p.exists():
            logger.warning("[PARAMS] File not found: %s", path)
            return 0
        text = p.read_text(encoding="utf-8")
        data = _parse_simple_yaml(text)
        changed = self.load_dict(data)
        logger.info("[PARAMS] Loaded from %s — %d params changed", path, changed)
        return changed

    def save_yaml(self, path: str) -> None:
        """Save current parameters to a YAML-like file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"# NEUROS OS Parameter Snapshot", f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}", ""]
        for group_name, group in self._groups.items():
            lines.append(f"{group_name}:")
            for key, value in group.to_dict().items():
                lines.append(f"  {key}: {_yaml_value(value)}")
            lines.append("")
        p.write_text('\n'.join(lines), encoding="utf-8")
        logger.info("[PARAMS] Saved to %s", path)

    def save_json(self, path: str) -> None:
        """Save current parameters to a JSON file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    # ── File Watcher (Hot-Reload) ─────────────────────────────────────────

    def enable_hot_reload(self, path: str, *, interval: float = 1.0) -> None:
        """
        Watch a YAML file for changes and auto-reload parameters.

        Parameters
        ----------
        path     : path to YAML file to watch
        interval : check interval in seconds
        """
        self._watch_file = path
        self._watch_running = True

        p = Path(path)
        if p.exists():
            self._last_mtime = p.stat().st_mtime
            self.load_yaml(path)

        self._file_watcher = threading.Thread(
            target=self._file_watch_loop,
            args=(path, interval),
            name="neuros-param-watcher",
            daemon=True,
        )
        self._file_watcher.start()
        logger.info("[PARAMS] Hot-reload enabled for %s (interval=%.1fs)", path, interval)

    def disable_hot_reload(self) -> None:
        """Stop watching for file changes."""
        self._watch_running = False
        if self._file_watcher:
            self._file_watcher.join(timeout=2.0)
        self._file_watcher = None
        logger.info("[PARAMS] Hot-reload disabled")

    def _file_watch_loop(self, path: str, interval: float) -> None:
        while self._watch_running:
            try:
                p = Path(path)
                if p.exists():
                    mtime = p.stat().st_mtime
                    if mtime > self._last_mtime:
                        self._last_mtime = mtime
                        changed = self.load_yaml(path)
                        if changed > 0:
                            logger.info("[PARAMS] Hot-reload: %d params updated from %s",
                                        changed, path)
            except Exception as e:
                logger.error("[PARAMS] File watcher error: %s", e)
            time.sleep(interval)

    # ── Info ──────────────────────────────────────────────────────────────

    def list_groups(self) -> List[str]:
        """List all registered group names."""
        return list(self._groups.keys())

    def list_params(self, group: Optional[str] = None) -> List[str]:
        """List all parameter keys, optionally filtered by group."""
        result = []
        for gname, g in self._groups.items():
            if group and gname != group:
                continue
            for key in g.to_dict():
                result.append(f"{gname}.{key}")
        return result

    def summary(self) -> dict:
        """Return a summary of the parameter manager state."""
        return {
            "groups": len(self._groups),
            "total_params": sum(len(g.to_dict()) for g in self._groups.values()),
            "watchers": len(self._watchers),
            "hot_reload": self._watch_running,
            "hot_reload_file": self._watch_file,
            "values": self.to_dict(),
        }

    def __repr__(self):
        return (f"ParameterManager(groups={len(self._groups)}, "
                f"params={sum(len(g.to_dict()) for g in self._groups.values())})")


def _yaml_value(v: Any) -> str:
    """Format a value for YAML output."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        if any(c in v for c in ':#{}[],"\''):
            return f'"{v}"'
        return v
    if v is None:
        return "null"
    return str(v)


__all__ = [
    "ParameterManager",
    "ParamGroup",
]
