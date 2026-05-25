"""Intent understanding module — converts natural language to workflow DAG.

This module bridges the gap between user intent and executable workflows.
It uses an LLM to parse natural language task descriptions into structured
intents, then generates complete Workflow DAG objects from those intents.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from knot.core.models import (
    AgentRole,
    Edge,
    MultiAgentMode,
    Node,
    NodeType,
    Workflow,
)
from knot.llm.base import LLMMessage, LLMProvider

logger = logging.getLogger(__name__)

# ─── Models ─────────────────────────────────────────────────────────────────


class SubTask(BaseModel):
    """A single sub-task extracted from user intent."""

    id: str = ""
    label: str
    description: str
    agent_role: str = "executor"
    depends_on: list[str] = Field(default_factory=list)
    node_type: str = "task"
    multi_agent_mode: str = "single"
    needs_knowledge: bool = True


class Intent(BaseModel):
    """Structured intent parsed from natural language."""

    task_description: str
    subtasks: list[SubTask]
    expected_output: str
    knowledge_domains: list[str] = Field(default_factory=list)
    global_instructions: str = ""


# ─── LLM Prompts ────────────────────────────────────────────────────────────

INTENT_PARSE_PROMPT = """\
You are a task planning AI. Given a user's natural language request, analyze it
and produce a structured task plan in JSON format.

Analyze the following aspects:
1. What is the overall goal?
2. What are the logical sub-steps needed to achieve it?
3. What are the dependencies between these sub-steps?
4. What kind of knowledge/domain expertise is required?
5. What is the expected output format?

Available agent roles:
- planner: strategic planning and decomposition
- researcher: information gathering and analysis
- coder: code generation and implementation
- executor: general-purpose execution
- validator: quality checking and validation
- summarizer: synthesis and summarization

Available node types:
- task: a regular execution step (most common)
- input: data entry point (always first)
- output: result collection (always last)
- condition: decision branch
- loop: repeated execution

Rules:
- Break the task into 2-6 sub-tasks
- The first sub-task should typically be "input" type
- The last sub-task should typically be "output" type
- Set depends_on based on logical ordering
- Set needs_knowledge=true for research/analysis steps
- For tasks requiring multiple perspectives, set multi_agent_mode to "parallel"
- For tasks needing validation, include a validator step

Respond ONLY with a valid JSON object. Use this exact structure:
[
  "task_description": a short summary,
  "subtasks": list of objects with keys:
    - label, description, agent_role, depends_on, node_type, multi_agent_mode, needs_knowledge,
  "expected_output": description,
  "knowledge_domains": list of relevant topics,
  "global_instructions": any special instructions
]

User request: %s
"""

WORKFLOW_GENERATE_PROMPT = """\
You are a workflow architect. Given a structured intent analysis, generate
additional configuration for each sub-task to make it executable.

For each sub-task, determine:
1. The appropriate LLM model to use (default: "deepseek-chat")
2. Max iterations (if loop type)
3. Timeout in seconds

Intent:
{intent_json}

Respond ONLY with a JSON object matching:
{{
  "subtask_configs": {{
    "subtask_label": {{
      "model": "deepseek-chat",
      "timeout_seconds": 120,
      "max_iterations": 3,
      "system_prompt_hint": "additional context for this step"
    }}
  }}
}}
"""


# ─── Parser ─────────────────────────────────────────────────────────────────


class IntentParser:
    """Parses natural language into structured Workflow objects."""

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    async def parse(self, user_request: str) -> Intent:
        """Parse a natural language request into a structured Intent."""
        logger.info("Parsing intent: %.80s", user_request)

        messages = [
            LLMMessage(
                role="user",
                content=INTENT_PARSE_PROMPT % user_request,
            ),
        ]

        response = await self._llm.chat(messages, temperature=0.2)
        logger.warning("LLM raw response: %.500s", response.content)
        intent = self._parse_response(response.content)
        logger.info(
            "Parsed intent: %d sub-tasks, domains: %s",
            len(intent.subtasks),
            intent.knowledge_domains,
        )
        return intent

    def _parse_response(self, content: str) -> Intent:
        """Parse LLM response JSON into an Intent object.

        Handles JSON code blocks and direct JSON responses.
        """
        # Strip markdown code fences if present
        text = content.strip()
        if text.startswith("```"):
            # Extract content between first and last ```
            start = text.find("\n") + 1
            end = text.rfind("```")
            if end > start:
                text = text[start:end].strip()
            else:
                text = text[6:].strip()  # remove ```json prefix

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning("JSON parse failed (%s), raw: %.100s", e, text)
            # Fallback: create a minimal intent wrapping the raw request
            return Intent(
                task_description=content[:200],
                subtasks=[
                    SubTask(
                        label="Execute Task",
                        description=content[:500],
                        agent_role="executor",
                        node_type="task",
                    )
                ],
                expected_output="Task result",
            )

        # Handle both dict ({"subtasks": [...]}) and list ([{...}, ...]) responses
        if isinstance(data, list):
            raw_subtasks = data
            task_desc = ""
            expected_out = ""
            domains = []
            instructions = ""
        else:
            raw_subtasks = data.get("subtasks", data.get("steps", []))
            task_desc = data.get("task_description", "")
            expected_out = data.get("expected_output", "")
            domains = data.get("knowledge_domains", data.get("domains", []))
            instructions = data.get("global_instructions", "")

        subtasks = []
        for st in raw_subtasks if isinstance(raw_subtasks, list) else []:
            label = st.get("label", st.get("name", "Untitled Step"))
            subtasks.append(
                SubTask(
                    label=label,
                    description=st.get("description", ""),
                    agent_role=st.get("agent_role", st.get("role", "executor")),
                    depends_on=st.get("depends_on", st.get("depends", [])),
                    node_type=st.get("node_type", st.get("type", "task")),
                    multi_agent_mode=st.get("multi_agent_mode", "single"),
                    needs_knowledge=st.get("needs_knowledge", True),
                )
            )

        return Intent(
            task_description=task_desc,
            subtasks=subtasks,
            expected_output=expected_out,
            knowledge_domains=domains,
            global_instructions=instructions,
        )


# ─── Workflow Generator ─────────────────────────────────────────────────────


class WorkflowGenerator:
    """Generates executable Workflow DAGs from parsed Intents."""

    ROLE_TO_AGENT_ID: dict[str, str] = {
        "planner": "agent_planner",
        "researcher": "agent_researcher",
        "coder": "agent_coder",
        "executor": "agent_executor",
        "validator": "agent_validator",
        "summarizer": "agent_summarizer",
    }

    def __init__(self, llm_provider: LLMProvider | None = None):
        self._llm = llm_provider

    async def generate(
        self,
        intent: Intent,
        user_request: str = "",
    ) -> Workflow:
        """Convert a parsed Intent into a complete Workflow DAG."""
        logger.info(
            "Generating workflow from intent: %s",
            intent.task_description[:60],
        )

        # Collect subtask configs from LLM (optional enhancement)
        config_map: dict[str, dict[str, Any]] = {}
        if self._llm and intent.subtasks:
            config_map = await self._enrich_subtask_configs(intent)

        # Build nodes
        nodes: list[Node] = []
        name_to_id: dict[str, str] = {}

        for i, st in enumerate(intent.subtasks):
            node_type = NodeType(st.node_type)
            agent_id = self.ROLE_TO_AGENT_ID.get(st.agent_role)

            config = config_map.get(st.label, {})

            node = Node(
                type=node_type,
                label=st.label,
                # description stored in config

                agent_id=agent_id,
                config={
                    "agent_role": st.agent_role,
                    "multi_agent_mode": st.multi_agent_mode,
                    "knowledge_enabled": st.needs_knowledge,
                    "intent_description": st.description[:200],
                    "model": config.get("model", "deepseek-chat"),
                    "timeout_seconds": config.get("timeout_seconds", 120),
                    "max_iterations": config.get("max_iterations", 3),
                    "system_prompt_hint": config.get(
                        "system_prompt_hint", ""
                    ),
                },
                max_retries=2,
            )

            nodes.append(node)
            name_to_id[st.label] = node.id

        # Build edges from dependency information
        edges: list[Edge] = []
        for st in intent.subtasks:
            target_id = name_to_id.get(st.label)
            if not target_id:
                continue
            for dep_label in st.depends_on:
                source_id = name_to_id.get(dep_label)
                if source_id:
                    edges.append(
                        Edge(source_id=source_id, target_id=target_id)
                    )

        # If no edges inferred, chain sequentially
        if not edges and len(nodes) > 1:
            for i in range(len(nodes) - 1):
                edges.append(
                    Edge(
                        source_id=nodes[i].id,
                        target_id=nodes[i + 1].id,
                    )
                )

        global_context = {
            "user_request": user_request,
            "task_description": intent.task_description,
            "knowledge_domains": intent.knowledge_domains,
            "global_instructions": intent.global_instructions,
        }

        # Extract a name from the task description
        name = intent.task_description[:60] or "Auto-generated Workflow"

        workflow = Workflow(
            name=name,
            description=intent.task_description[:500],
            nodes=nodes,
            edges=edges,
            global_context=global_context,
            tags=intent.knowledge_domains,
        )

        logger.info(
            "Generated workflow '%s' with %d nodes, %d edges",
            workflow.id,
            len(nodes),
            len(edges),
        )
        return workflow

    async def _enrich_subtask_configs(
        self,
        intent: Intent,
    ) -> dict[str, dict[str, Any]]:
        """Optionally enrich subtasks with LLM-generated config."""
        if not self._llm:
            return {}

        messages = [
            LLMMessage(
                role="system",
                content=WORKFLOW_GENERATE_PROMPT.format(
                    intent_json=intent.model_dump_json()
                ),
            ),
            LLMMessage(
                role="user",
                content="Generate configuration for these sub-tasks.",
            ),
        ]

        try:
            response = await self._llm.chat(messages, temperature=0.1)
            text = response.content.strip()
            if text.startswith("```"):
                start = text.find("\n") + 1
                end = text.rfind("```")
                if end > start:
                    text = text[start:end].strip()
            data = json.loads(text)
            return data.get("subtask_configs", {})
        except Exception as e:
            logger.warning("Config enrichment failed: %s", e)
            return {}


# ─── Convenience API ────────────────────────────────────────────────────────


async def nl_to_workflow(
    user_request: str,
    llm_provider: LLMProvider,
) -> Workflow:
    """One-shot: natural language → parsed intent → executable workflow.

    This is the main entry point for the intent understanding pipeline.
    """
    parser = IntentParser(llm_provider)
    generator = WorkflowGenerator(llm_provider)

    intent = await parser.parse(user_request)
    workflow = await generator.generate(intent, user_request=user_request)

    logger.info(
        "NL→Workflow complete: '%s' (%d nodes, %d edges)",
        workflow.name,
        len(workflow.nodes),
        len(workflow.edges),
    )
    return workflow
