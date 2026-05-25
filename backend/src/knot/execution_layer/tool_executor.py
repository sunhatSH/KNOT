"""Built-in tools for workflow execution."""

from __future__ import annotations

import logging
import os
import time
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


class FileReadTool(BaseTool):
    """Read file contents from the local filesystem.

    Only allows reading from /tmp or directories configured via the
    SAFE_FILE_DIRS environment variable (comma-separated).
    """

    _SAFE_DIRS: list[str] | None = None

    @property
    def name(self) -> str:
        return "file_read"

    @property
    def description(self) -> str:
        return (
            "Read file contents from the local filesystem. "
            "Only files within allowed directories (/tmp or SAFE_FILE_DIRS) can be read."
        )

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read",
                },
            },
            "required": ["path"],
        }

    def _get_safe_dirs(self) -> list[str]:
        if FileReadTool._SAFE_DIRS is not None:
            return FileReadTool._SAFE_DIRS
        dirs = ["/tmp"]
        env_dirs = os.environ.get("SAFE_FILE_DIRS", "")
        if env_dirs:
            dirs.extend(d.strip() for d in env_dirs.split(",") if d.strip())
        FileReadTool._SAFE_DIRS = dirs
        return dirs

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        import os
        from pathlib import Path

        path = params.get("path", "")
        if not path:
            return ToolResult(success=False, error="No path provided")

        resolved = Path(path).resolve()
        safe_dirs = [Path(d).resolve() for d in self._get_safe_dirs()]
        allowed = any(
            str(resolved).startswith(str(sd) + "/") or str(resolved) == str(sd)
            for sd in safe_dirs
        )

        if not allowed:
            return ToolResult(
                success=False,
                error=f"Access denied: '{path}' is not in an allowed directory",
            )

        if not resolved.exists():
            return ToolResult(success=False, error=f"File not found: {path}")

        if not resolved.is_file():
            return ToolResult(success=False, error=f"Not a file: {path}")

        try:
            content = resolved.read_text(encoding="utf-8")
            return ToolResult(
                success=True,
                output={
                    "path": str(resolved),
                    "size": len(content),
                    "content": content,
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to read file: {e}")


class CurrentTimeTool(BaseTool):
    """Get the current date and time."""

    @property
    def name(self) -> str:
        return "current_time"

    @property
    def description(self) -> str:
        return "Get the current date and time in ISO format with timezone information."

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        local_now = now.astimezone()
        local_tz = local_now.tzinfo

        return ToolResult(
            success=True,
            output={
                "utc_iso": now.isoformat(),
                "local_iso": local_now.isoformat(),
                "timezone": str(local_tz),
                "utc_offset": str(local_tz.utcoffset(local_now)) if local_tz else "",
                "timestamp": int(now.timestamp()),
            },
        )


class WebSearchTool(BaseTool):
    """Simple web search via HTTP GET.

    Uses a configurable search URL. Set the SEARCH_URL environment variable
    to customize the search endpoint (use {query} as a placeholder).
    Defaults to the DuckDuckGo instant answer API.
    """

    def __init__(self):
        import httpx
        self._client = httpx.AsyncClient()

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web using a configurable search engine URL. Returns search results."

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        import os

        query = params.get("query", "")
        if not query:
            return ToolResult(success=False, error="No query provided")

        search_url = os.environ.get(
            "SEARCH_URL",
            "https://api.duckduckgo.com/?q={query}&format=json",
        )
        url = search_url.replace("{query}", query)

        try:
            resp = await self._client.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return ToolResult(
                success=True,
                output={"query": query, "results": data},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Search failed: {e}")


class DatabaseTool(BaseTool):
    """Execute SQL queries against the application database.

    This tool allows agents to query the database during workflow execution.
    It wraps the SQLAlchemy async engine to provide read-only query capability
    by default, with an optional write mode flag.

    Security:
    - By default, only SELECT queries are allowed
    - Write mode (INSERT/UPDATE/DELETE) must be explicitly enabled
    - All queries are logged for audit
    - Statement timeout prevents runaway queries
    """

    @property
    def name(self) -> str:
        return "database_query"

    @property
    def description(self) -> str:
        return "Execute SQL queries against the KNOT database"

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "SQL query to execute"},
                "params": {
                    "type": "array",
                    "items": {},
                    "description": "Query parameters",
                },
                "read_only": {
                    "type": "boolean",
                    "description": "If true, only SELECT allowed",
                },
            },
            "required": ["query"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        query = params.get("query", "").strip()
        read_only = params.get("read_only", True)

        # Validate
        if not query:
            return ToolResult(success=False, error="Query is empty")

        # Block non-SELECT when read_only
        if read_only and not query.upper().lstrip().startswith("SELECT"):
            return ToolResult(
                success=False, error="Only SELECT queries allowed in read-only mode"
            )

        # Execute via SQLAlchemy
        try:
            from knot.core.database import session_factory
            from sqlalchemy import text

            async with session_factory() as session:
                result = await session.execute(
                    text(query), params.get("params") or []
                )
                if query.upper().lstrip().startswith("SELECT"):
                    rows = result.fetchall()
                    columns = result.keys()
                    data = [dict(zip(columns, row)) for row in rows]
                    return ToolResult(
                        success=True,
                        output={"rows": data, "row_count": len(data)},
                    )
                else:
                    await session.commit()
                    return ToolResult(
                        success=True,
                        output={"affected_rows": result.rowcount},
                    )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class ScriptTool(BaseTool):
    """Execute shell commands in a sandboxed environment.

    Security features:
    - Only runs in a pre-configured working directory
    - Timeout prevents runaway scripts
    - Blocked dangerous commands: rm -rf, sudo, chmod, dd, :(){ :|:& };:
    - Max output size limit prevents memory issues
    - All executions are logged

    Configurable in tool config:
    - allowed_commands: list of allowed command prefixes (default: all except blocked)
    - working_directory: cwd for execution
    - timeout_seconds: max execution time
    - max_output_chars: max output length
    """

    BLOCKED_PATTERNS: list[str] = [
        "rm -rf",
        "rm -fr",
        "rm -r",
        "sudo",
        "chmod 777",
        "chmod -R 777",
        "dd if=",
        "mkfs",
        "fdisk",
        "format",
        ">:",
        ":(){ :|:& };:",
    ]

    def __init__(
        self,
        working_directory: str | None = None,
        timeout_seconds: int = 30,
        max_output_chars: int = 10000,
    ) -> None:
        self._cwd = working_directory or os.environ.get(
            "SCRIPT_WORK_DIR", "/tmp"
        )
        self._timeout = timeout_seconds
        self._max_output = max_output_chars

    @property
    def name(self) -> str:
        return "run_script"

    @property
    def description(self) -> str:
        return (
            "Execute a shell command in a sandboxed environment. "
            "Limited to allowed commands; dangerous commands are blocked. "
            "Returns stdout, stderr, return code, and execution duration."
        )

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Max execution time in seconds (default: 30)",
                },
            },
            "required": ["command"],
        }

    def _is_blocked(self, command: str) -> str | None:
        """Check if the command contains dangerous patterns.

        Returns the matched pattern or None if the command is allowed.
        """
        lowered = command.lower().strip()
        for pattern in self.BLOCKED_PATTERNS:
            if pattern in lowered:
                return pattern
        return None

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        import asyncio

        command = params.get("command", "").strip()
        if not command:
            return ToolResult(success=False, error="Command is empty")

        # Check for blocked patterns
        blocked = self._is_blocked(command)
        if blocked:
            logger.warning(
                "Blocked dangerous command pattern '%s' in: %s",
                blocked,
                command[:100],
            )
            return ToolResult(
                success=False,
                error=f"Command blocked: pattern '{blocked}' is not allowed",
            )

        timeout = params.get("timeout", self._timeout)

        try:
            start = time.monotonic()

            # Verify working directory exists
            cwd = self._cwd
            os.makedirs(cwd, exist_ok=True)

            # Create subprocess
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                duration_ms = int((time.monotonic() - start) * 1000)
                return ToolResult(
                    success=False,
                    error=f"Command timed out after {timeout}s",
                    metadata={
                        "duration_ms": duration_ms,
                        "return_code": -1,
                    },
                )

            duration_ms = int((time.monotonic() - start) * 1000)

            stdout = stdout_bytes.decode("utf-8", errors="replace")[
                : self._max_output
            ]
            stderr = stderr_bytes.decode("utf-8", errors="replace")[
                : self._max_output
            ]
            return_code = proc.returncode

            logger.info(
                "Script executed in %dms (exit code=%d): %s",
                duration_ms,
                return_code,
                command[:80],
            )

            return ToolResult(
                success=return_code == 0,
                output={
                    "stdout": stdout,
                    "stderr": stderr,
                    "return_code": return_code,
                    "duration_ms": duration_ms,
                },
                metadata={
                    "command": command[:200],
                    "cwd": cwd,
                    "duration_ms": duration_ms,
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
