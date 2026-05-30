"""
NEUROS Skill Sandbox

Evaluates AI-generated parameters and dynamic code in a restricted environment
before it reaches the Validator. Prevents os.system(), file access, and other
dangerous operations.
"""

from __future__ import annotations

import ast
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("neuros.safety.sandbox")


class SandboxVerdict(Enum):
    SAFE = "safe"
    UNSAFE = "unsafe"
    ERROR = "error"


@dataclass
class SandboxResult:
    """Result of sandbox evaluation."""
    verdict: SandboxVerdict
    execution_time_ms: float = 0.0
    output: Any = None
    errors: list[str] = field(default_factory=list)
    blocked_operations: list[str] = field(default_factory=list)

    @property
    def is_safe(self) -> bool:
        return self.verdict == SandboxVerdict.SAFE


# Operations that are NEVER allowed in generated code
BLOCKED_MODULES = frozenset({
    "os", "sys", "subprocess", "shutil", "pathlib",
    "socket", "http", "urllib", "requests",
    "importlib", "ctypes", "signal", "multiprocessing",
    "pickle", "shelve", "tempfile", "glob",
    "webbrowser", "code", "codeop", "compile",
})

BLOCKED_BUILTINS = frozenset({
    "exec", "eval", "compile", "__import__",
    "open", "input", "breakpoint", "exit", "quit",
})

BLOCKED_ATTRIBUTES = frozenset({
    "__subclasses__", "__bases__", "__class__",
    "__globals__", "__code__", "__builtins__",
})


class _CodeAnalyzer(ast.NodeVisitor):
    """AST visitor that flags dangerous operations."""

    def __init__(self) -> None:
        self.violations: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root in BLOCKED_MODULES:
                self.violations.append(f"Blocked import: {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            root = node.module.split(".")[0]
            if root in BLOCKED_MODULES:
                self.violations.append(f"Blocked import from: {node.module}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            if node.func.id in BLOCKED_BUILTINS:
                self.violations.append(f"Blocked builtin call: {node.func.id}()")
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in BLOCKED_BUILTINS:
                self.violations.append(f"Blocked method call: .{node.func.attr}()")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in BLOCKED_ATTRIBUTES:
            self.violations.append(f"Blocked attribute access: .{node.attr}")
        self.generic_visit(node)


class SkillSandbox:
    """
    Sandbox for evaluating AI-generated skill parameters and code.

    Two modes:
    1. validate_code(code_str) — Static analysis of Python code via AST
    2. validate_params(params) — Checks parameter values against allowed types/ranges

    Usage:
        sandbox = SkillSandbox()
        result = sandbox.validate_code("import os; os.system('rm -rf /')")
        assert not result.is_safe  # blocked!
    """

    def __init__(self, max_param_depth: int = 5) -> None:
        self._max_param_depth = max_param_depth
        self._total_checks = 0
        self._blocked_count = 0
        logger.info("SkillSandbox initialized.")

    def validate_code(self, code: str) -> SandboxResult:
        """
        Statically analyze Python code for dangerous operations.
        Does NOT execute the code.
        """
        self._total_checks += 1
        start = time.time()

        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            elapsed = (time.time() - start) * 1000
            self._blocked_count += 1
            return SandboxResult(
                verdict=SandboxVerdict.ERROR,
                execution_time_ms=elapsed,
                errors=[f"Syntax error: {exc}"],
            )

        analyzer = _CodeAnalyzer()
        analyzer.visit(tree)

        elapsed = (time.time() - start) * 1000

        if analyzer.violations:
            self._blocked_count += 1
            logger.warning(
                "Sandbox BLOCKED code with %d violations: %s",
                len(analyzer.violations),
                analyzer.violations,
            )
            return SandboxResult(
                verdict=SandboxVerdict.UNSAFE,
                execution_time_ms=elapsed,
                errors=analyzer.violations,
                blocked_operations=analyzer.violations,
            )

        return SandboxResult(
            verdict=SandboxVerdict.SAFE,
            execution_time_ms=elapsed,
        )

    def validate_params(
        self, params: dict[str, Any], allowed_keys: set[str] | None = None
    ) -> SandboxResult:
        """
        Validate skill parameters for safety.
        Checks for:
        - Excessively nested structures
        - String values that look like code injection
        - Unexpected keys
        """
        self._total_checks += 1
        start = time.time()
        errors: list[str] = []

        # Check for unexpected keys
        if allowed_keys is not None:
            unexpected = set(params.keys()) - allowed_keys
            if unexpected:
                errors.append(f"Unexpected parameter keys: {unexpected}")

        # Check for injection in string values
        self._check_values(params, errors, depth=0)

        elapsed = (time.time() - start) * 1000

        if errors:
            self._blocked_count += 1
            logger.warning("Sandbox BLOCKED params: %s", errors)
            return SandboxResult(
                verdict=SandboxVerdict.UNSAFE,
                execution_time_ms=elapsed,
                errors=errors,
                blocked_operations=errors,
            )

        return SandboxResult(
            verdict=SandboxVerdict.SAFE,
            execution_time_ms=elapsed,
        )

    def _check_values(
        self, obj: Any, errors: list[str], depth: int
    ) -> None:
        """Recursively check parameter values for injection."""
        if depth > self._max_param_depth:
            errors.append(f"Parameter nesting too deep (max {self._max_param_depth})")
            return

        if isinstance(obj, dict):
            for k, v in obj.items():
                self._check_values(v, errors, depth + 1)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                self._check_values(item, errors, depth + 1)
        elif isinstance(obj, str):
            # Check for code injection patterns
            dangerous_patterns = [
                "__import__", "exec(", "eval(", "os.system",
                "subprocess", "import os", "import sys",
                "rm -rf", "chmod", "curl ", "wget ",
            ]
            lower = obj.lower()
            for pattern in dangerous_patterns:
                if pattern.lower() in lower:
                    errors.append(
                        f"Suspicious string value containing '{pattern}': {obj[:80]}"
                    )

    @property
    def stats(self) -> dict[str, int]:
        return {
            "total_checks": self._total_checks,
            "blocked": self._blocked_count,
        }
