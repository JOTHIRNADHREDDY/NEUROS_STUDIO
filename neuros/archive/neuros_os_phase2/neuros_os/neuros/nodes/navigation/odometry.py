"""
neuros.nodes.navigation.odometry
=================================
Odometry Node — dead-reckoning pose estimation.

Fuses left/right wheel encoder ticks with IMU yaw rate to maintain
a (x, y, θ) pose estimate in the robot's local frame.

Sensor fusion strategy (Phase 2)
---------------------------------
  Primary:   dual-encoder differential-drive kinematics
  Secondary: IMU gyro yaw integration (complementary filter)
  alpha:     weight for encoder-based heading vs gyro heading (default 0.7)

Published topics
----------------
  /robot/nav/odom/pose      {"x": m, "y": m, "theta": rad,
                              "vx": m/s, "omega": rad/s,
                              "stamp": monotonic_ts}
  /robot/nav/odom/twist     {"linear_x": m/s, "angular_z": rad/s}

Subscribed topics
-----------------
  /robot/sensor/encoder/enc_left    left wheel encoder
  /robot/sensor/encoder/enc_right   right wheel encoder
  /robot/sensor/imu/gyro            IMU angular velocity (optional)

Coordinate frame
----------------
  x     : forward (metres)
  y     : left (metres)
  theta : yaw (radians, CCW positive, range −π to +π)
"""
from __future__ import annotations
import logging, math, time
from neuros.nodes.base import Node, NodePriority

logger = logging.getLogger("neuros.nodes.nav.odometry")


class OdometryNode(Node):
    """
    Differential-drive odometry with optional IMU fusion.

    Parameters
    ----------
    name             : node identifier
    wheel_base_m     : distance between left and right wheel centres
    enc_left_topic   : Neural Bus topic for left encoder
    enc_right_topic  : Neural Bus topic for right encoder
    imu_topic        : Neural Bus topic for IMU gyro (empty = disabled)
    imu_alpha        : complementary filter weight for encoder yaw (0=IMU only, 1=enc only)
    hz               : update rate (default 50 Hz)
    """

    def __init__(
        self,
        name:             str   = "odom",
        *,
        wheel_base_m:     float = 0.15,
        enc_left_topic:   str   = "/robot/sensor/encoder/enc_left",
        enc_right_topic:  str   = "/robot/sensor/encoder/enc_right",
        imu_topic:        str   = "/robot/sensor/imu/gyro",
        imu_alpha:        float = 0.7,
        hz:               float = 50.0,
        priority:         NodePriority = NodePriority.HIGH,
    ) -> None:
        super().__init__(name, hz=hz, priority=priority)
        self._wheel_base   = wheel_base_m
        self._enc_l_topic  = enc_left_topic
        self._enc_r_topic  = enc_right_topic
        self._imu_topic    = imu_topic
        self._alpha        = imu_alpha

        # Pose state
        self.x:     float = 0.0
        self.y:     float = 0.0
        self.theta: float = 0.0   # radians
        self.vx:    float = 0.0
        self.omega: float = 0.0

        # Encoder state
        self._v_left:   float = 0.0   # m/s from left encoder
        self._v_right:  float = 0.0   # m/s from right encoder
        self._gz:       float = 0.0   # rad/s from IMU gyro Z

        self._last_t: float = 0.0

    def configure(self) -> None:
        self._last_t = time.monotonic()
        logger.info("[ODOM] '%s' wheel_base=%.3fm imu=%s alpha=%.2f",
                    self.name, self._wheel_base,
                    bool(self._imu_topic), self._alpha)

    def on_activate(self) -> None:
        self.subscribe(self._enc_l_topic, self._on_enc_left)
        self.subscribe(self._enc_r_topic, self._on_enc_right)
        if self._imu_topic:
            self.subscribe(self._imu_topic, self._on_imu)

    def _on_enc_left(self, msg) -> None:
        self._v_left  = float(msg.data.get("velocity_ms", 0.0))

    def _on_enc_right(self, msg) -> None:
        self._v_right = float(msg.data.get("velocity_ms", 0.0))

    def _on_imu(self, msg) -> None:
        self._gz = float(msg.data.get("gz", 0.0))   # rad/s

    def tick(self) -> None:
        now = time.monotonic()
        dt  = now - self._last_t
        self._last_t = now
        if dt <= 0:
            return

        # Differential-drive kinematics
        v_enc   = (self._v_left + self._v_right) / 2.0
        w_enc   = (self._v_right - self._v_left) / self._wheel_base

        # IMU-fused heading rate
        if self._imu_topic:
            w_fused = self._alpha * w_enc + (1.0 - self._alpha) * self._gz
        else:
            w_fused = w_enc

        # Integrate pose (midpoint method)
        dtheta     = w_fused * dt
        mid_theta  = self.theta + dtheta / 2.0
        self.x    += v_enc * math.cos(mid_theta) * dt
        self.y    += v_enc * math.sin(mid_theta) * dt
        self.theta = _wrap_angle(self.theta + dtheta)
        self.vx    = v_enc
        self.omega = w_fused

        self.publish("/robot/nav/odom/pose", {
            "x":     round(self.x,     4),
            "y":     round(self.y,     4),
            "theta": round(self.theta, 5),
            "vx":    round(self.vx,    4),
            "omega": round(self.omega, 4),
            "stamp": round(now,        4),
        })
        self.publish("/robot/nav/odom/twist", {
            "linear_x":  round(self.vx,    4),
            "angular_z": round(self.omega, 4),
        })

    def reset_pose(self, x: float = 0.0, y: float = 0.0, theta: float = 0.0) -> None:
        """Reset pose estimate to given values (e.g. after GPS fix)."""
        self.x, self.y, self.theta = x, y, theta
        logger.info("[ODOM] pose reset to (%.2f, %.2f, %.3f°)", x, y, math.degrees(theta))


def _wrap_angle(a: float) -> float:
    """Wrap angle to [-π, +π]."""
    while a >  math.pi: a -= 2 * math.pi
    while a < -math.pi: a += 2 * math.pi
    return a
