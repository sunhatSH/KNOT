"""Workflow management API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from knot.core.models import Execution, Workflow
from knot.llm.base import LLMProvider
from knot.orchestration_layer.intent_understanding import nl_to_workflow
from knot.orchestration_layer.workflow import WorkflowEngine

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])


# In-memory stores for MVP (replace with DB later)
_workflows: dict[str, Workflow] = {}
_executions: dict[str, Execution] = {}


def configure_routes(
    engine: WorkflowEngine,
    llm_provider: LLMProvider | None = None,
) -> None:
    """Inject the workflow engine (and optional LLM) dependency into routes."""

    @router.post("/from-nl")
    async def create_workflow_from_nl(request: dict[str, str]) -> Workflow:
        """Create a workflow from a natural language description."""
        if llm_provider is None:
            raise HTTPException(
                status_code=503,
                detail="LLM provider not available for NL→Workflow conversion",
            )
        description = request.get("description", "")
        if not description:
            raise HTTPException(
                status_code=422,
                detail="'description' field is required",
            )
        workflow = await nl_to_workflow(description, llm_provider)
        _workflows[workflow.id] = workflow
        return workflow

    @router.post("")
    async def create_workflow(workflow: Workflow) -> Workflow:
        """Create a new workflow definition."""
        _workflows[workflow.id] = workflow
        return workflow

    @router.get("")
    async def list_workflows() -> list[Workflow]:
        """List all workflow definitions."""
        return list(_workflows.values())

    @router.get("/{workflow_id}")
    async def get_workflow(workflow_id: str) -> Workflow:
        """Get a workflow by ID."""
        wf = _workflows.get(workflow_id)
        if not wf:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return wf

    @router.post("/{workflow_id}/execute")
    async def execute_workflow(
        workflow_id: str, context: dict[str, Any] = {}
    ) -> Execution:
        """Execute a workflow."""
        wf = _workflows.get(workflow_id)
        if not wf:
            raise HTTPException(status_code=404, detail="Workflow not found")

        wf.global_context.update(context)
        execution = await engine.execute(wf)
        _executions[execution.id] = execution
        return execution

    @router.get("/executions/{execution_id}")
    async def get_execution(execution_id: str) -> Execution:
        """Get execution status and results."""
        exec_ = _executions.get(execution_id)
        if not exec_:
            raise HTTPException(status_code=404, detail="Execution not found")
        return exec_
