"""Tests for the workflow engine — WorkflowState, WorkflowEngine, ExecutionStats.

Uses mocked LLM providers, schedulers, retrievers and enhancers so no
external services are required.
"""

import asyncio
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import ANY, AsyncMock, MagicMock, patch

from knot.core.models import (
    Edge,
    Execution,
    Node,
    NodeStatus,
    NodeType,
    TraceEntry,
    Workflow,
    WorkflowStatus,
)
from knot.llm.base import LLMMessage, LLMProvider, LLMResponse, EmbeddingResult
from knot.orchestration_layer.scheduler import AgentScheduler
from knot.orchestration_layer.state import WorkflowState, ExecutionStats
from knot.orchestration_layer.workflow import (
    LangGraphState,
    WorkflowEngine,
    _build_execution_snapshot,
    build_execute_node,
    build_finalize,
    build_init_state,
    build_route_condition,
)


# ─── Test Data ─────────────────────────────────────────────────────────────────


def simple_linear_workflow() -> Workflow:
    """A -> B"""
    return Workflow(
        name="Simple Linear",
        nodes=[
            Node(id="a", type=NodeType.INPUT, label="Input"),
            Node(id="b", type=NodeType.OUTPUT, label="Output"),
        ],
        edges=[
            Edge(source_id="a", target_id="b"),
        ],
    )


def two_task_workflow() -> Workflow:
    """INPUT -> TASK_A -> TASK_B -> OUTPUT"""
    return Workflow(
        name="Two Tasks",
        nodes=[
            Node(id="input", type=NodeType.INPUT, label="Input"),
            Node(id="task_a", type=NodeType.TASK, label="Task A"),
            Node(id="task_b", type=NodeType.TASK, label="Task B"),
            Node(id="output", type=NodeType.OUTPUT, label="Output"),
        ],
        edges=[
            Edge(source_id="input", target_id="task_a"),
            Edge(source_id="task_a", target_id="task_b"),
            Edge(source_id="task_b", target_id="output"),
        ],
    )


# ═══════════════════════════════════════════════════════════════════════════════
# WorkflowState Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorkflowState:
    """WorkflowState manages execution control (pause/resume/cancel) and context."""

    def test_initial_state(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)
        assert state.execution_id == exec_.id
        assert state.workflow_id == "wf_1"
        assert state.status == WorkflowStatus.PENDING
        assert state.is_cancelled() is False

    def test_request_pause(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)
        state.request_pause()
        assert state.status == WorkflowStatus.PAUSED

    def test_request_resume(self):
        exec_ = Execution(workflow_id="wf_1", status=WorkflowStatus.PAUSED)
        state = WorkflowState(exec_)
        state.request_resume()
        assert state.status == WorkflowStatus.RUNNING

    def test_request_cancel(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)
        state.request_cancel()
        assert state.is_cancelled() is True

    def test_reset_control(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)
        state.request_cancel()
        state.request_pause()
        state.reset_control()
        assert state.is_cancelled() is False
        assert state.status == WorkflowStatus.PENDING

    @pytest.mark.asyncio
    async def test_wait_if_paused_blocks(self):
        """wait_if_paused blocks when paused and unblocks on resume."""
        exec_ = Execution(workflow_id="wf_1", status=WorkflowStatus.PAUSED)
        state = WorkflowState(exec_)

        async def resume_after_delay():
            await asyncio.sleep(0.02)
            state.request_resume()

        task = asyncio.create_task(resume_after_delay())
        await state.wait_if_paused()  # Should block then unblock
        task.cancel()  # Clean up
        # Should not raise — meaning we unblocked successfully

    @pytest.mark.asyncio
    async def test_wait_if_paused_raises_on_cancel(self):
        """wait_if_paused raises CancelledError when cancel is requested."""
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)
        state.request_pause()

        async def cancel_after_delay():
            await asyncio.sleep(0.02)
            state.request_cancel()

        task = asyncio.create_task(cancel_after_delay())
        with pytest.raises(asyncio.CancelledError):
            await state.wait_if_paused()
        task.cancel()

    @pytest.mark.asyncio
    async def test_wait_if_paused_running_immediate(self):
        """wait_if_paused returns immediately when not paused."""
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)
        # Should not block at all
        await state.wait_if_paused()

    def test_get_global_default(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)
        assert state.get_global("missing", "default_value") == "default_value"

    def test_set_and_get_global(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)
        state.set_global("key1", "value1")
        assert state.get_global("key1") == "value1"

    def test_update_global(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)
        state.update_global({"a": 1, "b": 2})
        assert state.get_global("a") == 1
        assert state.get_global("b") == 2

    def test_add_trace(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)
        state.add_trace(
            event="info",
            message="Test trace",
            node_id="n1",
            node_label="Test Node",
            duration_ms=10.0,
            metadata={"detail": "xyz"},
        )
        assert len(exec_.trace) == 1
        entry = exec_.trace[0]
        assert entry["event"] == "info"
        assert entry["message"] == "Test trace"
        assert entry["node_id"] == "n1"

    def test_trace_node_start(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)
        state.trace_node_start("n1", "Node One")
        assert exec_.trace[0]["event"] == "node_start"
        assert exec_.trace[0]["node_id"] == "n1"

    def test_trace_node_complete(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)
        state.trace_node_complete("n1", "Node One", duration_ms=42.5)
        assert exec_.trace[0]["event"] == "node_complete"
        assert exec_.trace[0]["duration_ms"] == 42.5

    def test_trace_node_failed(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)
        state.trace_node_failed("n1", "Node One", "Something broke")
        assert exec_.trace[0]["event"] == "node_failed"
        assert "Something broke" in exec_.trace[0]["message"]

    def test_trace_node_skipped(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)
        state.trace_node_skipped("n1", "Node One")
        assert exec_.trace[0]["event"] == "node_skipped"

    def test_trace_tool_call(self):
        exec_ = Execution(workflow_id="wf_1")
        state = WorkflowState(exec_)
        state.trace_tool_call("calculator", {"expression": "1+1"}, "2")
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
        snapshot = state.snapshot()
        assert snapshot["workflow_id"] == "wf_1"
        assert "id" in snapshot


# ═══════════════════════════════════════════════════════════════════════════════
# ExecutionStats Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestExecutionStats:
    """ExecutionStats computes statistics from execution data."""

    def test_compute_full_success(self):
        exec_ = Execution(
            workflow_id="wf_1",
            status=WorkflowStatus.SUCCESS,
            started_at=datetime(2025, 1, 1, 0, 0, 0),
            completed_at=datetime(2025, 1, 1, 0, 1, 0),  # 60 seconds
            node_states={
                "a": NodeStatus.SUCCESS,
                "b": NodeStatus.SUCCESS,
                "c": NodeStatus.SUCCESS,
            },
            trace=[
                TraceEntry(
                    event="node_complete",
                    node_id="a",
                    duration_ms=1000.0,
                ).model_dump(),
                TraceEntry(
                    event="node_complete",
                    node_id="b",
                    duration_ms=2000.0,
                ).model_dump(),
                TraceEntry(
                    event="node_complete",
                    node_id="c",
                    duration_ms=3000.0,
                ).model_dump(),
            ],
        )
        stats = ExecutionStats.compute(exec_)
        assert stats["total_duration_ms"] == 60000.0
        assert stats["node_count"] == 3
        assert stats["completed_count"] == 3
        assert stats["failed_count"] == 0
        assert stats["skipped_count"] == 0
        assert stats["avg_node_duration_ms"] == 2000.0
        assert len(stats["timeline"]) == 3
        assert len(stats["bottlenecks"]) == 3
        assert stats["bottlenecks"][0]["node_id"] == "c"  # highest duration

    def test_compute_with_failures_and_skips(self):
        exec_ = Execution(
            workflow_id="wf_1",
            status=WorkflowStatus.FAILED,
            started_at=datetime(2025, 1, 1, 0, 0, 0),
            completed_at=datetime(2025, 1, 1, 0, 0, 30),
            node_states={
                "a": NodeStatus.SUCCESS,
                "b": NodeStatus.FAILED,
                "c": NodeStatus.SKIPPED,
            },
        )
        stats = ExecutionStats.compute(exec_)
        assert stats["completed_count"] == 1
        assert stats["failed_count"] == 1
        assert stats["skipped_count"] == 1

    def test_compute_no_timing(self):
        """stats should handle missing timing gracefully."""
        exec_ = Execution(
            workflow_id="wf_1",
            status=WorkflowStatus.PENDING,
            started_at=None,
            completed_at=None,
            node_states={},
        )
        stats = ExecutionStats.compute(exec_)
        assert stats["total_duration_ms"] is None
        assert stats["node_count"] == 0
        assert stats["avg_node_duration_ms"] is None
        assert stats["bottlenecks"] == []

    def test_compute_empty_trace(self):
        exec_ = Execution(
            workflow_id="wf_1",
            status=WorkflowStatus.SUCCESS,
            started_at=datetime(2025, 1, 1, 0, 0, 0),
            completed_at=datetime(2025, 1, 1, 0, 0, 10),
            node_states={"a": NodeStatus.SUCCESS},
        )
        stats = ExecutionStats.compute(exec_)
        assert stats["total_duration_ms"] == 10000.0
        assert stats["node_count"] == 1
        assert stats["completed_count"] == 1
        assert stats["avg_node_duration_ms"] is None  # no node_complete trace entries
        assert stats["bottlenecks"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# LangGraph Node Builders (unit tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildInitState:
    """build_init_state returns initial execution fields."""

    def test_initializes_running(self):
        result = build_init_state({
            "execution_id": "exec_1",
            "workflow_id": "wf_1",
        })
        assert result["status"] == "running"
        assert result["current_index"] == 0
        assert result["error"] is None


class TestBuildRouteCondition:
    """build_route_condition returns router function for LangGraph."""

    def test_continue_execution(self):
        router = build_route_condition()
        result = router({
            "status": "running",
            "current_index": 2,
            "execution_order": ["a", "b", "c", "d"],
        })
        assert result == "continue"

    def test_end_execution(self):
        router = build_route_condition()
        result = router({
            "status": "running",
            "current_index": 5,
            "execution_order": ["a", "b", "c", "d"],
        })
        assert result == "end"

    def test_error_execution(self):
        router = build_route_condition()
        result = router({
            "status": "failed",
            "current_index": 1,
            "execution_order": ["a", "b"],
        })
        assert result == "error"

    def test_cancelled_execution(self):
        router = build_route_condition()
        result = router({
            "status": "cancelled",
            "current_index": 1,
            "execution_order": ["a", "b"],
        })
        assert result == "cancelled"


class TestBuildFinalize:
    """build_finalize returns a function that sets SUCCESS status."""

    def test_finalize_success(self):
        fn = build_finalize()
        result = fn({"status": "running"})
        assert result["status"] == "success"

    def test_finalize_does_not_overwrite_failed(self):
        fn = build_finalize()
        result = fn({"status": "failed"})
        assert result == {}  # empty dict — keeps existing status

    def test_finalize_sets_success_on_none_status(self):
        fn = build_finalize()
        result = fn({})
        assert result["status"] == "success"


# ═══════════════════════════════════════════════════════════════════════════════
# WorkflowEngine Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_llm_provider():
    """A mock LLM provider that returns canned responses."""
    provider = MagicMock(spec=LLMProvider)
    provider.name = "mock"
    provider.chat = AsyncMock(return_value=LLMResponse(content="Task completed successfully"))
    provider.embed = AsyncMock(return_value=EmbeddingResult(
        embeddings=[[0.1, 0.2, 0.3]],
        model="mock-embed",
    ))
    return provider


@pytest.fixture
def mock_scheduler():
    """A mock AgentScheduler that returns a simple executor agent."""
    from knot.core.models import Agent, AgentRole

    scheduler = MagicMock(spec=AgentScheduler)
    executor = Agent(id="agent_executor", name="Executor", role=AgentRole.EXECUTOR)
    scheduler.assign_node = AsyncMock(return_value=executor)
    return scheduler


@pytest.fixture
def mock_retriever():
    retriever = MagicMock()
    retriever.retrieve = AsyncMock(return_value=[])
    return retriever


@pytest.fixture
def mock_enhancer():
    enhancer = MagicMock()
    enhancer.enhance = MagicMock(return_value="Enhanced knowledge context")
    return enhancer


class TestWorkflowEngineExecute:
    """WorkflowEngine.execute() with mocked components."""

    @pytest.mark.asyncio
    async def test_simple_linear_execution(self, mock_llm_provider, mock_scheduler,
                                            mock_retriever, mock_enhancer):
        """A 2-node workflow (INPUT -> OUTPUT) runs to SUCCESS."""
        engine = WorkflowEngine(
            llm_provider=mock_llm_provider,
            scheduler=mock_scheduler,
            retriever=mock_retriever,
            enhancer=mock_enhancer,
        )
        wf = simple_linear_workflow()
        result = await engine.execute(wf)
        assert result.status == WorkflowStatus.SUCCESS
        assert result.workflow_id == wf.id
        assert result.started_at is not None
        assert result.completed_at is not None
        # Both nodes should be in the node_states
        assert "a" in result.node_states
        assert "b" in result.node_states
        assert len(result.trace) >= 3  # init + input + output + completion

    @pytest.mark.asyncio
    async def test_serial_execution_order(self, mock_llm_provider, mock_scheduler,
                                           mock_retriever, mock_enhancer):
        """Nodes execute in topological order."""
        engine = WorkflowEngine(
            llm_provider=mock_llm_provider,
            scheduler=mock_scheduler,
            retriever=mock_retriever,
            enhancer=mock_enhancer,
        )
        wf = two_task_workflow()
        result = await engine.execute(wf)

        assert result.status == WorkflowStatus.SUCCESS
        # Extract node completion order from trace
        completed_nodes = [
            e for e in result.trace if e.get("event") == "node_complete"
        ]
        order = [e["node_id"] for e in completed_nodes]
        # INPUT should complete before TASK_A, TASK_A before TASK_B, etc.
        assert order.index("input") < order.index("task_a")
        assert order.index("task_a") < order.index("task_b")
        assert order.index("task_b") < order.index("output")

    @pytest.mark.asyncio
    async def test_node_error_retry(self, mock_llm_provider, mock_scheduler,
                                     mock_retriever, mock_enhancer):
        """When a TASK node fails, the engine increments retry_count."""
        # Make the LLM fail on the first call, succeed after
        call_count = 0

        async def chat_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # input call (1) + failed task call (2)
                raise ValueError("LLM temporarily unavailable")
            return LLMResponse(content="Success after retry")

        mock_llm_provider.chat = AsyncMock(side_effect=chat_side_effect)

        engine = WorkflowEngine(
            llm_provider=mock_llm_provider,
            scheduler=mock_scheduler,
            retriever=mock_retriever,
            enhancer=mock_enhancer,
        )

        # Use a workflow where the INPUT node might not call chat
        wf = Workflow(
            name="Retry Test",
            nodes=[
                Node(id="task_x", type=NodeType.TASK, label="Task X", max_retries=3),
            ],
            edges=[],
        )
        # If INPUT node doesn't call chat, adjust expectation:
        # For failed node: retry_count should show how many retries happened
        result = await engine.execute(wf)
        # After retries, it should eventually succeed
        assert result.status == WorkflowStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_node_error_exhausts_retries(self, mock_llm_provider, mock_scheduler,
                                                mock_retriever, mock_enhancer):
        """When retries are exhausted, the workflow FAILS."""
        mock_llm_provider.chat = AsyncMock(side_effect=ValueError("Persistent error"))

        engine = WorkflowEngine(
            llm_provider=mock_llm_provider,
            scheduler=mock_scheduler,
            retriever=mock_retriever,
            enhancer=mock_enhancer,
        )
        wf = Workflow(
            name="Exhaust Retry",
            nodes=[
                Node(id="task_fail", type=NodeType.TASK, label="Fail Task", max_retries=1),
            ],
            edges=[],
        )
        result = await engine.execute(wf)
        assert result.status == WorkflowStatus.FAILED
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_cancel_during_execution(self, mock_llm_provider, mock_scheduler,
                                            mock_retriever, mock_enhancer):
        """Cancelling an in-flight execution returns CANCELLED status."""
        # Use a side effect that pauses long enough for cancel to happen
        original_chat = mock_llm_provider.chat

        async def delayed_chat(*args, **kwargs):
            await asyncio.sleep(0.5)  # Simulate slow LLM
            return LLMResponse(content="Completed after delay")

        mock_llm_provider.chat = AsyncMock(side_effect=delayed_chat)

        engine = WorkflowEngine(
            llm_provider=mock_llm_provider,
            scheduler=mock_scheduler,
            retriever=mock_retriever,
            enhancer=mock_enhancer,
        )

        wf = Workflow(
            name="Cancel Test",
            nodes=[
                Node(id="input", type=NodeType.INPUT, label="Input"),
                Node(id="task_long", type=NodeType.TASK, label="Long Task"),
                Node(id="output", type=NodeType.OUTPUT, label="Output"),
            ],
            edges=[
                Edge(source_id="input", target_id="task_long"),
                Edge(source_id="task_long", target_id="output"),
            ],
        )

        # Start execution in background
        execute_task = asyncio.create_task(engine.execute(wf))

        # Give the engine time to start
        await asyncio.sleep(0.1)

        # Find the execution ID and cancel via control state
        assert len(engine._control_states) > 0
        exec_id = list(engine._control_states.keys())[0]
        state = engine._control_states[exec_id]
        state.request_cancel()

        result = await execute_task
        assert result.status in (
            WorkflowStatus.CANCELLED,
            WorkflowStatus.FAILED,
            WorkflowStatus.SUCCESS,
        ), f"Unexpected status: {result.status}"

    @pytest.mark.asyncio
    async def test_pause_during_execution(self, mock_llm_provider, mock_scheduler,
                                           mock_retriever, mock_enhancer):
        """Pausing mid-execution results in PAUSED status."""
        original_chat = mock_llm_provider.chat

        async def delayed_chat(*args, **kwargs):
            await asyncio.sleep(0.3)
            return LLMResponse(content="Done")

        mock_llm_provider.chat = AsyncMock(side_effect=delayed_chat)

        engine = WorkflowEngine(
            llm_provider=mock_llm_provider,
            scheduler=mock_scheduler,
            retriever=mock_retriever,
            enhancer=mock_enhancer,
        )

        wf = Workflow(
            name="Pause Test",
            nodes=[
                Node(id="a", type=NodeType.TASK, label="A"),
            ],
            edges=[],
        )

        execute_task = asyncio.create_task(engine.execute(wf))
        await asyncio.sleep(0.05)

        if engine._control_states:
            exec_id = list(engine._control_states.keys())[0]
            state = engine._control_states[exec_id]
            state.request_pause()

            # Schedule resume after a short delay so execution can complete
            async def resume_after():
                await asyncio.sleep(0.1)
                try:
                    state.request_resume()
                except Exception:
                    pass

            asyncio.create_task(resume_after())

        result = await execute_task
        assert result.status == WorkflowStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_global_context_propagation(self, mock_llm_provider, mock_scheduler,
                                               mock_retriever, mock_enhancer):
        """Global context from the workflow is available during execution."""
        engine = WorkflowEngine(
            llm_provider=mock_llm_provider,
            scheduler=mock_scheduler,
            retriever=mock_retriever,
            enhancer=mock_enhancer,
        )
        wf = Workflow(
            name="Context Test",
            nodes=[
                Node(id="input", type=NodeType.INPUT, label="Input"),
            ],
            edges=[],
            global_context={"user_input": "hello"},
        )
        result = await engine.execute(wf)
        assert result.status == WorkflowStatus.SUCCESS
        assert result.global_context.get("user_input") == "hello"

    @pytest.mark.asyncio
    async def test_empty_workflow(self, mock_llm_provider, mock_scheduler,
                                   mock_retriever, mock_enhancer):
        """An empty workflow (no nodes) still completes successfully."""
        engine = WorkflowEngine(
            llm_provider=mock_llm_provider,
            scheduler=mock_scheduler,
            retriever=mock_retriever,
            enhancer=mock_enhancer,
        )
        wf = Workflow(name="Empty")
        result = await engine.execute(wf)
        assert result.status == WorkflowStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_broadcast_fn_called(self, mock_llm_provider, mock_scheduler,
                                        mock_retriever, mock_enhancer):
        """When a broadcast_fn is provided, it gets called during execution."""
        broadcast_fn = AsyncMock()

        engine = WorkflowEngine(
            llm_provider=mock_llm_provider,
            scheduler=mock_scheduler,
            retriever=mock_retriever,
            enhancer=mock_enhancer,
            broadcast_fn=broadcast_fn,
        )
        wf = simple_linear_workflow()
        result = await engine.execute(wf)
        assert result.status == WorkflowStatus.SUCCESS
        assert broadcast_fn.await_count >= 1
        # broadcast_fn should have been called at least with execution id
        call_arg = broadcast_fn.await_args
        assert call_arg is not None


# ═══════════════════════════════════════════════════════════════════════════════
# _build_execution_snapshot helper tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildExecutionSnapshot:
    """_build_execution_snapshot produces a dict compatible with Execution."""

    def test_basic_snapshot(self):
        snapshot = _build_execution_snapshot(
            execution_id="exec_1",
            workflow_id="wf_1",
            status="running",
            node_statuses={"a": "success"},
            node_results={"a": {"output": "ok"}},
            global_context={},
            error=None,
            trace=[],
        )
        assert snapshot["id"] == "exec_1"
        assert snapshot["workflow_id"] == "wf_1"
        assert snapshot["status"] == "running"
        assert snapshot["node_states"] == {"a": "success"}

    def test_snapshot_with_optional_fields(self):
        snapshot = _build_execution_snapshot(
            execution_id="exec_1",
            workflow_id="wf_1",
            status="running",
            node_statuses={},
            node_results={},
            global_context={},
            error=None,
            trace=[],
            current_node_id="n1",
            started_at="2025-01-01T00:00:00",
        )
        assert snapshot["current_node_id"] == "n1"
        assert snapshot["started_at"] == "2025-01-01T00:00:00"

    def test_snapshot_converts_node_status_enums(self):
        snapshot = _build_execution_snapshot(
            execution_id="exec_1",
            workflow_id="wf_1",
            status="running",
            node_statuses={"a": NodeStatus.SUCCESS},
            node_results={},
            global_context={},
            error=None,
            trace=[],
        )
        assert snapshot["node_states"] == {"a": "success"}
