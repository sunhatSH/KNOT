"""LangGraph-based workflow execution engine."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Literal, TypedDict

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
from knot.knowledge_layer.enhancer import ContextEnhancer
from knot.knowledge_layer.retriever import HybridRetriever
from knot.llm import LLMProvider
from knot.llm.base import LLMMessage
from knot.orchestration_layer.multi_agent import dispatch_multi_agent
from knot.orchestration_layer.scheduler import AgentScheduler
from knot.orchestration_layer.state import WorkflowState

logger = logging.getLogger(__name__)


# ─── LangGraph State Schema ──────────────────────────────────────────────


class LangGraphState(TypedDict):
    """State schema for the LangGraph workflow executor."""

    workflow_json: str  # Serialized workflow definition
    execution_id: str
    current_node_id: str | None
    execution_order: list[str]  # Topological node order
    current_index: int  # Index in execution_order
    node_statuses: dict[str, str]
    node_results: dict[str, Any]
    global_context: dict[str, Any]
    status: str
    error: str | None
    trace: list[dict[str, Any]]


# ─── LangGraph Nodes ─────────────────────────────────────────────────────


def build_init_state(state: LangGraphState) -> dict[str, Any]:
    """Initialize the workflow execution state."""
    logger.info("Initializing execution %s", state["execution_id"])
    return {
        "status": WorkflowStatus.RUNNING.value,
        "current_index": 0,
        "error": None,
    }


def build_execute_node(
    llm_provider: LLMProvider,
    scheduler: AgentScheduler,
    retriever: HybridRetriever | None = None,
    enhancer: ContextEnhancer | None = None,
    workflow_state: WorkflowState | None = None,
):
    """Create a LangGraph node function that executes the current workflow node."""

    _ws = workflow_state  # Local ref for closure

    async def execute_node(state: LangGraphState) -> dict[str, Any]:
        # ── Control point: before each superstep ──
        if _ws is not None:
            try:
                await _ws.wait_if_paused()
            except asyncio.CancelledError:
                node_id = state.get("current_node_id", "")
                new_trace = list(state.get("trace", []))
                new_trace.append(
                    TraceEntry(
                        event="info",
                        node_id=node_id,
                        message="Workflow execution was cancelled",
                    ).model_dump()
                )
                return {
                    "status": WorkflowStatus.CANCELLED.value,
                    "trace": new_trace,
                }

        workflow = Workflow(**json.loads(state["workflow_json"]))
        order = state["execution_order"]
        idx = state["current_index"]

        if idx >= len(order):
            return {"status": WorkflowStatus.SUCCESS.value}

        node_id = order[idx]
        node = workflow.get_node(node_id)
        if not node:
            logger.warning("Node %s not found, skipping", node_id)
            return {"current_index": idx + 1}

        logger.info("Executing node: %s (%s)", node.label or node_id, node.type.value)
        node.status = NodeStatus.RUNNING
        node.started_at = datetime.now()
        start_time = time.monotonic()

        # Build trace entries for this step
        new_trace = list(state.get("trace", []))

        # Node start trace
        new_trace.append(
            TraceEntry(
                event="node_start",
                node_id=node_id,
                node_label=node.label or node_id,
                message=f"Starting execution of node '{node.label or node_id}'",
            ).model_dump()
        )

        # Internal trace collector for sub-operations
        internal_trace: list[dict[str, Any]] = []

        try:
            result = await _execute_node_logic(
                node=node,
                workflow=workflow,
                state=state,
                llm_provider=llm_provider,
                scheduler=scheduler,
                retriever=retriever,
                enhancer=enhancer,
                _trace_entries=internal_trace,
            )

            # ── Control point: after node execution ──
            if _ws is not None:
                try:
                    await _ws.wait_if_paused()
                except asyncio.CancelledError:
                    # Node completed, but workflow is cancelled — record
                    # the node result, then finish as cancelled.
                    node.status = NodeStatus.SUCCESS
                    node.result = result
                    node.completed_at = datetime.now()

                    new_trace.extend(internal_trace)
                    new_trace.append(
                        TraceEntry(
                            event="info",
                            node_id=node_id,
                            node_label=node.label or node_id,
                            message="Workflow execution was cancelled",
                        ).model_dump()
                    )

                    new_node_statuses = dict(state.get("node_statuses", {}))
                    new_node_statuses[node_id] = NodeStatus.SUCCESS.value

                    new_node_results = dict(state.get("node_results", {}))
                    new_node_results[node_id] = result

                    new_context = dict(state.get("global_context", {}))
                    if isinstance(result, dict):
                        new_context.update(result)

                    return {
                        "status": WorkflowStatus.CANCELLED.value,
                        "node_statuses": new_node_statuses,
                        "node_results": new_node_results,
                        "global_context": new_context,
                        "current_index": idx + 1,
                        "trace": new_trace,
                    }

            end_time = time.monotonic()
            duration_ms = round((end_time - start_time) * 1000, 2)

            node.status = NodeStatus.SUCCESS
            node.result = result
            node.completed_at = datetime.now()

            new_trace.extend(internal_trace)

            # Node complete trace
            new_trace.append(
                TraceEntry(
                    event="node_complete",
                    node_id=node_id,
                    node_label=node.label or node_id,
                    message=f"Node '{node.label or node_id}' completed successfully",
                    duration_ms=duration_ms,
                    metadata={"result_summary": str(result)[:200]},
                ).model_dump()
            )

            new_node_statuses = dict(state.get("node_statuses", {}))
            new_node_statuses[node_id] = NodeStatus.SUCCESS.value

            new_node_results = dict(state.get("node_results", {}))
            new_node_results[node_id] = result

            new_context = dict(state.get("global_context", {}))
            if isinstance(result, dict):
                new_context.update(result)

            return {
                "node_statuses": new_node_statuses,
                "node_results": new_node_results,
                "global_context": new_context,
                "current_index": idx + 1,
                "trace": new_trace,
            }

        except asyncio.CancelledError:
            # CancelledError raised from _execute_node_logic (unlikely but
            # possible with external task cancellation).
            new_trace.extend(internal_trace)
            new_trace.append(
                TraceEntry(
                    event="info",
                    node_id=node_id,
                    node_label=node.label or node_id,
                    message="Workflow execution was cancelled",
                ).model_dump()
            )
            return {
                "status": WorkflowStatus.CANCELLED.value,
                "trace": new_trace,
            }

        except Exception as e:
            end_time = time.monotonic()
            duration_ms = round((end_time - start_time) * 1000, 2)

            node.status = NodeStatus.FAILED
            node.error = str(e)
            node.completed_at = datetime.now()
            logger.error("Node %s failed: %s", node_id, e)

            new_trace.extend(internal_trace)

            # Node failed trace
            new_trace.append(
                TraceEntry(
                    event="node_failed",
                    node_id=node_id,
                    node_label=node.label or node_id,
                    message=f"Node '{node.label or node_id}' failed: {e}",
                    duration_ms=duration_ms,
                    metadata={"error": str(e)},
                ).model_dump()
            )

            new_node_statuses = dict(state.get("node_statuses", {}))
            new_node_statuses[node_id] = NodeStatus.FAILED.value

            if node.max_retries > 0 and node.retry_count < node.max_retries:
                node.retry_count += 1
                logger.info("Retrying node %s (attempt %d/%d)", node_id, node.retry_count, node.max_retries)
                return {
                    "node_statuses": new_node_statuses,
                    "current_index": idx,  # Re-run same node
                    "trace": new_trace,
                }

            return {
                "status": WorkflowStatus.FAILED.value,
                "error": str(e),
                "node_statuses": new_node_statuses,
                "trace": new_trace,
            }

    return execute_node


def build_route_condition():
    """Create a LangGraph router that checks execution status."""

    def route_condition(
        state: LangGraphState,
    ) -> Literal["continue", "end", "error", "cancelled"]:
        status = state.get("status", WorkflowStatus.RUNNING.value)
        if status == WorkflowStatus.FAILED.value:
            return "error"
        if status == WorkflowStatus.CANCELLED.value:
            return "cancelled"
        idx = state.get("current_index", 0)
        order = state.get("execution_order", [])
        if idx >= len(order):
            return "end"
        return "continue"

    return route_condition


def build_finalize():
    """Create a LangGraph node that finalizes execution."""

    def finalize(state: LangGraphState) -> dict[str, Any]:
        status = state.get("status", WorkflowStatus.RUNNING.value)
        if status != WorkflowStatus.FAILED.value:
            return {"status": WorkflowStatus.SUCCESS.value}
        return {}

    return finalize


# ─── Node Execution Logic ────────────────────────────────────────────────


async def _execute_node_logic(
    node: Node,
    workflow: Workflow,
    state: LangGraphState,
    llm_provider: LLMProvider,
    scheduler: AgentScheduler,
    retriever: HybridRetriever | None,
    enhancer: ContextEnhancer | None,
    _trace_entries: list[dict[str, Any]] | None = None,
) -> Any:
    """Execute the logic for a single workflow node based on its type."""

    context = state.get("global_context", {})

    if node.type == NodeType.INPUT:
        return {"data": context.get("user_input", "")}

    if node.type == NodeType.OUTPUT:
        return {"output": dict(context)}

    if node.type == NodeType.CONDITION:
        messages = [
            LLMMessage(
                role="system",
                content=f"Evaluate this condition based on current context:\n{node.condition or 'True'}",
            ),
            LLMMessage(role="user", content=f"Context: {json.dumps(context, ensure_ascii=False)}"),
        ]
        response = await llm_provider.chat(messages, temperature=0.1)
        result_text = response.content.strip().lower()
        return {"condition_met": result_text.startswith("true") or result_text.startswith("yes")}

    if node.type == NodeType.TASK:
        # Determine multi-agent mode from node config
        from knot.core.models import MultiAgentMode

        mode = MultiAgentMode(node.config.get("multi_agent_mode", "single"))
        is_multi = mode in (MultiAgentMode.PARALLEL, MultiAgentMode.DEBATE)

        input_data = {k: context.get(v, v) for k, v in node.inputs.items()}
        task_description = node.label or "Execute task"
        task_input = json.dumps({"input": input_data, "context": context}, ensure_ascii=False)

        # Knowledge enhancement
        knowledge_context = ""
        if retriever and enhancer and node.config.get("knowledge_enabled", True):
            query = str(input_data.get("query", input_data.get("input", "")))
            chunks = await retriever.retrieve(
                collection_name=node.config.get("knowledge_base", "default"),
                query=query,
            )
            chunks_count = len(chunks)
            if _trace_entries is not None:
                _trace_entries.append(
                    TraceEntry(
                        event="knowledge_retrieval",
                        node_id=node.id,
                        node_label=node.label or node.id,
                        message=f"Retrieved {chunks_count} knowledge chunk(s)",
                        metadata={
                            "query": query,
                            "chunks_count": chunks_count,
                        },
                    ).model_dump()
                )
            if chunks:
                knowledge_context = enhancer.enhance(query, chunks)
                logger.info("Enhanced node %s with %d knowledge chunks", node.id, chunks_count)

        if is_multi:
            # Multi-agent execution (parallel or debate)
            team = await scheduler.assign_team(node, context)
            if len(team) < 2:
                logger.warning("Multi-agent mode %s needs ≥2 agents, got %d. Falling back to single.", mode, len(team))

            full_task = f"{task_description}\nInput: {task_input}"
            if knowledge_context:
                full_task = f"{full_task}\n\nBackground knowledge:\n{knowledge_context}"

            result = await dispatch_multi_agent(
                mode=mode,
                task=full_task,
                agents=team if len(team) >= 2 else [team[0]] if team else [],
                context=context,
                llm_provider=llm_provider,
                config=node.config,
            )
            return {**input_data, **result}

        # Single agent execution
        agent = await scheduler.assign_node(node, context)
        agent_prompt = agent.system_prompt if agent else "You are a helpful AI assistant."
        system_content = agent_prompt
        if knowledge_context:
            system_content = f"{agent_prompt}\n\n{knowledge_context}"

        messages = [
            LLMMessage(role="system", content=system_content),
            LLMMessage(
                role="user",
                content=f"Task: {task_description}\nInput: {task_input}",
            ),
        ]
        response = await llm_provider.chat(messages, model=agent.model if agent else None)
        return {"output": response.content, **input_data}

    if node.type == NodeType.LOOP:
        iterations = node.config.get("max_iterations", 3)
        results = []
        for i in range(iterations):
            loop_context = {**context, "iteration": i, "previous_results": results}
            messages = [
                LLMMessage(
                    role="system",
                    content=f"Execute this loop iteration {i + 1}/{iterations}. "
                    f"Goal: {node.label}. Stop when done.",
                ),
                LLMMessage(
                    role="user",
                    content=f"Context: {json.dumps(loop_context, ensure_ascii=False)}",
                ),
            ]
            response = await llm_provider.chat(messages)
            results.append(response.content)
            if "COMPLETE" in response.content.upper():
                break
        return {"loop_results": results, "iterations": len(results)}

    return {"output": f"Executed node: {node.label}"}


# ─── Graph Builder ──────────────────────────────────────────────────────


class WorkflowEngine:
    """LangGraph-based workflow execution engine.

    Wraps a LangGraph StateGraph that processes workflow DAG nodes
    in topological order, handling serial and conditional execution.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        scheduler: AgentScheduler,
        retriever: HybridRetriever | None = None,
        enhancer: ContextEnhancer | None = None,
    ):
        self._llm_provider = llm_provider
        self._scheduler = scheduler
        self._retriever = retriever
        self._enhancer = enhancer
        # Map execution_id -> WorkflowState for in-flight executions.
        # Control API endpoints (pause/resume/cancel) look up the state
        # from this dict to signal the running task.
        self._control_states: dict[str, WorkflowState] = {}

    async def execute(self, workflow: Workflow) -> Execution:
        """Execute a workflow and return the execution result."""
        from langgraph.graph import END, StateGraph

        execution = Execution(workflow_id=workflow.id)
        execution.started_at = datetime.now()
        order = [n.id for n in workflow.topological_sort()]

        logger.info("Starting workflow '%s' exec=%s nodes=%d", workflow.name, execution.id, len(order))

        # Initial trace entry
        initial_trace = [
            TraceEntry(
                event="info",
                message=f"Workflow '{workflow.name}' started with {len(order)} node(s)",
            ).model_dump()
        ]

        # ── Create and register WorkflowState for control API ──
        workflow_state = WorkflowState(execution)
        self._control_states[execution.id] = workflow_state

        try:
            # Build LangGraph
            graph = StateGraph(LangGraphState)

            graph.add_node("init", build_init_state)
            graph.add_node("execute", build_execute_node(
                llm_provider=self._llm_provider,
                scheduler=self._scheduler,
                retriever=self._retriever,
                enhancer=self._enhancer,
                workflow_state=workflow_state,
            ))
            graph.add_node("finalize", build_finalize())

            graph.set_entry_point("init")
            graph.add_edge("init", "execute")

            graph.add_conditional_edges(
                "execute",
                build_route_condition(),
                {
                    "continue": "execute",
                    "end": "finalize",
                    "error": "finalize",
                    "cancelled": END,
                },
            )
            graph.add_edge("finalize", END)

            app = graph.compile()

            # Run
            initial_state: LangGraphState = {
                "workflow_json": workflow.model_dump_json(),
                "execution_id": execution.id,
                "current_node_id": None,
                "execution_order": order,
                "current_index": 0,
                "node_statuses": {},
                "node_results": {},
                "global_context": dict(workflow.global_context),
                "status": WorkflowStatus.PENDING.value,
                "error": None,
                "trace": initial_trace,
            }

            result_state = await app.ainvoke(initial_state)

            # Map result back to Execution model
            execution.status = WorkflowStatus(
                result_state.get("status", WorkflowStatus.FAILED.value)
            )
            execution.node_states = {
                k: NodeStatus(v) if isinstance(v, str) else v
                for k, v in result_state.get("node_statuses", {}).items()
            }
            execution.global_context = result_state.get("global_context", {})
            execution.error = result_state.get("error")

            # When cancelled, mark any remaining pending nodes as SKIPPED
            if execution.status == WorkflowStatus.CANCELLED:
                for node_id in order:
                    if node_id not in execution.node_states:
                        execution.node_states[node_id] = NodeStatus.SKIPPED

            # Add final trace entries
            final_trace = list(result_state.get("trace", []))
            final_trace.append(
                TraceEntry(
                    event="info",
                    message=f"Workflow '{workflow.name}' completed with status {execution.status.value}",
                ).model_dump()
            )
            execution.trace = final_trace
            execution.completed_at = datetime.now()

            logger.info(
                "Workflow '%s' completed: %s", workflow.name, execution.status.value
            )
            return execution

        finally:
            self._control_states.pop(execution.id, None)
