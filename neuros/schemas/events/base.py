"""
NEUROS V2 — Base Event Schema

All domain events inherit from :class:`BaseEvent`, which provides:

* Automatic ``event_id`` (UUID4) and ``timestamp`` (UTC epoch) generation.
* ``event_type`` derived from the concrete class name (e.g. ``"MotorEvent"``).
* Round-trip ``to_dict()`` / ``from_dict()`` serialisation.
* Frozen-style immutability recommendation (enforced by convention, not
  ``frozen=True``, so ``from_dict`` can still populate fields).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from typing import Any, ClassVar, Self


def _default_event_id() -> str:
    """Generate a unique event identifier."""
    return str(uuid.uuid4())


def _default_timestamp() -> float:
    """Generate a UTC epoch timestamp."""
    return time.time()


@dataclass
class BaseEvent:
    """Immutable base for every NEUROS event.

    Sub-classes simply add their own typed fields; ``event_type`` is filled
    in automatically from the class name.

    Example
    -------
    >>> from neuros.schemas.events.motor import MotorEvent
    >>> evt = MotorEvent(motor_id="left", speed=0.5, direction="forward", pwm=120, current_draw=1.2)
    >>> d = evt.to_dict()
    >>> restored = MotorEvent.from_dict(d)
    >>> restored.motor_id
    'left'
    """

    event_id: str = field(default_factory=_default_event_id)
    timestamp: float = field(default_factory=_default_timestamp)
    event_type: str = field(default="", init=True)
    source: str = "neuros"

    # Registry for from_dict() polymorphic deserialisation
    _registry: ClassVar[dict[str, type[BaseEvent]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Auto-register every concrete subclass."""
        super().__init_subclass__(**kwargs)
        BaseEvent._registry[cls.__name__] = cls

    def __post_init__(self) -> None:
        if not self.event_type:
            self.event_type = type(self).__name__

    # -- Serialisation -------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain JSON-safe dictionary.

        Enum members are converted to their ``.value``.
        """
        raw = asdict(self)
        return _enum_to_value(raw)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Deserialise from a plain dictionary.

        If called on :class:`BaseEvent` directly, the concrete subclass is
        looked up via ``event_type``.  If called on a subclass, only that
        subclass's fields are used.
        """
        data = dict(data)  # shallow copy to avoid mutating the caller's dict

        # Polymorphic dispatch when called as BaseEvent.from_dict(...)
        if cls is BaseEvent:
            event_type = data.get("event_type", "")
            target_cls = BaseEvent._registry.get(event_type, BaseEvent)
            return target_cls.from_dict(data)  # type: ignore[return-value]

        # Build kwargs from the class's own fields
        valid_names = {f.name for f in fields(cls)}
        kwargs: dict[str, Any] = {}
        for name in valid_names:
            if name in data:
                fld = _field_by_name(cls, name)
                kwargs[name] = _coerce_field(fld.type, data[name]) if fld else data[name]

        return cls(**kwargs)

    # -- Dunder helpers ------------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<{self.event_type} id={self.event_id[:8]}… "
            f"source={self.source} t={self.timestamp:.3f}>"
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _field_by_name(cls: type, name: str) -> Any:
    """Return the dataclass Field for *name*, or ``None``."""
    for fld in fields(cls):
        if fld.name == name:
            return fld
    return None


def _coerce_field(type_hint: Any, value: Any) -> Any:
    """Attempt to coerce *value* back into enum types where applicable."""
    if isinstance(type_hint, type) and issubclass(type_hint, Enum):
        try:
            return type_hint(value)
        except (ValueError, KeyError):
            return value
    return value


def _enum_to_value(obj: Any) -> Any:
    """Recursively replace Enum instances with their ``.value``."""
    if isinstance(obj, dict):
        return {k: _enum_to_value(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_enum_to_value(v) for v in obj]
    if isinstance(obj, Enum):
        return obj.value
    return obj
