"""
neuros.parser.engine
====================
Plain English Rule Parser — regex-based rule engine.

This is the Phase 1 implementation of NEUROS natural language control.
It uses pattern matching and synonym resolution to convert plain English
commands into executable NEUROS Python code.

No external API calls, no LLM, runs 100% offline.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from neuros.api.robot import Robot

logger = logging.getLogger("neuros.parser")


# ── Action types ──────────────────────────────────────────────────────────
class ActionType(Enum):
    BLINK       = "blink"
    MOVE        = "move"
    TURN        = "turn"
    STOP        = "stop"
    SET_PIN     = "set_pin"
    READ_SENSOR = "read_sensor"
    SET_SERVO   = "set_servo"
    SET_SPEED   = "set_speed"
    CONDITION   = "condition"
    FOLLOW_LINE = "follow_line"
    AVOID       = "avoid_obstacles"
    SET_PWM     = "set_pwm"
    WAIT        = "wait"
    REPEAT      = "repeat"
    TOGGLE      = "toggle"


@dataclass
class ParsedAction:
    """A single parsed action from a natural language command."""
    action_type: ActionType
    target:      str = ""
    value:       Any = None
    unit:        str = ""
    interval_ms: float = 0.0
    condition:   Optional[str] = None
    params:      Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParseResult:
    """Result of parsing a plain English command."""
    original:    str                  # original command text
    actions:     List[ParsedAction]   # parsed actions
    code:        str = ""             # generated Python code
    confidence:  float = 0.0         # 0.0 to 1.0
    explanation: str = ""            # human-readable explanation


# ── Synonym tables ─────────────────────────────────────────────────────────
_SYNONYMS = {
    # Movement
    "go":       "move",
    "drive":    "move",
    "travel":   "move",
    "advance":  "move",
    "proceed":  "move",

    # Direction
    "forwards":  "forward",
    "ahead":     "forward",
    "backwards": "backward",
    "reverse":   "backward",
    "back":      "backward",

    # Stop
    "halt":     "stop",
    "freeze":   "stop",
    "brake":    "stop",
    "pause":    "stop",

    # Speed
    "slow":     "0.3",
    "half":     "0.5",
    "medium":   "0.5",
    "fast":     "0.8",
    "full":     "1.0",
    "max":      "1.0",
    "maximum":  "1.0",

    # LED
    "light":    "led",
    "lamp":     "led",
    "bulb":     "led",

    # Motor
    "motors":   "motor",
    "wheels":   "motor",
    "engine":   "motor",

    # Sensor
    "sensors":  "sensor",
    "detector": "sensor",

    # Time
    "sec":      "seconds",
    "secs":     "seconds",
    "second":   "seconds",
    "s":        "seconds",
    "ms":       "milliseconds",
    "millis":   "milliseconds",
    "millisecond": "milliseconds",

    # Conditions
    "below":    "less_than",
    "under":    "less_than",
    "above":    "greater_than",
    "over":     "greater_than",
    "exceeds":  "greater_than",
}


# ── Rule patterns ──────────────────────────────────────────────────────────
@dataclass
class Rule:
    """A pattern matching rule."""
    pattern:     str           # regex pattern
    action_type: ActionType
    extractor:   Callable      # function to extract params from match
    confidence:  float = 0.9
    description: str = ""


def _extract_blink(match: re.Match) -> ParsedAction:
    """Extract blink parameters."""
    target = match.group("target") if "target" in match.groupdict() else "LED"
    interval = match.group("interval") if "interval" in match.groupdict() else "1000"
    unit = match.group("unit") if "unit" in match.groupdict() else "milliseconds"

    interval_val = float(interval)
    if unit and ("sec" in unit.lower()):
        interval_val *= 1000  # convert to ms

    return ParsedAction(
        action_type=ActionType.BLINK,
        target=target.upper(),
        interval_ms=interval_val,
    )


def _extract_move(match: re.Match) -> ParsedAction:
    """Extract movement parameters."""
    direction = "forward"
    speed = 0.5

    groups = match.groupdict()
    if "direction" in groups and groups["direction"]:
        direction = groups["direction"].lower()
    if "speed" in groups and groups["speed"]:
        speed_str = _SYNONYMS.get(groups["speed"].lower(), groups["speed"])
        try:
            speed = float(speed_str)
        except ValueError:
            speed = 0.5

    return ParsedAction(
        action_type=ActionType.MOVE,
        value=speed,
        params={"direction": direction, "speed": speed},
    )


def _extract_turn(match: re.Match) -> ParsedAction:
    """Extract turn parameters."""
    groups = match.groupdict()
    direction = groups.get("direction", "left").lower()
    angle = float(groups.get("angle", "90"))

    return ParsedAction(
        action_type=ActionType.TURN,
        value=angle,
        unit="degrees",
        params={"direction": direction, "angle": angle},
    )


def _extract_stop(match: re.Match) -> ParsedAction:
    """Extract stop parameters."""
    groups = match.groupdict()
    target = groups.get("target", "all").lower()
    return ParsedAction(
        action_type=ActionType.STOP,
        target=target,
    )


def _extract_servo(match: re.Match) -> ParsedAction:
    """Extract servo parameters."""
    groups = match.groupdict()
    angle = float(groups.get("angle", "90"))
    target = groups.get("target", "servo")
    return ParsedAction(
        action_type=ActionType.SET_SERVO,
        target=target,
        value=angle,
        unit="degrees",
    )


def _extract_condition(match: re.Match) -> ParsedAction:
    """Extract conditional rule."""
    groups = match.groupdict()
    sensor = groups.get("sensor", "distance")
    operator = groups.get("operator", "less_than")
    threshold = groups.get("threshold", "20")
    unit = groups.get("unit", "cm")
    action = groups.get("action", "stop motors")

    op = _SYNONYMS.get(operator.lower().replace(" ", "_"), operator)

    return ParsedAction(
        action_type=ActionType.CONDITION,
        condition=f"{sensor} {op} {threshold}{unit}",
        params={
            "sensor": sensor,
            "operator": op,
            "threshold": float(threshold),
            "unit": unit,
            "then_action": action,
        },
    )


def _extract_read(match: re.Match) -> ParsedAction:
    """Extract sensor read."""
    groups = match.groupdict()
    sensor = groups.get("sensor", "sensor")
    return ParsedAction(
        action_type=ActionType.READ_SENSOR,
        target=sensor,
    )


def _extract_set_pwm(match: re.Match) -> ParsedAction:
    """Extract PWM/brightness setting."""
    groups = match.groupdict()
    target = groups.get("target", "LED")
    value = float(groups.get("value", "50")) / 100.0
    return ParsedAction(
        action_type=ActionType.SET_PWM,
        target=target.upper(),
        value=value,
    )


def _extract_toggle(match: re.Match) -> ParsedAction:
    """Extract toggle action."""
    groups = match.groupdict()
    target = groups.get("target", "LED")
    return ParsedAction(
        action_type=ActionType.TOGGLE,
        target=target.upper(),
    )


def _extract_wait(match: re.Match) -> ParsedAction:
    """Extract wait/delay."""
    groups = match.groupdict()
    duration = float(groups.get("duration", "1"))
    unit = groups.get("unit", "seconds")
    if "ms" in unit.lower() or "milli" in unit.lower():
        duration /= 1000.0
    return ParsedAction(
        action_type=ActionType.WAIT,
        value=duration,
        unit="seconds",
    )


# ── Rule definitions ──────────────────────────────────────────────────────
_RULES: List[Rule] = [
    # Blink patterns
    Rule(
        pattern=r"blink\s+(?:the\s+)?(?P<target>\w+)\s+every\s+(?P<interval>[\d.]+)\s*(?P<unit>ms|milliseconds?|seconds?|s|sec)",
        action_type=ActionType.BLINK,
        extractor=_extract_blink,
        confidence=0.95,
        description="Blink an output at a regular interval",
    ),
    Rule(
        pattern=r"blink\s+(?:the\s+)?(?P<target>\w+)",
        action_type=ActionType.BLINK,
        extractor=_extract_blink,
        confidence=0.8,
        description="Blink an output at default interval",
    ),

    # Movement patterns
    Rule(
        pattern=r"move\s+(?P<direction>forward|backward|left|right)(?:\s+at\s+(?P<speed>\w+)\s+speed)?",
        action_type=ActionType.MOVE,
        extractor=_extract_move,
        confidence=0.95,
        description="Move the robot in a direction",
    ),
    Rule(
        pattern=r"go\s+(?P<direction>forward|backward|left|right|ahead|back)(?:\s+at\s+(?P<speed>\w+)\s+speed)?",
        action_type=ActionType.MOVE,
        extractor=_extract_move,
        confidence=0.9,
        description="Move the robot (synonym: go)",
    ),

    # Turn patterns
    Rule(
        pattern=r"turn\s+(?P<direction>left|right)(?:\s+(?P<angle>[\d.]+)\s*(?:degrees?|deg|°))?",
        action_type=ActionType.TURN,
        extractor=_extract_turn,
        confidence=0.95,
        description="Turn/rotate the robot",
    ),
    Rule(
        pattern=r"rotate\s+(?P<direction>left|right|clockwise|counterclockwise)(?:\s+(?P<angle>[\d.]+)\s*(?:degrees?|deg|°))?",
        action_type=ActionType.TURN,
        extractor=_extract_turn,
        confidence=0.9,
        description="Rotate the robot",
    ),

    # Stop patterns
    Rule(
        pattern=r"stop(?:\s+(?:all\s+)?(?P<target>\w+))?",
        action_type=ActionType.STOP,
        extractor=_extract_stop,
        confidence=0.95,
        description="Stop motors/movement",
    ),

    # Servo patterns
    Rule(
        pattern=r"set\s+(?P<target>\w+)\s+(?:to\s+)?(?P<angle>[\d.]+)\s*(?:degrees?|deg|°)",
        action_type=ActionType.SET_SERVO,
        extractor=_extract_servo,
        confidence=0.9,
        description="Set servo angle",
    ),

    # Conditional patterns
    Rule(
        pattern=r"(?:if|when)\s+(?P<sensor>\w+)\s+(?:is\s+)?(?P<operator>less than|greater than|above|below|under|over|exceeds)\s+(?P<threshold>[\d.]+)\s*(?P<unit>\w*),?\s*(?P<action>.+)",
        action_type=ActionType.CONDITION,
        extractor=_extract_condition,
        confidence=0.9,
        description="Conditional rule: if sensor meets condition, do action",
    ),
    Rule(
        pattern=r"(?:when|if)\s+(?P<sensor>\w+)\s+(?:is\s+)?(?:pressed|triggered|activated),?\s*(?P<action>.+)",
        action_type=ActionType.CONDITION,
        extractor=lambda m: ParsedAction(
            action_type=ActionType.CONDITION,
            condition=f"{m.group('sensor')} == pressed",
            params={
                "sensor": m.group("sensor"),
                "operator": "equals",
                "threshold": 1,
                "then_action": m.group("action"),
            },
        ),
        confidence=0.85,
        description="Event trigger: when something is pressed/triggered",
    ),

    # Read sensor
    Rule(
        pattern=r"read\s+(?:the\s+)?(?P<sensor>\w+)\s*(?:sensor)?",
        action_type=ActionType.READ_SENSOR,
        extractor=_extract_read,
        confidence=0.85,
        description="Read a sensor value",
    ),

    # PWM / brightness
    Rule(
        pattern=r"set\s+(?P<target>\w+)\s+brightness\s+(?:to\s+)?(?P<value>[\d.]+)\s*%?",
        action_type=ActionType.SET_PWM,
        extractor=_extract_set_pwm,
        confidence=0.9,
        description="Set LED brightness / PWM duty cycle",
    ),

    # Toggle
    Rule(
        pattern=r"toggle\s+(?:the\s+)?(?P<target>\w+)",
        action_type=ActionType.TOGGLE,
        extractor=_extract_toggle,
        confidence=0.9,
        description="Toggle an output on/off",
    ),

    # Wait/delay
    Rule(
        pattern=r"wait\s+(?:for\s+)?(?P<duration>[\d.]+)\s*(?P<unit>ms|milliseconds?|seconds?|s|sec)",
        action_type=ActionType.WAIT,
        extractor=_extract_wait,
        confidence=0.95,
        description="Wait/delay",
    ),

    # Follow line
    Rule(
        pattern=r"follow\s+(?:the\s+)?line",
        action_type=ActionType.FOLLOW_LINE,
        extractor=lambda m: ParsedAction(action_type=ActionType.FOLLOW_LINE),
        confidence=0.95,
        description="Follow a line on the ground",
    ),

    # Avoid obstacles
    Rule(
        pattern=r"avoid\s+(?:the\s+)?obstacles?",
        action_type=ActionType.AVOID,
        extractor=lambda m: ParsedAction(action_type=ActionType.AVOID),
        confidence=0.95,
        description="Enable obstacle avoidance",
    ),
]


# ── Code generation ────────────────────────────────────────────────────────
def _generate_code(actions: List[ParsedAction], robot_name: str = "robot") -> str:
    """Generate executable NEUROS Python code from parsed actions."""
    lines = [
        '"""Auto-generated by NEUROS Plain English Parser"""',
        "from neuros import Robot, spin",
        "",
        f'robot = Robot("{robot_name}")',
        "robot.start()",
        "",
    ]

    for action in actions:
        if action.action_type == ActionType.BLINK:
            interval_s = action.interval_ms / 1000.0
            hz = 1.0 / interval_s if interval_s > 0 else 2.0
            lines.append(f'robot.pin("{action.target}", pin=13, mode="output")')
            lines.append("")
            lines.append(f"@robot.every(hz={hz:.1f})")
            lines.append("def blink():")
            lines.append(f'    robot.toggle("{action.target}")')
            lines.append("")

        elif action.action_type == ActionType.MOVE:
            speed = action.params.get("speed", 0.5)
            direction = action.params.get("direction", "forward")
            if direction == "forward":
                lines.append(f"robot.publish('motor/cmd', {{'left': {speed}, 'right': {speed}}})")
            elif direction == "backward":
                lines.append(f"robot.publish('motor/cmd', {{'left': {-speed}, 'right': {-speed}}})")
            elif direction == "left":
                lines.append(f"robot.publish('motor/cmd', {{'left': {-speed}, 'right': {speed}}})")
            elif direction == "right":
                lines.append(f"robot.publish('motor/cmd', {{'left': {speed}, 'right': {-speed}}})")
            lines.append("")

        elif action.action_type == ActionType.TURN:
            direction = action.params.get("direction", "left")
            angle = action.params.get("angle", 90)
            lines.append(f"robot.publish('motor/turn', {{'direction': '{direction}', 'angle': {angle}}})")
            lines.append("")

        elif action.action_type == ActionType.STOP:
            lines.append("robot.publish('motor/cmd', {'left': 0, 'right': 0})")
            lines.append("")

        elif action.action_type == ActionType.SET_SERVO:
            lines.append(f'robot.pin("{action.target}", pin=9, mode="pwm")')
            duty = action.value / 180.0  # normalize angle to duty
            lines.append(f'robot.write("{action.target}", {duty:.3f})')
            lines.append("")

        elif action.action_type == ActionType.CONDITION:
            sensor = action.params.get("sensor", "distance")
            op = action.params.get("operator", "less_than")
            threshold = action.params.get("threshold", 20)
            then_action = action.params.get("then_action", "stop")

            py_op = "<" if "less" in op else ">"
            lines.append(f"@robot.every(hz=10)")
            lines.append(f"def check_{sensor}():")
            lines.append(f'    val = robot.read("{sensor}")')
            lines.append(f"    if val {py_op} {threshold}:")
            lines.append(f"        robot.publish('motor/cmd', {{'left': 0, 'right': 0}})  # {then_action}")
            lines.append("")

        elif action.action_type == ActionType.READ_SENSOR:
            lines.append(f'value = robot.read("{action.target}")')
            lines.append(f'print(f"{action.target}: {{value}}")')
            lines.append("")

        elif action.action_type == ActionType.SET_PWM:
            lines.append(f'robot.pin("{action.target}", pin=13, mode="pwm")')
            lines.append(f'robot.write("{action.target}", {action.value:.2f})')
            lines.append("")

        elif action.action_type == ActionType.TOGGLE:
            lines.append(f'robot.toggle("{action.target}")')
            lines.append("")

        elif action.action_type == ActionType.WAIT:
            lines.append(f"import time")
            lines.append(f"time.sleep({action.value})")
            lines.append("")

        elif action.action_type == ActionType.FOLLOW_LINE:
            lines.append("# Line following behavior")
            lines.append('robot.pin("LINE_L", pin=2, mode="analog_in")')
            lines.append('robot.pin("LINE_R", pin=3, mode="analog_in")')
            lines.append("")
            lines.append("@robot.every(hz=50)")
            lines.append("def follow_line():")
            lines.append('    left = robot.read("LINE_L")')
            lines.append('    right = robot.read("LINE_R")')
            lines.append("    error = left - right")
            lines.append("    robot.publish('motor/cmd', {'left': 0.5 - error, 'right': 0.5 + error})")
            lines.append("")

        elif action.action_type == ActionType.AVOID:
            lines.append("# Obstacle avoidance behavior")
            lines.append('robot.pin("SONAR", pin=4, mode="input")')
            lines.append("")
            lines.append("@robot.every(hz=10)")
            lines.append("def avoid_obstacles():")
            lines.append('    dist = robot.read("SONAR")')
            lines.append("    if dist < 0.2:  # 20cm threshold")
            lines.append("        robot.publish('motor/cmd', {'left': -0.3, 'right': 0.3})  # turn away")
            lines.append("    else:")
            lines.append("        robot.publish('motor/cmd', {'left': 0.5, 'right': 0.5})  # go forward")
            lines.append("")

    lines.append("spin(robot)")
    return "\n".join(lines)


# ── Main parser class ─────────────────────────────────────────────────────
class PlainEnglishParser:
    """
    NEUROS Plain English Parser.

    Converts human-readable robot commands into executable NEUROS code.

    Example
    -------
        parser = PlainEnglishParser()

        result = parser.parse("blink LED every 500ms")
        print(result.code)
        # → generates valid NEUROS Python code

        result = parser.parse("if distance is less than 20cm, stop motors")
        print(result.confidence)
        # → 0.9

        # Execute directly on a robot
        parser.execute("move forward at half speed", robot=my_robot)
    """

    def __init__(self, *, rules: Optional[List[Rule]] = None) -> None:
        self._rules = rules or list(_RULES)
        self._compiled = [(re.compile(r.pattern, re.IGNORECASE), r) for r in self._rules]

    def parse(self, command: str, *, robot_name: str = "robot") -> ParseResult:
        """
        Parse a plain English command.

        Returns a ParseResult with generated code and confidence score.
        """
        # Normalize
        normalized = self._normalize(command)
        logger.debug("[PARSER] normalized: %r → %r", command, normalized)

        # Try each rule
        best_match: Optional[Tuple[re.Match, Rule]] = None
        best_confidence = 0.0

        for compiled_pat, rule in self._compiled:
            match = compiled_pat.search(normalized)
            if match and rule.confidence > best_confidence:
                best_match = (match, rule)
                best_confidence = rule.confidence

        if best_match is None:
            logger.warning("[PARSER] no rule matched: %r", command)
            return ParseResult(
                original=command,
                actions=[],
                code=f"# Could not parse: {command}",
                confidence=0.0,
                explanation="No matching pattern found. Try simpler commands like 'blink LED every 500ms'.",
            )

        match, rule = best_match
        action = rule.extractor(match)
        code = _generate_code([action], robot_name)

        result = ParseResult(
            original=command,
            actions=[action],
            code=code,
            confidence=best_confidence,
            explanation=f"Matched: {rule.description} → {action.action_type.value}",
        )

        logger.info(
            "[PARSER] parsed %r → %s (confidence=%.2f)",
            command, action.action_type.value, best_confidence,
        )
        return result

    def parse_multi(self, commands: str, *, robot_name: str = "robot") -> ParseResult:
        """
        Parse multiple commands separated by newlines or periods.
        Generates a single unified script.
        """
        # Split on newlines, periods, or "and then"
        parts = re.split(r'[.\n]|(?:\s+and\s+then\s+)', commands.strip())
        parts = [p.strip() for p in parts if p.strip()]

        all_actions = []
        total_confidence = 0.0

        for part in parts:
            result = self.parse(part, robot_name=robot_name)
            all_actions.extend(result.actions)
            total_confidence += result.confidence

        avg_confidence = total_confidence / len(parts) if parts else 0.0
        code = _generate_code(all_actions, robot_name)

        return ParseResult(
            original=commands,
            actions=all_actions,
            code=code,
            confidence=avg_confidence,
            explanation=f"Parsed {len(parts)} commands into {len(all_actions)} actions",
        )

    def execute(self, command: str, *, robot: "Robot") -> ParseResult:
        """
        Parse and execute a command directly on a robot instance.
        """
        result = self.parse(command)

        for action in result.actions:
            try:
                self._execute_action(action, robot)
            except Exception as e:
                logger.error("[PARSER] execution error: %s", e)

        return result

    def _execute_action(self, action: ParsedAction, robot: "Robot") -> None:
        """Execute a single parsed action on a robot."""
        if action.action_type == ActionType.BLINK:
            hz = 1000.0 / action.interval_ms if action.interval_ms > 0 else 2.0

            @robot.every(hz=hz, name=f"blink_{action.target.lower()}")
            def _blink():
                robot.toggle(action.target)

        elif action.action_type == ActionType.MOVE:
            speed = action.params.get("speed", 0.5)
            direction = action.params.get("direction", "forward")
            if direction in ("forward", "ahead"):
                robot.publish("motor/cmd", {"left": speed, "right": speed})
            elif direction in ("backward", "back", "reverse"):
                robot.publish("motor/cmd", {"left": -speed, "right": -speed})
            elif direction == "left":
                robot.publish("motor/cmd", {"left": -speed, "right": speed})
            elif direction == "right":
                robot.publish("motor/cmd", {"left": speed, "right": -speed})

        elif action.action_type == ActionType.STOP:
            robot.publish("motor/cmd", {"left": 0, "right": 0})

        elif action.action_type == ActionType.TOGGLE:
            robot.toggle(action.target)

        elif action.action_type == ActionType.SET_PWM:
            robot.write(action.target, action.value)

        elif action.action_type == ActionType.READ_SENSOR:
            val = robot.read(action.target)
            logger.info("[PARSER] %s = %s", action.target, val)

    def _normalize(self, text: str) -> str:
        """Normalize text: lowercase, expand synonyms."""
        text = text.strip().lower()
        # Replace synonyms
        words = text.split()
        normalized_words = []
        for word in words:
            clean = word.strip(".,!?;:'\"")
            replacement = _SYNONYMS.get(clean, clean)
            normalized_words.append(replacement)
        return " ".join(normalized_words)

    def add_rule(self, rule: Rule) -> None:
        """Add a custom rule to the parser."""
        self._rules.append(rule)
        self._compiled.append((re.compile(rule.pattern, re.IGNORECASE), rule))

    def list_capabilities(self) -> List[str]:
        """Return a list of what the parser can understand."""
        return [f"• {r.description}" for r in self._rules]

    def __repr__(self) -> str:
        return f"<PlainEnglishParser rules={len(self._rules)}>"
