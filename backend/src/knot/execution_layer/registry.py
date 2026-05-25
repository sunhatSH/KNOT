"""Tool registry — plugin-based tool registration and discovery."""

from __future__ import annotations

import logging
from typing import Any

from knot.execution_layer.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for executable tools.

    Tools can be registered by name and discovered at runtime.
    Supports plugin-based integration through a unified interface.
    """

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
        logger.info("Registered tool: %s", tool.name)

    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        """Execute a tool by name with given parameters."""
        tool = self.get(tool_name)
        if not tool:
            return ToolResult(success=False, error=f"Tool '{tool_name}' not found")
        try:
            return await tool.execute(params)
        except Exception as e:
            logger.error("Tool '%s' failed: %s", tool_name, e)
            return ToolResult(success=False, error=str(e))

    def list_tools(self) -> list[dict[str, Any]]:
        """List all registered tools."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema(),
            }
            for t in self._tools.values()
        ]

    def to_openai_tools(self) -> list[dict[str, Any]]:
        """Convert all tools to OpenAI-compatible format."""
        return [t.to_openai_tool() for t in self._tools.values()]


# Global tool registry instance
tool_registry = ToolRegistry()
