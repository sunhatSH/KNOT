"""Tests for the REST API — auth, workflows, and knowledge routes.

Uses FastAPI TestClient with mocked database sessions and repositories
so no real database connection is required.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from knot.api.auth import create_access_token
from knot.core.database import get_session
from knot.core.models import (
    Edge,
    Execution,
    Node,
    NodeType,
    NodeStatus,
    User,
    UserRole,
    Workflow,
    WorkflowStatus,
)
from knot.llm.base import LLMResponse


# ─── Helpers ───────────────────────────────────────────────────────────────────


def make_workflow(**overrides) -> Workflow:
    """Build a simple linear workflow for testing."""
    defaults = {
        "name": "Test WF",
        "nodes": [
            Node(id="a", type=NodeType.INPUT, label="Input"),
            Node(id="b", type=NodeType.TASK, label="Process"),
            Node(id="c", type=NodeType.OUTPUT, label="Output"),
        ],
        "edges": [
            Edge(source_id="a", target_id="b"),
            Edge(source_id="b", target_id="c"),
        ],
    }
    defaults.update(overrides)
    return Workflow(**defaults)


def make_execution(**overrides) -> Execution:
    defaults = {
        "workflow_id": "wf_test",
        "status": WorkflowStatus.SUCCESS,
        "node_states": {"a": NodeStatus.SUCCESS, "b": NodeStatus.SUCCESS},
    }
    defaults.update(overrides)
    return Execution(**defaults)


# ─── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _mock_dependencies():
    """Patch database repositories and external services for all tests.

    We patch the module-level repository instances so that no real
    database calls are made.
    """
    mocks = {}

    # ── Auth repo ──────────────────────────────────────────────────────────
    mocks["auth_repo"] = MagicMock()
    mocks["auth_repo"].get_by_username = AsyncMock(return_value=None)
    mocks["auth_repo"].save = AsyncMock()

    # ── Workflow / Execution repos ─────────────────────────────────────────
    mocks["wf_repo"] = MagicMock()
    mocks["wf_repo"].get = AsyncMock(return_value=None)
    mocks["wf_repo"].list = AsyncMock(return_value=[])
    mocks["wf_repo"].save = AsyncMock()

    mocks["exec_repo"] = MagicMock()
    mocks["exec_repo"].get = AsyncMock(return_value=None)
    mocks["exec_repo"].save = AsyncMock()

    # ── Knowledge repo ─────────────────────────────────────────────────────
    mocks["kb_repo"] = MagicMock()
    mocks["kb_repo"].save = AsyncMock()

    patches = [
        patch("knot.api.routes.auth._user_repo", mocks["auth_repo"]),
        patch("knot.api.auth._user_repo", mocks["auth_repo"]),
        patch("knot.api.routes.workflows._wf_repo", mocks["wf_repo"]),
        patch("knot.api.routes.workflows._exec_repo", mocks["exec_repo"]),
        patch("knot.api.routes.knowledge._kb_repo", mocks["kb_repo"]),
    ]
    for p in patches:
        p.start()
    yield mocks
    for p in patches:
        p.stop()


@pytest.fixture
def engine_with_control():
    """Build a mock WorkflowEngine that registers a WorkflowState for control API tests."""
    engine = MagicMock()
    engine._control_states = {}
    engine.execute = AsyncMock()
    return engine


@pytest.fixture
def app(_mock_dependencies, engine_with_control):
    """Build a FastAPI app with the router and dependency overrides."""
    from knot.api.routes import auth as auth_routes
    from knot.api.routes import knowledge as knowledge_routes
    from knot.api.routes import workflows as workflow_routes

    app = FastAPI()

    # Need a mock LLM provider so that configure_routes can set up
    # the /from-nl endpoint without error.
    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(return_value=LLMResponse(content='{"nodes": [], "edges": []}'))

    # Clear previously registered routes so repeated configure_routes
    # calls don't accumulate stale handlers on the shared module router.
    workflow_routes.router.routes.clear()

    # Configure routes (this registers route handlers on the module routers)
    workflow_routes.configure_routes(engine_with_control, llm_provider=mock_llm)

    # Mock retriever for knowledge routes
    mock_retriever = MagicMock()
    mock_retriever.retrieve = AsyncMock(return_value=[])
    knowledge_routes.configure_routes(mock_retriever)

    # Include all routers
    app.include_router(workflow_routes.router)
    app.include_router(knowledge_routes.router)
    app.include_router(auth_routes.router)

    # Override the get_session dependency so no real DB is needed
    async def _override_get_session():
        mock_session = MagicMock(spec=AsyncSession)
        yield mock_session

    app.dependency_overrides[get_session] = _override_get_session

    return app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def auth_header(client: TestClient):
    """Register a user and return an Authorization header with a valid token."""
    token = create_access_token({"sub": "testuser", "role": "user"})
    return {"Authorization": f"Bearer {token}"}


# ═══════════════════════════════════════════════════════════════════════════════
# Auth Route Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuthRegister:
    """POST /api/v1/auth/register"""

    def test_register_success(self, client, _mock_dependencies):
        resp = client.post("/api/v1/auth/register", params={
            "username": "newuser",
            "password": "secret123",
            "email": "new@example.com",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "newuser"
        assert "id" in data
        _mock_dependencies["auth_repo"].save.assert_awaited_once()

    def test_register_duplicate_username(self, client, _mock_dependencies):
        """409 when username already exists."""
        _mock_dependencies["auth_repo"].get_by_username.return_value = (
            User(username="existing", role=UserRole.USER),
            "hashed_pw",
        )
        resp = client.post("/api/v1/auth/register", params={
            "username": "existing",
            "password": "secret",
        })
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]


class TestAuthLogin:
    """POST /api/v1/auth/login"""

    def test_login_success(self, client, _mock_dependencies):
        from knot.api.auth import hash_password
        pw_hash = hash_password("correct_password")
        _mock_dependencies["auth_repo"].get_by_username.return_value = (
            User(username="testuser", role=UserRole.USER, is_active=True),
            pw_hash,
        )
        resp = client.post("/api/v1/auth/login", params={
            "username": "testuser",
            "password": "correct_password",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "testuser"

    def test_login_wrong_password(self, client, _mock_dependencies):
        from knot.api.auth import hash_password
        pw_hash = hash_password("correct_password")
        _mock_dependencies["auth_repo"].get_by_username.return_value = (
            User(username="testuser", role=UserRole.USER, is_active=True),
            pw_hash,
        )
        resp = client.post("/api/v1/auth/login", params={
            "username": "testuser",
            "password": "wrong_password",
        })
        assert resp.status_code == 401

    def test_login_user_not_found(self, client, _mock_dependencies):
        _mock_dependencies["auth_repo"].get_by_username.return_value = None
        resp = client.post("/api/v1/auth/login", params={
            "username": "nobody",
            "password": "any",
        })
        assert resp.status_code == 401

    def test_login_inactive_user(self, client, _mock_dependencies):
        from knot.api.auth import hash_password
        pw_hash = hash_password("secret")
        _mock_dependencies["auth_repo"].get_by_username.return_value = (
            User(username="inactive", role=UserRole.USER, is_active=False),
            pw_hash,
        )
        resp = client.post("/api/v1/auth/login", params={
            "username": "inactive",
            "password": "secret",
        })
        assert resp.status_code == 403
        assert "inactive" in resp.json()["detail"].lower()


class TestAuthMe:
    """GET /api/v1/auth/me"""

    def test_get_me_authenticated(self, client, _mock_dependencies, auth_header):
        _mock_dependencies["auth_repo"].get_by_username.return_value = (
            User(username="testuser", role=UserRole.USER, is_active=True),
            "hash",
        )
        resp = client.get("/api/v1/auth/me", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "testuser"

    def test_get_me_no_token(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401  # missing credentials

    def test_get_me_invalid_token(self, client):
        resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalidtoken"})
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow Route Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorkflowCreate:
    """POST /api/v1/workflows"""

    def test_create_workflow(self, client, _mock_dependencies):
        payload = make_workflow(name="New WF").model_dump(mode="json")
        resp = client.post("/api/v1/workflows", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "New WF"
        assert len(data["nodes"]) == 3

    def test_create_workflow_with_version(self, client, _mock_dependencies):
        """Creating with an existing workflow ID triggers version auto-creation when nodes change."""
        existing = make_workflow(name="Existing")
        _mock_dependencies["wf_repo"].get.return_value = existing
        payload = make_workflow(name="Existing").model_dump(mode="json")
        # The existing nodes are INPUT -> TASK -> OUTPUT; send different ones to trigger version
        payload["nodes"] = [
            Node(id="x", type=NodeType.TASK, label="New Node").model_dump()
        ]
        resp = client.post("/api/v1/workflows", json=payload)
        assert resp.status_code == 200

    def test_workflow_from_nl(self, client, _mock_dependencies):
        resp = client.post("/api/v1/workflows/from-nl", json={
            "description": "A workflow that fetches data and processes it",
        })
        assert resp.status_code == 200

    def test_workflow_from_nl_missing_description(self, client):
        resp = client.post("/api/v1/workflows/from-nl", json={})
        assert resp.status_code == 422

    def test_workflow_create_invalid_body(self, client):
        resp = client.post("/api/v1/workflows", json={"name": 42})
        assert resp.status_code == 422


class TestWorkflowList:
    """GET /api/v1/workflows"""

    def test_list_workflows(self, client, _mock_dependencies):
        _mock_dependencies["wf_repo"].list.return_value = [
            make_workflow(name="WF1"),
            make_workflow(name="WF2"),
        ]
        resp = client.get("/api/v1/workflows")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "WF1"

    def test_list_workflows_empty(self, client):
        resp = client.get("/api/v1/workflows")
        assert resp.status_code == 200
        assert resp.json() == []


class TestWorkflowGet:
    """GET /api/v1/workflows/{workflow_id}"""

    def test_get_workflow_found(self, client, _mock_dependencies):
        wf = make_workflow(name="My WF")
        _mock_dependencies["wf_repo"].get.return_value = wf
        resp = client.get(f"/api/v1/workflows/{wf.id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "My WF"

    def test_get_workflow_not_found(self, client):
        resp = client.get("/api/v1/workflows/nonexistent")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


class TestWorkflowExecute:
    """POST /api/v1/workflows/{workflow_id}/execute"""

    def test_execute_workflow(self, client, app, _mock_dependencies, engine_with_control):
        wf = make_workflow(name="Exec WF")
        _mock_dependencies["wf_repo"].get.return_value = wf

        exec_result = Execution(
            workflow_id=wf.id,
            status=WorkflowStatus.SUCCESS,
            node_states={"a": NodeStatus.SUCCESS},
        )
        # Replace the execute method entirely with one that returns exec_result
        engine_with_control.execute = AsyncMock(return_value=exec_result)

        resp = client.post(f"/api/v1/workflows/{wf.id}/execute", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        _mock_dependencies["exec_repo"].save.assert_awaited_once()

    def test_execute_workflow_not_found(self, client):
        resp = client.post("/api/v1/workflows/nonexistent/execute", json={})
        assert resp.status_code == 404

    def test_get_execution(self, client, _mock_dependencies):
        exec_ = make_execution()
        _mock_dependencies["exec_repo"].get.return_value = exec_
        resp = client.get(f"/api/v1/workflows/executions/{exec_.id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_get_execution_not_found(self, client):
        resp = client.get("/api/v1/workflows/executions/nonexistent")
        assert resp.status_code == 404


class TestWorkflowPauseResumeCancel:
    """Control API endpoints."""

    def _make_control_state(self, app, engine_with_control, status: WorkflowStatus):
        """Helper: populate engine._control_states with a fake state."""
        from knot.orchestration_layer.state import WorkflowState

        exec_ = Execution(workflow_id="wf_ctrl", status=status)
        state = WorkflowState(exec_)
        state.status = status
        engine_with_control._control_states[exec_.id] = state
        return exec_.id

    def test_pause_running_execution(self, client, app, engine_with_control):
        exec_id = self._make_control_state(
            app, engine_with_control, WorkflowStatus.RUNNING
        )
        resp = client.post(f"/api/v1/workflows/executions/{exec_id}/pause")
        assert resp.status_code == 200

    def test_pause_not_found(self, client):
        resp = client.post("/api/v1/workflows/executions/nonexistent/pause")
        assert resp.status_code == 404

    def test_pause_not_running(self, client, app, engine_with_control):
        exec_id = self._make_control_state(
            app, engine_with_control, WorkflowStatus.SUCCESS
        )
        resp = client.post(f"/api/v1/workflows/executions/{exec_id}/pause")
        assert resp.status_code == 409

    def test_resume_paused_execution(self, client, app, engine_with_control):
        exec_id = self._make_control_state(
            app, engine_with_control, WorkflowStatus.PAUSED
        )
        resp = client.post(f"/api/v1/workflows/executions/{exec_id}/resume")
        assert resp.status_code == 200

    def test_resume_not_found(self, client):
        resp = client.post("/api/v1/workflows/executions/nonexistent/resume")
        assert resp.status_code == 404

    def test_resume_not_paused(self, client, app, engine_with_control):
        exec_id = self._make_control_state(
            app, engine_with_control, WorkflowStatus.RUNNING
        )
        resp = client.post(f"/api/v1/workflows/executions/{exec_id}/resume")
        assert resp.status_code == 409

    def test_cancel_running_execution(self, client, app, engine_with_control):
        exec_id = self._make_control_state(
            app, engine_with_control, WorkflowStatus.RUNNING
        )
        resp = client.post(f"/api/v1/workflows/executions/{exec_id}/cancel")
        assert resp.status_code == 200

    def test_cancel_paused_execution(self, client, app, engine_with_control):
        exec_id = self._make_control_state(
            app, engine_with_control, WorkflowStatus.PAUSED
        )
        resp = client.post(f"/api/v1/workflows/executions/{exec_id}/cancel")
        assert resp.status_code == 200

    def test_cancel_not_found(self, client):
        resp = client.post("/api/v1/workflows/executions/nonexistent/cancel")
        assert resp.status_code == 404

    def test_cancel_not_active(self, client, app, engine_with_control):
        exec_id = self._make_control_state(
            app, engine_with_control, WorkflowStatus.SUCCESS
        )
        resp = client.post(f"/api/v1/workflows/executions/{exec_id}/cancel")
        assert resp.status_code == 409

    def test_cancel_skipped_execution(self, client, app, engine_with_control):
        exec_id = self._make_control_state(
            app, engine_with_control, WorkflowStatus.FAILED
        )
        resp = client.post(f"/api/v1/workflows/executions/{exec_id}/cancel")
        assert resp.status_code == 409


class TestWorkflowVersions:
    """Version history endpoints."""

    def test_list_versions(self, client, _mock_dependencies):
        from knot.core.models import WorkflowVersion
        wf = make_workflow(name="Versioned WF")
        wf.versions = [
            WorkflowVersion(version=1, workflow_id=wf.id),
            WorkflowVersion(version=2, workflow_id=wf.id),
        ]
        _mock_dependencies["wf_repo"].get.return_value = wf
        resp = client.get(f"/api/v1/workflows/{wf.id}/versions")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_versions_not_found(self, client):
        resp = client.get("/api/v1/workflows/nonexistent/versions")
        assert resp.status_code == 404

    def test_get_version(self, client, _mock_dependencies):
        from knot.core.models import WorkflowVersion
        wf = make_workflow(name="WF")
        wf.versions = [WorkflowVersion(version=1, workflow_id=wf.id)]
        _mock_dependencies["wf_repo"].get.return_value = wf
        resp = client.get(f"/api/v1/workflows/{wf.id}/versions/1")
        assert resp.status_code == 200
        assert resp.json()["version"] == 1

    def test_get_version_not_found(self, client, _mock_dependencies):
        from knot.core.models import WorkflowVersion
        wf = make_workflow(name="WF")
        wf.versions = [WorkflowVersion(version=1, workflow_id=wf.id)]
        _mock_dependencies["wf_repo"].get.return_value = wf
        resp = client.get(f"/api/v1/workflows/{wf.id}/versions/999")
        assert resp.status_code == 404

    def test_restore_version(self, client, _mock_dependencies):
        from knot.core.models import WorkflowVersion
        original_nodes = [Node(id="old", label="Old Node")]
        wf = make_workflow(name="WF")
        wf.versions = [WorkflowVersion(version=1, workflow_id=wf.id, nodes=original_nodes)]
        _mock_dependencies["wf_repo"].get.return_value = wf
        resp = client.post(f"/api/v1/workflows/{wf.id}/versions/restore/1")
        assert resp.status_code == 200
        data = resp.json()
        # Should have restored the old node
        assert any(n["id"] == "old" for n in data["nodes"])


# ═══════════════════════════════════════════════════════════════════════════════
# Knowledge Route Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestKnowledgeSearch:
    """POST /api/v1/knowledge/search"""

    def test_search_empty_results(self, client):
        resp = client.post(
            "/api/v1/knowledge/search",
            params={"collection_name": "test_coll", "query": "test query"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "test query"
        assert data["results"] == []


class TestKnowledgeCreateCollection:
    """POST /api/v1/knowledge/collections"""

    @patch("knot.api.routes.knowledge.vector_store.create_collection")
    def test_create_collection(self, mock_create, client):
        mock_create.return_value = MagicMock()
        resp = client.post(
            "/api/v1/knowledge/collections",
            params={"name": "my_collection"},
        )
        assert resp.status_code == 200
        assert resp.json()["collection"] == "my_collection"
        assert resp.json()["status"] == "created"
