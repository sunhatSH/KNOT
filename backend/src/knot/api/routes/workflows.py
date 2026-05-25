"""Workflow management API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from knot.core.database import get_session
from knot.core.models import Execution, Workflow
from knot.core.repository import ExecutionRepository, WorkflowRepository
from knot.llm.base import LLMProvider
from knot.orchestration_layer.intent_understanding import nl_to_workflow
from knot.orchestration_layer.workflow import WorkflowEngine

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])

# Repository instances (stateless - session injected per-request)
_wf_repo = WorkflowRepository()
_exec_repo = ExecutionRepository()


def configure_routes(
    engine: WorkflowEngine,
    llm_provider: LLMProvider | None = None,
) -> None:
    """Inject the workflow engine (and optional LLM) dependency into routes."""

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
        """Create a new workflow definition."""
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
