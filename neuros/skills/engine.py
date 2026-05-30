"""
neuros.skills.engine
====================
The Skill Engine — central registry and executor for all NEUROS skills.

Responsibilities
----------------
1. **Register / unregister** skill implementations keyed by ``(name, version)``.
2. **Look-up** skills by name, version, or required capability.
3. **Execute** a skill: validate parameters → call ``execute()`` → return
   a :class:`~neuros.skills.base.SkillResult`.

The Skill Engine is instantiated once per robot runtime.  The Planner
resolves a high-level intent into a sequence of ``execute_skill()`` calls;
the Execution Manager then drives those calls through the safety sandbox
and validator before reaching the HAL.

Thread safety
-------------
The internal registry is protected by a ``threading.Lock`` so skills can
be registered and looked up from different threads.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from neuros.skills.base import BaseSkill, SkillContext, SkillResult, SkillStatus

logger = logging.getLogger("neuros.skills.engine")


class SkillEngine:
    """
    Central skill registry and executor.

    Usage
    -----
    ::

        engine = SkillEngine()
        engine.register_skill(MoveSkill())
        engine.register_skill(StopSkill())

        result = await engine.execute_skill(
            name="move",
            params={"direction": "forward", "speed": 0.5, "duration_s": 2.0},
            context=ctx,
        )
    """

    def __init__(self) -> None:
        # (name, version) → BaseSkill
        self._skills: dict[tuple[str, str], BaseSkill] = {}
        self._lock = threading.Lock()
        self._status: dict[tuple[str, str], SkillStatus] = {}
        logger.info("[SkillEngine] initialised")

    # ── Registration ──────────────────────────────────────────────────────
    def register_skill(self, skill: BaseSkill) -> None:
        """
        Register a skill instance.

        Raises
        ------
        ValueError
            If a skill with the same ``(name, version)`` is already
            registered.
        """
        key = (skill.name, skill.version)
        with self._lock:
            if key in self._skills:
                raise ValueError(
                    f"Skill {skill.name!r} version {skill.version!r} "
                    f"is already registered."
                )
            self._skills[key] = skill
            self._status[key] = SkillStatus.IDLE
        logger.info(
            "[SkillEngine] registered %s@%s  caps=%s",
            skill.name,
            skill.version,
            skill.required_capabilities,
        )

    def unregister_skill(self, name: str, version: str) -> None:
        """
        Remove a previously registered skill.

        Raises
        ------
        KeyError
            If the skill is not found.
        """
        key = (name, version)
        with self._lock:
            if key not in self._skills:
                raise KeyError(
                    f"Skill {name!r} version {version!r} not found."
                )
            del self._skills[key]
            self._status.pop(key, None)
        logger.info("[SkillEngine] unregistered %s@%s", name, version)

    # ── Lookup ────────────────────────────────────────────────────────────
    def get_skill(self, name: str, version: str = "v1") -> BaseSkill:
        """
        Retrieve a registered skill by name and version.

        Raises
        ------
        KeyError
            If the skill is not found.
        """
        key = (name, version)
        with self._lock:
            skill = self._skills.get(key)
        if skill is None:
            raise KeyError(
                f"Skill {name!r} version {version!r} not registered."
            )
        return skill

    def list_skills(self) -> list[dict[str, Any]]:
        """
        Return metadata dicts for every registered skill.

        Each dict contains:
        ``name``, ``version``, ``description``, ``required_capabilities``,
        ``parameters_schema``, ``status``.
        """
        with self._lock:
            out: list[dict[str, Any]] = []
            for (name, ver), skill in self._skills.items():
                out.append(
                    {
                        "name": skill.name,
                        "version": skill.version,
                        "description": skill.description,
                        "required_capabilities": skill.required_capabilities,
                        "parameters_schema": skill.parameters_schema,
                        "status": self._status.get((name, ver), SkillStatus.IDLE).value,
                    }
                )
        return out

    def list_by_capability(self, capability: str) -> list[BaseSkill]:
        """Return all skills that declare *capability* as required."""
        with self._lock:
            return [
                s
                for s in self._skills.values()
                if capability in s.required_capabilities
            ]

    # ── Execution ─────────────────────────────────────────────────────────
    async def execute_skill(
        self,
        name: str,
        params: dict,
        context: SkillContext,
        version: str = "v1",
    ) -> SkillResult:
        """
        Validate parameters then execute the named skill.

        Parameters
        ----------
        name
            Registered skill name.
        params
            Keyword parameters — validated against the skill's JSON schema.
        context
            Runtime context (bus, HAL, registries …).
        version
            Skill version to use (default ``"v1"``).

        Returns
        -------
        SkillResult
            The outcome of the execution.
        """
        key = (name, version)
        skill = self.get_skill(name, version)

        # ── Validate ──────────────────────────────────────────────────────
        self._set_status(key, SkillStatus.VALIDATING)
        start = time.perf_counter()
        try:
            skill.validate_params(params)
        except Exception as exc:
            self._set_status(key, SkillStatus.FAILED)
            elapsed = (time.perf_counter() - start) * 1_000.0
            logger.warning(
                "[SkillEngine] %s@%s param validation failed: %s",
                name,
                version,
                exc,
            )
            return SkillResult(
                success=False,
                data={},
                error=f"Validation error: {exc}",
                duration_ms=elapsed,
                skill_name=name,
                skill_version=version,
            )

        # ── Execute ───────────────────────────────────────────────────────
        self._set_status(key, SkillStatus.EXECUTING)
        try:
            result = await skill.execute(params, context)
            self._set_status(key, SkillStatus.COMPLETED)
            logger.info(
                "[SkillEngine] %s@%s completed in %.1f ms",
                name,
                version,
                result.duration_ms,
            )
            return result
        except Exception as exc:
            self._set_status(key, SkillStatus.FAILED)
            elapsed = (time.perf_counter() - start) * 1_000.0
            logger.error(
                "[SkillEngine] %s@%s execution error: %s",
                name,
                version,
                exc,
                exc_info=True,
            )
            return SkillResult(
                success=False,
                data={},
                error=f"Execution error: {exc}",
                duration_ms=elapsed,
                skill_name=name,
                skill_version=version,
            )

    # ── Internal helpers ──────────────────────────────────────────────────
    def _set_status(self, key: tuple[str, str], status: SkillStatus) -> None:
        with self._lock:
            self._status[key] = status

    def get_status(self, name: str, version: str = "v1") -> SkillStatus:
        """Return the current lifecycle status of a skill."""
        key = (name, version)
        with self._lock:
            return self._status.get(key, SkillStatus.IDLE)

    # ── Dunder ────────────────────────────────────────────────────────────
    def __len__(self) -> int:
        with self._lock:
            return len(self._skills)

    def __contains__(self, key: tuple[str, str]) -> bool:
        with self._lock:
            return key in self._skills

    def __repr__(self) -> str:
        with self._lock:
            n = len(self._skills)
        return f"<SkillEngine skills={n}>"
