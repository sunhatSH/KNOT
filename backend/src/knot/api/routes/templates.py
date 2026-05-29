"""Workflow template API routes.

Provides CRUD operations for ``WorkflowTemplate`` as well as the
``instantiate`` endpoint that materialises a template into a live
``Workflow``.

Category listing, server-side search/filter, and usage tracking are
also exposed for the template browser UI.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from knot.core.database import get_session
from knot.core.models import Workflow, WorkflowTemplate
from knot.core.repository import WorkflowRepository
from knot.core.template_store import TemplateStore

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])

_store = TemplateStore()
_wf_repo = WorkflowRepository()


@router.get("")
async def list_templates(
    category: str | None = Query(None, description="Filter by category"),
    search: str | None = Query(None, description="Search by name, description, or tags"),
) -> list[WorkflowTemplate]:
    """Return all stored templates, optionally filtered."""
    return _store.list_templates(category=category, search=search)


@router.get("/categories")
async def list_categories() -> list[dict]:
    """Return distinct template categories with usage counts."""
    return _store.list_categories()


@router.get("/{template_id}")
async def get_template(template_id: str) -> WorkflowTemplate:
    """Return a single template by id."""
    tpl = _store.get_template(template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return tpl


@router.post("", status_code=201)
async def create_template(
    template: WorkflowTemplate,
) -> WorkflowTemplate:
    """Save a new template (or overwrite an existing one with the same id)."""
    return _store.save_template(template)


@router.post("/{template_id}/use")
async def use_template(template_id: str) -> WorkflowTemplate:
    """Increment the usage counter for a template (popularity tracking)."""
    tpl = _store.increment_usage(template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return tpl


@router.post("/{template_id}/instantiate", status_code=201)
async def instantiate_template(
    template_id: str,
    session: AsyncSession = Depends(get_session),
) -> Workflow:
    """Create a new Workflow from a template and persist it."""
    workflow = _store.instantiate(template_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Template not found")
    await _wf_repo.save(session, workflow)
    return workflow


@router.delete("/{template_id}", status_code=204)
async def delete_template(template_id: str) -> None:
    """Remove a template."""
    if not _store.delete_template(template_id):
        raise HTTPException(status_code=404, detail="Template not found")
