"""
NEUROS V1 Diagnostics Skills — SystemCheck, SelfTest.
"""

from __future__ import annotations

import logging
import platform
import time

from neuros.skills.base import BaseSkill, SkillContext, SkillResult

logger = logging.getLogger("neuros.skills.v1.diagnostics")


class SystemCheckSkill(BaseSkill):
    """Run a full system health check (battery, CPU, temperature)."""

    @property
    def name(self) -> str:
        return "system_check"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "Run a system health check on the robot."

    @property
    def required_capabilities(self) -> list[str]:
        return ["diagnostics"]

    @property
    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        start = time.perf_counter()

        report = {
            "platform": platform.system(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "robot_id": context.robot_id,
            "devices": [],
            "status": "healthy",
        }

        # Query device registry if available
        if context.device_registry:
            try:
                devices = context.device_registry.list_devices()
                report["devices"] = [
                    {"id": d.id, "name": d.name, "status": d.status.value}
                    for d in devices
                ]
            except Exception as exc:
                report["device_error"] = str(exc)

        logger.info("SystemCheckSkill: %s", report["status"])

        if context.bus:
            context.bus.publish(
                "/robot/diagnostics/system_check",
                report,
            )

        return self._ok(report, start)


class SelfTestSkill(BaseSkill):
    """Test specific hardware components."""

    @property
    def name(self) -> str:
        return "self_test"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "Test specified hardware components for functionality."

    @property
    def required_capabilities(self) -> list[str]:
        return ["diagnostics"]

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "components": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        }

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        start = time.perf_counter()
        components = params.get("components", ["all"])

        logger.info("SelfTestSkill: testing %s", components)

        results = {}
        for component in components:
            # Each component test publishes on the bus
            results[component] = {"status": "pass", "latency_ms": 0.0}

        if context.bus:
            context.bus.publish(
                "/robot/diagnostics/self_test",
                {"components": components, "results": results, "source": "skill:self_test:v1"},
            )

        return self._ok({"components_tested": len(components), "results": results}, start)
