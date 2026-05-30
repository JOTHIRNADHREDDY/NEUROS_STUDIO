"""
neuros.ai
=========
AI Core Layer — Phase 1 stub.

What exists now (Phase 1)
--------------------------
  • LLMOrchestrator stub — accepts natural language, returns structured intent
    (currently rule-based keyword matching, no LLM call)
  • IntentParser — maps phrases to Robot API calls
  • Hooks wired so Phase 3 can replace the stub with a real LLM call
    without changing any node or robot code.

Phase 3 will activate
---------------------
  • Real LLM call (OpenAI / local LLaMA / Gemini)
  • "Make it patrol the room" → mission graph generation
  • Auto node generation from English description
  • System self-diagnosis via conversation
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger("neuros.ai")


@dataclass
class Intent:
    """Parsed intent from a natural language command."""
    action:  str                   # e.g. "blink", "move_forward", "stop"
    params:  Dict[str, Any]        # e.g. {"pin": "LED", "hz": 1}
    raw:     str                   # original text
    confidence: float = 1.0


# ── Rule-based intent parser (Phase 1 — no LLM) ───────────────────────────
_RULES: List[tuple] = [
    # (regex, action, param_extractor)
    (r"blink.*led",      "blink",        lambda m: {"pin": "LED", "hz": 1}),
    (r"turn on.*led",    "write_high",   lambda m: {"pin": "LED"}),
    (r"turn off.*led",   "write_low",    lambda m: {"pin": "LED"}),
    (r"move forward",    "motor_forward",lambda m: {"speed": 0.5}),
    (r"move backward",   "motor_backward",lambda m: {"speed": 0.5}),
    (r"turn left",       "motor_left",   lambda m: {"angle": 90}),
    (r"turn right",      "motor_right",  lambda m: {"angle": 90}),
    (r"stop",            "stop_all",     lambda m: {}),
    (r"emergency stop",  "emergency",    lambda m: {}),
    (r"read.*sensor",    "sensor_read",  lambda m: {"sensor": "generic"}),
    (r"status",          "status",       lambda m: {}),
]


class LLMOrchestrator:
    """
    LLM Orchestrator — Phase 1 stub.

    In Phase 3, `parse()` will call a real LLM endpoint.
    The interface is already frozen so nodes and the Robot class
    don't need to change when the LLM is activated.

    Usage
    -----
        llm = LLMOrchestrator()
        intent = llm.parse("Make the LED blink at 2 Hz")
        print(intent.action, intent.params)
        # → "blink"  {"pin": "LED", "hz": 2}
    """

    def __init__(self, *, model: Optional[str] = None) -> None:
        self._model   = model  # ignored in Phase 1
        self._history: List[tuple] = []
        logger.info("[LLM] Phase-1 stub initialised (rule-based, no LLM call)")

    def parse(self, text: str) -> Optional[Intent]:
        """
        Parse a natural language command into a structured Intent.

        Phase 1: keyword rules.
        Phase 3: LLM JSON output.
        """
        text_lower = text.lower().strip()
        self._history.append(("user", text))

        for pattern, action, extractor in _RULES:
            m = re.search(pattern, text_lower)
            if m:
                params = extractor(m)
                # Extract numeric values from text (e.g. "at 2 Hz")
                hz_match = re.search(r"(\d+\.?\d*)\s*hz", text_lower)
                if hz_match:
                    params["hz"] = float(hz_match.group(1))
                intent = Intent(action=action, params=params, raw=text, confidence=0.85)
                logger.info("[LLM] parsed: '%s' → %s %s", text, action, params)
                self._history.append(("assistant", f"Intent: {action} {params}"))
                return intent

        logger.warning("[LLM] could not parse: '%s'", text)
        return Intent(action="unknown", params={}, raw=text, confidence=0.0)

    def execute_on(self, robot, text: str) -> bool:
        """
        Parse text and execute the resulting intent on `robot`.
        Returns True if executed successfully.

        Phase 1: executes a limited set of Robot API calls.
        Phase 3: generates and installs new nodes dynamically.
        """
        intent = self.parse(text)
        if intent is None or intent.confidence == 0.0:
            logger.warning("[LLM] cannot execute unknown intent for: %s", text)
            return False

        action  = intent.action
        params  = intent.params

        try:
            if action == "blink":
                pin = params.get("pin", "LED")
                hz  = float(params.get("hz", 1.0))
                robot.every(hz=hz)(lambda: robot.toggle(pin))
            elif action == "write_high":
                robot.write(params.get("pin", "LED"), 1)
            elif action == "write_low":
                robot.write(params.get("pin", "LED"), 0)
            elif action == "stop_all":
                robot.stop()
            elif action == "emergency":
                robot._kernel.emergency_stop("LLM command")
            elif action == "status":
                import json
                print(json.dumps(robot.status(), indent=2))
            else:
                logger.warning("[LLM] no executor for action='%s'", action)
                return False
            return True
        except Exception as exc:
            logger.error("[LLM] execute failed for '%s': %s", text, exc)
            return False

    @property
    def history(self) -> List[tuple]:
        return list(self._history)
