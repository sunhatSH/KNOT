"""Tests for workflow execution state and NL->Workflow parsing."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import pytest

from knot.core.models import (
    Execution,
    NodeStatus,
    TraceEntry,
    WorkflowStatus,
)
from knot.orchestration_layer.intent_understanding import (
    Intent,
    IntentParser,
    SubTask,
    WorkflowGenerator,
)
from knot.orchestration_layer.state import ExecutionStats, WorkflowState


# --- WorkflowState --------------------------------------------------------


class TestWorkflowState:
    def test_initial_state(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)
        assert state.execution_id == exec_.id
        assert state.workflow_id == "wf_1"
        assert state.status == WorkflowStatus.PENDING
        assert state.is_cancelled() is False

    def test_request_pause_and_resume(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)

        state.request_pause()
        assert state.status == WorkflowStatus.PAUSED

        state.request_resume()
        assert state.status == WorkflowStatus.RUNNING

    def test_request_cancel(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)

        assert state.is_cancelled() is False
        state.request_cancel()
        assert state.is_cancelled() is True

    def test_reset_control(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)

        state.request_pause()
        state.request_cancel()
        assert state.is_cancelled() is True
        assert state.status == WorkflowStatus.PAUSED

        state.reset_control()
        assert state.is_cancelled() is False
        # After reset, control_event should be set (running)
        assert state._control_event.is_set()

    def test_get_global_default(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)
        assert state.get_global("nonexistent") is None
        assert state.get_global("nonexistent", 42) == 42

    def test_set_and_get_global(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)

        state.set_global("key1", "value1")
        assert state.get_global("key1") == "value1"

    def test_update_global(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)

        state.set_global("a", 1)
        state.update_global({"a": 10, "b": 20})
        assert state.get_global("a") == 10
        assert state.get_global("b") == 20

    def test_set_node_result(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)

        state.set_node_result("n1", NodeStatus.SUCCESS)
        assert state.get_node_result("n1") == NodeStatus.SUCCESS

    def test_add_trace_entry(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)

        state.add_trace(
            event="info",
            message="Test trace",
            node_id="n1",
            metadata={"key": "val"},
        )
        assert len(exec_.trace) == 1
        entry = exec_.trace[0]
        assert entry["event"] == "info"
        assert entry["message"] == "Test trace"
        assert entry["node_id"] == "n1"
        assert entry["metadata"]["key"] == "val"
        assert "timestamp" in entry

    def test_trace_node_start_complete(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)

        state.trace_node_start("n1", "Node 1")
        assert len(exec_.trace) == 1
        assert exec_.trace[0]["event"] == "node_start"

        state.trace_node_complete("n1", "Node 1", duration_ms=100.5)
        assert len(exec_.trace) == 2
        assert exec_.trace[1]["event"] == "node_complete"
        assert exec_.trace[1]["duration_ms"] == 100.5

    def test_trace_node_failed(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)

        state.trace_node_failed("n1", "Node 1", "Something broke")
        assert exec_.trace[0]["event"] == "node_failed"
        assert "Something broke" in exec_.trace[0]["message"]

    def test_trace_node_skipped(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)

        state.trace_node_skipped("n1", "Node 1")
        assert exec_.trace[0]["event"] == "node_skipped"

    def test_trace_tool_call(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)

        state.trace_tool_call("calculator", {"expression": "2+2"}, result=4)
        assert exec_.trace[0]["event"] == "tool_call"
        assert exec_.trace[0]["metadata"]["tool_name"] == "calculator"

    def test_trace_knowledge_retrieval(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)

        state.trace_knowledge_retrieval("test query", 5)
        assert exec_.trace[0]["event"] == "knowledge_retrieval"
        assert exec_.trace[0]["metadata"]["chunks_count"] == 5

    def test_trace_info(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)

        state.trace_info("Something happened")
        assert exec_.trace[0]["event"] == "info"
        assert exec_.trace[0]["message"] == "Something happened"

    def test_snapshot(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)

        snap = state.snapshot()
        assert snap["workflow_id"] == "wf_1"
        assert snap["status"] == "pending"

    def test_wait_if_paused_not_paused(self):
        """wait_if_paused should return immediately when not paused."""
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)

        # Should not block (control_event is set by default) - just run synchronously
        async def check():
            await state.wait_if_paused()

        asyncio.run(check())
        # No explicit assertion needed - it just should not raise

    def test_wait_if_paused_cancelled_raises(self):
        """wait_if_paused should raise CancelledError when cancelled."""
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)

        state.request_cancel()

        async def check():
            await state.wait_if_paused()

        with pytest.raises(asyncio.CancelledError):
            asyncio.run(check())


# --- ExecutionStats -------------------------------------------------------


class TestExecutionStats:
    def test_empty_execution(self):
        exec_ = Execution(workflow_id="wf_1")
        stats = ExecutionStats.compute(exec_)
        assert stats["total_duration_ms"] is None
        assert stats["node_count"] == 0
        assert stats["completed_count"] == 0
        assert stats["failed_count"] == 0
        assert stats["skipped_count"] == 0
        assert stats["avg_node_duration_ms"] is None
        assert stats["bottlenecks"] == []
        assert "timeline" in stats

    def test_with_node_states(self):
        exec_ = Execution(
            workflow_id="wf_1",
            node_states={
                "n1": NodeStatus.SUCCESS,
                "n2": NodeStatus.SUCCESS,
                "n3": NodeStatus.FAILED,
                "n4": NodeStatus.SKIPPED,
            },
        )
        stats = ExecutionStats.compute(exec_)
        assert stats["node_count"] == 4
        assert stats["completed_count"] == 2
        assert stats["failed_count"] == 1
        assert stats["skipped_count"] == 1

    def test_with_duration(self):
        start = datetime.now() - timedelta(seconds=5)
        end = datetime.now()
        exec_ = Execution(
            workflow_id="wf_1",
            started_at=start,
            completed_at=end,
        )
        stats = ExecutionStats.compute(exec_)
        assert stats["total_duration_ms"] is not None
        assert stats["total_duration_ms"] > 0

    def test_timeline_from_trace(self):
        exec_ = Execution(
            workflow_id="wf_1",
            trace=[
                TraceEntry(event="info", message="start").model_dump(),
                TraceEntry(
                    event="node_complete",
                    node_id="n1",
                    duration_ms=150.0,
                ).model_dump(),
                TraceEntry(
                    event="node_complete",
                    node_id="n2",
                    duration_ms=200.0,
                ).model_dump(),
            ],
        )
        stats = ExecutionStats.compute(exec_)
        assert len(stats["timeline"]) == 3
        assert stats["timeline"][0]["event"] == "info"
        assert stats["avg_node_duration_ms"] == pytest.approx(175.0, rel=0.1)

    def test_bottlenecks(self):
        exec_ = Execution(
            workflow_id="wf_1",
            trace=[
                TraceEntry(
                    event="node_complete",
                    node_id="fast",
                    duration_ms=50.0,
                ).model_dump(),
                TraceEntry(
                    event="node_complete",
                    node_id="slow",
                    duration_ms=500.0,
                ).model_dump(),
                TraceEntry(
                    event="node_complete",
                    node_id="medium",
                    duration_ms=150.0,
                ).model_dump(),
            ],
        )
        stats = ExecutionStats.compute(exec_)
        assert len(stats["bottlenecks"]) == 3
        # Slowest first
        assert stats["bottlenecks"][0]["node_id"] == "slow"


# --- IntentParser (NL -> Workflow) ----------------------------------------


class TestIntentParser:
    """Test the JSON parsing logic of IntentParser without an LLM."""

    def setup_method(self):
        # Create parser without LLM for parse_response testing
        self.parser = IntentParser(llm_provider=None)  # type: ignore[arg-type]

    def test_parse_response_direct_json(self):
        content = '{"task_description": "Test task", "subtasks": [{"label": "Step1", "description": "First step"}]}'
        intent = self.parser._parse_response(content)
        assert intent is not None
        assert intent.task_description == "Test task"
        assert len(intent.subtasks) == 1
        assert intent.subtasks[0].label == "Step1"

    def test_parse_response_code_block(self):
        content = """Some text before
```json
{"task_description": "Test", "subtasks": [{"label": "A", "description": "desc"}]}
```
Some text after"""
        intent = self.parser._parse_response(content)
        assert intent is not None
        assert intent.task_description == "Test"

    def test_parse_response_code_block_no_lang(self):
        content = """```
{"task_description": "Test", "subtasks": [{"label": "A", "description": "desc"}]}
```"""
        intent = self.parser._parse_response(content)
        assert intent is not None
        assert intent.task_description == "Test"

    def test_parse_response_list_format(self):
        """LLM sometimes returns just a list of subtasks."""
        content = '[{"label": "Step1", "description": "First"}, {"label": "Step2", "description": "Second"}]'
        intent = self.parser._parse_response(content)
        assert intent is not None
        assert len(intent.subtasks) == 2
        assert intent.subtasks[0].label == "Step1"

    def test_parse_response_single_dict_subtask(self):
        """Handle case where subtask is a dict instead of list."""
        content = '{"subtasks": {"label": "Single", "description": "One"}}'
        intent = self.parser._parse_response(content)
        assert intent is not None
        assert len(intent.subtasks) == 1
        assert intent.subtasks[0].label == "Single"

    def test_parse_response_chinese_fields(self):
        content = '{"task_description": "测试", "subtasks": [{"标签": "步骤1", "描述": "第一个步骤", "依赖": [], "节点类型": "task"}]}'
        intent = self.parser._parse_response(content, user_request="测试请求")
        assert intent is not None
        assert intent.task_description == "测试"
        assert len(intent.subtasks) == 1

    def test_parse_response_chinese_field_map_full(self):
        """Use the Chinese field map keys."""
        content = (
            '{"任务描述": "Test", "子任务": [{"标签": "S1", "描述": "desc", "依赖": [], "节点类型": "task"}], '
            '"预期输出": "result", "知识领域": ["AI"]}'
        )
        intent = self.parser._parse_response(content)
        assert intent is not None
        assert intent.task_description == "Test"
        assert intent.expected_output == "result"
        assert "AI" in intent.knowledge_domains

    def test_parse_response_invalid_json(self):
        content = "This is not JSON at all"
        intent = self.parser._parse_response(content)
        assert intent is None

    def test_parse_response_empty_subtasks(self):
        content = '{"task_description": "Test", "subtasks": []}'
        intent = self.parser._parse_response(content)
        assert intent is None

    def test_parse_response_all_untitled(self):
        content = '{"task_description": "Test", "subtasks": [{"label": "Untitled Step", "description": ""}]}'
        intent = self.parser._parse_response(content)
        assert intent is None

    def test_parse_response_with_regex_fallback(self):
        """JSON embedded in surrounding text should be extracted via regex."""
        content = 'Here is the result: {"task_description": "Regex", "subtasks": [{"label": "R1", "description": "Found"}]} End'
        intent = self.parser._parse_response(content)
        assert intent is not None
        assert intent.task_description == "Regex"

    def test_parse_response_multiline_code_block(self):
        content = "```json\n{\n  \"task_description\": \"Multi\",\n  \"subtasks\": [\n    {\"label\": \"M1\", \"description\": \"Line\"}\n  ]\n}\n```"
        intent = self.parser._parse_response(content)
        assert intent is not None
        assert intent.task_description == "Multi"

    def test_parse_response_fills_empty_fields(self):
        """Empty task_description should fall back to user_request."""
        content = '{"task_description": "", "subtasks": [{"label": "S1", "description": "do stuff"}]}'
        intent = self.parser._parse_response(content, user_request="User's request here")
        assert intent is not None
        assert "User's request" in intent.task_description

    def test_parse_response_fills_empty_description(self):
        """Empty subtask description should fall back to label."""
        content = '{"task_description": "T", "subtasks": [{"label": "MyLabel", "description": ""}]}'
        intent = self.parser._parse_response(content)
        assert intent is not None
        assert intent.subtasks[0].description == "MyLabel"


class TestWorkflowGenerator:
    async def test_generate_workflow_from_intent(self):
        generator = WorkflowGenerator(llm_provider=None)

        intent_obj = Intent(
            task_description="Test workflow",
            subtasks=[
                SubTask(label="InputStep", description="Input", node_type="input"),
                SubTask(label="ProcessStep", description="Process", node_type="task", depends_on=["InputStep"]),
                SubTask(label="OutputStep", description="Output", node_type="output", depends_on=["ProcessStep"]),
            ],
            expected_output="Done",
        )

        wf = await generator.generate(intent_obj, user_request="test")
        assert wf.name == "Test workflow"
        assert len(wf.nodes) == 3
        assert len(wf.edges) >= 2  # sequential chaining
        assert wf.global_context["user_request"] == "test"
        assert wf.global_context["knowledge_domains"] == []

    async def test_generate_with_no_edges_chains_sequentially(self):
        generator = WorkflowGenerator(llm_provider=None)

        intent_obj = Intent(
            task_description="Chain test",
            subtasks=[
                SubTask(label="A", description="First", node_type="input"),
                SubTask(label="B", description="Second", node_type="task"),
                SubTask(label="C", description="Third", node_type="output"),
            ],
            expected_output="Done",
        )

        wf = await generator.generate(intent_obj)
        assert len(wf.edges) >= 2

    async def test_generate_with_tags_from_knowledge_domains(self):
        generator = WorkflowGenerator(llm_provider=None)

        intent_obj = Intent(
            task_description="Domain test",
            subtasks=[SubTask(label="S1", description="Step 1")],
            expected_output="Done",
            knowledge_domains=["AI", "ML"],
        )

        wf = await generator.generate(intent_obj)
        assert "AI" in wf.tags
        assert "ML" in wf.tags

    def test_translate_label(self):
        """Chinese labels should be translated to English equivalents."""
        assert WorkflowGenerator._translate_label("搜索文件") == "Search文件"
        assert WorkflowGenerator._translate_label("分析数据") == "Analyze数据"
        assert WorkflowGenerator._translate_label("English Label") == "English Label"


# --- Fallback Intent ------------------------------------------------------


class TestFallbackIntent:
    def test_fallback_creates_intent(self):
        intent = IntentParser._create_fallback_intent("搜索并分析最新的AI论文")
        assert intent is not None
        assert len(intent.subtasks) >= 1
        assert intent.task_description == "搜索并分析最新的AI论文"

    def test_fallback_with_chinese_actions(self):
        intent = IntentParser._create_fallback_intent("搜索数据，分析结果，生成报告")
        assert len(intent.subtasks) >= 2
        labels = [st.label for st in intent.subtasks]
        assert any("Search" in l or "Analyze" in l or "Generate" in l for l in labels)

    def test_fallback_empty_string(self):
        intent = IntentParser._create_fallback_intent("")
        assert intent is not None
        assert len(intent.subtasks) >= 1

    def test_fallback_single_segment(self):
        intent = IntentParser._create_fallback_intent("SayHello")
        assert len(intent.subtasks) >= 1
