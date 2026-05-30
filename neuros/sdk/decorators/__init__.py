"""
NEUROS SDK Decorators

Convenience decorators for building robot applications.

Usage:
    from neuros.sdk.decorators import on_event, every, on_start

    @on_event("/robot/sensor/battery")
    def handle_battery(msg):
        print(f"Battery: {msg['voltage']}V")

    @every(hz=10)
    def control_loop():
        pass
"""

from __future__ import annotations

import asyncio
import functools
import logging
from typing import Any, Callable

logger = logging.getLogger("neuros.sdk.decorators")

# Registry of decorated handlers
_event_handlers: dict[str, list[Callable]] = {}
_periodic_handlers: list[tuple[float, Callable]] = []
_startup_handlers: list[Callable] = []
_shutdown_handlers: list[Callable] = []


def on_event(topic: str) -> Callable:
    """Register a function as an event handler for a Neural Bus topic."""
    def decorator(func: Callable) -> Callable:
        if topic not in _event_handlers:
            _event_handlers[topic] = []
        _event_handlers[topic].append(func)
        logger.debug("Registered event handler for '%s': %s", topic, func.__name__)
        return func
    return decorator


def every(hz: float = 1.0) -> Callable:
    """Register a function to be called at a fixed frequency."""
    def decorator(func: Callable) -> Callable:
        _periodic_handlers.append((hz, func))
        logger.debug("Registered periodic handler at %s Hz: %s", hz, func.__name__)
        return func
    return decorator


def on_start(func: Callable) -> Callable:
    """Register a function to be called on robot start."""
    _startup_handlers.append(func)
    return func


def on_shutdown(func: Callable) -> Callable:
    """Register a function to be called on robot shutdown."""
    _shutdown_handlers.append(func)
    return func


def get_event_handlers() -> dict[str, list[Callable]]:
    return dict(_event_handlers)


def get_periodic_handlers() -> list[tuple[float, Callable]]:
    return list(_periodic_handlers)


def get_startup_handlers() -> list[Callable]:
    return list(_startup_handlers)


def get_shutdown_handlers() -> list[Callable]:
    return list(_shutdown_handlers)
