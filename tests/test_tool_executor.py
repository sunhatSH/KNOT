"""Tests for built-in tools (EchoTool, CalculatorTool) and ToolRegistry."""

import pytest
from knot.execution_layer.tool_executor import CalculatorTool, EchoTool
from knot.execution_layer.registry import ToolRegistry


# ─── EchoTool Tests ─────────────────────────────────────────────────────────


class TestEchoTool:
    """Execute an echo tool that returns the input message unchanged."""

    @pytest.mark.asyncio
    async def test_echo_with_message(self):
        tool = EchoTool()
        result = await tool.execute({"message": "hello world"})
        assert result.success is True
        assert result.output == {"message": "hello world"}

    @pytest.mark.asyncio
    async def test_echo_empty_message(self):
        tool = EchoTool()
        result = await tool.execute({"message": ""})
        assert result.success is True
        assert result.output == {"message": ""}

    @pytest.mark.asyncio
    async def test_echo_missing_message_key(self):
        tool = EchoTool()
        result = await tool.execute({})
        assert result.success is True
        assert result.output == {"message": ""}

    def test_name(self):
        tool = EchoTool()
        assert tool.name == "echo"

    def test_description(self):
        tool = EchoTool()
        assert "Echoes" in tool.description

    def test_input_schema(self):
        tool = EchoTool()
        schema = tool.input_schema()
        assert "message" in schema["properties"]
        assert "message" in schema["required"]


# ─── CalculatorTool Tests ───────────────────────────────────────────────────


class TestCalculatorTool:
    """Execute a calculator tool that safely evaluates math expressions."""

    @pytest.mark.asyncio
    async def test_addition(self):
        tool = CalculatorTool()
        result = await tool.execute({"expression": "2 + 2"})
        assert result.success is True
        assert result.output == {"result": 4}

    @pytest.mark.asyncio
    async def test_subtraction(self):
        tool = CalculatorTool()
        result = await tool.execute({"expression": "10 - 3"})
        assert result.success is True
        assert result.output == {"result": 7}

    @pytest.mark.asyncio
    async def test_multiplication(self):
        tool = CalculatorTool()
        result = await tool.execute({"expression": "3 * 4"})
        assert result.success is True
        assert result.output == {"result": 12}

    @pytest.mark.asyncio
    async def test_division(self):
        tool = CalculatorTool()
        result = await tool.execute({"expression": "10 / 2"})
        assert result.success is True
        assert result.output == {"result": 5.0}

    @pytest.mark.asyncio
    async def test_operator_precedence(self):
        tool = CalculatorTool()
        result = await tool.execute({"expression": "2 + 3 * 4"})
        assert result.success is True
        assert result.output == {"result": 14}

    @pytest.mark.asyncio
    async def test_parentheses(self):
        tool = CalculatorTool()
        result = await tool.execute({"expression": "(2 + 3) * 4"})
        assert result.success is True
        assert result.output == {"result": 20}

    @pytest.mark.asyncio
    async def test_float_division(self):
        tool = CalculatorTool()
        result = await tool.execute({"expression": "7 / 2"})
        assert result.success is True
        assert result.output == {"result": 3.5}

    @pytest.mark.asyncio
    async def test_invalid_expression(self):
        tool = CalculatorTool()
        result = await tool.execute({"expression": "invalid + +"})
        assert result.success is False
        assert "Invalid expression" in result.error

    @pytest.mark.asyncio
    async def test_empty_expression(self):
        tool = CalculatorTool()
        result = await tool.execute({"expression": ""})
        assert result.success is False
        assert "Invalid expression" in result.error

    @pytest.mark.asyncio
    async def test_unsafe_builtins_blocked(self):
        """Verify that dangerous builtins like __import__ are blocked."""
        tool = CalculatorTool()
        result = await tool.execute(
            {"expression": "__import__('os')"}
        )
        assert result.success is False

    def test_name(self):
        tool = CalculatorTool()
        assert tool.name == "calculator"

    def test_description(self):
        tool = CalculatorTool()
        assert "mathematical" in tool.description.lower()

    def test_input_schema(self):
        tool = CalculatorTool()
        schema = tool.input_schema()
        assert "expression" in schema["properties"]
        assert "expression" in schema["required"]


# ─── ToolRegistry Tests ─────────────────────────────────────────────────────


class TestToolRegistry:
    """ToolRegistry for registering, looking up, and listing tools."""

    def test_register_and_get(self):
        registry = ToolRegistry()
        tool = EchoTool()
        registry.register(tool)
        retrieved = registry.get("echo")
        assert retrieved is not None
        assert isinstance(retrieved, EchoTool)

    def test_get_not_found(self):
        registry = ToolRegistry()
        assert registry.get("nonexistent") is None

    def test_register_overwrites_same_name(self):
        registry = ToolRegistry()
        registry.register(EchoTool())
        registry.register(EchoTool())  # Same name, should overwrite
        assert len(registry.list_tools()) == 1

    def test_list_tools_populated(self):
        registry = ToolRegistry()
        registry.register(EchoTool())
        registry.register(CalculatorTool())
        tools = registry.list_tools()
        assert len(tools) == 2
        names = {t["name"] for t in tools}
        assert names == {"echo", "calculator"}

    def test_list_tools_empty(self):
        registry = ToolRegistry()
        assert registry.list_tools() == []

    def test_list_tools_structure(self):
        registry = ToolRegistry()
        registry.register(CalculatorTool())
        tools = registry.list_tools()
        entry = tools[0]
        assert "name" in entry
        assert "description" in entry
        assert "input_schema" in entry

    @pytest.mark.asyncio
    async def test_execute_registered_tool(self):
        registry = ToolRegistry()
        registry.register(EchoTool())
        result = await registry.execute("echo", {"message": "registry test"})
        assert result.success is True
        assert result.output == {"message": "registry test"}

    @pytest.mark.asyncio
    async def test_execute_unregistered_tool(self):
        registry = ToolRegistry()
        result = await registry.execute("nonexistent", {})
        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_execute_failing_tool(self):
        registry = ToolRegistry()
        registry.register(CalculatorTool())
        result = await registry.execute(
            "calculator", {"expression": "bad ++ expr"}
        )
        assert result.success is False
