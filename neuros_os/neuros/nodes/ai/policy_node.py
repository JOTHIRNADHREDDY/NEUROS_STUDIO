"""
neuros.nodes.ai.policy_node
============================
PolicyExecutorNode — deploys a trained RL policy as a NEUROS node.

Runs policy.predict(obs) at control frequency and publishes velocity commands.
Hot-swappable: call node.swap_policy(new_policy) at runtime.
"""
from __future__ import annotations
import logging
from neuros.nodes.base import Node, NodePriority
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from neuros.ai.rl.engine import RLPolicy

logger = logging.getLogger("neuros.nodes.ai.policy")


class PolicyExecutorNode(Node):
    """
    Executes a trained RL policy at the declared control frequency.

    Parameters
    ----------
    name    : node identifier
    policy  : RLPolicy instance
    hz      : control frequency (default 20 Hz)
    """

    def __init__(
        self,
        name:     str,
        *,
        policy:   "RLPolicy",
        hz:       float        = 20.0,
        priority: NodePriority = NodePriority.HIGH,
    ) -> None:
        super().__init__(name, hz=hz, priority=priority)
        self._policy = policy
        self._obs:    list = []

    def configure(self) -> None:
        logger.info("[POLICY] '%s' loaded policy='%s' algo=%s hz=%.0f",
                    self.name, self._policy.name, self._policy.algorithm, self.hz)

    def on_activate(self) -> None:
        # Build observation from same topics as RLEnvironment
        from neuros.ai.rl.engine import RLEnvironment
        self._obs_buffer: dict = {}
        for topic in RLEnvironment.OBS_TOPICS:
            self.subscribe(topic, self._on_obs)

    def _on_obs(self, msg) -> None:
        self._obs_buffer[msg.topic] = msg.data

    def tick(self) -> None:
        obs = self._build_obs()
        if not obs:
            return
        action, info = self._policy.predict(obs)
        if len(action) >= 2:
            self.publish("/robot/cmd/velocity", {
                "linear":  round(float(action[0]), 3),
                "angular": round(float(action[1]), 3),
            })
        self.publish("/robot/ai/policy/info", {
            "policy":     self._policy.name,
            "algorithm":  self._policy.algorithm,
            "infer_count": self._policy.infer_count,
            "avg_ms":     round(self._policy.avg_ms, 2),
        })

    def _build_obs(self) -> list:
        obs = []
        pose = self._obs_buffer.get("/robot/nav/odom/pose", {})
        obs += [float(pose.get(k, 0.0)) for k in ("x","y","theta","vx","omega")]
        imu  = self._obs_buffer.get("/robot/sensor/imu/full", {})
        obs += [float(imu.get(k, 0.0)) for k in ("ax","ay","az")]
        sects = self._obs_buffer.get("/robot/sensor/lidar/lidar/sectors",
                                      {}).get("sectors", {})
        obs += [float(sects.get(s, 12.0)) for s in ["N","NE","E","SE","S","SW","W","NW"]]
        batt = self._obs_buffer.get("/robot/sensor/battery", {})
        obs.append(float(batt.get("soc_pct", 100.0)))
        return obs

    def swap_policy(self, new_policy: "RLPolicy") -> None:
        """Hot-swap to a new policy without restarting the node."""
        old = self._policy.name
        self._policy = new_policy
        logger.info("[POLICY] hot-swapped '%s' → '%s'", old, new_policy.name)
