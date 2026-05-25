"""Agent management API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from knot.core.database import get_session
from knot.core.models import Agent
from knot.core.repository import AgentRepository
from knot.orchestration_layer.scheduler import AgentScheduler

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

_scheduler: AgentScheduler | None = None
_agent_repo = AgentRepository()


def configure_routes(scheduler: AgentScheduler) -> None:
    """Inject dependencies into agent routes."""
    global _scheduler
    _scheduler = scheduler

    @router.post("")
    async def register_agent(
        agent: Agent,
        session: AsyncSession = Depends(get_session),
    ) -> Agent:
        """Register a new agent."""
        scheduler.register_agent(agent)
        await _agent_repo.save(session, agent)
        return agent

    @router.get("")
    async def list_agents(
        session: AsyncSession = Depends(get_session),
    ) -> list[Agent]:
        """List all registered agents."""
        return await _agent_repo.list(session)
