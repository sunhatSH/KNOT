"""Workflow management API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from knot.core.database import get_session
from knot.core.models import Execution, Workflow, WorkflowStatus, WorkflowVersion
from knot.core.repository import ExecutionRepository, WorkflowRepository
from knot.llm.base import LLMProvider
from knot.orchestration_layer.intent_understanding import nl_to_workflow
from knot.orchestration_layer.workflow import WorkflowEngine

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])

# Repository instances (stateless - session injected per-request)
_wf_repo = WorkflowRepository()
_exec_repo = ExecutionRepository()

# Stored by configure_routes() so control endpoints can reach it.
_engine: WorkflowEngine | None = None


def _has_changed(old: Workflow, new: Workflow) -> bool:
    """Return True if nodes or edges differ between two workflow snapshots."""
    old_nodes = {(n.id, n.type, n.label) for n in old.nodes}
    new_nodes = {(n.id, n.type, n.label) for n in new.nodes}
    if old_nodes != new_nodes:
        return True
    old_edges = {(e.id, e.source_id, e.target_id) for e in old.edges}
    new_edges = {(e.id, e.source_id, e.target_id) for e in new.edges}
    if old_edges != new_edges:
        return True
    return False


def configure_routes(
    engine: WorkflowEngine,
    llm_provider: LLMProvider | None = None,
) -> None:
    """Inject the workflow engine (and optional LLM) dependency into routes."""
    global _engine
    _engine = engine

    @router.post("/from-nl")
    async def create_workflow_from_nl(
        request: dict[str, str],
        session: AsyncSession = Depends(get_session),
    ) -> Workflow:
        """Create a workflow from a natural language description."""
        if llm_provider is None:
            raise HTTPException(
                status_code=503,
                detail="LLM provider not available for NL->Workflow conversion",
            )
        description = request.get("description", "")
        if not description:
            raise HTTPException(
                status_code=422,
                detail="'description' field is required",
            )
        workflow = await nl_to_workflow(description, llm_provider)
        await _wf_repo.save(session, workflow)
        return workflow

    @router.post("")
    async def create_workflow(
        workflow: Workflow,
        session: AsyncSession = Depends(get_session),
    ) -> Workflow:
        """Create or update a workflow definition. Auto-creates a version snapshot
        when nodes or edges have changed."""
        existing = await _wf_repo.get(session, workflow.id) if workflow.id else None
        if existing:
            # Check if nodes/edges changed
            if _has_changed(existing, workflow):
                next_ver = max((v.version for v in existing.versions), default=0) + 1
                version = WorkflowVersion(
                    version=next_ver,
                    workflow_id=existing.id,
                    nodes=existing.nodes,
                    edges=existing.edges,
                    config=existing.global_context,
                    saved_by=workflow.versions[-1].saved_by if workflow.versions else "",
                    message=workflow.versions[-1].message if workflow.versions else "",
                )
                workflow.versions = [*existing.versions, version]
            else:
                workflow.versions = existing.versions
        await _wf_repo.save(session, workflow)
        return workflow

    @router.get("")
    async def list_workflows(
        session: AsyncSession = Depends(get_session),
    ) -> list[Workflow]:
        """List all workflow definitions."""
        return await _wf_repo.list(session)

    @router.get("/{workflow_id}")
    async def get_workflow(
        workflow_id: str,
        session: AsyncSession = Depends(get_session),
    ) -> Workflow:
        """Get a workflow by ID."""
        wf = await _wf_repo.get(session, workflow_id)
        if not wf:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return wf

    @router.post("/{workflow_id}/execute")
    async def execute_workflow(
        workflow_id: str,
        context: dict[str, Any] = {},
        session: AsyncSession = Depends(get_session),
    ) -> Execution:
        """Execute a workflow."""
        wf = await _wf_repo.get(session, workflow_id)
        if not wf:
            raise HTTPException(status_code=404, detail="Workflow not found")

        wf.global_context.update(context)
        execution = await engine.execute(wf)
        await _exec_repo.save(session, execution)
        return execution

    @router.get("/executions/{execution_id}")
    async def get_execution(
        execution_id: str,
        session: AsyncSession = Depends(get_session),
    ) -> Execution:
        """Get execution status and results."""
        exec_ = await _exec_repo.get(session, execution_id)
        if not exec_:
            raise HTTPException(status_code=404, detail="Execution not found")
        return exec_

    # ── Execution Control Endpoints ──────────────────────────────────────

    @router.post("/executions/{execution_id}/pause")
    async def pause_execution(
        execution_id: str,
    ) -> Execution:
        """Pause a running execution."""
        assert _engine is not None
        state = _engine._control_states.get(execution_id)
        if state is None:
            raise HTTPException(
                status_code=404,
                detail="Running execution not found",
            )
        if state.status != WorkflowStatus.RUNNING:
            raise HTTPException(
                status_code=409,
                detail=f"Execution is {state.status.value}, only RUNNING executions can be paused",
            )
        state.request_pause()
        return state.execution

    @router.post("/executions/{execution_id}/resume")
    async def resume_execution(
        execution_id: str,
    ) -> Execution:
        """Resume a paused execution."""
        assert _engine is not None
        state = _engine._control_states.get(execution_id)
        if state is None:
            raise HTTPException(
                status_code=404,
                detail="Paused execution not found",
            )
        if state.status != WorkflowStatus.PAUSED:
            raise HTTPException(
                status_code=409,
                detail=f"Execution is {state.status.value}, only PAUSED executions can be resumed",
            )
        state.request_resume()
        return state.execution

    @router.post("/executions/{execution_id}/cancel")
    async def cancel_execution(
        execution_id: str,
    ) -> Execution:
        """Cancel a running or paused execution."""
        assert _engine is not None
        state = _engine._control_states.get(execution_id)
        if state is None:
            raise HTTPException(
                status_code=404,
                detail="Active execution not found",
            )
        if state.status not in (WorkflowStatus.RUNNING, WorkflowStatus.PAUSED):
            raise HTTPException(
                status_code=409,
                detail=f"Execution is {state.status.value}, only RUNNING or PAUSED executions can be cancelled",
            )
        state.request_cancel()
        return state.execution

    # ── Version History Endpoints ─────────────────────────────────────────

    @router.get("/{workflow_id}/versions")
    async def list_versions(
        workflow_id: str,
        session: AsyncSession = Depends(get_session),
    ) -> list[WorkflowVersion]:
        """List all saved versions of a workflow."""
        wf = await _wf_repo.get(session, workflow_id)
        if not wf:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return wf.versions

    @router.get("/{workflow_id}/versions/{version:int}")
    async def get_version(
        workflow_id: str,
        version: int,
        session: AsyncSession = Depends(get_session),
    ) -> WorkflowVersion:
        """Get a specific version of a workflow."""
        wf = await _wf_repo.get(session, workflow_id)
        if not wf:
            raise HTTPException(status_code=404, detail="Workflow not found")
        for v in wf.versions:
            if v.version == version:
                return v
        raise HTTPException(status_code=404, detail="Version not found")

    @router.post("/{workflow_id}/versions/restore/{version:int}")
    async def restore_version(
        workflow_id: str,
        version: int,
        session: AsyncSession = Depends(get_session),
    ) -> Workflow:
        """Restore a workflow to a previous version."""
        wf = await _wf_repo.get(session, workflow_id)
        if not wf:
            raise HTTPException(status_code=404, detail="Workflow not found")
        snapshot = None
        for v in wf.versions:
            if v.version == version:
                snapshot = v
                break
        if not snapshot:
            raise HTTPException(status_code=404, detail="Version not found")

        wf.nodes = snapshot.nodes
        wf.edges = snapshot.edges
        wf.global_context = snapshot.config
        await _wf_repo.save(session, wf)
        return wf
