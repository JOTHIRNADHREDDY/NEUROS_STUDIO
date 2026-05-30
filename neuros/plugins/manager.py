"""NEUROS V3 — Plugin Platform.

Supports hot-reloading of plugins and provides an SDK for plugins
to register drivers, tools, UI components, and skills.
"""

from typing import Any, Callable, Dict
import logging
import importlib
import sys
import os

logger = logging.getLogger(__name__)

class PluginSDK:
    """The interface passed to plugins during initialization."""
    
    def __init__(self) -> None:
        self.drivers: Dict[str, Any] = {}
        self.tools: Dict[str, Callable] = {}
        self.ui_components: Dict[str, Any] = {}
        self.skills: Dict[str, Any] = {}

    def register_driver(self, name: str, driver_class: Any) -> None:
        self.drivers[name] = driver_class
        logger.info("Registered driver: %s", name)

    def register_tool(self, name: str, func: Callable) -> None:
        self.tools[name] = func
        logger.info("Registered tool: %s", name)

    def register_ui(self, name: str, component: Any) -> None:
        self.ui_components[name] = component
        logger.info("Registered UI component: %s", name)

    def register_skill(self, name: str, skill_class: Any) -> None:
        self.skills[name] = skill_class
        logger.info("Registered skill: %s", name)

class PluginManager:
    """Manages discovery, loading, and hot-reloading of plugins."""

    def __init__(self) -> None:
        self.sdk = PluginSDK()
        self.loaded_plugins: Dict[str, Any] = {}

    def install_plugin(self, module_name: str) -> None:
        """Dynamically load and initialize a plugin."""
        try:
            logger.info("Installing plugin: %s", module_name)
            
            # Hot reload support: remove from sys.modules if it exists
            if module_name in sys.modules:
                logger.debug("Plugin %s already loaded, reloading...", module_name)
                module = importlib.reload(sys.modules[module_name])
            else:
                module = importlib.import_module(module_name)
            
            # Every plugin must implement an `initialize(sdk)` function
            if hasattr(module, "initialize"):
                module.initialize(self.sdk)
                self.loaded_plugins[module_name] = module
                logger.info("Successfully initialized plugin: %s", module_name)
            else:
                logger.error("Plugin %s lacks an 'initialize(sdk)' entrypoint.", module_name)
                
        except Exception as e:
            logger.error("Failed to install plugin %s: %s", module_name, e)

    def get_plugin_manifest(self, module_name: str) -> Dict[str, str]:
        """Fetch version compatibility info."""
        if module_name in self.loaded_plugins:
            module = self.loaded_plugins[module_name]
            return getattr(module, "MANIFEST", {"neuros": ">=3.0"})
        return {}
