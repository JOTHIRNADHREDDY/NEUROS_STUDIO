"""
neuros.ai.llm.orchestrator
===========================
LLM Orchestrator — Phase 3 (replaces Phase 1 rule-based stub).

Supports four backends
-----------------------
  LLMProvider.ANTHROPIC  Claude claude-sonnet-4-20250514 via Anthropic API
  LLMProvider.OPENAI     GPT-4o via OpenAI API
  LLMProvider.OLLAMA     Any local model via Ollama (http://localhost:11434)
  LLMProvider.STUB       Phase 1 rule-based (no API key, always available)

Auto-selection
--------------
  1. Check NEUROS_LLM_PROVIDER env var
  2. Try ANTHROPIC_API_KEY → Anthropic
  3. Try OPENAI_API_KEY    → OpenAI
  4. Try Ollama ping       → Ollama (default model: llama3.2)
  5. Fall back to STUB

Intent schema
-------------
  The LLM is instructed to return JSON conforming to:
  {
    "action":      str,          # e.g. "patrol", "go_to", "blink", "stop"
    "target":      str|null,     # "LED", "motor_left", coordinates, ...
    "params":      dict,         # action-specific parameters
    "nodes_needed": [str],       # nodes that must exist for this action
    "explanation": str           # LLM reasoning (for logging/debug)
  }

Conversation history
--------------------
  Each LLMOrchestrator instance maintains a conversation history so
  follow-up commands reference prior context:
    User: "patrol the room"
    Bot:  "Starting patrol mission with 4 waypoints."
    User: "faster"      ← LLM understands this refers to the patrol

System prompt
-------------
  The system prompt includes:
    1. NEUROS OS description (roles of nodes, bus, HAL)
    2. Available action vocabulary (auto-generated from registered nodes)
    3. Live robot context block (from ContextBuilder)
    4. Response format requirement (JSON)
"""

from __future__ import annotations

import enum
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from neuros.api.robot import Robot
    from neuros.ai.llm.context import RobotContext

logger = logging.getLogger("neuros.ai.llm")


# ── Intent dataclass ───────────────────────────────────────────────────────
@dataclass
class Intent:
    """Structured intent parsed from a natural language command."""
    action:       str
    target:       Optional[str]       = None
    params:       Dict[str, Any]      = field(default_factory=dict)
    nodes_needed: List[str]           = field(default_factory=list)
    explanation:  str                 = ""
    raw_text:     str                 = ""
    confidence:   float               = 1.0
    provider:     str                 = "stub"
    latency_ms:   float               = 0.0

    def is_valid(self) -> bool:
        return bool(self.action) and self.action != "unknown"

    def __repr__(self) -> str:
        return (f"Intent(action={self.action!r}, target={self.target!r}, "
                f"params={self.params}, conf={self.confidence:.2f})")


class LLMProvider(enum.Enum):
    ANTHROPIC = "anthropic"
    OPENAI    = "openai"
    OLLAMA    = "ollama"
    STUB      = "stub"


# ── System prompt template ─────────────────────────────────────────────────
_SYSTEM_PROMPT = """\
You are the AI brain of NEUROS OS, a universal robot operating system.

NEUROS runs on every robot — from a simple Arduino LED blinker to a surgical robot.
You translate natural language commands into structured robot actions.

YOUR ROLE:
- Parse user commands into specific robot actions
- Generate new node configurations when needed
- Plan multi-step missions
- Explain what you're doing

AVAILABLE ACTIONS (respond ONLY with these action names):
  blink          - blink an LED at a given Hz
  led_on/off     - turn LED on or off
  led_pattern    - set LED pattern (blink/pulse/sos/alarm)
  motor_speed    - set motor speed (-1.0 to 1.0)
  move_forward   - drive forward at given speed and duration
  move_backward  - drive backward
  turn_left/right - rotate left or right by angle_deg
  stop           - stop all motors immediately
  go_to          - navigate to x,y coordinates
  patrol         - patrol a list of waypoints in a loop
  follow_line    - activate line-following mode
  avoid_obstacles - activate obstacle avoidance
  servo_angle    - set servo to angle_deg
  buzzer_tone    - play a tone at frequency Hz
  buzzer_pattern - play a pattern (startup/beep/alarm/sos)
  read_sensor    - read a named sensor and report value
  camera_on/off  - start or stop camera capture
  detect_objects - run object detection on camera feed
  add_node       - generate and install a new custom node
  mission_plan   - plan a multi-step mission from description
  status         - report current robot status
  emergency_stop - trigger emergency stop immediately
  reset_estop    - reset emergency stop
  unknown        - could not parse the command

RESPONSE FORMAT - you MUST respond with ONLY valid JSON, no other text:
{
  "action": "<action_name>",
  "target": "<target_or_null>",
  "params": { "key": "value" },
  "nodes_needed": ["NodeClassName"],
  "explanation": "brief explanation of what you will do"
}

ROBOT CONTEXT:
{context}
"""

# ── Stub rules (Phase 1 fallback, always available) ──────────────────────
_STUB_RULES = [
    (r"blink.*?(\d+\.?\d*)\s*hz",  "blink",         lambda m: {"hz": float(m.group(1))}),
    (r"blink",                      "blink",         lambda m: {"hz": 1.0}),
    (r"turn on.*led|led.*on",       "led_on",        lambda m: {}),
    (r"turn off.*led|led.*off",     "led_off",       lambda m: {}),
    (r"move forward|go forward",    "move_forward",  lambda m: {"speed": 0.5, "duration_s": 2.0}),
    (r"move backward|go backward",  "move_backward", lambda m: {"speed": 0.5, "duration_s": 2.0}),
    (r"turn left",                  "turn_left",     lambda m: {"angle_deg": 90}),
    (r"turn right",                 "turn_right",    lambda m: {"angle_deg": 90}),
    (r"patrol",                     "patrol",        lambda m: {"loop": True}),
    (r"follow.*line|line.*follow",  "follow_line",   lambda m: {}),
    (r"avoid.*obstacle",            "avoid_obstacles",lambda m: {}),
    (r"emergency.*stop|e.stop",     "emergency_stop",lambda m: {}),
    (r"stop",                       "stop",          lambda m: {}),
    (r"status|report",              "status",        lambda m: {}),
    (r"detect|yolo|object",         "detect_objects",lambda m: {}),
    (r"camera.*on|start.*camera",   "camera_on",     lambda m: {}),
    (r"camera.*off|stop.*camera",   "camera_off",    lambda m: {}),
]


# ── Main orchestrator ──────────────────────────────────────────────────────
class LLMOrchestrator:
    """
    NEUROS LLM Orchestrator — Phase 3.

    Provides natural language → robot action conversion backed by a
    real LLM (Anthropic, OpenAI, Ollama) with fallback to stub rules.

    Parameters
    ----------
    provider    : LLMProvider enum or "auto" for auto-detection
    model       : model name (default per provider)
    api_key     : API key (or read from env)
    ollama_url  : Ollama server URL (default http://localhost:11434)
    robot       : attach to a Robot for context-aware prompts
    max_history : conversation history turns to keep (default 20)

    Usage
    -----
        llm = LLMOrchestrator(provider="auto", robot=robot)
        intent = await llm.parse_async("patrol the perimeter at 0.3 m/s")
        # or synchronous:
        intent = llm.parse("make the led blink twice per second")
        llm.execute_on(robot, "go to position 2, 1")
    """

    _DEFAULT_MODELS = {
        LLMProvider.ANTHROPIC: "claude-sonnet-4-20250514",
        LLMProvider.OPENAI:    "gpt-4o",
        LLMProvider.OLLAMA:    "llama3.2",
        LLMProvider.STUB:      "stub-v1",
    }

    def __init__(
        self,
        provider:    str | LLMProvider = "auto",
        *,
        model:       Optional[str]    = None,
        api_key:     Optional[str]    = None,
        ollama_url:  str              = "http://localhost:11434",
        robot:       Optional["Robot"] = None,
        max_history: int              = 20,
    ) -> None:
        self._provider   = self._resolve_provider(provider, api_key)
        self._model      = model or self._DEFAULT_MODELS[self._provider]
        self._api_key    = api_key or self._env_api_key()
        self._ollama_url = ollama_url
        self._robot      = robot
        self._max_hist   = max_history

        self._history: List[Dict[str, str]] = []
        self._context_builder = None
        if robot:
            from neuros.ai.llm.context import ContextBuilder
            self._context_builder = ContextBuilder(robot)

        # Stats
        self._call_count  = 0
        self._total_ms    = 0.0
        self._error_count = 0

        logger.info(
            "[LLM] Orchestrator ready | provider=%s model=%s",
            self._provider.value, self._model,
        )

    # ── Parse ──────────────────────────────────────────────────────────────
    def parse(self, text: str) -> Intent:
        """Synchronous parse. Calls LLM if available, else stub."""
        t0  = time.monotonic()
        self._call_count += 1

        if self._provider == LLMProvider.STUB:
            intent = self._stub_parse(text)
        else:
            try:
                intent = self._llm_parse(text)
            except Exception as e:
                logger.warning("[LLM] API call failed (%s) — falling back to stub", e)
                self._error_count += 1
                intent = self._stub_parse(text)

        intent.latency_ms = (time.monotonic() - t0) * 1000
        self._total_ms   += intent.latency_ms

        # Append to history
        self._history.append({"role": "user",      "content": text})
        self._history.append({"role": "assistant",  "content": intent.explanation})
        if len(self._history) > self._max_hist * 2:
            self._history = self._history[-self._max_hist * 2:]

        logger.info("[LLM] '%s' → %s (%.0fms, provider=%s)",
                    text[:60], intent.action, intent.latency_ms, intent.provider)
        return intent

    def execute_on(self, robot: "Robot", text: str) -> bool:
        """Parse text and execute the resulting intent on robot."""
        from neuros.ai.executor import IntentExecutor
        intent = self.parse(text)
        return IntentExecutor(robot, self).execute(intent)

    # ── LLM backends ───────────────────────────────────────────────────────
    def _llm_parse(self, text: str) -> Intent:
        context_block = ""
        if self._context_builder:
            ctx = self._context_builder.build()
            context_block = ctx.to_prompt_block()

        system = _SYSTEM_PROMPT.format(context=context_block or "No context available.")
        messages = list(self._history[-self._max_hist * 2:]) + [
            {"role": "user", "content": text}
        ]

        if self._provider == LLMProvider.ANTHROPIC:
            raw = self._call_anthropic(system, messages)
        elif self._provider == LLMProvider.OPENAI:
            raw = self._call_openai(system, messages)
        elif self._provider == LLMProvider.OLLAMA:
            raw = self._call_ollama(system, messages)
        else:
            return self._stub_parse(text)

        return self._parse_json_response(raw, text)

    def _call_anthropic(self, system: str, messages: list) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=self._api_key)
        resp = client.messages.create(
            model      = self._model,
            max_tokens = 512,
            system     = system,
            messages   = messages,
        )
        return resp.content[0].text

    def _call_openai(self, system: str, messages: list) -> str:
        import openai
        client = openai.OpenAI(api_key=self._api_key)
        all_msgs = [{"role": "system", "content": system}] + messages
        resp = client.chat.completions.create(
            model      = self._model,
            max_tokens = 512,
            messages   = all_msgs,
        )
        return resp.choices[0].message.content

    def _call_ollama(self, system: str, messages: list) -> str:
        import urllib.request
        payload = json.dumps({
            "model":    self._model,
            "messages": [{"role": "system", "content": system}] + messages,
            "stream":   False,
            "format":   "json",
        }).encode()
        req = urllib.request.Request(
            f"{self._ollama_url}/api/chat",
            data    = payload,
            headers = {"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        return data["message"]["content"]

    # ── JSON response parser ───────────────────────────────────────────────
    def _parse_json_response(self, raw: str, original_text: str) -> Intent:
        """Extract JSON from LLM response, tolerating markdown code fences."""
        # Strip ```json fences
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().strip("`").strip()
        # Find first { ... }
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            logger.warning("[LLM] no JSON in response: %r", raw[:200])
            return self._stub_parse(original_text)
        try:
            data = json.loads(match.group())
            return Intent(
                action       = data.get("action",      "unknown"),
                target       = data.get("target"),
                params       = data.get("params",      {}),
                nodes_needed = data.get("nodes_needed",[]),
                explanation  = data.get("explanation", ""),
                raw_text     = original_text,
                confidence   = 0.95,
                provider     = self._provider.value,
            )
        except json.JSONDecodeError as e:
            logger.warning("[LLM] JSON decode error: %s — raw: %r", e, raw[:200])
            return self._stub_parse(original_text)

    # ── Stub backend ────────────────────────────────────────────────────────
    def _stub_parse(self, text: str) -> Intent:
        t = text.lower().strip()
        for pattern, action, extractor in _STUB_RULES:
            m = re.search(pattern, t)
            if m:
                params = extractor(m)
                # Extract numeric values from text
                hz_m = re.search(r"(\d+\.?\d*)\s*hz", t)
                if hz_m:
                    params["hz"] = float(hz_m.group(1))
                speed_m = re.search(r"(\d+\.?\d*)\s*m/s", t)
                if speed_m:
                    params["speed"] = float(speed_m.group(1))
                return Intent(
                    action      = action,
                    params      = params,
                    raw_text    = text,
                    explanation = f"Rule-based: matched pattern '{pattern}'",
                    confidence  = 0.75,
                    provider    = "stub",
                )
        return Intent(
            action      = "unknown",
            raw_text    = text,
            explanation = "No matching rule found",
            confidence  = 0.0,
            provider    = "stub",
        )

    # ── Provider resolution ─────────────────────────────────────────────────
    @staticmethod
    def _resolve_provider(
        provider: str | LLMProvider,
        api_key: Optional[str],
    ) -> LLMProvider:
        if isinstance(provider, LLMProvider):
            return provider
        p = provider.lower()
        if p == "anthropic": return LLMProvider.ANTHROPIC
        if p == "openai":    return LLMProvider.OPENAI
        if p == "ollama":    return LLMProvider.OLLAMA
        if p == "stub":      return LLMProvider.STUB
        if p != "auto":
            logger.warning("[LLM] unknown provider '%s' — using auto", provider)

        # Auto-detect
        if api_key or os.getenv("ANTHROPIC_API_KEY"):
            try:
                import anthropic   # noqa: F401
                return LLMProvider.ANTHROPIC
            except ImportError:
                pass
        if os.getenv("OPENAI_API_KEY"):
            try:
                import openai   # noqa: F401
                return LLMProvider.OPENAI
            except ImportError:
                pass
        # Try Ollama ping
        try:
            import urllib.request
            urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1)
            return LLMProvider.OLLAMA
        except Exception:
            pass
        logger.info("[LLM] no LLM provider found — using stub (rule-based)")
        return LLMProvider.STUB

    def _env_api_key(self) -> Optional[str]:
        if self._provider == LLMProvider.ANTHROPIC:
            return os.getenv("ANTHROPIC_API_KEY")
        if self._provider == LLMProvider.OPENAI:
            return os.getenv("OPENAI_API_KEY")
        return None

    # ── Introspection ───────────────────────────────────────────────────────
    @property
    def history(self) -> List[dict]:
        return list(self._history)

    @property
    def avg_latency_ms(self) -> float:
        return self._total_ms / max(1, self._call_count)

    def stats(self) -> dict:
        return {
            "provider":      self._provider.value,
            "model":         self._model,
            "call_count":    self._call_count,
            "error_count":   self._error_count,
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "history_turns": len(self._history) // 2,
        }

    def clear_history(self) -> None:
        self._history.clear()
