"""Agent scheduler — routes tasks to appropriate agents."""

from __future__ import annotations

import logging
from typing import Any

from knot.core.models import Agent, AgentRole, Node

logger = logging.getLogger(__name__)


class AgentScheduler:
    """Routes workflow tasks to appropriate agents and manages multi-agent coordination."""

    def __init__(self):
        self._agents: dict[str, Agent] = {}

    def register_agent(self, agent: Agent) -> None:
        """Register an agent with the scheduler."""
        self._agents[agent.id] = agent
        logger.info("Registered agent: %s (%s)", agent.name, agent.role)

    def get_agent(self, agent_id: str) -> Agent | None:
        """Get an agent by ID."""
        return self._agents.get(agent_id)

    def get_agents_by_role(self, role: AgentRole) -> list[Agent]:
        """Find all agents matching a role."""
        return [a for a in self._agents.values() if a.role == role]

    async def assign_node(self, node: Node, context: dict[str, Any]) -> Agent | None:
        """Assign a node to the most suitable agent."""
        if node.agent_id and node.agent_id in self._agents:
            return self._agents[node.agent_id]

        role_map = {
            "planner": AgentRole.PLANNER,
            "executor": AgentRole.EXECUTOR,
            "validator": AgentRole.VALIDATOR,
            "summarizer": AgentRole.SUMMARIZER,
        }
        preferred_role = role_map.get(node.config.get("agent_role", ""), AgentRole.EXECUTOR)
        candidates = self.get_agents_by_role(preferred_role)

        if candidates:
            return candidates[0]

        logger.warning("No agent found for node %s (role: %s)", node.id, preferred_role)
        return None

    def list_agents(self) -> list[Agent]:
        """List all registered agents."""
        return list(self._agents.values())
