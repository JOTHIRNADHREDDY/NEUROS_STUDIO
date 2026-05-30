"""V1 Skills Package — Initial set of concrete skills for NEUROS."""

from neuros.skills.v1.mobility import MoveSkill, StopSkill, TurnSkill, ReverseSkill
from neuros.skills.v1.navigation import NavigateToSkill, ExploreSkill, FollowPathSkill
from neuros.skills.v1.vision import DetectObjectSkill, TrackObjectSkill, ScanAreaSkill
from neuros.skills.v1.manipulation import PickObjectSkill, PlaceObjectSkill, GripSkill, ReleaseSkill
from neuros.skills.v1.diagnostics import SystemCheckSkill, SelfTestSkill

__all__ = [
    "MoveSkill", "StopSkill", "TurnSkill", "ReverseSkill",
    "NavigateToSkill", "ExploreSkill", "FollowPathSkill",
    "DetectObjectSkill", "TrackObjectSkill", "ScanAreaSkill",
    "PickObjectSkill", "PlaceObjectSkill", "GripSkill", "ReleaseSkill",
    "SystemCheckSkill", "SelfTestSkill",
]
