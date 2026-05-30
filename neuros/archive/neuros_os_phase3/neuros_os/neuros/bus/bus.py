"""
neuros.bus.bus
==============
NeuralBus — the Neural Bus.

Architecture
------------
The NeuralBus is the single communication backbone for all NEUROS nodes.
Every message published by any node passes through the bus, is logged
for replay (Phase 5 data layer), and is dispatched to all subscribers.

Phase 1   : in-process, synchronous dispatch (threading.Lock protected)
Phase 2   : DDS-backed (FastDDS / Zenoh) for cross-process ROS2 bridge
Phase 4+  : SROS2 + TLS + role-based access for safety-critical domains

Subscription model
------------------
Subscribers register a callback with a topic pattern.
Patterns support exact match AND simple wildcards:
    "/robot/sensor/*"       — any sensor topic
    "/robot/+/imu"          — any category, imu name
    "#"                     — all topics (monitor / logger)

QoS enforcement (Phase 1: advisory only)
-----------------------------------------
BEST_EFFORT   → fire-and-forget, no retry
RELIABLE      → TODO Phase 2: retry queue
REAL_TIME     → TODO Phase 2: deadline enforcement
SAFETY_CRITICAL → TODO Phase 4: certified channel
"""

from __future__ import annotations

import threading
import time
import logging
import fnmatch
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set

from neuros.bus.message import Message, MessageType, QoS

logger = logging.getLogger("neuros.bus")


# ── Subscription record ────────────────────────────────────────────────────
@dataclass
class Subscription:
    pattern:      str                      # topic or glob pattern
    callback:     Callable[[Message], None]
    subscriber_id: str                     # node_id of subscriber
    qos:          QoS  = QoS.BEST_EFFORT
    received:     int  = 0


# ── NeuralBus ──────────────────────────────────────────────────────────────
class NeuralBus:
    """
    NEUROS Neural Bus — pub/sub backbone.

    Usage
    -----
        bus = NeuralBus()

        # Subscribe
        sub = bus.subscribe("/robot/sensor/imu", on_imu, node_id="nav-01")

        # Publish
        bus.publish(Message(topic="/robot/sensor/imu", data={"ax": 0.1, "ay": 0.0}))

        # Unsubscribe
        bus.unsubscribe(sub)

    Wildcard subscribe
    ------------------
        bus.subscribe("/robot/sensor/*", on_any_sensor, node_id="logger")
        bus.subscribe("#",               on_everything,  node_id="monitor")
    """

    def __init__(self) -> None:
        self._subs:    List[Subscription]       = []
        self._lock     = threading.Lock()
        self._seq:     Dict[str, int]           = defaultdict(int)   # topic → seq
        self._metrics: Dict[str, dict]          = defaultdict(
            lambda: {"published": 0, "dropped": 0, "last_ts": 0.0}
        )

    # ── Publish ────────────────────────────────────────────────────────────
    def publish(
        self,
        msg: Message,
        *,
        source_id: Optional[str] = None,
    ) -> int:
        """
        Publish a message to the bus.

        Returns the number of subscribers the message was dispatched to.
        """
        if source_id:
            msg.source_id = source_id

        # Assign sequence number
        with self._lock:
            self._seq[msg.topic] += 1
            msg.seq = self._seq[msg.topic]
            subscribers = [s for s in self._subs if self._matches(s.pattern, msg.topic)]
            self._metrics[msg.topic]["published"] += 1
            self._metrics[msg.topic]["last_ts"]    = msg.timestamp

        dispatched = 0
        for sub in subscribers:
            try:
                sub.callback(msg)
                sub.received += 1
                dispatched += 1
            except Exception as exc:
                logger.error(
                    "[BUS] subscriber '%s' raised on topic '%s': %s",
                    sub.subscriber_id, msg.topic, exc,
                )

        return dispatched

    # ── Subscribe / Unsubscribe ────────────────────────────────────────────
    def subscribe(
        self,
        pattern:       str,
        callback:      Callable[[Message], None],
        *,
        node_id:       str  = "unknown",
        qos:           QoS  = QoS.BEST_EFFORT,
    ) -> Subscription:
        sub = Subscription(
            pattern=pattern,
            callback=callback,
            subscriber_id=node_id,
            qos=qos,
        )
        with self._lock:
            self._subs.append(sub)
        logger.debug("[BUS] subscribed node='%s' pattern='%s'", node_id, pattern)
        return sub

    def unsubscribe(self, sub: Subscription) -> None:
        with self._lock:
            try:
                self._subs.remove(sub)
            except ValueError:
                pass

    # ── Pattern matching ───────────────────────────────────────────────────
    @staticmethod
    def _matches(pattern: str, topic: str) -> bool:
        if pattern == "#":
            return True
        # Convert MQTT-style + to fnmatch ?* patterns
        pat = pattern.replace("+", "*")
        return fnmatch.fnmatch(topic, pat)

    # ── Service call (request/response over bus) ───────────────────────────
    def call(
        self,
        request_topic:  str,
        data:           dict,
        *,
        timeout_s:      float = 1.0,
        caller_id:      str   = "caller",
    ) -> Optional[Message]:
        """
        Synchronous service call (Phase 1 stub — in-process).
        Phase 2 will implement action servers with async + retry.
        """
        response: List[Optional[Message]] = [None]
        event = threading.Event()
        response_topic = f"{request_topic}/response/{caller_id}"

        def _on_response(msg: Message) -> None:
            response[0] = msg
            event.set()

        sub = self.subscribe(response_topic, _on_response, node_id=caller_id)
        try:
            self.publish(Message(
                topic=request_topic,
                data={**data, "_reply_to": response_topic},
                msg_type=MessageType.COMMAND,
            ), source_id=caller_id)
            event.wait(timeout=timeout_s)
        finally:
            self.unsubscribe(sub)

        if response[0] is None:
            logger.warning("[BUS] call to '%s' timed out after %.2fs", request_topic, timeout_s)
        return response[0]

    # ── Metrics / introspection ────────────────────────────────────────────
    def topic_list(self) -> List[str]:
        with self._lock:
            return sorted(self._metrics.keys())

    def metrics(self) -> dict:
        with self._lock:
            return dict(self._metrics)

    def subscriber_count(self, topic: str) -> int:
        with self._lock:
            return sum(1 for s in self._subs if self._matches(s.pattern, topic))

    def __repr__(self) -> str:
        with self._lock:
            n_subs = len(self._subs)
            n_topics = len(self._seq)
        return f"<NeuralBus topics={n_topics} subscribers={n_subs}>"
