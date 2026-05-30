"""
neuros.nodes.sensor.imu
========================
IMU node — 6-DOF Inertial Measurement Unit.

Supports
--------
  Phase 1 (Simulator): full simulated IMU with configurable motion profiles
  Phase 1 (Arduino):   I2C read from MPU6050 / MPU9250 / ICM-42688-P

Register map (MPU6050 default)
--------------------------------
  0x3B  ACCEL_XOUT_H    (6 bytes: AX, AY, AZ)
  0x43  GYRO_XOUT_H     (6 bytes: GX, GY, GZ)
  0x41  TEMP_OUT_H      (2 bytes: TEMP)
  0x68  device address

Published topics
----------------
  /robot/sensor/imu/accel      {"ax": m/s², "ay": m/s², "az": m/s²}
  /robot/sensor/imu/gyro       {"gx": rad/s, "gy": rad/s, "gz": rad/s}
  /robot/sensor/imu/full       combined payload + temperature + timestamp
  /robot/sensor/imu/orientation  {"roll": deg, "pitch": deg}  (complementary filter)

Phase 2: will add Madgwick / Mahony quaternion filter.
Phase 2: will add ROS2 sensor_msgs/Imu bridge.
"""

from __future__ import annotations

import logging
import math
import struct
import time
from typing import Tuple

from neuros.nodes.base import Node, NodePriority

logger = logging.getLogger("neuros.nodes.sensor.imu")

# MPU6050 register addresses
_MPU6050_ADDR      = 0x68
_REG_PWR_MGMT_1    = 0x6B
_REG_ACCEL_XOUT_H  = 0x3B
_REG_GYRO_XOUT_H   = 0x43
_REG_TEMP_OUT_H    = 0x41

# Sensitivity divisors (default full-scale ±2g, ±250°/s)
_ACCEL_SENS = 16384.0   # LSB/g
_GYRO_SENS  = 131.0     # LSB/(°/s)
_TEMP_SENS  = 340.0
_TEMP_OFFS  = 36.53


class IMUNode(Node):
    """
    IMU sensor node.

    Parameters
    ----------
    name          : node identifier
    i2c_address   : I2C device address (default 0x68 for MPU6050)
    hz            : polling rate (default 100 Hz — recommended minimum)
    publish_full  : also publish /imu/full combined payload
    complementary : run complementary filter for orientation estimate
    alpha         : complementary filter weight for gyro (0.96 default)

    Example
    -------
        imu = IMUNode("imu", hz=100)
        robot.add_node(imu)

        @robot.subscribe("/robot/sensor/imu/orientation")
        def on_orientation(msg):
            print(msg.data["roll"], msg.data["pitch"])
    """

    def __init__(
        self,
        name:          str           = "imu",
        *,
        i2c_address:   int           = _MPU6050_ADDR,
        hz:            float         = 100.0,
        publish_full:  bool          = True,
        complementary: bool          = True,
        alpha:         float         = 0.96,
        priority:      NodePriority  = NodePriority.HIGH,
    ) -> None:
        super().__init__(name, hz=hz, priority=priority)
        self._addr         = i2c_address
        self._publish_full = publish_full
        self._comp_filter  = complementary
        self._alpha        = alpha

        # Complementary filter state
        self._roll:  float = 0.0
        self._pitch: float = 0.0
        self._last_t: float = 0.0

        # Latest readings (accessible without bus)
        self.accel: dict = {"ax": 0.0, "ay": 0.0, "az": 9.81}
        self.gyro:  dict = {"gx": 0.0, "gy": 0.0, "gz": 0.0}
        self.temperature: float = 25.0

    def configure(self) -> None:
        # Wake the MPU6050 from sleep (register 0x6B ← 0x00)
        try:
            self.hal.i2c_write(self._addr, _REG_PWR_MGMT_1, bytes([0x00]))
            logger.info("[IMU] '%s' initialised at I2C 0x%02X hz=%.0f", self.name, self._addr, self.hz)
        except Exception as e:
            logger.warning("[IMU] I2C write failed (simulator mode?): %s", e)
        self._last_t = time.monotonic()

    def tick(self) -> None:
        now = time.monotonic()
        dt  = now - self._last_t
        self._last_t = now

        ax, ay, az, gx, gy, gz, temp = self._read_raw()

        self.accel       = {"ax": ax, "ay": ay, "az": az}
        self.gyro        = {"gx": gx, "gy": gy, "gz": gz}
        self.temperature = temp

        # Publish accel
        self.publish("/robot/sensor/imu/accel", self.accel)
        # Publish gyro
        self.publish("/robot/sensor/imu/gyro", self.gyro)

        # Complementary filter orientation estimate
        if self._comp_filter and dt > 0:
            roll_acc  = math.degrees(math.atan2(ay, az))
            pitch_acc = math.degrees(math.atan2(-ax, math.sqrt(ay**2 + az**2)))
            self._roll  = self._alpha * (self._roll  + gx * dt) + (1 - self._alpha) * roll_acc
            self._pitch = self._alpha * (self._pitch + gy * dt) + (1 - self._alpha) * pitch_acc
            self.publish("/robot/sensor/imu/orientation", {
                "roll":  round(self._roll,  3),
                "pitch": round(self._pitch, 3),
            })

        if self._publish_full:
            self.publish("/robot/sensor/imu/full", {
                **self.accel, **self.gyro,
                "temp": round(temp, 2),
                "roll": round(self._roll, 3),
                "pitch": round(self._pitch, 3),
                "dt_ms": round(dt * 1000, 2),
            })

    def _read_raw(self) -> Tuple[float, ...]:
        """Read 14 bytes from MPU6050 and decode. Falls back to simulated data."""
        try:
            raw = self.hal.i2c_read(self._addr, _REG_ACCEL_XOUT_H, 14)
            if len(raw) >= 14 and any(b != 0 for b in raw):
                ax_r, ay_r, az_r = struct.unpack(">hhh", raw[0:6])
                t_r              = struct.unpack(">h",   raw[6:8])[0]
                gx_r, gy_r, gz_r = struct.unpack(">hhh", raw[8:14])

                ax = ax_r / _ACCEL_SENS * 9.81
                ay = ay_r / _ACCEL_SENS * 9.81
                az = az_r / _ACCEL_SENS * 9.81
                gx = math.radians(gx_r / _GYRO_SENS)
                gy = math.radians(gy_r / _GYRO_SENS)
                gz = math.radians(gz_r / _GYRO_SENS)
                temp = t_r / _TEMP_SENS + _TEMP_OFFS
                return ax, ay, az, gx, gy, gz, temp
        except Exception:
            pass

        # Simulator fallback — inject named sensor values or use defaults
        try:
            ax = float(self.hal.read_sensor(f"{self.name}_ax"))
            ay = float(self.hal.read_sensor(f"{self.name}_ay"))
            az = float(self.hal.read_sensor(f"{self.name}_az"))
            gx = float(self.hal.read_sensor(f"{self.name}_gx"))
            gy = float(self.hal.read_sensor(f"{self.name}_gy"))
            gz = float(self.hal.read_sensor(f"{self.name}_gz"))
        except Exception:
            ax, ay, az = 0.0, 0.0, 9.81
            gx, gy, gz = 0.0, 0.0, 0.0

        return ax, ay, az, gx, gy, gz, 25.0
