"""Agent management API routes."""

from __future__ import annotations

from fastapi import APIRouter

from knot.core.models import Agent
from knot.orchestration_layer.scheduler import AgentScheduler

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

_scheduler: AgentScheduler | None = None


def configure_routes(scheduler: AgentScheduler) -> None:
    """Inject dependencies into agent routes."""
    global _scheduler
    _scheduler = scheduler

    @router.post("")
    async def register_agent(agent: Agent) -> Agent:
        """Register a new agent."""
        scheduler.register_agent(agent)
        return agent

    @router.get("")
    async def list_agents() -> list[Agent]:
        """List all registered agents."""
        return scheduler.list_agents()
