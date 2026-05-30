"""
neuros.bus.message
==================
Core message types for the Neural Bus.

All data flowing through NEUROS is a `Message`. Topics are strongly-typed
strings with a namespace convention: `/<domain>/<category>/<name>`.

Examples
--------
  /robot/sensor/imu
  /robot/actuator/motor_left
  /robot/system/heartbeat
  /robot/ai/intent
"""

from __future__ import annotations

import time
import enum
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


class MessageType(enum.Enum):
    DATA        = "DATA"        # regular sensor / actuator payload
    COMMAND     = "COMMAND"     # action request
    EVENT       = "EVENT"       # one-shot notification
    HEARTBEAT   = "HEARTBEAT"   # kernel watchdog signal
    EMERGENCY   = "EMERGENCY"   # safety-critical stop
    TELEMETRY   = "TELEMETRY"   # diagnostic / logging


class QoS(enum.Enum):
    """Quality-of-Service profile for a topic."""
    BEST_EFFORT     = "best_effort"    # fire-and-forget (beginner / hobbyist)
    RELIABLE        = "reliable"       # retry until ack (advanced)
    REAL_TIME       = "real_time"      # deadline-aware (industrial)
    SAFETY_CRITICAL = "safety_critical" # certified path (medical / space, Phase 4)


@dataclass
class Topic:
    """
    A topic descriptor.

    Naming convention:  /<domain>/<category>/<name>
    Examples:
        Topic("/robot/sensor/imu",     qos=QoS.RELIABLE,   hz=100)
        Topic("/robot/actuator/motor", qos=QoS.REAL_TIME,  hz=1000)
        Topic("/robot/ai/intent",      qos=QoS.BEST_EFFORT, hz=10)
    """
    name:   str
    qos:    QoS   = QoS.BEST_EFFORT
    hz:     float = 0.0              # 0 = event-driven (no fixed rate)

    def __post_init__(self) -> None:
        if not self.name.startswith("/"):
            raise ValueError(f"Topic name must start with '/'. Got: {self.name!r}")

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Topic) and self.name == other.name

    def __repr__(self) -> str:
        return f"Topic({self.name!r}, qos={self.qos.value}, hz={self.hz})"


@dataclass
class Message:
    """
    A single message on the Neural Bus.

    Fields
    ------
    topic       : destination topic
    data        : arbitrary payload (dict, numpy array, bytes, etc.)
    msg_type    : classification for routing and priority
    source_id   : node_id of the sender (set by bus)
    timestamp   : monotonic clock at creation (seconds)
    seq         : per-topic sequence number (set by bus)
    msg_id      : globally unique message identifier
    """
    topic:      str
    data:       Any                  = None
    msg_type:   MessageType          = MessageType.DATA
    source_id:  Optional[str]        = None
    timestamp:  float                = field(default_factory=time.monotonic)
    seq:        int                  = 0
    msg_id:     str                  = field(default_factory=lambda: str(uuid.uuid4())[:12])

    def age_ms(self) -> float:
        """How old this message is, in milliseconds."""
        return (time.monotonic() - self.timestamp) * 1000.0

    def is_stale(self, max_age_ms: float) -> bool:
        return self.age_ms() > max_age_ms

    def __repr__(self) -> str:
        return (
            f"Message(topic={self.topic!r}, type={self.msg_type.value}, "
            f"age={self.age_ms():.1f}ms, seq={self.seq})"
        )
