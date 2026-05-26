"""Tests for Pydantic domain models."""

from __future__ import annotations

from datetime import datetime

from knot.core.models import (
    Agent,
    AgentRole,
    ConversationSession,
    ConversationTurn,
    Edge,
    Execution,
    KnowledgeBase,
    KnowledgeChunk,
    MultiAgentMode,
    Node,
    NodeStatus,
    NodeType,
    TraceEntry,
    User,
    UserRole,
    Workflow,
    WorkflowStatus,
)


# ─── Enums ────────────────────────────────────────────────────────────────


class TestEnums:
    def test_node_type_values(self):
        assert NodeType.TASK.value == "task"
        assert NodeType.CONDITION.value == "condition"
        assert NodeType.PARALLEL.value == "parallel"
        assert NodeType.LOOP.value == "loop"
        assert NodeType.INPUT.value == "input"
        assert NodeType.OUTPUT.value == "output"

    def test_node_status_values(self):
        assert NodeStatus.PENDING.value == "pending"
        assert NodeStatus.RUNNING.value == "running"
        assert NodeStatus.SUCCESS.value == "success"
        assert NodeStatus.FAILED.value == "failed"
        assert NodeStatus.SKIPPED.value == "skipped"

    def test_workflow_status_values(self):
        assert WorkflowStatus.PENDING.value == "pending"
        assert WorkflowStatus.RUNNING.value == "running"
        assert WorkflowStatus.SUCCESS.value == "success"
        assert WorkflowStatus.FAILED.value == "failed"
        assert WorkflowStatus.PAUSED.value == "paused"
        assert WorkflowStatus.CANCELLED.value == "cancelled"

    def test_agent_role_values(self):
        assert AgentRole.PLANNER.value == "planner"
        assert AgentRole.EXECUTOR.value == "executor"
        assert AgentRole.RESEARCHER.value == "researcher"
        assert AgentRole.CODER.value == "coder"
        assert AgentRole.VALIDATOR.value == "validator"
        assert AgentRole.SUMMARIZER.value == "summarizer"

    def test_multi_agent_mode_values(self):
        assert MultiAgentMode.SINGLE.value == "single"
        assert MultiAgentMode.PARALLEL.value == "parallel"
        assert MultiAgentMode.DEBATE.value == "debate"

    def test_user_role_values(self):
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.USER.value == "user"
        assert UserRole.VIEWER.value == "viewer"


# ─── Node ─────────────────────────────────────────────────────────────────


class TestNode:
    def test_default_values(self):
        node = Node()
        assert node.id.startswith("node_")
        assert node.type == NodeType.TASK
        assert node.label == ""
        assert node.agent_id is None
        assert node.config == {}
        assert node.inputs == {}
        assert node.outputs == {}
        assert node.condition is None
        assert node.retry_count == 0
        assert node.max_retries == 3
        assert node.timeout_seconds == 300
        assert node.status == NodeStatus.PENDING
        assert node.result is None
        assert node.error is None
        assert node.started_at is None
        assert node.completed_at is None

    def test_with_values(self):
        now = datetime.now()
        node = Node(
            id="node_test123",
            type=NodeType.CONDITION,
            label="Check status",
            agent_id="agent_1",
            config={"key": "val"},
            inputs={"x": "y"},
            outputs={"a": "b"},
            condition="x > 5",
            retry_count=1,
            max_retries=5,
            timeout_seconds=600,
            status=NodeStatus.RUNNING,
            result={"data": 42},
            error=None,
            started_at=now,
            completed_at=None,
        )
        assert node.id == "node_test123"
        assert node.type == NodeType.CONDITION
        assert node.label == "Check status"
        assert node.agent_id == "agent_1"
        assert node.config == {"key": "val"}
        assert node.inputs == {"x": "y"}
        assert node.outputs == {"a": "b"}
        assert node.condition == "x > 5"
        assert node.retry_count == 1
        assert node.max_retries == 5
        assert node.timeout_seconds == 600
        assert node.status == NodeStatus.RUNNING
        assert node.result == {"data": 42}
        assert node.started_at == now

    def test_serialization_roundtrip(self):
        node = Node(label="test", type=NodeType.INPUT)
        d = node.model_dump()
        restored = Node(**d)
        assert restored.id == node.id
        assert restored.label == node.label
        assert restored.type == node.type
        assert restored.status == node.status

    def test_json_roundtrip(self):
        node = Node(label="json_test", config={"max_tokens": 512})
        json_str = node.model_dump_json()
        restored = Node.model_validate_json(json_str)
        assert restored.label == "json_test"
        assert restored.config == {"max_tokens": 512}

    def test_unique_ids(self):
        ids = {Node().id for _ in range(100)}
        assert len(ids) == 100, "Node IDs should be unique"


# ─── Edge ─────────────────────────────────────────────────────────────────


class TestEdge:
    def test_default_values(self):
        edge = Edge(source_id="a", target_id="b")
        assert edge.id.startswith("edge_")
        assert edge.source_id == "a"
        assert edge.target_id == "b"
        assert edge.label == ""
        assert edge.condition is None

    def test_serialization_roundtrip(self):
        edge = Edge(source_id="n1", target_id="n2", label="connects", condition="x")
        d = edge.model_dump()
        restored = Edge(**d)
        assert restored.source_id == "n1"
        assert restored.target_id == "n2"
        assert restored.label == "connects"
        assert restored.condition == "x"


# ─── Workflow ─────────────────────────────────────────────────────────────


class TestWorkflow:
    def test_default_values(self):
        wf = Workflow(name="test")
        assert wf.id.startswith("wf_")
        assert wf.name == "test"
        assert wf.description == ""
        assert wf.nodes == []
        assert wf.edges == []
        assert wf.global_context == {}
        assert isinstance(wf.created_at, datetime)
        assert isinstance(wf.updated_at, datetime)
        assert wf.tags == []

    def test_get_node(self):
        node = Node(id="n1", label="alpha")
        wf = Workflow(name="test", nodes=[node])
        assert wf.get_node("n1") is node
        assert wf.get_node("nonexistent") is None

    def test_get_dependencies(self):
        n1 = Node(id="n1")
        n2 = Node(id="n2")
        n3 = Node(id="n3")
        edges = [
            Edge(source_id="n1", target_id="n3"),
            Edge(source_id="n2", target_id="n3"),
        ]
        wf = Workflow(name="test", nodes=[n1, n2, n3], edges=edges)
        deps = wf.get_dependencies("n3")
        assert sorted(deps) == ["n1", "n2"]
        assert wf.get_dependencies("n1") == []

    def test_get_dependents(self):
        n1 = Node(id="n1")
        n2 = Node(id="n2")
        n3 = Node(id="n3")
        edges = [
            Edge(source_id="n1", target_id="n2"),
            Edge(source_id="n1", target_id="n3"),
        ]
        wf = Workflow(name="test", nodes=[n1, n2, n3], edges=edges)
        deps = wf.get_dependents("n1")
        assert sorted(deps) == ["n2", "n3"]
        assert wf.get_dependents("n2") == []

    def test_topological_sort_simple_chain(self):
        n1 = Node(id="n1")
        n2 = Node(id="n2")
        n3 = Node(id="n3")
        edges = [
            Edge(source_id="n1", target_id="n2"),
            Edge(source_id="n2", target_id="n3"),
        ]
        wf = Workflow(name="test", nodes=[n1, n2, n3], edges=edges)
        order = wf.topological_sort()
        assert [n.id for n in order] == ["n1", "n2", "n3"]

    def test_topological_sort_diamond(self):
        n1 = Node(id="n1")
        n2 = Node(id="n2")
        n3 = Node(id="n3")
        n4 = Node(id="n4")
        edges = [
            Edge(source_id="n1", target_id="n2"),
            Edge(source_id="n1", target_id="n3"),
            Edge(source_id="n2", target_id="n4"),
            Edge(source_id="n3", target_id="n4"),
        ]
        wf = Workflow(name="test", nodes=[n1, n2, n3, n4], edges=edges)
        order = wf.topological_sort()
        ids = [n.id for n in order]
        assert ids[0] == "n1"
        assert ids[-1] == "n4"
        assert ids.index("n2") < ids.index("n4")
        assert ids.index("n3") < ids.index("n4")

    def test_topological_sort_no_edges(self):
        n1 = Node(id="n1")
        n2 = Node(id="n2")
        wf = Workflow(name="test", nodes=[n1, n2])
        order = wf.topological_sort()
        assert len(order) == 2

    def test_serialization_roundtrip(self):
        wf = Workflow(
            name="roundtrip",
            nodes=[Node(id="x"), Node(id="y")],
            edges=[Edge(source_id="x", target_id="y")],
            tags=["dev"],
        )
        d = wf.model_dump()
        restored = Workflow(**d)
        assert restored.name == "roundtrip"
        assert len(restored.nodes) == 2
        assert len(restored.edges) == 1
        assert restored.tags == ["dev"]


# ─── User / Auth Models ───────────────────────────────────────────────────


class TestUser:
    def test_default_values(self):
        user = User(username="alice")
        assert user.id.startswith("user_")
        assert user.username == "alice"
        assert user.email == ""
        assert user.role == UserRole.USER
        assert user.is_active is True
        assert isinstance(user.created_at, datetime)

    def test_admin_role(self):
        user = User(username="admin", role=UserRole.ADMIN)
        assert user.role == UserRole.ADMIN
        assert user.role.value == "admin"

    def test_serialization_roundtrip(self):
        user = User(username="bob", email="bob@example.com", role=UserRole.VIEWER)
        d = user.model_dump()
        restored = User(**d)
        assert restored.username == "bob"
        assert restored.email == "bob@example.com"
        assert restored.role == UserRole.VIEWER


# ─── Agent ────────────────────────────────────────────────────────────────


class TestAgent:
    def test_default_values(self):
        agent = Agent(name="helper")
        assert agent.id.startswith("agent_")
        assert agent.name == "helper"
        assert agent.role == AgentRole.EXECUTOR
        assert agent.system_prompt == ""
        assert agent.model == "deepseek-chat"
        assert agent.tools == []
        assert agent.config == {}

    def test_custom_values(self):
        agent = Agent(
            name="coder-bot",
            role=AgentRole.CODER,
            system_prompt="Write code",
            model="gpt-4",
            tools=["python", "bash"],
            config={"max_tokens": 4096},
        )
        assert agent.role == AgentRole.CODER
        assert agent.model == "gpt-4"
        assert agent.tools == ["python", "bash"]
        assert agent.config == {"max_tokens": 4096}

    def test_serialization_roundtrip(self):
        agent = Agent(name="original", role=AgentRole.PLANNER, tools=["a", "b"])
        d = agent.model_dump()
        restored = Agent(**d)
        assert restored.name == "original"
        assert restored.role == AgentRole.PLANNER
        assert restored.tools == ["a", "b"]


# ─── Execution ────────────────────────────────────────────────────────────


class TestExecution:
    def test_default_values(self):
        exec_ = Execution(workflow_id="wf_123")
        assert exec_.id.startswith("exec_")
        assert exec_.workflow_id == "wf_123"
        assert exec_.status == WorkflowStatus.PENDING
        assert exec_.node_states == {}
        assert exec_.global_context == {}
        assert exec_.started_at is None
        assert exec_.completed_at is None
        assert exec_.error is None
        assert exec_.trace == []

    def test_with_states(self):
        exec_ = Execution(
            workflow_id="wf_1",
            status=WorkflowStatus.RUNNING,
            node_states={"n1": NodeStatus.SUCCESS, "n2": NodeStatus.FAILED},
            error="Something broke",
        )
        assert exec_.status == WorkflowStatus.RUNNING
        assert exec_.node_states["n1"] == NodeStatus.SUCCESS
        assert exec_.node_states["n2"] == NodeStatus.FAILED
        assert exec_.error == "Something broke"


# ─── TraceEntry ───────────────────────────────────────────────────────────


class TestTraceEntry:
    def test_default_values(self):
        entry = TraceEntry(event="info")
        assert isinstance(entry.timestamp, datetime)
        assert entry.event == "info"
        assert entry.message == ""
        assert entry.node_id == ""
        assert entry.node_label == ""
        assert entry.duration_ms is None
        assert entry.metadata == {}

    def test_node_complete(self):
        entry = TraceEntry(
            event="node_complete",
            node_id="n1",
            node_label="Node 1",
            message="Done",
            duration_ms=150.5,
            metadata={"result_summary": "ok"},
        )
        assert entry.event == "node_complete"
        assert entry.node_id == "n1"
        assert entry.duration_ms == 150.5


# ─── Knowledge Models ─────────────────────────────────────────────────────


class TestKnowledgeBase:
    def test_default_values(self):
        kb = KnowledgeBase(name="docs")
        assert kb.id.startswith("kb_")
        assert kb.name == "docs"
        assert kb.description == ""
        assert kb.embedding_model == "deepseek-embedding"
        assert kb.collection_name == ""
        assert kb.chunk_size == 512
        assert kb.chunk_overlap == 64

    def test_serialization_roundtrip(self):
        kb = KnowledgeBase(
            name="kb1",
            chunk_size=256,
            chunk_overlap=32,
        )
        d = kb.model_dump()
        restored = KnowledgeBase(**d)
        assert restored.name == "kb1"
        assert restored.chunk_size == 256
        assert restored.chunk_overlap == 32


class TestKnowledgeChunk:
    def test_default_values(self):
        chunk = KnowledgeChunk(content="hello")
        assert chunk.id == ""
        assert chunk.document_id == ""
        assert chunk.content == "hello"
        assert chunk.metadata == {}
        assert chunk.embedding is None
        assert chunk.score == 0.0

    def test_with_embedding(self):
        chunk = KnowledgeChunk(
            id="chunk_1",
            document_id="doc_1",
            content="vector content",
            embedding=[0.1, 0.2, 0.3],
            score=0.95,
        )
        assert chunk.embedding == [0.1, 0.2, 0.3]
        assert chunk.score == 0.95


# ─── Conversation Models ──────────────────────────────────────────────────


class TestConversationTurn:
    def test_default_values(self):
        turn = ConversationTurn(role="user", content="hi")
        assert turn.id.startswith("turn_")
        assert turn.role == "user"
        assert turn.content == "hi"
        assert isinstance(turn.timestamp, datetime)
        assert turn.metadata == {}
        assert turn.token_count == 0

    def test_with_metadata(self):
        turn = ConversationTurn(
            role="assistant",
            content="Hello!",
            metadata={"name": "bot"},
            token_count=42,
        )
        assert turn.role == "assistant"
        assert turn.token_count == 42


class TestConversationSession:
    def test_default_values(self):
        session = ConversationSession()
        assert session.id.startswith("conv_")
        assert session.workflow_id == ""
        assert session.execution_id == ""
        assert session.turns == []
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.updated_at, datetime)
        assert session.summary == ""
        assert session.turn_count == 0

    def test_with_turns(self):
        turn = ConversationTurn(role="user", content="hello")
        session = ConversationSession(
            turns=[turn],
            turn_count=1,
            summary="Old context",
        )
        assert len(session.turns) == 1
        assert session.summary == "Old context"
        assert session.turn_count == 1
