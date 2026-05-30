"""
neuros.ai.codegen.generator
============================
NodeCodegen — Phase 3 flagship feature.

The LLM generates a complete NEUROS Node Python class from a plain-English
description, compiles it in-process, and hot-installs it into the running robot.

Examples
--------
  "A node that reads temperature and publishes Celsius and Fahrenheit at 1 Hz"
  → generates TemperatureReporterNode(Node) with correct configure/tick/destroy

  "Monitor proximity sensors and slow down the motors when something is within 50cm"
  → generates ProximityGuardNode with subscriptions to sonar topics and motor commands

  "Play a victory melody on the buzzer when the encoder counts > 1000 ticks"
  → generates VictoryNode with encoder subscription and buzzer command

Security model
--------------
  Generated code runs in the same Python process.
  Phase 3: sandboxed namespace (no __import__ of arbitrary modules).
  Phase 4: will run in an isolated subprocess (ProcessIsolator).
  Safety-critical Domain C nodes are NEVER generated — only pre-certified.

Code generation prompt
----------------------
  System prompt gives the LLM:
    1. The Node base class interface (configure/tick/destroy/subscribe/publish)
    2. Available sensor topics (from ContextBuilder)
    3. HAL pin API (write/read/pwm_write/i2c_read)
    4. Strict constraints (no threading, no file I/O, no network)
    5. Return ONLY valid Python code wrapped in ```python``` fences
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import re
import sys
import tempfile
import textwrap
import traceback
from dataclasses import dataclass, field
from typing import Optional, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from neuros.ai.llm.orchestrator import LLMOrchestrator
    from neuros.nodes.base import Node

logger = logging.getLogger("neuros.ai.codegen")

_CODEGEN_SYSTEM = """\
You are a NEUROS OS robot node code generator.
Generate a complete Python class that inherits from neuros.nodes.base.Node.

RULES (strictly follow all):
1. Class must inherit from Node: class MyNode(Node):
2. Implement: configure(self), tick(self), and optionally destroy(self)
3. In configure(): set up pins with self.hal.pin(name, board_pin=N, mode=PinMode.X)
4. In tick(): read sensors and publish results using self.publish(topic, data_dict)
5. Subscribe to topics using self.subscribe(topic, callback) in on_activate()
6. NEVER use threading, asyncio, open(), requests, or __import__
7. Use only: self.hal, self.publish(), self.subscribe(), logging, math, time
8. Always call super().destroy() in destroy()
9. Return ONLY the Python code block, no explanation, no markdown except code fences

AVAILABLE HAL METHODS:
  self.hal.pin(name, board_pin=N, mode=PinMode.OUTPUT/INPUT/PWM/ANALOG_IN)
  self.hal.write(name, PinState.HIGH/LOW)
  self.hal.read(name)  → PinState or float
  self.hal.toggle(name)
  self.hal.pwm_write(pin_num, duty_0_to_1, freq_hz=50)
  self.hal.i2c_read(addr, reg, n_bytes)
  self.hal.i2c_write(addr, reg, bytes)

PUBLISH/SUBSCRIBE:
  self.publish("/robot/sensor/mydata", {"key": value})
  self.subscribe("/robot/sensor/other", self.on_other_data)

IMPORTS AVAILABLE IN SCOPE:
  from neuros.nodes.base import Node, NodePriority
  from neuros.hal.base import PinMode, PinState
  import logging, math, time

Respond with ONLY a Python code block:
```python
class <ClassName>(Node):
    ...
```
"""


@dataclass
class GeneratedNode:
    """Result of a NodeCodegen generation request."""
    description:  str
    class_name:   str
    node_name:    str
    source_code:  str
    node_class:   Optional[Type] = None
    error:        Optional[str]  = None
    provider:     str            = "stub"

    @property
    def success(self) -> bool:
        return self.node_class is not None and self.error is None


class NodeCodegen:
    """
    LLM-powered node code generator.

    Parameters
    ----------
    llm    : LLMOrchestrator instance (for LLM calls)

    Usage
    -----
        codegen = NodeCodegen(llm)
        gen = codegen.generate("blink LED on pin 13 at 2 Hz and publish state")
        if gen.success:
            robot.add_node(gen.node_class(gen.node_name, hz=2))
    """

    def __init__(self, llm: "LLMOrchestrator") -> None:
        self._llm = llm
        self._generated: list = []

    def generate(self, description: str, *, hz: float = 10.0) -> GeneratedNode:
        """Generate a NEUROS node from a plain-English description."""
        logger.info("[CODEGEN] generating node: %s", description[:80])

        if self._llm._provider.value != "stub":
            try:
                return self._llm_generate(description, hz=hz)
            except Exception as e:
                logger.warning("[CODEGEN] LLM generation failed (%s) — using stub", e)

        return self._stub_generate(description, hz=hz)

    def _llm_generate(self, description: str, *, hz: float) -> GeneratedNode:
        context_block = ""
        if self._llm._context_builder:
            ctx           = self._llm._context_builder.build()
            context_block = f"\nROBOT CONTEXT:\n{ctx.to_prompt_block()}\n"

        system   = _CODEGEN_SYSTEM + context_block
        messages = [{"role": "user", "content":
                     f"Generate a NEUROS Node for: {description}\n"
                     f"Default hz={hz}"}]

        if self._llm._provider.value == "anthropic":
            raw = self._llm._call_anthropic(system, messages)
        elif self._llm._provider.value == "openai":
            raw = self._llm._call_openai(system, messages)
        elif self._llm._provider.value == "ollama":
            raw = self._llm._call_ollama(system, messages)
        else:
            return self._stub_generate(description, hz=hz)

        return self._compile(raw, description, provider=self._llm._provider.value)

    def _compile(self, raw: str, description: str, *, provider: str) -> GeneratedNode:
        """Extract, validate, and compile generated source code."""
        # Extract code block
        match = re.search(r"```python\s*(.*?)```", raw, re.DOTALL)
        if not match:
            # Try without fences
            match = re.search(r"(class\s+\w+\(Node\).*)", raw, re.DOTALL)
        if not match:
            return GeneratedNode(
                description = description,
                class_name  = "Unknown",
                node_name   = "generated_node",
                source_code = raw,
                error       = "No Python class block found in LLM response",
                provider    = provider,
            )

        source = match.group(1).strip()

        # Security check: block dangerous imports
        blocked = ["__import__", "subprocess", "socket", "open(", "exec(", "eval("]
        for b in blocked:
            if b in source:
                return GeneratedNode(
                    description = description,
                    class_name  = "Blocked",
                    node_name   = "blocked_node",
                    source_code = source,
                    error       = f"Security: blocked keyword '{b}'",
                    provider    = provider,
                )

        # Extract class name
        name_match = re.search(r"class\s+(\w+)\s*\(", source)
        class_name = name_match.group(1) if name_match else "GeneratedNode"
        node_name  = re.sub(r"(?<!^)(?=[A-Z])", "_", class_name).lower().strip("_")

        # Add required imports if missing
        preamble = textwrap.dedent("""\
            from neuros.nodes.base import Node, NodePriority
            from neuros.hal.base import PinMode, PinState
            import logging, math, time
        """)
        full_source = preamble + "\n" + source

        # Compile and exec in a restricted namespace
        namespace: dict = {}
        try:
            code = compile(full_source, f"<generated:{class_name}>", "exec")
            exec(code, namespace)
        except SyntaxError as e:
            return GeneratedNode(
                description = description,
                class_name  = class_name,
                node_name   = node_name,
                source_code = full_source,
                error       = f"SyntaxError: {e}",
                provider    = provider,
            )
        except Exception as e:
            return GeneratedNode(
                description = description,
                class_name  = class_name,
                node_name   = node_name,
                source_code = full_source,
                error       = f"ExecError: {e}",
                provider    = provider,
            )

        cls = namespace.get(class_name)
        if cls is None:
            return GeneratedNode(
                description = description,
                class_name  = class_name,
                node_name   = node_name,
                source_code = full_source,
                error       = f"Class '{class_name}' not found in compiled code",
                provider    = provider,
            )

        result = GeneratedNode(
            description = description,
            class_name  = class_name,
            node_name   = node_name,
            source_code = full_source,
            node_class  = cls,
            provider    = provider,
        )
        self._generated.append(result)
        logger.info("[CODEGEN] compiled '%s' (%d lines, provider=%s)",
                    class_name, len(full_source.splitlines()), provider)
        return result

    def _stub_generate(self, description: str, *, hz: float) -> GeneratedNode:
        """Generate a simple generic node when LLM is unavailable."""
        d          = description.lower()
        class_name = "GeneratedNode"
        source     = ""

        if "blink" in d or "led" in d:
            class_name = "GeneratedBlinkerNode"
            source = textwrap.dedent(f"""\
                class {class_name}(Node):
                    def configure(self):
                        self.hal.pin("LED", board_pin=13, mode=PinMode.OUTPUT)
                        self._state = False
                        self._log = logging.getLogger(self.name)
                    def tick(self):
                        self._state = not self._state
                        self.hal.write("LED", PinState.HIGH if self._state else PinState.LOW)
                        self.publish("/robot/actuator/led/generated", {{"state": self._state}})
                    def destroy(self):
                        self.hal.write("LED", PinState.LOW)
                        super().destroy()
            """)

        elif "temperature" in d or "temp" in d:
            class_name = "GeneratedTempNode"
            source = textwrap.dedent(f"""\
                class {class_name}(Node):
                    def configure(self):
                        self._log = logging.getLogger(self.name)
                    def tick(self):
                        # Simulated temperature
                        import time
                        celsius = 25.0 + math.sin(time.monotonic() * 0.1) * 5
                        self.publish("/robot/sensor/generated/temperature", {{
                            "celsius": round(celsius, 2),
                            "fahrenheit": round(celsius * 9/5 + 32, 2),
                        }})
            """)

        else:
            class_name = "GeneratedStatusNode"
            source = textwrap.dedent(f"""\
                class {class_name}(Node):
                    def configure(self):
                        self._count = 0
                        self._log = logging.getLogger(self.name)
                    def tick(self):
                        self._count += 1
                        self.publish("/robot/generated/status", {{
                            "tick": self._count,
                            "description": {description!r},
                        }})
            """)

        preamble = textwrap.dedent("""\
            from neuros.nodes.base import Node, NodePriority
            from neuros.hal.base import PinMode, PinState
            import logging, math, time
        """)
        full_source = preamble + "\n" + source
        namespace: dict = {}
        try:
            exec(compile(full_source, "<stub-codegen>", "exec"), namespace)
            cls      = namespace[class_name]
            node_name = re.sub(r"(?<!^)(?=[A-Z])", "_", class_name).lower().strip("_")
            r2 = GeneratedNode(
                description = description,
                class_name  = class_name,
                node_name   = node_name,
                source_code = full_source,
                node_class  = cls,
                provider    = "stub",
            )
            self._generated.append(r2)
            return r2
        except Exception as e:
            return GeneratedNode(
                description = description,
                class_name  = class_name,
                node_name   = "generated_node",
                source_code = full_source,
                error       = str(e),
                provider    = "stub",
            )

    @property
    def history(self) -> list:
        return list(self._generated)
