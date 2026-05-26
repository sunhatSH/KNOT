"""Tests for built-in tools (Calculator, Echo, Script, Database, etc.)."""

from __future__ import annotations

import pytest

from knot.execution_layer.base import ToolResult
from knot.execution_layer.tool_executor import (
    CalculatorTool,
    DatabaseTool,
    EchoTool,
    FileReadTool,
    ScriptTool,
)


# --- EchoTool -------------------------------------------------------------


class TestEchoTool:
    async def test_echo_basic(self):
        tool = EchoTool()
        result = await tool.execute({"message": "hello"})
        assert result.success is True
        assert result.output == {"message": "hello"}

    async def test_echo_empty_message(self):
        tool = EchoTool()
        result = await tool.execute({"message": ""})
        assert result.success is True
        assert result.output == {"message": ""}

    async def test_echo_missing_message(self):
        tool = EchoTool()
        result = await tool.execute({})
        assert result.success is True
        assert result.output == {"message": ""}

    def test_name_and_description(self):
        tool = EchoTool()
        assert tool.name == "echo"
        assert "Echoes" in tool.description

    def test_input_schema(self):
        tool = EchoTool()
        schema = tool.input_schema()
        assert "message" in schema["properties"]


# --- CalculatorTool -------------------------------------------------------


class TestCalculatorTool:
    async def test_basic_arithmetic(self):
        tool = CalculatorTool()
        result = await tool.execute({"expression": "2 + 2"})
        assert result.success is True
        assert result.output["result"] == 4

    async def test_complex_expression(self):
        tool = CalculatorTool()
        result = await tool.execute({"expression": "(3 + 5) * 2 - 4 / 2"})
        assert result.success is True
        assert result.output["result"] == 14

    async def test_float_result(self):
        tool = CalculatorTool()
        result = await tool.execute({"expression": "10 / 3"})
        assert result.success is True
        assert isinstance(result.output["result"], float)

    async def test_abs_function(self):
        tool = CalculatorTool()
        result = await tool.execute({"expression": "abs(-5)"})
        assert result.success is True
        assert result.output["result"] == 5

    async def test_round_function(self):
        tool = CalculatorTool()
        result = await tool.execute({"expression": "round(3.14159, 2)"})
        assert result.success is True
        assert result.output["result"] == 3.14

    async def test_min_max(self):
        tool = CalculatorTool()
        result = await tool.execute({"expression": "min(10, 20, 5) + max(1, 9)"})
        assert result.success is True
        assert result.output["result"] == 14

    async def test_invalid_expression(self):
        tool = CalculatorTool()
        result = await tool.execute({"expression": "invalid + + garbage"})
        assert result.success is False
        assert "Invalid expression" in result.error

    async def test_empty_expression(self):
        tool = CalculatorTool()
        result = await tool.execute({"expression": ""})
        assert result.success is False

    async def test_safety_blocked(self):
        """Calculator should not allow builtins like __import__."""
        tool = CalculatorTool()
        result = await tool.execute({"expression": "__import__('os')"})
        assert result.success is False

    async def test_zero_division(self):
        tool = CalculatorTool()
        result = await tool.execute({"expression": "1 / 0"})
        assert result.success is False

    async def test_power(self):
        tool = CalculatorTool()
        result = await tool.execute({"expression": "2 ** 10"})
        assert result.success is True
        assert result.output["result"] == 1024

    def test_name_and_description(self):
        tool = CalculatorTool()
        assert tool.name == "calculator"
        assert "mathematical" in tool.description.lower()

    def test_input_schema(self):
        tool = CalculatorTool()
        schema = tool.input_schema()
        assert "expression" in schema["properties"]
        assert "expression" in schema["required"]


# --- ScriptTool -----------------------------------------------------------


class TestScriptTool:
    def test_blocked_patterns_exist(self):
        assert len(ScriptTool.BLOCKED_PATTERNS) > 0
        assert "rm -rf" in ScriptTool.BLOCKED_PATTERNS
        assert "sudo" in ScriptTool.BLOCKED_PATTERNS

    def test_is_blocked(self):
        tool = ScriptTool(working_directory="/tmp")
        assert tool._is_blocked("rm -rf /") is not None
        assert tool._is_blocked("sudo rm -rf /") is not None
        assert tool._is_blocked("echo hello") is None
        assert tool._is_blocked("ls -la") is None

    def test_blocked_case_insensitive(self):
        tool = ScriptTool(working_directory="/tmp")
        assert tool._is_blocked("RM -RF /") is not None

    def test_blocked_partial_match(self):
        """Patterns should match within longer commands."""
        tool = ScriptTool(working_directory="/tmp")
        assert tool._is_blocked("something rm -rf /something") is not None

    async def test_empty_command(self):
        tool = ScriptTool(working_directory="/tmp")
        result = await tool.execute({"command": ""})
        assert result.success is False
        assert "empty" in result.error.lower()

    async def test_blocked_command_returns_error(self):
        tool = ScriptTool(working_directory="/tmp")
        result = await tool.execute({"command": "rm -rf /"})
        assert result.success is False
        assert "blocked" in result.error.lower()

    async def test_echo_command_succeeds(self):
        tool = ScriptTool(working_directory="/tmp")
        result = await tool.execute({"command": "echo hello world"})
        assert result.success is True
        assert result.output["stdout"].strip() == "hello world"
        assert result.output["return_code"] == 0

    async def test_failing_command(self):
        tool = ScriptTool(working_directory="/tmp")
        result = await tool.execute({"command": "exit 42"})
        assert result.success is False
        assert result.output["return_code"] == 42

    async def test_tool_custom_timeout(self):
        tool = ScriptTool(working_directory="/tmp", timeout_seconds=5)
        result = await tool.execute({"command": "echo custom"})
        assert result.success is True
        assert "custom" in result.output["stdout"]

    def test_name_and_description(self):
        tool = ScriptTool()
        assert tool.name == "run_script"
        assert "sandboxed" in tool.description.lower()


# --- DatabaseTool ---------------------------------------------------------


class TestDatabaseTool:
    async def test_empty_query(self):
        tool = DatabaseTool()
        result = await tool.execute({"query": ""})
        assert result.success is False
        assert "empty" in result.error.lower()

    async def test_rejects_non_select_in_read_only(self):
        tool = DatabaseTool()
        result = await tool.execute({"query": "INSERT INTO users VALUES (1)", "read_only": True})
        assert result.success is False
        assert "Only SELECT" in result.error

    async def test_accepts_select_in_read_only(self):
        tool = DatabaseTool()
        # SELECT queries in read-only mode should pass validation
        result = await tool.execute({"query": "SELECT 1", "read_only": True})
        # The read-only validation should pass (won't get "Only SELECT" error).
        # Execution may fail since it uses the module-level engine, not test fixtures.
        assert "Only SELECT" not in (result.error or "")

    async def test_mixed_case_select(self):
        tool = DatabaseTool()
        result = await tool.execute({"query": "select * from users", "read_only": True})
        # It should fail with execution error, not validation error
        assert "Only SELECT" not in (result.error or "")

    def test_name_and_description(self):
        tool = DatabaseTool()
        assert tool.name == "database_query"


# --- FileReadTool ---------------------------------------------------------


class TestFileReadTool:
    async def test_no_path(self):
        tool = FileReadTool()
        result = await tool.execute({})
        assert result.success is False
        assert "No path" in result.error

    async def test_empty_path(self):
        tool = FileReadTool()
        result = await tool.execute({"path": ""})
        assert result.success is False
        assert "No path" in result.error

    async def test_denies_outside_safe_dir(self):
        tool = FileReadTool()
        result = await tool.execute({"path": "/etc/passwd"})
        assert result.success is False
        assert "denied" in result.error.lower() or "allowed" in result.error.lower()

    async def test_reads_tmp_file(self):
        import tempfile
        import os

        tool = FileReadTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, dir="/tmp") as f:
            f.write("test content")
            f.flush()
            tmp_path = f.name

        try:
            result = await tool.execute({"path": tmp_path})
            assert result.success is True
            assert result.output["content"] == "test content"
            assert result.output["size"] > 0
            assert tmp_path in result.output["path"]
        finally:
            os.unlink(tmp_path)

    def test_name_and_description(self):
        tool = FileReadTool()
        assert tool.name == "file_read"


# --- ToolResult ------------------------------------------------------------

class TestToolResult:
    def test_success_result(self):
        r = ToolResult(success=True, output={"key": "val"})
        assert r.success is True
        assert r.output == {"key": "val"}
        assert r.error is None
        assert r.metadata == {}

    def test_failure_result(self):
        r = ToolResult(success=False, error="Something went wrong")
        assert r.success is False
        assert r.output is None
        assert r.error == "Something went wrong"

    def test_with_metadata(self):
        r = ToolResult(success=True, metadata={"duration_ms": 100})
        assert r.metadata["duration_ms"] == 100
