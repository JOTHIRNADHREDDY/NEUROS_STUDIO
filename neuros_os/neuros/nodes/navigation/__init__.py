"""
neuros.nodes.navigation
========================
Navigation nodes — Phase 2, Domain B.

Nodes in this package
---------------------
  OdometryNode           dead-reckoning pose estimator (encoder + IMU fusion)
  ObstacleAvoidanceNode  reactive collision avoidance from LiDAR/sonar sectors
  WaypointNavigatorNode  goal-seeking controller with waypoint queue

All navigation nodes consume from the Neural Bus and produce
commands on /robot/cmd/velocity (standard differential-drive format):
  {"linear": m/s, "angular": rad/s}

This is the same format Nav2 / ROS2 uses, so the ROS2 bridge
forwards these transparently to /cmd_vel.
"""

from neuros.nodes.navigation.odometry          import OdometryNode
from neuros.nodes.navigation.obstacle_avoidance import ObstacleAvoidanceNode
from neuros.nodes.navigation.waypoint_nav       import WaypointNavigatorNode

__all__ = [
    "OdometryNode",
    "ObstacleAvoidanceNode",
    "WaypointNavigatorNode",
]
