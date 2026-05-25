"""Agent scheduler — routes tasks to agents and manages multi-agent teams."""

from __future__ import annotations

import logging
from typing import Any

from knot.core.models import Agent, AgentRole, MultiAgentMode, Node

logger = logging.getLogger(__name__)


class AgentScheduler:
    """Routes workflow tasks to appropriate agents and manages multi-agent coordination.

    Supports:
    - Single agent assignment by role or ID
    - Agent teams for parallel/debate execution
    - Runtime agent registration and discovery
    """

    def __init__(self):
        self._agents: dict[str, Agent] = {}

    # ─── Registration ───────────────────────────────────────────────────

    def register_agent(self, agent: Agent) -> None:
        """Register an agent with the scheduler."""
        self._agents[agent.id] = agent
        logger.info("Registered agent: %s (%s)", agent.name, agent.role.value)

    def register_default_agents(self) -> list[Agent]:
        """Register and return a standard set of agents for multi-agent collaboration."""
        agents = [
            Agent(
                id="agent_planner",
                name="Planner",
                role=AgentRole.PLANNER,
                system_prompt=(
                    "You are a task planning agent. Analyze complex tasks and break them "
                    "down into clear, actionable steps. Define dependencies between steps "
                    "and identify the optimal execution order."
                ),
            ),
            Agent(
                id="agent_researcher",
                name="Researcher",
                role=AgentRole.RESEARCHER,
                system_prompt=(
                    "You are a research specialist agent. You excel at gathering, analyzing, "
                    "and synthesizing information. Be thorough, cite sources when possible, "
                    "and organize findings in a structured format."
                ),
            ),
            Agent(
                id="agent_coder",
                name="Coder",
                role=AgentRole.CODER,
                system_prompt=(
                    "You are a code specialist agent. You write clean, efficient, well-documented "
                    "code. When solving problems, explain your approach first, then provide "
                    "the implementation. Handle edge cases and include error handling."
                ),
            ),
            Agent(
                id="agent_executor",
                name="Executor",
                role=AgentRole.EXECUTOR,
                system_prompt=(
                    "You are a general-purpose execution agent. You handle a wide range of tasks "
                    "efficiently and accurately. When given a task, complete it thoroughly "
                    "and present results in a clear, organized manner."
                ),
            ),
            Agent(
                id="agent_validator",
                name="Validator",
                role=AgentRole.VALIDATOR,
                system_prompt=(
                    "You are a quality validation agent. Review work for correctness, "
                    "completeness, and quality. Identify errors, inconsistencies, and "
                    "areas for improvement. Provide specific, actionable feedback."
                ),
            ),
            Agent(
                id="agent_summarizer",
                name="Summarizer",
                role=AgentRole.SUMMARIZER,
                system_prompt=(
                    "You are a summarization agent. Synthesize complex information into "
                    "clear, concise summaries. Focus on key findings, decisions, and "
                    "actionable outputs. Maintain accuracy while maximizing clarity."
                ),
            ),
        ]
        for a in agents:
            self.register_agent(a)
        return agents

    # ─── Lookup ─────────────────────────────────────────────────────────

    def get_agent(self, agent_id: str) -> Agent | None:
        """Get an agent by ID."""
        return self._agents.get(agent_id)

    def get_agents_by_role(self, role: AgentRole) -> list[Agent]:
        """Find all agents matching a role."""
        return [a for a in self._agents.values() if a.role == role]

    def list_agents(self) -> list[Agent]:
        """List all registered agents."""
        return list(self._agents.values())

    # ─── Node Assignment ────────────────────────────────────────────────

    async def assign_node(self, node: Node, context: dict[str, Any]) -> Agent | None:
        """Assign a single node to the most suitable agent."""
        # Exact ID match
        if node.agent_id and node.agent_id in self._agents:
            return self._agents[node.agent_id]

        # Role-based match
        role_map: dict[str, AgentRole] = {
            "planner": AgentRole.PLANNER,
            "executor": AgentRole.EXECUTOR,
            "researcher": AgentRole.RESEARCHER,
            "coder": AgentRole.CODER,
            "validator": AgentRole.VALIDATOR,
            "summarizer": AgentRole.SUMMARIZER,
        }
        preferred_role_str = node.config.get("agent_role", "executor")
        preferred_role = role_map.get(preferred_role_str, AgentRole.EXECUTOR)
        candidates = self.get_agents_by_role(preferred_role)
        if candidates:
            return candidates[0]

        logger.warning("No agent found for node %s (role: %s)", node.id, preferred_role_str)
        return None

    async def assign_team(
        self,
        node: Node,
        context: dict[str, Any],
    ) -> list[Agent]:
        """Assign a team of agents based on the node's multi-agent mode.

        For PARALLEL mode: returns agents of the specified role (all of them).
        For DEBATE mode: returns agents from different roles for diverse perspectives.
        For SINGLE mode: returns single agent (same as assign_node).
        """
        mode = MultiAgentMode(node.config.get("multi_agent_mode", "single"))

        if mode == MultiAgentMode.SINGLE:
            agent = await self.assign_node(node, context)
            return [agent] if agent else []

        if mode == MultiAgentMode.PARALLEL:
            role_str = node.config.get("agent_role", "executor")
            role_map = {
                "planner": AgentRole.PLANNER, "executor": AgentRole.EXECUTOR,
                "researcher": AgentRole.RESEARCHER, "coder": AgentRole.CODER,
                "validator": AgentRole.VALIDATOR, "summarizer": AgentRole.SUMMARIZER,
            }
            role = role_map.get(role_str, AgentRole.EXECUTOR)
            return self.get_agents_by_role(role)

        if mode == MultiAgentMode.DEBATE:
            # Diverse team: one of each relevant role
            team_ids = node.config.get("debate_agent_ids", [])
            if team_ids:
                return [a for aid in team_ids if (a := self.get_agent(aid))]

            # Default debate team: researcher + coder + validator
            return [
                a for role in [AgentRole.RESEARCHER, AgentRole.CODER, AgentRole.VALIDATOR]
                for a in self.get_agents_by_role(role)[:1]
            ]

        return []
