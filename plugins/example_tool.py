"""Example plugin for the KNOT plugin system.

This demonstrates the plugin API. Each plugin should export:
- `tools: list[BaseTool]` -- tools to register
- Optionally: `__version__`, `__description__`, `__author__`
- Optionally: `def register(registry)` or `async def register(registry)`

Usage:
    Place this file in the plugins/ directory.
    The PluginLoader will auto-discover and load it.
"""

from __future__ import annotations

from knot.execution_layer.base import BaseTool, ToolResult

__version__ = "0.1.0"
__description__ = "Example plugin demonstrating the KNOT plugin API"
__author__ = "KNOT Team"


class WeatherTool(BaseTool):
    """Example tool that simulates weather lookup."""

    @property
    def name(self) -> str:
        return "weather"

    @property
    def description(self) -> str:
        return "Get current weather for a city (demonstration tool)"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name",
                },
            },
            "required": ["city"],
        }

    async def execute(self, params: dict) -> ToolResult:
        city = params.get("city", "unknown")
        # Simulated weather data
        return ToolResult(
            success=True,
            output={
                "city": city,
                "temperature": 22,
                "humidity": 65,
                "condition": "sunny",
                "note": "This is a demo tool -- replace with real API call",
            },
        )


# Tools to register (auto-discovered by PluginLoader)
tools = [WeatherTool()]
