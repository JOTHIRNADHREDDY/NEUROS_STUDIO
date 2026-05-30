"""
neuros.skills.base
==================
Core abstractions for the NEUROS V2 Skill Engine.

Skills are the **only** sanctioned way to interact with hardware.
The execution flow is:

    Agent → Planner → **Skill** → Execution Manager → Sandbox → Validator → HAL

Every concrete skill subclasses :class:`BaseSkill`, declares its
``required_capabilities`` (e.g. ``["motor", "encoder"]``), and
provides a JSON-schema for parameter validation.

Classes
-------
SkillStatus   – lifecycle enum (IDLE → VALIDATING → EXECUTING → …)
SkillContext   – runtime context injected into every execute() call
SkillResult    – immutable result payload returned by every skill
BaseSkill      – abstract base that all skills inherit from
"""

from __future__ import annotations

import abc
import enum
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import jsonschema  # vendored / pip dependency

logger = logging.getLogger("neuros.skills")


# ── Lifecycle enum ─────────────────────────────────────────────────────────
class SkillStatus(enum.Enum):
    """Tracks the current phase of a skill's lifecycle."""

    IDLE = "IDLE"
    """Skill is registered but not executing."""

    VALIDATING = "VALIDATING"
    """Parameters are being validated against the JSON schema."""

    EXECUTING = "EXECUTING"
    """The skill's ``execute()`` coroutine is running."""

    COMPLETED = "COMPLETED"
    """Execution finished successfully."""

    FAILED = "FAILED"
    """Execution failed (exception or validation error)."""

    CANCELLED = "CANCELLED"
    """Execution was cancelled (e.g. e-stop or planner abort)."""


# ── Runtime context ───────────────────────────────────────────────────────
@dataclass(frozen=True)
class SkillContext:
    """
    Immutable runtime context injected into every ``BaseSkill.execute()`` call.

    Attributes
    ----------
    robot_id
        Unique identifier of the robot executing this skill.
    device_registry
        Handle to the NEUROS device registry (read-only from the skill's
        perspective).
    capability_registry
        Handle to the NEUROS capability registry — used to verify that
        required capabilities are available at runtime.
    bus
        Reference to the :class:`~neuros.bus.NeuralBus` for publishing
        typed events.
    hal
        Reference to the :class:`~neuros.hal.HAL` for hardware proxy
        queries (the skill itself **never** writes PWM directly).
    config
        Free-form configuration dictionary propagated from the planner
        or execution manager.
    """

    robot_id: str
    device_registry: object
    capability_registry: object
    bus: object
    hal: object
    config: dict = field(default_factory=dict)


# ── Execution result ──────────────────────────────────────────────────────
@dataclass(frozen=True)
class SkillResult:
    """
    Immutable result payload returned by every skill execution.

    Attributes
    ----------
    success
        ``True`` when the skill completed without error.
    data
        Arbitrary result payload (sensor readings, computed path, etc.).
    error
        Human-readable error string, or ``None`` on success.
    duration_ms
        Wall-clock execution time in milliseconds.
    skill_name
        Name of the skill that produced this result.
    skill_version
        Version string of the skill (e.g. ``"v1"``).
    """

    success: bool
    data: dict
    error: str | None
    duration_ms: float
    skill_name: str
    skill_version: str

    def __repr__(self) -> str:
        status = "OK" if self.success else f"FAIL({self.error})"
        return (
            f"SkillResult({self.skill_name}@{self.skill_version} "
            f"{status} {self.duration_ms:.1f}ms)"
        )


# ── Abstract base skill ──────────────────────────────────────────────────
class BaseSkill(abc.ABC):
    """
    Abstract base class for every NEUROS skill.

    Subclasses **must** override:

    * :pyattr:`name`
    * :pyattr:`version`
    * :pyattr:`description`
    * :pyattr:`required_capabilities`
    * :pyattr:`parameters_schema`
    * :pymeth:`execute`

    The engine calls :pymeth:`validate_params` before ``execute()`` and
    wraps the result in a :class:`SkillResult` with timing information.
    """

    # ── Metadata (override in subclass) ────────────────────────────────────
    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique human-readable name, e.g. ``"move"``."""

    @property
    @abc.abstractmethod
    def version(self) -> str:
        """Semantic version tag, e.g. ``"v1"``."""

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """One-line description shown in ``list_skills()``."""

    @property
    @abc.abstractmethod
    def required_capabilities(self) -> list[str]:
        """Capabilities the robot must expose (e.g. ``["motor"]``)."""

    @property
    @abc.abstractmethod
    def parameters_schema(self) -> dict:
        """JSON Schema (draft-07) for the *params* dict."""

    # ── Core contract ──────────────────────────────────────────────────────
    @abc.abstractmethod
    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        """
        Execute the skill.

        Parameters
        ----------
        params
            Validated parameter dictionary.
        context
            Runtime context providing bus, HAL, registries, etc.

        Returns
        -------
        SkillResult
            Outcome of the execution including timing.
        """

    @abc.abstractmethod
    async def cancel(self) -> None:
        """
        Cancel the executing skill.
        Must clean up hardware state and return immediately.
        """

    # ── Validation ─────────────────────────────────────────────────────────
    def validate_params(self, params: dict) -> bool:
        """
        Validate *params* against :pyattr:`parameters_schema`.

        Returns ``True`` if valid.  Raises :class:`jsonschema.ValidationError`
        on the first schema violation so callers can surface a clear error
        message.
        """
        jsonschema.validate(instance=params, schema=self.parameters_schema)
        return True

    # ── Convenience helpers ────────────────────────────────────────────────
    @staticmethod
    def _elapsed_ms(start: float) -> float:
        """Return milliseconds elapsed since *start* (``time.perf_counter``)."""
        return (time.perf_counter() - start) * 1_000.0

    def _ok(
        self,
        data: dict,
        start: float,
    ) -> SkillResult:
        """Build a successful :class:`SkillResult`."""
        return SkillResult(
            success=True,
            data=data,
            error=None,
            duration_ms=self._elapsed_ms(start),
            skill_name=self.name,
            skill_version=self.version,
        )

    def _fail(
        self,
        error: str,
        start: float,
        data: dict | None = None,
    ) -> SkillResult:
        """Build a failed :class:`SkillResult`."""
        return SkillResult(
            success=False,
            data=data or {},
            error=error,
            duration_ms=self._elapsed_ms(start),
            skill_name=self.name,
            skill_version=self.version,
        )

    # ── Dunder helpers ─────────────────────────────────────────────────────
    def __str__(self) -> str:
        return f"{self.name}@{self.version}"

    def __repr__(self) -> str:
        caps = ", ".join(self.required_capabilities) or "none"
        return (
            f"<{self.__class__.__name__} "
            f"name={self.name!r} version={self.version!r} "
            f"caps=[{caps}]>"
        )
