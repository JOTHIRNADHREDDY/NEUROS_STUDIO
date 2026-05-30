"""
neuros.bridge.dds
==================
DDS / Zenoh Bridge — Phase 2, Domain B.

Extends the in-process NeuralBus with a network-transparent layer.
Nodes in different processes (or on different machines) can
communicate via Zenoh without changing any node code.

Architecture
------------
  Process A                      Process B
  ┌─────────────┐                ┌─────────────────┐
  │ NeuralBus   │◄──ZenohBridge──►│ NeuralBus       │
  │ (in-memory) │  (UDP/TCP)     │ (in-memory)     │
  └─────────────┘                └─────────────────┘

  All topics published in Process A automatically appear in Process B
  and vice versa. The DDS bridge is transparent — nodes don't know
  whether their subscribers are local or remote.

Zenoh topic mapping
-------------------
  NEUROS topic  /robot/sensor/imu
  Zenoh key     neuros/robot/sensor/imu

QoS mapping
-----------
  BEST_EFFORT       → Zenoh BestEffort reliability
  RELIABLE          → Zenoh Reliable reliability
  REAL_TIME         → Zenoh Reliable + low-latency congestion control
  SAFETY_CRITICAL   → Phase 4 (not implemented here)

Graceful degradation
--------------------
  If zenoh is not installed, DDS bridge is a NO-OP.
  All local pub/sub still works perfectly.

Install
-------
  pip install eclipse-zenoh
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from neuros.bus.bus import NeuralBus

logger = logging.getLogger("neuros.bridge.dds")

ZENOH_PREFIX = "neuros"


def _zenoh_available() -> bool:
    try:
        import zenoh   # noqa: F401
        return True
    except ImportError:
        return False


class ZenohBridge:
    """
    Zenoh-based DDS bridge for cross-process Neural Bus communication.

    Parameters
    ----------
    bus           : the local NeuralBus instance to bridge
    mode          : "peer" (LAN discovery) | "client" (connect to router)
    router_url    : Zenoh router URL for client mode (e.g. "tcp/192.168.1.10:7447")
    topics_bridge : list of topic patterns to bridge (default: ["#"] = all)
    node_id       : unique identifier for this bridge node

    Example
    -------
        dds = ZenohBridge(robot._bus, mode="peer")
        dds.start()

        # Now any topic published locally is also visible remotely,
        # and any remote publication appears on the local bus.
    """

    def __init__(
        self,
        bus,
        *,
        mode:          str       = "peer",
        router_url:    str       = "",
        topics_bridge: List[str] = None,
        node_id:       str       = "neuros-dds",
    ) -> None:
        self._bus          = bus
        self._mode         = mode
        self._router_url   = router_url
        self._topics       = topics_bridge or ["#"]
        self._node_id      = node_id
        self._available    = _zenoh_available()
        self._session      = None
        self._pubs: Dict[str, Any]   = {}   # topic → zenoh.Publisher
        self._subs: List[Any]        = []   # zenoh subscribers
        self._local_subs             = []   # neuros bus subscriptions
        self._running      = False
        self._lock         = threading.Lock()
        self._stats        = {"tx": 0, "rx": 0}

        if not self._available:
            logger.warning(
                "[DDS] zenoh not installed — bridge is NO-OP. "
                "Install: pip install eclipse-zenoh"
            )

    def start(self) -> None:
        if not self._available:
            return
        try:
            import zenoh
            conf = zenoh.Config()
            if self._mode == "client" and self._router_url:
                conf.insert_json5("connect/endpoints", f'["{self._router_url}"]')
            self._session = zenoh.open(conf)
            self._running = True

            # Subscribe to all bridged topic patterns on Zenoh
            for pattern in self._topics:
                zenoh_key = self._neuros_to_zenoh(pattern)
                sub = self._session.declare_subscriber(
                    zenoh_key, self._on_zenoh_message
                )
                self._subs.append(sub)

            # Mirror local Neural Bus → Zenoh
            for pattern in self._topics:
                local_sub = self._bus.subscribe(
                    pattern, self._on_local_message, node_id=self._node_id
                )
                self._local_subs.append(local_sub)

            logger.info("[DDS] Zenoh bridge started | mode=%s topics=%s",
                        self._mode, self._topics)
        except Exception as e:
            logger.error("[DDS] start failed: %s", e)

    def stop(self) -> None:
        self._running = False
        for sub in self._local_subs:
            try:
                self._bus.unsubscribe(sub)
            except Exception:
                pass
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
        logger.info("[DDS] stopped | tx=%d rx=%d",
                    self._stats["tx"], self._stats["rx"])

    def _on_local_message(self, msg) -> None:
        """Local Neural Bus message → publish to Zenoh."""
        if not self._running or not self._session:
            return
        try:
            zenoh_key = self._neuros_to_zenoh(msg.topic)
            payload   = json.dumps({
                "topic":  msg.topic,
                "data":   msg.data,
                "seq":    msg.seq,
                "src":    msg.source_id,
            }).encode()
            with self._lock:
                if zenoh_key not in self._pubs:
                    self._pubs[zenoh_key] = self._session.declare_publisher(zenoh_key)
            self._pubs[zenoh_key].put(payload)
            self._stats["tx"] += 1
        except Exception as e:
            logger.debug("[DDS] tx error: %s", e)

    def _on_zenoh_message(self, sample) -> None:
        """Remote Zenoh message → publish to local Neural Bus."""
        if not self._running:
            return
        try:
            payload = json.loads(bytes(sample.value.payload))
            topic   = payload.get("topic", self._zenoh_to_neuros(str(sample.key_expr)))
            data    = payload.get("data")
            # Don't re-publish messages we sent (loop prevention)
            if payload.get("src") == self._node_id:
                return
            from neuros.bus.message import Message, MessageType
            self._bus.publish(
                Message(topic=topic, data=data, msg_type=MessageType.DATA),
                source_id=f"zenoh:{sample.key_expr}",
            )
            self._stats["rx"] += 1
        except Exception as e:
            logger.debug("[DDS] rx error: %s", e)

    @staticmethod
    def _neuros_to_zenoh(topic: str) -> str:
        """Convert /robot/sensor/imu → neuros/robot/sensor/imu"""
        t = topic.lstrip("/").replace("#", "**").replace("+", "*")
        return f"{ZENOH_PREFIX}/{t}"

    @staticmethod
    def _zenoh_to_neuros(zenoh_key: str) -> str:
        """Convert neuros/robot/sensor/imu → /robot/sensor/imu"""
        k = zenoh_key
        if k.startswith(ZENOH_PREFIX + "/"):
            k = k[len(ZENOH_PREFIX):]
        return "/" + k.lstrip("/")

    def stats(self) -> dict:
        return {
            "available": self._available,
            "running":   self._running,
            "mode":      self._mode,
            **self._stats,
        }
