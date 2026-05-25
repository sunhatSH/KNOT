"""Core domain models for KNOT."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ─── Enums ────────────────────────────────────────────────────────────────


class NodeType(str, Enum):
    """Types of nodes in a workflow DAG."""

    TASK = "task"
    CONDITION = "condition"
    PARALLEL = "parallel"
    LOOP = "loop"
    INPUT = "input"
    OUTPUT = "output"


class ExecutionMode(str, Enum):
    """Workflow execution mode."""

    SERIAL = "serial"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    LOOP = "loop"


class NodeStatus(str, Enum):
    """Execution status of a single node."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowStatus(str, Enum):
    """Overall workflow execution status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class AgentRole(str, Enum):
    """Role assigned to an agent in collaborative execution."""

    PLANNER = "planner"
    EXECUTOR = "executor"
    VALIDATOR = "validator"
    SUMMARIZER = "summarizer"


# ─── Core Data Models ─────────────────────────────────────────────────────


class Node(BaseModel):
    """A single node in a workflow DAG."""

    id: str = Field(default_factory=lambda: f"node_{uuid.uuid4().hex[:8]}")
    type: NodeType = NodeType.TASK
    label: str = ""
    agent_id: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    inputs: dict[str, str] = Field(default_factory=dict)
    outputs: dict[str, str] = Field(default_factory=dict)
    condition: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 300

    # Runtime state
    status: NodeStatus = NodeStatus.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class Edge(BaseModel):
    """A directed edge between two nodes in a DAG."""

    id: str = Field(default_factory=lambda: f"edge_{uuid.uuid4().hex[:8]}")
    source_id: str
    target_id: str
    label: str = ""
    condition: str | None = None


class Workflow(BaseModel):
    """A workflow definition represented as a DAG."""

    id: str = Field(default_factory=lambda: f"wf_{uuid.uuid4().hex[:8]}")
    name: str
    description: str = ""
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    global_context: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    tags: list[str] = Field(default_factory=list)

    def get_node(self, node_id: str) -> Node | None:
        return next((n for n in self.nodes if n.id == node_id), None)

    def get_dependencies(self, node_id: str) -> list[str]:
        """Return IDs of nodes that the given node depends on."""
        return [e.source_id for e in self.edges if e.target_id == node_id]

    def get_dependents(self, node_id: str) -> list[str]:
        """Return IDs of nodes that depend on the given node."""
        return [e.target_id for e in self.edges if e.source_id == node_id]

    def topological_sort(self) -> list[Node]:
        """Return nodes in topological order."""
        in_degree: dict[str, int] = {n.id: 0 for n in self.nodes}
        for e in self.edges:
            in_degree[e.target_id] = in_degree.get(e.target_id, 0) + 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        sorted_nodes = []

        while queue:
            nid = queue.pop(0)
            node = self.get_node(nid)
            if node:
                sorted_nodes.append(node)
            for dep in self.get_dependents(nid):
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    queue.append(dep)

        return sorted_nodes


# ─── Agent ────────────────────────────────────────────────────────────────


class Agent(BaseModel):
    """An AI agent that can execute workflow tasks."""

    id: str = Field(default_factory=lambda: f"agent_{uuid.uuid4().hex[:8]}")
    name: str
    role: AgentRole = AgentRole.EXECUTOR
    system_prompt: str = ""
    model: str = "deepseek-chat"
    tools: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)


# ─── Execution ────────────────────────────────────────────────────────────


class Execution(BaseModel):
    """An execution run of a workflow."""

    id: str = Field(default_factory=lambda: f"exec_{uuid.uuid4().hex[:8]}")
    workflow_id: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    node_states: dict[str, NodeStatus] = Field(default_factory=dict)
    global_context: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    trace: list[dict[str, Any]] = Field(default_factory=list)


# ─── Knowledge ────────────────────────────────────────────────────────────


class KnowledgeBase(BaseModel):
    """A knowledge base for RAG."""

    id: str = Field(default_factory=lambda: f"kb_{uuid.uuid4().hex[:8]}")
    name: str
    description: str = ""
    embedding_model: str = "deepseek-embedding"
    collection_name: str = ""
    chunk_size: int = 512
    chunk_overlap: int = 64


class KnowledgeChunk(BaseModel):
    """A chunk of text from a knowledge document."""

    id: str = ""
    document_id: str = ""
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = None
    score: float = 0.0


# ─── Tool ─────────────────────────────────────────────────────────────────


class ToolDefinition(BaseModel):
    """Definition of a tool that can be called during workflow execution."""

    id: str = Field(default_factory=lambda: f"tool_{uuid.uuid4().hex[:8]}")
    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
