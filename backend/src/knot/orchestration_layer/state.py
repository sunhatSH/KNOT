"""State management for workflow execution."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from knot.core.models import Execution, NodeStatus, TraceEntry, WorkflowStatus


class WorkflowState:
    """Manages the state of a running workflow execution.

    Provides a centralized store for node results, global context,
    and execution metadata that agents can read/write during execution.

    Also provides execution control — pause, resume, and cancel —
    via an ``asyncio.Event``-based mechanism.
    """

    def __init__(self, execution: Execution):
        self._execution = execution
        # Event is SET when execution should continue (running),
        # CLEAR when execution should pause.
        self._control_event = asyncio.Event()
        self._control_event.set()  # Start in running state
        self._cancelled: bool = False

    @property
    def execution_id(self) -> str:
        return self._execution.id

    @property
    def workflow_id(self) -> str:
        return self._execution.workflow_id

    @property
    def status(self) -> WorkflowStatus:
        return self._execution.status

    @status.setter
    def status(self, value: WorkflowStatus) -> None:
        self._execution.status = value

    @property
    def execution(self) -> Execution:
        """Return the underlying Execution model."""
        return self._execution

    # ── Control API ──────────────────────────────────────────────────────────

    def request_pause(self) -> None:
        """Request pause at the next safe point between node executions."""
        self._control_event.clear()
        self._execution.status = WorkflowStatus.PAUSED

    def request_resume(self) -> None:
        """Resume a paused execution."""
        self._control_event.set()
        self._execution.status = WorkflowStatus.RUNNING

    def request_cancel(self) -> None:
        """Request cancellation. Unblocks any paused state."""
        self._cancelled = True
        self._control_event.set()  # Unblock any waiter so it can exit

    def is_cancelled(self) -> bool:
        """Check whether cancellation has been requested."""
        return self._cancelled

    async def wait_if_paused(self) -> None:
        """Block if paused, pass through if running.

        Called between node executions. If cancellation has been
        requested, raises ``asyncio.CancelledError`` so the caller
        can abort gracefully.
        """
        await self._control_event.wait()
        if self._cancelled:
            raise asyncio.CancelledError()

    def reset_control(self) -> None:
        """Reset all control flags so the state can be reused."""
        self._control_event.set()
        self._cancelled = False

    def get_global(self, key: str, default: Any = None) -> Any:
        """Read a value from global context."""
        return self._execution.global_context.get(key, default)

    def set_global(self, key: str, value: Any) -> None:
        """Write a value to global context."""
        self._execution.global_context[key] = value

    def update_global(self, updates: dict[str, Any]) -> None:
        """Merge multiple values into global context."""
        self._execution.global_context.update(updates)

    def get_node_result(self, node_id: str) -> Any:
        """Get the result of a completed node."""
        return self._execution.node_states.get(node_id)

    def set_node_result(self, node_id: str, result: Any) -> None:
        """Set the result of a completed node."""
        self._execution.node_states[node_id] = result

    # ─── Structured Tracing ─────────────────────────────────────────────────

    def add_trace(
        self,
        event: str,
        message: str,
        node_id: str = "",
        node_label: str = "",
        duration_ms: float | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Add a structured trace entry for observability.

        Args:
            event: Event type (node_start, node_complete, node_failed,
                   node_skipped, branch, tool_call, knowledge_retrieval,
                   error, info).
            message: Human-readable description of the event.
            node_id: Optional ID of the associated node.
            node_label: Optional label of the associated node.
            duration_ms: Optional duration in milliseconds.
            metadata: Optional dictionary of additional data.
        """
        entry = TraceEntry(
            timestamp=datetime.now(),
            node_id=node_id,
            node_label=node_label,
            event=event,
            message=message,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )
        self._execution.trace.append(entry.model_dump())

    def trace_node_start(self, node_id: str, node_label: str) -> None:
        """Trace the start of a node execution."""
        self.add_trace(
            event="node_start",
            message=f"Starting execution of node '{node_label}'",
            node_id=node_id,
            node_label=node_label,
        )

    def trace_node_complete(
        self, node_id: str, node_label: str, duration_ms: float | None = None
    ) -> None:
        """Trace the successful completion of a node execution."""
        self.add_trace(
            event="node_complete",
            message=f"Node '{node_label}' completed successfully",
            node_id=node_id,
            node_label=node_label,
            duration_ms=duration_ms,
        )

    def trace_node_failed(
        self, node_id: str, node_label: str, error: str
    ) -> None:
        """Trace a node execution failure."""
        self.add_trace(
            event="node_failed",
            message=f"Node '{node_label}' failed: {error}",
            node_id=node_id,
            node_label=node_label,
            metadata={"error": error},
        )

    def trace_node_skipped(self, node_id: str, node_label: str) -> None:
        """Trace a skipped node."""
        self.add_trace(
            event="node_skipped",
            message=f"Node '{node_label}' was skipped",
            node_id=node_id,
            node_label=node_label,
        )

    def trace_tool_call(
        self,
        tool_name: str,
        params: dict | None = None,
        result: Any = None,
    ) -> None:
        """Trace a tool call during execution."""
        self.add_trace(
            event="tool_call",
            message=f"Tool '{tool_name}' called",
            metadata={
                "tool_name": tool_name,
                "params": params or {},
                "result_summary": str(result)[:200] if result is not None else None,
            },
        )

    def trace_knowledge_retrieval(
        self, query: str, chunks_count: int
    ) -> None:
        """Trace a knowledge retrieval operation."""
        self.add_trace(
            event="knowledge_retrieval",
            message=f"Retrieved {chunks_count} knowledge chunk(s)",
            metadata={
                "query": query,
                "chunks_count": chunks_count,
            },
        )

    def trace_info(self, message: str) -> None:
        """Trace an informational event."""
        self.add_trace(
            event="info",
            message=message,
        )

    # ─── Snapshot ──────────────────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        """Return a snapshot of current state for serialization."""
        return self._execution.model_dump()


class ExecutionStats:
    """Compute statistics from an execution."""

    @staticmethod
    def compute(execution: Execution) -> dict:
        """Compute execution statistics.

        Returns a dictionary with:
        - total_duration_ms: overall execution time
        - node_count: total nodes
        - completed_count: nodes with SUCCESS status
        - failed_count: nodes with FAILED status
        - skipped_count: nodes with SKIPPED status
        - avg_node_duration_ms: average time per completed node
        - timeline: list of (event, timestamp, duration_ms) for chart rendering
        - bottlenecks: nodes with highest duration
        """
        stats: dict[str, Any] = {}

        # Total duration
        if execution.started_at and execution.completed_at:
            total_ms = (
                execution.completed_at - execution.started_at
            ).total_seconds() * 1000
            stats["total_duration_ms"] = round(total_ms, 2)
        else:
            stats["total_duration_ms"] = None

        # Node counts
        node_states = execution.node_states
        stats["node_count"] = len(node_states)

        completed = 0
        failed = 0
        skipped = 0
        for s in node_states.values():
            status = NodeStatus(s) if isinstance(s, str) else s
            if status == NodeStatus.SUCCESS:
                completed += 1
            elif status == NodeStatus.FAILED:
                failed += 1
            elif status == NodeStatus.SKIPPED:
                skipped += 1

        stats["completed_count"] = completed
        stats["failed_count"] = failed
        stats["skipped_count"] = skipped

        # Timeline and bottlenecks from trace entries
        timeline: list[dict[str, Any]] = []
        node_durations: dict[str, float] = {}

        for entry in execution.trace:
            ts = entry.get("timestamp")
            duration = entry.get("duration_ms")
            event = entry.get("event", "")

            timeline.append({
                "event": event,
                "timestamp": ts,
                "duration_ms": duration,
            })

            # Collect per-node durations from node_complete events
            if event == "node_complete" and duration is not None:
                node_id = entry.get("node_id", "")
                if node_id:
                    existing = node_durations.get(node_id, 0)
                    node_durations[node_id] = max(existing, duration)

        stats["timeline"] = timeline

        # Average node duration
        durations = list(node_durations.values())
        if durations:
            stats["avg_node_duration_ms"] = round(
                sum(durations) / len(durations), 2
            )
        else:
            stats["avg_node_duration_ms"] = None

        # Bottlenecks (top 5 nodes by duration)
        bottlenecks = sorted(
            node_durations.items(), key=lambda x: x[1], reverse=True
        )[:5]
        stats["bottlenecks"] = [
            {"node_id": nid, "duration_ms": round(dur, 2)}
            for nid, dur in bottlenecks
        ]

        return stats
