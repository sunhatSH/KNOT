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
    RESEARCHER = "researcher"
    CODER = "coder"
    VALIDATOR = "validator"
    SUMMARIZER = "summarizer"


class MultiAgentMode(str, Enum):
    """Multi-agent collaboration mode for a workflow node."""

    SINGLE = "single"          # One agent executes (default)
    PARALLEL = "parallel"      # Multiple agents execute independently, merge results
    DEBATE = "debate"          # Multiple agents discuss iteratively until consensus


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
    versions: list[WorkflowVersion] = Field(default_factory=list)

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


# ─── Workflow Version ─────────────────────────────────────────────────────


class WorkflowVersion(BaseModel):
    """A snapshot version of a workflow at a point in time."""

    version: int = 1
    workflow_id: str
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    saved_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    saved_by: str = ""  # username
    message: str = ""   # commit message


# ─── User / Auth ──────────────────────────────────────────────────────────


class UserRole(str, Enum):
    """System user roles for RBAC."""

    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class User(BaseModel):
    """A system user."""

    id: str = Field(default_factory=lambda: f"user_{uuid.uuid4().hex[:8]}")
    username: str
    email: str = ""
    role: UserRole = UserRole.USER
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    # Note: password_hash is NOT included — it is only in the ORM model


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


# ─── Trace Entry ───────────────────────────────────────────────────────────


class TraceEntry(BaseModel):
    """A structured trace entry for workflow execution observability."""

    timestamp: datetime = Field(default_factory=datetime.now)
    node_id: str = ""
    node_label: str = ""
    event: str  # "node_start", "node_complete", "node_failed", "node_skipped", "branch", "tool_call", "knowledge_retrieval", "error", "info"
    message: str = ""
    duration_ms: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


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


# ─── Workflow Template ────────────────────────────────────────────────────


class WorkflowTemplate(BaseModel):
    """A reusable workflow template that can be instantiated into a Workflow."""

    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    name: str
    description: str = ""
    category: str = "general"  # general, ops, finance, medical, custom
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    usage_count: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ─── Tool ─────────────────────────────────────────────────────────────────


class ToolDefinition(BaseModel):
    """Definition of a tool that can be called during workflow execution."""

    id: str = Field(default_factory=lambda: f"tool_{uuid.uuid4().hex[:8]}")
    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)


# ─── Conversation Memory ──────────────────────────────────────────────────


class ConversationTurn(BaseModel):
    """A single turn in a conversation history."""

    id: str = Field(default_factory=lambda: f"turn_{uuid.uuid4().hex[:8]}")
    role: str  # "user" | "assistant" | "system" | "tool"
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)
    token_count: int = 0


class ConversationSession(BaseModel):
    """A conversation session with history."""

    id: str = Field(default_factory=lambda: f"conv_{uuid.uuid4().hex[:8]}")
    workflow_id: str = ""
    execution_id: str = ""
    turns: list[ConversationTurn] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    summary: str = ""  # Compressed summary of older turns
    turn_count: int = 0
