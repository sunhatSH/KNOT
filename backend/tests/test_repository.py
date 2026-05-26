"""Tests for async repository CRUD operations."""

from __future__ import annotations

from knot.core.models import (
    Agent,
    AgentRole,
    ConversationSession,
    ConversationTurn,
    Execution,
    KnowledgeBase,
    Node,
    NodeStatus,
    User,
    UserRole,
    Workflow,
    WorkflowStatus,
)
from knot.core.repository import (
    AgentRepository,
    ConversationRepository,
    ExecutionRepository,
    KnowledgeBaseRepository,
    UserRepository,
    WorkflowRepository,
)


# ─── WorkflowRepository ───────────────────────────────────────────────────


class TestWorkflowRepository:
    """CRUD tests for WorkflowRepository."""

    async def test_save_and_get(self, db_session):
        repo = WorkflowRepository()
        wf = Workflow(name="test-wf", description="A test workflow")

        saved = await repo.save(db_session, wf)
        assert saved.id == wf.id
        assert saved.name == "test-wf"

        fetched = await repo.get(db_session, wf.id)
        assert fetched is not None
        assert fetched.name == "test-wf"
        assert fetched.description == "A test workflow"

    async def test_get_nonexistent(self, db_session):
        repo = WorkflowRepository()
        result = await repo.get(db_session, "nonexistent")
        assert result is None

    async def test_list(self, db_session):
        repo = WorkflowRepository()
        wf1 = Workflow(name="alpha")
        wf2 = Workflow(name="beta")
        await repo.save(db_session, wf1)
        await repo.save(db_session, wf2)

        all_wfs = await repo.list(db_session)
        assert len(all_wfs) >= 2
        names = {w.name for w in all_wfs}
        assert "alpha" in names
        assert "beta" in names

    async def test_list_empty(self, db_session):
        repo = WorkflowRepository()
        result = await repo.list(db_session)
        assert result == []

    async def test_update(self, db_session):
        repo = WorkflowRepository()
        wf = Workflow(name="original")
        await repo.save(db_session, wf)

        wf.name = "updated"
        wf.description = "New description"
        await repo.save(db_session, wf)

        fetched = await repo.get(db_session, wf.id)
        assert fetched is not None
        assert fetched.name == "updated"
        assert fetched.description == "New description"

    async def test_delete(self, db_session):
        repo = WorkflowRepository()
        wf = Workflow(name="delete-me")
        await repo.save(db_session, wf)

        deleted = await repo.delete(db_session, wf.id)
        assert deleted is True

        fetched = await repo.get(db_session, wf.id)
        assert fetched is None

    async def test_delete_nonexistent(self, db_session):
        repo = WorkflowRepository()
        result = await repo.delete(db_session, "no-such-id")
        assert result is False

    async def test_search(self, db_session):
        repo = WorkflowRepository()
        wf1 = Workflow(name="data-pipeline", description="ETL pipeline")
        wf2 = Workflow(name="report-gen", description="Generate reports")
        await repo.save(db_session, wf1)
        await repo.save(db_session, wf2)

        results = await repo.search(db_session, "pipeline")
        assert len(results) >= 1
        assert results[0].name == "data-pipeline"

        results = await repo.search(db_session, "report")
        assert len(results) >= 1
        assert results[0].name == "report-gen"

    async def test_search_no_match(self, db_session):
        repo = WorkflowRepository()
        wf = Workflow(name="unique-name")
        await repo.save(db_session, wf)

        results = await repo.search(db_session, "zzz_nonexistent")
        assert results == []

    async def test_save_with_nodes_and_edges(self, db_session):
        from knot.core.models import Edge

        repo = WorkflowRepository()
        n1 = Node(id="n1", label="Start")
        n2 = Node(id="n2", label="End")
        wf = Workflow(
            name="dag-test",
            nodes=[n1, n2],
            edges=[Edge(source_id="n1", target_id="n2")],
        )

        await repo.save(db_session, wf)
        fetched = await repo.get(db_session, wf.id)
        assert fetched is not None
        assert len(fetched.nodes) == 2
        assert len(fetched.edges) == 1
        assert fetched.edges[0].source_id == "n1"


# ─── ExecutionRepository ──────────────────────────────────────────────────


class TestExecutionRepository:
    async def test_save_and_get(self, db_session):
        repo = ExecutionRepository()
        exec_ = Execution(workflow_id="wf_1", status=WorkflowStatus.RUNNING)

        saved = await repo.save(db_session, exec_)
        assert saved.id == exec_.id

        fetched = await repo.get(db_session, exec_.id)
        assert fetched is not None
        assert fetched.workflow_id == "wf_1"
        assert fetched.status == WorkflowStatus.RUNNING

    async def test_get_nonexistent(self, db_session):
        repo = ExecutionRepository()
        result = await repo.get(db_session, "no-such-exec")
        assert result is None

    async def test_list_by_workflow(self, db_session):
        repo = ExecutionRepository()
        e1 = Execution(workflow_id="wf_a")
        e2 = Execution(workflow_id="wf_a")
        e3 = Execution(workflow_id="wf_b")
        await repo.save(db_session, e1)
        await repo.save(db_session, e2)
        await repo.save(db_session, e3)

        results = await repo.list_by_workflow(db_session, "wf_a")
        assert len(results) == 2

        results = await repo.list_by_workflow(db_session, "wf_b")
        assert len(results) == 1

        results = await repo.list_by_workflow(db_session, "wf_none")
        assert results == []

    async def test_update_execution(self, db_session):
        repo = ExecutionRepository()
        exec_ = Execution(workflow_id="wf_1")
        await repo.save(db_session, exec_)

        exec_.status = WorkflowStatus.SUCCESS
        exec_.error = None
        await repo.save(db_session, exec_)

        fetched = await repo.get(db_session, exec_.id)
        assert fetched is not None
        assert fetched.status == WorkflowStatus.SUCCESS

    async def test_trace_persistence(self, db_session):
        repo = ExecutionRepository()
        exec_ = Execution(
            workflow_id="wf_trace",
            trace=[
                {"event": "info", "message": "started"},
                {"event": "node_complete", "message": "done"},
            ],
        )
        await repo.save(db_session, exec_)
        fetched = await repo.get(db_session, exec_.id)
        assert fetched is not None
        assert len(fetched.trace) == 2
        assert fetched.trace[0]["event"] == "info"


# ─── AgentRepository ──────────────────────────────────────────────────────


class TestAgentRepository:
    async def test_save_and_get(self, db_session):
        repo = AgentRepository()
        agent = Agent(name="helper-bot", role=AgentRole.EXECUTOR)

        saved = await repo.save(db_session, agent)
        assert saved.id == agent.id

        fetched = await repo.get(db_session, agent.id)
        assert fetched is not None
        assert fetched.name == "helper-bot"
        assert fetched.role == AgentRole.EXECUTOR

    async def test_list(self, db_session):
        repo = AgentRepository()
        a1 = Agent(name="alpha", role=AgentRole.CODER)
        a2 = Agent(name="beta", role=AgentRole.PLANNER)
        await repo.save(db_session, a1)
        await repo.save(db_session, a2)

        agents = await repo.list(db_session)
        assert len(agents) >= 2

    async def test_get_by_role(self, db_session):
        repo = AgentRepository()
        a1 = Agent(name="coder-1", role=AgentRole.CODER)
        a2 = Agent(name="coder-2", role=AgentRole.CODER)
        a3 = Agent(name="planner-1", role=AgentRole.PLANNER)
        await repo.save(db_session, a1)
        await repo.save(db_session, a2)
        await repo.save(db_session, a3)

        coders = await repo.get_by_role(db_session, "coder")
        assert len(coders) == 2

        planners = await repo.get_by_role(db_session, "planner")
        assert len(planners) == 1

        none_found = await repo.get_by_role(db_session, "researcher")
        assert none_found == []

    async def test_update_agent(self, db_session):
        repo = AgentRepository()
        agent = Agent(name="original", tools=["echo"])
        await repo.save(db_session, agent)

        agent.name = "renamed"
        agent.tools = ["echo", "calc"]
        await repo.save(db_session, agent)

        fetched = await repo.get(db_session, agent.id)
        assert fetched is not None
        assert fetched.name == "renamed"
        assert fetched.tools == ["echo", "calc"]


# ─── KnowledgeBaseRepository ──────────────────────────────────────────────


class TestKnowledgeBaseRepository:
    async def test_save_and_get(self, db_session):
        repo = KnowledgeBaseRepository()
        kb = KnowledgeBase(name="my-kb", chunk_size=256, chunk_overlap=32)

        saved = await repo.save(db_session, kb)
        assert saved.id == kb.id

        fetched = await repo.get(db_session, kb.id)
        assert fetched is not None
        assert fetched.name == "my-kb"
        assert fetched.chunk_size == 256
        assert fetched.chunk_overlap == 32

    async def test_list(self, db_session):
        repo = KnowledgeBaseRepository()
        kb1 = KnowledgeBase(name="kb1")
        kb2 = KnowledgeBase(name="kb2")
        await repo.save(db_session, kb1)
        await repo.save(db_session, kb2)

        all_kbs = await repo.list(db_session)
        assert len(all_kbs) >= 2

    async def test_search(self, db_session):
        repo = KnowledgeBaseRepository()
        kb = KnowledgeBase(name="finance-reports", description="Financial data")
        await repo.save(db_session, kb)

        results = await repo.search(db_session, "finance")
        assert len(results) >= 1

        results = await repo.search(db_session, "data")
        assert len(results) >= 1

        results = await repo.search(db_session, "nonexistent")
        assert results == []

    async def test_search_by_description(self, db_session):
        repo = KnowledgeBaseRepository()
        kb1 = KnowledgeBase(name="docs-v1", description="Technical documentation")
        kb2 = KnowledgeBase(name="wiki", description="General knowledge wiki")
        await repo.save(db_session, kb1)
        await repo.save(db_session, kb2)

        results = await repo.search(db_session, "technical")
        assert len(results) >= 1
        assert results[0].name == "docs-v1"


# ─── UserRepository ───────────────────────────────────────────────────────


class TestUserRepository:
    async def test_save_and_get(self, db_session):
        repo = UserRepository()
        user = User(username="alice", email="alice@example.com", role=UserRole.ADMIN)

        saved = await repo.save(db_session, user, password_hash="hashed_pwd_abc")
        assert saved.username == "alice"

        fetched = await repo.get(db_session, user.id)
        assert fetched is not None
        assert fetched.username == "alice"
        assert fetched.email == "alice@example.com"
        assert fetched.role == UserRole.ADMIN

    async def test_get_by_username(self, db_session):
        repo = UserRepository()
        user = User(username="bob", role=UserRole.USER)
        await repo.save(db_session, user, password_hash="secret_hash")

        result = await repo.get_by_username(db_session, "bob")
        assert result is not None
        fetched_user, pwd_hash = result
        assert fetched_user.username == "bob"
        assert pwd_hash == "secret_hash"

    async def test_get_by_username_nonexistent(self, db_session):
        repo = UserRepository()
        result = await repo.get_by_username(db_session, "ghost")
        assert result is None

    async def test_list_users(self, db_session):
        repo = UserRepository()
        u1 = User(username="alice")
        u2 = User(username="bob")
        await repo.save(db_session, u1, "hash1")
        await repo.save(db_session, u2, "hash2")

        users = await repo.list(db_session)
        assert len(users) >= 2
        usernames = {u.username for u in users}
        assert "alice" in usernames
        assert "bob" in usernames

    async def test_list_empty(self, db_session):
        repo = UserRepository()
        result = await repo.list(db_session)
        assert result == []


# ─── ConversationRepository ───────────────────────────────────────────────


class TestConversationRepository:
    async def test_save_and_get(self, db_session):
        repo = ConversationRepository()
        turn = ConversationTurn(role="user", content="hello")
        conv = ConversationSession(
            turns=[turn],
            turn_count=1,
            summary="",
        )

        saved = await repo.save(db_session, conv)
        assert saved.id == conv.id

        fetched = await repo.get(db_session, conv.id)
        assert fetched is not None
        assert len(fetched.turns) == 1
        assert fetched.turns[0].role == "user"
        assert fetched.turns[0].content == "hello"
        assert fetched.turn_count == 1

    async def test_update_session(self, db_session):
        repo = ConversationRepository()
        conv = ConversationSession()
        await repo.save(db_session, conv)

        turn = ConversationTurn(role="assistant", content="Hello!")
        conv.turns.append(turn)
        conv.turn_count = 1
        conv.summary = "A greeting"
        await repo.save(db_session, conv)

        fetched = await repo.get(db_session, conv.id)
        assert fetched is not None
        assert fetched.turn_count == 1
        assert fetched.summary == "A greeting"
        assert len(fetched.turns) == 1

    async def test_list(self, db_session):
        repo = ConversationRepository()
        c1 = ConversationSession()
        c2 = ConversationSession()
        await repo.save(db_session, c1)
        await repo.save(db_session, c2)

        sessions = await repo.list(db_session)
        assert len(sessions) >= 2

    async def test_delete(self, db_session):
        repo = ConversationRepository()
        conv = ConversationSession()
        await repo.save(db_session, conv)

        deleted = await repo.delete(db_session, conv.id)
        assert deleted is True

        fetched = await repo.get(db_session, conv.id)
        assert fetched is None

    async def test_delete_nonexistent(self, db_session):
        repo = ConversationRepository()
        result = await repo.delete(db_session, "no-such-conv")
        assert result is False

    async def test_get_nonexistent(self, db_session):
        repo = ConversationRepository()
        result = await repo.get(db_session, "no-such-conv")
        assert result is None
