"""Built-in tools for workflow execution."""

from __future__ import annotations

import logging
from typing import Any

from knot.execution_layer.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class EchoTool(BaseTool):
    """Simple echo tool for testing."""

    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echoes back the input message. Useful for testing."

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Message to echo"},
            },
            "required": ["message"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        message = params.get("message", "")
        logger.info("Echo: %s", message)
        return ToolResult(success=True, output={"message": message})


class HTTPRequestTool(BaseTool):
    """Makes HTTP requests to external APIs."""

    def __init__(self):
        import httpx
        self._client = httpx.AsyncClient()

    @property
    def name(self) -> str:
        return "http_request"

    @property
    def description(self) -> str:
        return "Make HTTP requests to external services. Supports GET and POST."

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Target URL"},
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST"],
                    "default": "GET",
                },
                "headers": {
                    "type": "object",
                    "description": "HTTP headers",
                },
                "body": {
                    "type": "object",
                    "description": "Request body (for POST)",
                },
            },
            "required": ["url"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        url = params["url"]
        method = params.get("method", "GET").upper()
        headers = params.get("headers", {})
        body = params.get("body")

        try:
            if method == "GET":
                resp = await self._client.get(url, headers=headers, timeout=30)
            else:
                resp = await self._client.post(url, headers=headers, json=body, timeout=30)
            return ToolResult(
                success=resp.is_success,
                output={
                    "status_code": resp.status_code,
                    "body": resp.text[:10000],
                },
                metadata={"url": url, "method": method},
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class CalculatorTool(BaseTool):
    """Simple calculator tool."""

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "Evaluate mathematical expressions."

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate (e.g., '2 + 2 * 3')",
                },
            },
            "required": ["expression"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        expression = params.get("expression", "")
        try:
            # Safe evaluation using only math builtins
            allowed_names = {
                "abs": abs, "min": min, "max": max,
                "sum": sum, "round": round,
                "float": float, "int": int,
            }
            result = eval(expression, {"__builtins__": {}}, allowed_names)
            return ToolResult(success=True, output={"result": result})
        except Exception as e:
            return ToolResult(success=False, error=f"Invalid expression: {e}")
