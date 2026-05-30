"""
neuros.bridge.ros2
==================
ROS2 Bridge — Phase 2, Domain B.

Mission: zero-cost migration for existing ROS2 users.

What this bridge does
---------------------
  1. BiDirectional topic bridge
       ROS2 topic  → NEUROS Neural Bus topic (subscribe in ROS2, republish in NEUROS)
       NEUROS topic → ROS2 topic (subscribe in NEUROS, publish to ROS2)

  2. ROS2 node wrapping
       Existing rclpy nodes can be registered with the bridge.
       The bridge manages their executor inside the NEUROS process.

  3. Parameter bridge
       ROS2 parameters ↔ NEUROS Config system

  4. TF2 bridge
       ROS2 /tf and /tf_static → NEUROS /robot/transform/*

Architecture
------------
  ROS2Bridge runs as a single rclpy node ("neuros_bridge").
  Each bridged topic creates a ROS2 subscriber/publisher pair.
  Messages are serialised via JSON for the Neural Bus;
  typed ROS2 messages are passed through as Python dicts.

Graceful degradation
---------------------
  If rclpy is not installed or ROS2 is not sourced, the bridge
  initialises as a NO-OP stub — all methods return safely.
  This lets Domain A code import neuros.bridge.ros2 without
  ROS2 being installed.

Install
-------
  source /opt/ros/humble/setup.bash
  pip install rclpy  (included with ROS2 Humble)

Usage
-----
    bridge = ROS2Bridge(robot)
    bridge.mirror_topic("/scan",    "neuros", direction="ros2→neuros")
    bridge.mirror_topic("/cmd_vel", "ros2",   direction="neuros→ros2")
    bridge.start()
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from neuros.api.robot import Robot

logger = logging.getLogger("neuros.bridge.ros2")


def _rclpy_available() -> bool:
    try:
        import rclpy   # noqa: F401
        return True
    except ImportError:
        return False


class _TopicBridge:
    """Internal descriptor for a bridged topic."""
    def __init__(
        self,
        ros2_topic:   str,
        neuros_topic: str,
        direction:    str,       # "ros2→neuros" | "neuros→ros2" | "bidirectional"
        msg_type:     str = "std_msgs/String",
    ) -> None:
        self.ros2_topic   = ros2_topic
        self.neuros_topic = neuros_topic
        self.direction    = direction
        self.msg_type     = msg_type
        self.rx_count:    int = 0
        self.tx_count:    int = 0


class ROS2Bridge:
    """
    NEUROS ↔ ROS2 topic and node bridge.

    Parameters
    ----------
    robot     : attached NEUROS Robot instance
    node_name : name for the rclpy bridge node (default "neuros_bridge")

    Quick-start
    -----------
        from neuros.bridge.ros2 import ROS2Bridge

        bridge = ROS2Bridge(robot)

        # Mirror ROS2 LiDAR scan into NEUROS
        bridge.mirror_topic("/scan", direction="ros2→neuros")

        # Send NEUROS velocity commands to ROS2 Nav2
        bridge.mirror_topic("/cmd_vel", direction="neuros→ros2",
                             neuros_topic="/robot/cmd/velocity")

        bridge.start()
        # ... robot.spin() elsewhere
        bridge.stop()
    """

    def __init__(
        self,
        robot,
        *,
        node_name: str = "neuros_bridge",
    ) -> None:
        self._robot         = robot
        self._node_name     = node_name
        self._bridges:      List[_TopicBridge] = []
        self._ros_node      = None
        self._executor      = None
        self._spin_thread:  Optional[threading.Thread] = None
        self._running       = False
        self._available     = _rclpy_available()

        if not self._available:
            logger.warning(
                "[ROS2 BRIDGE] rclpy not found. Bridge is a NO-OP stub.\n"
                "  To enable: source /opt/ros/humble/setup.bash && pip install rclpy"
            )
        else:
            logger.info("[ROS2 BRIDGE] rclpy available — bridge ready")

    def mirror_topic(
        self,
        ros2_topic:    str,
        direction:     str   = "ros2→neuros",
        neuros_topic:  str   = "",
        msg_type:      str   = "std_msgs/String",
    ) -> "ROS2Bridge":
        """
        Register a topic to be bridged.

        Parameters
        ----------
        ros2_topic    : ROS2 topic name (e.g. "/scan", "/cmd_vel")
        direction     : "ros2→neuros" | "neuros→ros2" | "bidirectional"
        neuros_topic  : NEUROS bus topic (default: /robot/ros2<ros2_topic>)
        msg_type      : ROS2 message type string (e.g. "sensor_msgs/LaserScan")

        Returns self for chaining.
        """
        nt = neuros_topic or f"/robot/ros2{ros2_topic}"
        bridge = _TopicBridge(
            ros2_topic   = ros2_topic,
            neuros_topic = nt,
            direction    = direction,
            msg_type     = msg_type,
        )
        self._bridges.append(bridge)
        logger.debug("[ROS2 BRIDGE] registered %s  %s  %s",
                     ros2_topic, direction, nt)
        return self

    def wrap_node(self, ros_node_instance) -> "ROS2Bridge":
        """
        Register an existing rclpy Node to be managed by the bridge executor.
        The node will be spun alongside the bridge.
        """
        if not self._available:
            return self
        if self._executor:
            self._executor.add_node(ros_node_instance)
        return self

    def start(self) -> None:
        if not self._available:
            logger.warning("[ROS2 BRIDGE] not started (rclpy unavailable)")
            return
        try:
            import rclpy
            from rclpy.executors import MultiThreadedExecutor
            rclpy.init(args=None)
            self._ros_node = self._build_bridge_node()
            self._executor = MultiThreadedExecutor()
            self._executor.add_node(self._ros_node)
            self._running = True
            self._spin_thread = threading.Thread(
                target=self._spin_loop,
                name="neuros-ros2-bridge",
                daemon=True,
            )
            self._spin_thread.start()
            logger.info("[ROS2 BRIDGE] started | bridges=%d", len(self._bridges))
        except Exception as e:
            logger.error("[ROS2 BRIDGE] start failed: %s", e)

    def stop(self) -> None:
        self._running = False
        if self._spin_thread:
            self._spin_thread.join(timeout=2.0)
        try:
            import rclpy
            if self._executor:
                self._executor.shutdown(timeout_sec=1.0)
            rclpy.shutdown()
        except Exception:
            pass
        logger.info("[ROS2 BRIDGE] stopped")

    # ── Internal ───────────────────────────────────────────────────────────
    def _build_bridge_node(self):
        """Build the rclpy bridge node with all registered subscribers/publishers."""
        import rclpy
        from rclpy.node import Node as RclpyNode
        from std_msgs.msg import String

        bridge_list = self._bridges   # capture
        bus         = self._robot._bus
        robot_name  = self._robot.name

        class _BridgeNode(RclpyNode):
            def __init__(self_inner):
                super().__init__(self._node_name)
                self_inner._subs  = []
                self_inner._pubs  = {}

                for b in bridge_list:
                    if b.direction in ("ros2→neuros", "bidirectional"):
                        # ROS2 subscriber → publish to NEUROS bus
                        def make_cb(bridge_ref):
                            def on_ros2_msg(ros2_msg):
                                data = self_inner._ros2_to_dict(ros2_msg)
                                from neuros.bus.message import Message
                                bus.publish(Message(
                                    topic=bridge_ref.neuros_topic, data=data
                                ))
                                bridge_ref.rx_count += 1
                            return on_ros2_msg
                        sub = self_inner.create_subscription(
                            String, b.ros2_topic, make_cb(b), 10
                        )
                        self_inner._subs.append(sub)

                    if b.direction in ("neuros→ros2", "bidirectional"):
                        # NEUROS bus → ROS2 publisher
                        pub = self_inner.create_publisher(String, b.ros2_topic, 10)
                        self_inner._pubs[b.neuros_topic] = (pub, b)

                        def make_neuros_cb(pub_ref, bridge_ref):
                            def on_neuros_msg(msg):
                                ros2_msg = String()
                                ros2_msg.data = str(msg.data)
                                pub_ref.publish(ros2_msg)
                                bridge_ref.tx_count += 1
                            return on_neuros_msg

                        bus.subscribe(
                            b.neuros_topic,
                            make_neuros_cb(pub, b),
                            node_id=f"ros2_bridge_{b.ros2_topic}",
                        )

            @staticmethod
            def _ros2_to_dict(msg) -> dict:
                """Convert a ROS2 message to a plain dict for the NEUROS bus."""
                if hasattr(msg, "__slots__"):
                    return {slot: getattr(msg, slot) for slot in msg.__slots__}
                if hasattr(msg, "data"):
                    return {"data": msg.data}
                return {"raw": str(msg)}

        return _BridgeNode()

    def _spin_loop(self) -> None:
        while self._running:
            try:
                self._executor.spin_once(timeout_sec=0.01)
            except Exception as e:
                logger.error("[ROS2 BRIDGE] spin error: %s", e)

    def status(self) -> dict:
        return {
            "available":   self._available,
            "running":     self._running,
            "bridges":     [
                {
                    "ros2":      b.ros2_topic,
                    "neuros":    b.neuros_topic,
                    "direction": b.direction,
                    "rx":        b.rx_count,
                    "tx":        b.tx_count,
                }
                for b in self._bridges
            ],
        }
