"""
NEUROS V2 — Navigation Event Schema

Emitted by the navigation planner / controller as the robot moves
toward a goal pose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from neuros.schemas.events.base import BaseEvent, _default_event_id, _default_timestamp


class NavigationStatus(str, Enum):
    """High-level navigation state machine values."""

    NAVIGATING = "NAVIGATING"
    ARRIVED = "ARRIVED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


@dataclass
class NavigationEvent(BaseEvent):
    """Tracks progress toward a 2-D navigation goal.

    All coordinates are in metres; angles are in radians (−π … π).

    Attributes
    ----------
    goal_x / goal_y / goal_theta:
        Target pose.
    current_x / current_y / current_theta:
        Latest estimated pose.
    status:
        Navigation state.
    distance_remaining:
        Euclidean distance to the goal (m).
    """

    # -- BaseEvent overrides --
    event_id: str = field(default_factory=_default_event_id)
    timestamp: float = field(default_factory=_default_timestamp)
    event_type: str = field(default="NavigationEvent", init=True)
    source: str = "navigation_controller"

    # -- Goal pose --
    goal_x: float = 0.0
    goal_y: float = 0.0
    goal_theta: float = 0.0

    # -- Current pose --
    current_x: float = 0.0
    current_y: float = 0.0
    current_theta: float = 0.0

    # -- Status --
    status: NavigationStatus = NavigationStatus.NAVIGATING
    distance_remaining: float = 0.0
