"""Plugin framework for dynamically loading external tools.

The plugin system allows third-party tools to be discovered and loaded
from a configured directory without modifying the core codebase.

Architecture:
- Plugin: a Python module or package that exports a 'tools' list or 'register' function
- PluginLoader: discovers plugins in configured directories and loads them
- PluginInfo: metadata about each loaded plugin (name, version, tools, author)
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from knot.execution_layer.base import BaseTool
from knot.execution_layer.registry import tool_registry

logger = logging.getLogger(__name__)


@dataclass
class PluginInfo:
    """Metadata about a loaded plugin."""

    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    tools: list[str] = field(default_factory=list)
    enabled: bool = True


class PluginLoader:
    """Discover, load, and manage external tool plugins.

    Plugins are Python files in a configured directory. Each plugin file should
    define a module-level list `tools: list[BaseTool]` or async function
    `async def register(registry)`.

    Usage:
        loader = PluginLoader(plugin_dirs=["plugins/"])
        await loader.discover()    # Find all plugin files
        await loader.load_all()    # Load and register all discovered plugins
        await loader.load("my_tool")  # Load a specific plugin
    """

    def __init__(self, plugin_dirs: list[str] | None = None) -> None:
        self._plugin_dirs = [
            Path(d).resolve() for d in (plugin_dirs or ["plugins"])
        ]
        self._discovered: dict[str, Path] = {}
        self._loaded: dict[str, PluginInfo] = {}

    async def discover(self) -> list[str]:
        """Scan plugin directories for Python files.

        Returns a list of discovered plugin names.
        """
        self._discovered.clear()
        for plugin_dir in self._plugin_dirs:
            if not plugin_dir.exists():
                logger.debug(
                    "Plugin directory does not exist: %s", plugin_dir
                )
                continue
            for f in plugin_dir.glob("*.py"):
                if f.name.startswith("_"):
                    continue
                name = f.stem
                self._discovered[name] = f
                logger.info("Discovered plugin: %s (%s)", name, f)
        return list(self._discovered.keys())

    async def load(self, name: str) -> PluginInfo | None:
        """Load a specific plugin by name."""
        if name not in self._discovered:
            logger.warning(
                "Plugin '%s' not found in discovered plugins", name
            )
            return None

        path = self._discovered[name]
        try:
            spec = importlib.util.spec_from_file_location(name, path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load spec for {path}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Register tools from the plugin
            tools: list[BaseTool] = getattr(module, "tools", [])
            for tool in tools:
                tool_registry.register(tool)

            # Also support async register function
            register_fn = getattr(module, "register", None)
            if register_fn is not None and callable(register_fn):
                try:
                    result = register_fn(tool_registry)
                    if hasattr(result, "__await__"):
                        await result
                except Exception as e:
                    logger.warning(
                        "Plugin '%s' register function failed: %s", name, e
                    )

            info = PluginInfo(
                name=name,
                version=getattr(module, "__version__", "0.1.0"),
                description=getattr(module, "__description__", ""),
                author=getattr(module, "__author__", ""),
                tools=[t.name for t in tools],
                enabled=True,
            )
            self._loaded[name] = info
            logger.info(
                "Loaded plugin '%s' with %d tools", name, len(tools)
            )
            return info
        except Exception as e:
            logger.error("Failed to load plugin '%s': %s", name, e)
            return None

    async def load_all(self) -> list[PluginInfo]:
        """Load all discovered plugins."""
        results: list[PluginInfo] = []
        for name in self._discovered:
            info = await self.load(name)
            if info:
                results.append(info)
        return results

    def list_loaded(self) -> list[PluginInfo]:
        """List all loaded plugins with metadata."""
        return list(self._loaded.values())

    @property
    def loaded_plugins(self) -> dict[str, PluginInfo]:
        """Get a dict of loaded plugins keyed by name."""
        return dict(self._loaded)
