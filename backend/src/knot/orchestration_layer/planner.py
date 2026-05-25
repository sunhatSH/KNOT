"""Task planning module — converts intent into a DAG workflow."""

from __future__ import annotations

import json
import logging
from typing import Any

from knot.core.models import Edge, Node, NodeType, Workflow
from knot.llm import LLMProvider
from knot.llm.base import LLMMessage

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """\
You are a task planning engine. Given a user's goal and available agents,
design a DAG (Directed Acyclic Graph) workflow to accomplish it.

Available node types:
- task: A unit of work assigned to an agent
- condition: A decision point that routes to different branches
- parallel: A fan-out point for parallel execution
- loop: An iterative execution node
- input: Entry point for external data
- output: Terminal node that produces the final result

Respond in JSON format:
{
  "workflow_name": "descriptive name",
  "description": "what this workflow does",
  "nodes": [
    {
      "id": "node_001",
      "type": "task",
      "label": "meaningful label",
      "agent_role": "executor|planner|validator|summarizer",
      "inputs": {"param1": "source_param"},
      "outputs": {"result": "output_name"},
      "config": {}
    }
  ],
  "edges": [
    {"source_id": "node_001", "target_id": "node_002", "label": ""}
  ]
}
"""


class TaskPlanner:
    """Converts parsed intents into Workflow DAGs."""

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    async def plan(
        self,
        intent: dict[str, Any],
        available_agents: list[dict[str, Any]] | None = None,
    ) -> Workflow:
        """Generate a workflow DAG from a parsed intent."""
        agents_context = (
            f"Available agents: {json.dumps(available_agents, ensure_ascii=False)}"
            if available_agents
            else ""
        )

        messages = [
            LLMMessage(role="system", content=PLANNER_SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=f"Goal: {intent.get('goal', '')}\n"
                f"Constraints: {json.dumps(intent.get('constraints', []), ensure_ascii=False)}\n"
                f"Expected output: {intent.get('expected_output', '')}\n"
                f"Domain hints: {json.dumps(intent.get('domain_hints', []), ensure_ascii=False)}\n"
                f"{agents_context}",
            ),
        ]

        response = await self._llm.chat(messages, temperature=0.2)

        try:
            plan_data = json.loads(response.content)
        except json.JSONDecodeError:
            logger.error("Planner returned non-JSON: %.200s", response.content)
            plan_data = self._fallback_plan(intent)

        nodes = [Node(**n) for n in plan_data.get("nodes", [])]
        edges = [Edge(**e) for e in plan_data.get("edges", [])]

        workflow = Workflow(
            name=plan_data.get("workflow_name", intent.get("goal", "Untitled")),
            description=plan_data.get("description", ""),
            nodes=nodes,
            edges=edges,
        )
        logger.info("Planned workflow '%s' with %d nodes, %d edges", workflow.name, len(nodes), len(edges))
        return workflow

    def _fallback_plan(self, intent: dict[str, Any]) -> dict[str, Any]:
        """Generate a minimal fallback plan when LLM parsing fails."""
        return {
            "workflow_name": intent.get("goal", "Untitled Workflow"),
            "description": "Auto-generated fallback workflow",
            "nodes": [
                {
                    "id": "node_001",
                    "type": "input",
                    "label": "Input",
                    "inputs": {},
                    "outputs": {"data": "user_input"},
                    "config": {},
                },
                {
                    "id": "node_002",
                    "type": "task",
                    "label": "Execute Task",
                    "agent_role": "executor",
                    "inputs": {"input": "user_input"},
                    "outputs": {"result": "output"},
                    "config": {},
                },
                {
                    "id": "node_003",
                    "type": "output",
                    "label": "Output",
                    "inputs": {"data": "output"},
                    "outputs": {},
                    "config": {},
                },
            ],
            "edges": [
                {"source_id": "node_001", "target_id": "node_002", "label": ""},
                {"source_id": "node_002", "target_id": "node_003", "label": ""},
            ],
        }
