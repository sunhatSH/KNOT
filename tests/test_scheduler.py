"""Tests for AgentScheduler — agent registration, lookup, and node assignment."""

import pytest
from knot.core.models import Agent, AgentRole, Node, NodeType
from knot.orchestration_layer.scheduler import AgentScheduler


@pytest.fixture
def scheduler() -> AgentScheduler:
    return AgentScheduler()


# ─── Agent Registration & Lookup ────────────────────────────────────────────


class TestAgentRegistration:
    """AgentScheduler.register_agent() and get_agent()."""

    def test_register_and_get(self, scheduler, sample_agent_executor):
        scheduler.register_agent(sample_agent_executor)
        retrieved = scheduler.get_agent("agent_executor")
        assert retrieved is not None
        assert retrieved.name == "Executor"
        assert retrieved.role == AgentRole.EXECUTOR

    def test_get_agent_not_found(self, scheduler):
        assert scheduler.get_agent("nonexistent") is None

    def test_register_overwrites_existing(self, scheduler):
        agent_a = Agent(id="same_id", name="Alpha", role=AgentRole.EXECUTOR)
        agent_b = Agent(id="same_id", name="Beta", role=AgentRole.PLANNER)
        scheduler.register_agent(agent_a)
        scheduler.register_agent(agent_b)
        retrieved = scheduler.get_agent("same_id")
        assert retrieved is not None
        assert retrieved.name == "Beta"  # Last registered wins

    def test_register_default_agents_count(self, scheduler):
        agents = scheduler.register_default_agents()
        assert len(agents) == 6

    def test_register_default_agents_ids(self, scheduler):
        scheduler.register_default_agents()
        expected_ids = {
            "agent_planner",
            "agent_researcher",
            "agent_coder",
            "agent_executor",
            "agent_validator",
            "agent_summarizer",
        }
        registered_ids = {a.id for a in scheduler.list_agents()}
        assert registered_ids == expected_ids

    def test_register_default_agents_roles(self, scheduler):
        agents = scheduler.register_default_agents()
        roles = {a.role for a in agents}
        assert roles == {
            AgentRole.PLANNER,
            AgentRole.RESEARCHER,
            AgentRole.CODER,
            AgentRole.EXECUTOR,
            AgentRole.VALIDATOR,
            AgentRole.SUMMARIZER,
        }


class TestGetAgentsByRole:
    """AgentScheduler.get_agents_by_role()."""

    def test_single_match(self, scheduler):
        scheduler.register_default_agents()
        planners = scheduler.get_agents_by_role(AgentRole.PLANNER)
        assert len(planners) == 1
        assert planners[0].id == "agent_planner"

    def test_multiple_matches(self, scheduler):
        scheduler.register_agent(
            Agent(id="exec1", name="Exec1", role=AgentRole.EXECUTOR)
        )
        scheduler.register_agent(
            Agent(id="exec2", name="Exec2", role=AgentRole.EXECUTOR)
        )
        executors = scheduler.get_agents_by_role(AgentRole.EXECUTOR)
        assert len(executors) == 2

    def test_no_match(self, scheduler):
        agents = scheduler.get_agents_by_role(AgentRole.PLANNER)
        assert agents == []

    def test_list_agents(self, scheduler):
        scheduler.register_default_agents()
        all_agents = scheduler.list_agents()
        assert len(all_agents) == 6

    def test_list_agents_empty(self, scheduler):
        assert scheduler.list_agents() == []


# ─── Node Assignment ────────────────────────────────────────────────────────


class TestAssignNode:
    """AgentScheduler.assign_node() selects the best agent for a node."""

    @pytest.mark.asyncio
    async def test_assign_by_agent_id(self, scheduler):
        scheduler.register_default_agents()
        node = Node(
            type=NodeType.TASK,
            label="Research Task",
            agent_id="agent_researcher",
        )
        agent = await scheduler.assign_node(node, {})
        assert agent is not None
        assert agent.id == "agent_researcher"
        assert agent.role == AgentRole.RESEARCHER

    @pytest.mark.asyncio
    async def test_assign_by_role(self, scheduler):
        scheduler.register_default_agents()
        node = Node(
            type=NodeType.TASK,
            label="Code Task",
            config={"agent_role": "coder"},
        )
        agent = await scheduler.assign_node(node, {})
        assert agent is not None
        assert agent.role == AgentRole.CODER
        assert agent.id == "agent_coder"

    @pytest.mark.asyncio
    async def test_assign_default_role(self, scheduler):
        scheduler.register_default_agents()
        node = Node(type=NodeType.TASK, label="Generic Task")
        agent = await scheduler.assign_node(node, {})
        assert agent is not None
        assert agent.role == AgentRole.EXECUTOR

    @pytest.mark.asyncio
    async def test_assign_no_match_returns_none(self, scheduler):
        # Scheduler has no registered agents
        node = Node(type=NodeType.TASK, label="Orphan")
        agent = await scheduler.assign_node(node, {})
        assert agent is None

    @pytest.mark.asyncio
    async def test_assign_prefers_id_over_role(self, scheduler):
        scheduler.register_default_agents()
        # Node has both explicit agent_id and a different role config
        node = Node(
            type=NodeType.TASK,
            label="Custom",
            agent_id="agent_coder",
            config={"agent_role": "planner"},
        )
        agent = await scheduler.assign_node(node, {})
        assert agent is not None
        assert agent.id == "agent_coder"
        assert agent.role == AgentRole.CODER

    @pytest.mark.asyncio
    async def test_assign_fallback_when_agent_id_missing(self, scheduler):
        scheduler.register_default_agents()
        # agent_id refers to a non-existent agent
        node = Node(
            type=NodeType.TASK,
            label="Missing ID",
            agent_id="agent_ghost",
        )
        agent = await scheduler.assign_node(node, {})
        # Should fall back to role-based lookup (default: executor)
        assert agent is not None
        assert agent.role == AgentRole.EXECUTOR

    @pytest.mark.asyncio
    async def test_assign_unknown_role_falls_to_executor(self, scheduler):
        scheduler.register_default_agents()
        node = Node(
            type=NodeType.TASK,
            label="Unknown Role",
            config={"agent_role": "nonexistent_role"},
        )
        agent = await scheduler.assign_node(node, {})
        # The role_map won't match, so it defaults to executor
        assert agent is not None
        assert agent.role == AgentRole.EXECUTOR
