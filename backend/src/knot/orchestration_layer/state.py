"""State management for workflow execution."""

from __future__ import annotations

from typing import Any

from knot.core.models import Execution, WorkflowStatus


class WorkflowState:
    """Manages the state of a running workflow execution.

    Provides a centralized store for node results, global context,
    and execution metadata that agents can read/write during execution.
    """

    def __init__(self, execution: Execution):
        self._execution = execution

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

    def add_trace(self, entry: dict[str, Any]) -> None:
        """Add a trace entry for observability."""
        self._execution.trace.append(entry)

    def snapshot(self) -> dict[str, Any]:
        """Return a snapshot of current state for serialization."""
        return self._execution.model_dump()
