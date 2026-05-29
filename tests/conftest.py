"""Pytest fixtures for KNOT backend tests.

Sets up the Python path and overrides the database URL to use an
in-memory SQLite database so tests do not require a real PostgreSQL
or Milvus instance.
"""

import os
import sys
from pathlib import Path

# Override database URL so that engine creation during import
# uses SQLite (which is always available with aiosqlite) instead
# of the PostgreSQL URL defined in the .env file.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")

# Add the backend source directory to sys.path so that
# `from knot.core.models import ...` works when tests are run
# from the project root (/Users/sunhao/Documents/KNOT).
_src = str(Path(__file__).resolve().parent.parent / "backend" / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

import pytest
from knot.core.models import Agent, AgentRole, Edge, Node, NodeType, Workflow


# ─── Node fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def sample_node_task() -> Node:
    return Node(id="n1", type=NodeType.TASK, label="Test Task")


@pytest.fixture
def sample_node_input() -> Node:
    return Node(id="n_input", type=NodeType.INPUT, label="Input")


@pytest.fixture
def sample_node_output() -> Node:
    return Node(id="n_output", type=NodeType.OUTPUT, label="Output")


# ─── Edge fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def sample_edge() -> Edge:
    return Edge(id="e1", source_id="n1", target_id="n2")


# ─── Agent fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def sample_agent_executor() -> Agent:
    return Agent(id="agent_executor", name="Executor", role=AgentRole.EXECUTOR)


@pytest.fixture
def sample_agent_planner() -> Agent:
    return Agent(id="agent_planner", name="Planner", role=AgentRole.PLANNER)


# ─── Workflow fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def linear_workflow() -> Workflow:
    """A -> B -> C"""
    nodes = [
        Node(id="a", type=NodeType.TASK, label="A"),
        Node(id="b", type=NodeType.TASK, label="B"),
        Node(id="c", type=NodeType.TASK, label="C"),
    ]
    edges = [
        Edge(id="e1", source_id="a", target_id="b"),
        Edge(id="e2", source_id="b", target_id="c"),
    ]
    return Workflow(name="Linear Workflow", nodes=nodes, edges=edges)


@pytest.fixture
def diamond_workflow() -> Workflow:
    """     B
          / \
         A   D
          \ /
           C
    """
    nodes = [
        Node(id="a", type=NodeType.TASK, label="A"),
        Node(id="b", type=NodeType.TASK, label="B"),
        Node(id="c", type=NodeType.TASK, label="C"),
        Node(id="d", type=NodeType.TASK, label="D"),
    ]
    edges = [
        Edge(id="e1", source_id="a", target_id="b"),
        Edge(id="e2", source_id="a", target_id="c"),
        Edge(id="e3", source_id="b", target_id="d"),
        Edge(id="e4", source_id="c", target_id="d"),
    ]
    return Workflow(name="Diamond Workflow", nodes=nodes, edges=edges)


@pytest.fixture
def complex_dag() -> Workflow:
    """Complex DAG with multiple dependency layers

    A -> B -> D
    A -> B -> E
    A -> C -> E
    """
    nodes = [
        Node(id="a", type=NodeType.TASK, label="A"),
        Node(id="b", type=NodeType.TASK, label="B"),
        Node(id="c", type=NodeType.TASK, label="C"),
        Node(id="d", type=NodeType.TASK, label="D"),
        Node(id="e", type=NodeType.TASK, label="E"),
    ]
    edges = [
        Edge(id="e1", source_id="a", target_id="b"),
        Edge(id="e2", source_id="a", target_id="c"),
        Edge(id="e3", source_id="b", target_id="d"),
        Edge(id="e4", source_id="b", target_id="e"),
        Edge(id="e5", source_id="c", target_id="e"),
    ]
    return Workflow(name="Complex DAG", nodes=nodes, edges=edges)
