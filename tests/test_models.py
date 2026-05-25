"""Tests for core domain models (Node, Edge, Workflow)."""

import pytest
from knot.core.models import Edge, Node, NodeType, Workflow


# ─── Node Tests ─────────────────────────────────────────────────────────────


class TestNodeCreation:
    """Verify Node creation with every available NodeType."""

    def test_create_task_node(self):
        node = Node(type=NodeType.TASK, label="My Task")
        assert node.type == NodeType.TASK
        assert node.label == "My Task"
        assert node.id.startswith("node_")
        assert node.retry_count == 0
        assert node.max_retries == 3
        assert node.timeout_seconds == 300

    def test_create_input_node(self):
        node = Node(type=NodeType.INPUT, label="Input Data")
        assert node.type == NodeType.INPUT

    def test_create_output_node(self):
        node = Node(type=NodeType.OUTPUT, label="Output")
        assert node.type == NodeType.OUTPUT

    def test_create_condition_node(self):
        node = Node(
            type=NodeType.CONDITION, label="Check", condition="x > 5"
        )
        assert node.type == NodeType.CONDITION
        assert node.condition == "x > 5"

    def test_create_loop_node(self):
        node = Node(
            type=NodeType.LOOP,
            label="Loop",
            config={"max_iterations": 5},
        )
        assert node.type == NodeType.LOOP
        assert node.config["max_iterations"] == 5

    def test_create_parallel_node(self):
        node = Node(type=NodeType.PARALLEL, label="Parallel")
        assert node.type == NodeType.PARALLEL

    def test_node_with_agent_id(self):
        node = Node(
            type=NodeType.TASK,
            label="Agent Task",
            agent_id="agent_researcher",
        )
        assert node.agent_id == "agent_researcher"

    def test_node_with_inputs_outputs(self):
        node = Node(
            type=NodeType.TASK,
            label="Transform",
            inputs={"data": "input_data"},
            outputs={"result": "output_data"},
        )
        assert node.inputs["data"] == "input_data"
        assert node.outputs["result"] == "output_data"

    def test_node_default_status_pending(self):
        node = Node(type=NodeType.TASK, label="Fresh")
        assert node.status.value == "pending"

    def test_node_id_auto_generation(self):
        node1 = Node(type=NodeType.TASK, label="A")
        node2 = Node(type=NodeType.TASK, label="B")
        assert node1.id != node2.id


# ─── Edge Tests ─────────────────────────────────────────────────────────────


class TestEdgeCreation:
    """Verify Edge creation and field defaults."""

    def test_create_edge(self):
        edge = Edge(source_id="node_a", target_id="node_b")
        assert edge.source_id == "node_a"
        assert edge.target_id == "node_b"
        assert edge.id.startswith("edge_")
        assert edge.label == ""
        assert edge.condition is None

    def test_edge_with_label_and_condition(self):
        edge = Edge(
            source_id="a",
            target_id="b",
            label="depends on",
            condition="result == 'ok'",
        )
        assert edge.label == "depends on"
        assert edge.condition == "result == 'ok'"

    def test_edge_id_auto_generation(self):
        e1 = Edge(source_id="a", target_id="b")
        e2 = Edge(source_id="a", target_id="b")
        assert e1.id != e2.id


# ─── Workflow Tests ─────────────────────────────────────────────────────────


class TestWorkflowCreation:
    """Verify Workflow scaffolding."""

    def test_create_empty_workflow(self):
        wf = Workflow(name="Test Workflow", description="A test")
        assert wf.name == "Test Workflow"
        assert wf.description == "A test"
        assert wf.id.startswith("wf_")
        assert wf.nodes == []
        assert wf.edges == []

    def test_workflow_with_nodes_and_edges(self, linear_workflow):
        assert len(linear_workflow.nodes) == 3
        assert len(linear_workflow.edges) == 2
        assert linear_workflow.name == "Linear Workflow"

    def test_workflow_auto_id(self):
        wf1 = Workflow(name="A")
        wf2 = Workflow(name="B")
        assert wf1.id != wf2.id


class TestWorkflowGetNode:
    """Workflow.get_node() retrieves nodes by ID."""

    def test_get_node_found(self, linear_workflow):
        node = linear_workflow.get_node("a")
        assert node is not None
        assert node.label == "A"

    def test_get_node_not_found(self, linear_workflow):
        node = linear_workflow.get_node("nonexistent")
        assert node is None

    def test_get_node_after_rebuild(self, diamond_workflow):
        """Re-creating nodes with same IDs still works."""
        for node_id in ("a", "b", "c", "d"):
            assert diamond_workflow.get_node(node_id) is not None


class TestWorkflowDependencies:
    """Workflow.get_dependencies() returns upstream node IDs."""

    def test_get_dependencies_middle(self, linear_workflow):
        assert linear_workflow.get_dependencies("b") == ["a"]

    def test_get_dependencies_root(self, linear_workflow):
        assert linear_workflow.get_dependencies("a") == []

    def test_get_dependencies_leaf(self, linear_workflow):
        assert linear_workflow.get_dependencies("c") == ["b"]

    def test_get_dependencies_diamond(self, diamond_workflow):
        # D depends on both B and C
        deps = diamond_workflow.get_dependencies("d")
        assert set(deps) == {"b", "c"}

    def test_get_dependencies_nonexistent(self, linear_workflow):
        assert linear_workflow.get_dependencies("z") == []


class TestWorkflowDependents:
    """Workflow.get_dependents() returns downstream node IDs."""

    def test_get_dependents_root(self, linear_workflow):
        assert linear_workflow.get_dependents("a") == ["b"]

    def test_get_dependents_leaf(self, linear_workflow):
        assert linear_workflow.get_dependents("c") == []

    def test_get_dependents_diamond(self, diamond_workflow):
        # A has dependents B and C
        deps = diamond_workflow.get_dependents("a")
        assert set(deps) == {"b", "c"}

    def test_get_dependents_nonexistent(self, linear_workflow):
        assert linear_workflow.get_dependents("z") == []


# ─── Topological Sort Tests ─────────────────────────────────────────────────


class TestTopologicalSort:
    """Workflow.topological_sort() produces a valid topological ordering."""

    def test_linear_chain(self, linear_workflow):
        sorted_nodes = linear_workflow.topological_sort()
        ids = [n.id for n in sorted_nodes]
        assert set(ids) == {"a", "b", "c"}
        # a must come before b, b before c
        assert ids.index("a") < ids.index("b") < ids.index("c")

    def test_diamond_dag(self, diamond_workflow):
        sorted_nodes = diamond_workflow.topological_sort()
        ids = [n.id for n in sorted_nodes]
        assert set(ids) == {"a", "b", "c", "d"}
        # a must be first
        assert ids[0] == "a"
        # b and c must both come before d
        assert ids.index("b") < ids.index("d")
        assert ids.index("c") < ids.index("d")
        # d must be last
        assert ids[-1] == "d"

    def test_complex_dag(self, complex_dag):
        sorted_nodes = complex_dag.topological_sort()
        ids = [n.id for n in sorted_nodes]
        assert set(ids) == {"a", "b", "c", "d", "e"}
        # a must be first
        assert ids[0] == "a"
        # b must come before d and e
        assert ids.index("b") < ids.index("d")
        assert ids.index("b") < ids.index("e")
        # c must come before e
        assert ids.index("c") < ids.index("e")
        # d and e must come after a
        assert ids.index("d") > ids.index("a")
        assert ids.index("e") > ids.index("a")

    def test_single_node(self):
        wf = Workflow(
            name="Single", nodes=[Node(id="only", label="Only")]
        )
        sorted_nodes = wf.topological_sort()
        assert [n.id for n in sorted_nodes] == ["only"]

    def test_empty_workflow(self):
        wf = Workflow(name="Empty")
        sorted_nodes = wf.topological_sort()
        assert sorted_nodes == []

    def test_disconnected_nodes(self):
        wf = Workflow(
            name="Disconnected",
            nodes=[
                Node(id="a", label="A"),
                Node(id="b", label="B"),
                Node(id="c", label="C"),
            ],
        )
        sorted_nodes = wf.topological_sort()
        assert {n.id for n in sorted_nodes} == {"a", "b", "c"}

    def test_two_independent_chains(self):
        """A -> B  and  C -> D  (no edges between the two groups)."""
        wf = Workflow(
            name="Two Chains",
            nodes=[
                Node(id="a", label="A"),
                Node(id="b", label="B"),
                Node(id="c", label="C"),
                Node(id="d", label="D"),
            ],
            edges=[
                Edge(source_id="a", target_id="b"),
                Edge(source_id="c", target_id="d"),
            ],
        )
        sorted_nodes = wf.topological_sort()
        ids = [n.id for n in sorted_nodes]
        assert set(ids) == {"a", "b", "c", "d"}
        assert ids.index("a") < ids.index("b")
        assert ids.index("c") < ids.index("d")


# ─── Serialization Tests ────────────────────────────────────────────────────


class TestSerialization:
    """Round-trip serialization via model_dump_json / model_validate_json."""

    def test_workflow_round_trip(self, diamond_workflow):
        json_str = diamond_workflow.model_dump_json()
        restored = Workflow.model_validate_json(json_str)
        assert restored.id == diamond_workflow.id
        assert restored.name == diamond_workflow.name
        assert len(restored.nodes) == len(diamond_workflow.nodes)
        assert len(restored.edges) == len(diamond_workflow.edges)

        for original_node in diamond_workflow.nodes:
            restored_node = restored.get_node(original_node.id)
            assert restored_node is not None
            assert restored_node.type == original_node.type
            assert restored_node.label == original_node.label

    def test_node_round_trip(self, sample_node_task):
        json_str = sample_node_task.model_dump_json()
        restored = Node.model_validate_json(json_str)
        assert restored.id == sample_node_task.id
        assert restored.type == sample_node_task.type
        assert restored.label == sample_node_task.label
        assert restored.agent_id == sample_node_task.agent_id

    def test_edge_round_trip(self, sample_edge):
        json_str = sample_edge.model_dump_json()
        restored = Edge.model_validate_json(json_str)
        assert restored.id == sample_edge.id
        assert restored.source_id == sample_edge.source_id
        assert restored.target_id == sample_edge.target_id

    def test_empty_workflow_round_trip(self):
        wf = Workflow(name="Empty")
        json_str = wf.model_dump_json()
        restored = Workflow.model_validate_json(json_str)
        assert restored.name == "Empty"
        assert restored.nodes == []
        assert restored.edges == []

    def test_round_trip_preserves_status(self):
        node = Node(type=NodeType.TASK, label="Running", status="running")
        json_str = node.model_dump_json()
        restored = Node.model_validate_json(json_str)
        assert restored.status.value == "running"
