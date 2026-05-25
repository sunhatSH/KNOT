"""Intent understanding module — converts natural language to workflow DAG.

This module bridges the gap between user intent and executable workflows.
It uses an LLM to parse natural language task descriptions into structured
intents, then generates complete Workflow DAG objects from those intents.
"""

from __future__ import annotations

import json
import logging
import re
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

# ─── Constants ──────────────────────────────────────────────────────────────

CHINESE_FIELD_MAP: dict[str, str] = {
    "任务描述": "task_description",
    "子任务": "subtasks",
    "输出": "expected_output",
    "预期输出": "expected_output",
    "知识领域": "knowledge_domains",
    "知识域": "knowledge_domains",
    "全局指令": "global_instructions",
    "标签": "label",
    "名称": "name",
    "描述": "description",
    "角色": "agent_role",
    "agent角色": "agent_role",
    "Agent角色": "agent_role",
    "依赖": "depends_on",
    "节点类型": "node_type",
    "类型": "type",
    "多智能体模式": "multi_agent_mode",
    "需要知识": "needs_knowledge",
    "步骤": "steps",
}


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
- The "task_description" field MUST be a non-empty summary of the user's request
- All "label" fields MUST be non-empty and descriptive (never use "Untitled" or "Step" as labels)
- All "description" fields MUST be non-empty and explain what the step does
- Never return empty strings for any required field

You may use English field names (as shown in the example below) or Chinese
field names. Chinese field names are automatically mapped, so both forms
are valid:
  - 任务描述 -> task_description
  - 子任务 -> subtasks
  - 输出 / 预期输出 -> expected_output
  - 知识域 / 知识领域 -> knowledge_domains
  - 全局指令 -> global_instructions
  - 标签 -> label
  - 描述 -> description
  - agent角色 / 角色 -> agent_role
  - 依赖 -> depends_on
  - 步骤 -> steps

Respond ONLY with valid JSON. Do NOT include any text or markdown before or
after the JSON object -- no explanations, no commentary.

Example with Chinese input:
User request: 搜索并分析最新的AI论文，然后生成一份总结报告
Response:
{
  "task_description": "搜索并分析最新的AI论文并生成总结报告",
  "subtasks": [
    {
      "label": "SearchLatestPapers",
      "description": "Search for the most recent AI research papers from academic sources",
      "agent_role": "researcher",
      "depends_on": [],
      "node_type": "input",
      "multi_agent_mode": "single",
      "needs_knowledge": true
    },
    {
      "label": "AnalyzeFindings",
      "description": "Analyze the search results, extract key findings, and identify trends",
      "agent_role": "researcher",
      "depends_on": ["SearchLatestPapers"],
      "node_type": "task",
      "multi_agent_mode": "parallel",
      "needs_knowledge": true
    },
    {
      "label": "GenerateSummaryReport",
      "description": "Generate a comprehensive summary report based on the analysis",
      "agent_role": "summarizer",
      "depends_on": ["AnalyzeFindings"],
      "node_type": "output",
      "multi_agent_mode": "single",
      "needs_knowledge": true
    }
  ],
  "expected_output": "一份关于最新AI论文的总结报告",
  "knowledge_domains": ["人工智能", "machine learning", "NLP"],
  "global_instructions": ""
}

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
        intent = self._parse_response(response.content, user_request)

        # If JSON parsing failed or no subtasks extracted, try LLM re-parse
        if intent is None or not intent.subtasks:
            logger.warning(
                "Initial parse yielded %s, requesting LLM re-parse",
                "no intent" if intent is None
                else f"{len(intent.subtasks)} subtask(s)",
            )
            retry_prompt = (
                "Extract ONLY valid JSON from this response, "
                "return nothing else:\n\n"
                f"{response.content}"
            )
            retry_messages = [
                LLMMessage(role="user", content=retry_prompt),
            ]
            response = await self._llm.chat(retry_messages, temperature=0.1)
            logger.warning("LLM re-parse response: %.500s", response.content)
            intent = self._parse_response(response.content, user_request)

        # Final fallback if all parsing attempts fail
        if intent is None or not intent.subtasks:
            logger.warning(
                "All parsing attempts failed, creating fallback intent from request"
            )
            intent = self._create_fallback_intent(user_request)

        logger.info(
            "Parsed intent: %d sub-tasks, domains: %s",
            len(intent.subtasks),
            intent.knowledge_domains,
        )
        return intent

    def _parse_response(self, content: str, user_request: str = "") -> Intent | None:
        """Parse LLM response JSON into an Intent object.

        Handles:
        - ```json ... ``` and ``` ... ``` markdown code blocks anywhere in text
        - Chinese field names (e.g. "任务描述" -> "task_description")
        - Regex-based JSON extraction when direct parsing fails
        - Both dict ({"subtasks": [...]}) and list ([{...}, ...]) response formats
        - Single dict subtask (wraps it in a list)
        - Empty fields with fallback to user_request

        Returns None if all parsing methods fail (caller may retry with LLM).
        """
        text = content.strip()
        logger.info("Parsing LLM response of %d characters", len(text))
        logger.debug("Raw response starts: %.200s", text)

        # 1. Find and extract markdown code blocks (```json ... ``` or ``` ... ```)
        #    anywhere in the text, handling text before/after the fences
        code_block_match = re.search(
            r'```(?:json)?\s*\n(.+?)\n\s*```', text, re.DOTALL
        )
        if code_block_match:
            extracted = code_block_match.group(1).strip()
            logger.debug(
                "Extracted text from markdown code block "
                "(%d chars -> %d chars)",
                len(text), len(extracted),
            )
            text = extracted
        else:
            # Fallback: handle ``` at very start (no text before fence)
            if text.startswith("```"):
                first_newline = text.find("\n")
                if first_newline != -1:
                    text = text[first_newline + 1:]
                else:
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

        # 2. Try direct JSON parsing
        data = None
        try:
            data = json.loads(text)
            logger.debug("Direct JSON parse succeeded")
        except json.JSONDecodeError:
            logger.warning("Direct JSON parse failed on: %.120s", text)

        # 3. Try regex extraction if direct parsing failed
        if data is None:
            data = self._extract_json_with_regex(text)
            if data is not None:
                logger.debug("Regex JSON extraction succeeded")

        if data is None:
            logger.warning(
                "All JSON parsing methods failed, raw: %.200s", text
            )
            return None

        # 4. Map Chinese field names to English at the top level
        if isinstance(data, dict):
            data = self._map_chinese_fields(data)
            logger.debug("Mapped top-level fields: %s", list(data.keys()))

        # 5. Handle both dict ({"subtasks": [...]}) and list ([{...}, ...]) responses
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

        # 5b. Handle single-item subtask returned as dict instead of list
        if isinstance(raw_subtasks, dict):
            logger.debug("Wrapping single subtask dict in list")
            raw_subtasks = [raw_subtasks]

        # 6. Build subtasks (also mapping Chinese fields in each subtask item)
        subtasks = []
        for st in raw_subtasks if isinstance(raw_subtasks, list) else []:
            if isinstance(st, dict):
                st = self._map_chinese_fields(st)

            label = st.get("label", st.get("name", "Untitled Step"))
            if not label:
                label = "Untitled Step"

            description = st.get("description", "")
            if not description and label != "Untitled Step":
                description = label[:200]

            subtasks.append(
                SubTask(
                    label=label,
                    description=description,
                    agent_role=st.get(
                        "agent_role", st.get("role", "executor")
                    ),
                    depends_on=st.get(
                        "depends_on", st.get("depends", [])
                    ),
                    node_type=st.get(
                        "node_type", st.get("type", "task")
                    ),
                    multi_agent_mode=st.get("multi_agent_mode", "single"),
                    needs_knowledge=st.get("needs_knowledge", True),
                )
            )

        if not subtasks:
            logger.warning("No subtasks extracted from parsed JSON")
            return None

        # 7. Validate subtask quality -- ensure at least one has a meaningful label
        meaningful_labels = [
            st.label for st in subtasks
            if st.label and st.label != "Untitled Step"
        ]
        if not meaningful_labels:
            logger.warning(
                "All %d subtask(s) have empty/filler labels "
                "(e.g. 'Untitled Step'), treating as parse failure",
                len(subtasks),
            )
            return None

        # 8. Fill in empty task_description with user_request if available
        if not task_desc and user_request:
            task_desc = user_request[:500]
            logger.info(
                "Filled empty task_description from user request: %.80s",
                task_desc,
            )

        # 9. Fill in empty subtask descriptions from labels
        for st in subtasks:
            if not st.description and st.label and st.label != "Untitled Step":
                st.description = st.label[:200]

        logger.info(
            "Parsed response: task_desc=%.80s, %d subtask(s), %d domain(s)",
            task_desc,
            len(subtasks),
            len(domains) if isinstance(domains, list) else 0,
        )

        return Intent(
            task_description=task_desc or "User request",
            subtasks=subtasks,
            expected_output=expected_out or "Completed task output",
            knowledge_domains=domains if isinstance(domains, list) else [],
            global_instructions=instructions,
        )

    @staticmethod
    def _extract_json_with_regex(text: str) -> dict | list | None:
        """Extract JSON from text using regex and json.JSONDecoder.raw_decode.

        Iterates through the text looking for '{' or '[' characters and
        attempts to decode a JSON value starting at each position. This
        handles nested structures correctly and finds JSON even when
        surrounded by arbitrary text.
        """
        decoder = json.JSONDecoder()
        for i, ch in enumerate(text):
            if ch in ("{", "["):
                try:
                    data, _ = decoder.raw_decode(text, i)
                    return data
                except (json.JSONDecodeError, ValueError):
                    continue
        return None

    @staticmethod
    def _map_chinese_fields(data: dict) -> dict:
        """Recursively map Chinese field names to English equivalents."""
        if not isinstance(data, dict):
            return data
        mapped: dict[str, Any] = {}
        for key, value in data.items():
            new_key = CHINESE_FIELD_MAP.get(key, key)
            if isinstance(value, dict):
                mapped[new_key] = IntentParser._map_chinese_fields(value)
            elif isinstance(value, list):
                mapped[new_key] = [
                    IntentParser._map_chinese_fields(item)
                    if isinstance(item, dict)
                    else item
                    for item in value
                ]
            else:
                mapped[new_key] = value
        return mapped

    @staticmethod
    def _create_fallback_intent(content: str) -> Intent:
        """Create a reasonable fallback Intent when all parsing methods fail.

        Extracts meaningful step labels from the user's request text instead of
        using generic defaults. Falls back to a simple DAG when the request
        text cannot be parsed into segments.
        """
        # Split content by common punctuation to extract sub-requests
        segments = re.split(r'[，,。.；;、\n]+', content)
        segments = [s.strip() for s in segments if s.strip()]

        if not segments:
            segments = ["Process the request"]

        # Map common Chinese action verbs to English subtask names
        action_verbs = {
            "搜索": "Search", "检索": "Search", "查找": "Find",
            "分析": "Analyze", "解析": "Parse", "研究": "Research",
            "总结": "Summarize", "归纳": "Summarize", "汇总": "Collate",
            "生成": "Generate", "创建": "Create", "构建": "Build",
            "提取": "Extract", "采集": "Collect", "收集": "Collect",
            "验证": "Validate", "检查": "Check", "测试": "Test",
            "规划": "Plan", "设计": "Design", "组织": "Organize",
            "执行": "Execute", "运行": "Run", "处理": "Process",
            "报告": "Report", "输出": "Output", "展示": "Display",
            "比较": "Compare", "评估": "Evaluate", "审查": "Review",
            "优化": "Optimize", "转换": "Transform",
            "合并": "Merge", "分割": "Split", "过滤": "Filter",
            "分类": "Classify", "排序": "Sort",
        }

        def _make_label(text: str) -> str:
            """Convert a text segment into a concise English label."""
            for cn, en in action_verbs.items():
                if cn in text:
                    remainder = text.replace(cn, "", 1).strip()
                    remainder = re.sub(
                        r'^(并|和|与|及|以及|然后|接着|再|，|,)\s*',
                        '',
                        remainder,
                    )
                    if remainder:
                        return f"{en}{remainder[:30]}"
                    return en
            return text[:40]

        subtasks = []
        prev_label = None

        for i, segment in enumerate(segments):
            label = _make_label(segment)
            depends_on = [prev_label] if prev_label else []

            if i == 0:
                role = (
                    "researcher"
                    if any(
                        kw in segment
                        for kw in ["搜索", "检索", "查找", "分析", "研究"]
                    )
                    else "planner"
                )
                node_type = "input"
            elif i == len(segments) - 1:
                role = (
                    "summarizer"
                    if any(
                        kw in segment
                        for kw in ["总结", "生成", "报告", "输出"]
                    )
                    else "executor"
                )
                node_type = "output"
            else:
                role = "executor"
                node_type = "task"

            subtasks.append(
                SubTask(
                    label=label,
                    description=segment[:200],
                    agent_role=role,
                    node_type=node_type,
                    depends_on=depends_on,
                    needs_knowledge=True,
                )
            )
            prev_label = label

        return Intent(
            task_description=content[:500] if content else "User request",
            subtasks=subtasks,
            expected_output="Completed task output",
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

    # Chinese-to-English label mapping for subtitle display
    CHINESE_LABEL_MAP: dict[str, str] = {
        "搜索": "Search",
        "分析": "Analyze",
        "总结": "Summarize",
        "生成": "Generate",
        "提取": "Extract",
        "验证": "Validate",
        "规划": "Plan",
        "执行": "Execute",
        "报告": "Report",
        "收集": "Collect",
        "处理": "Process",
        "转换": "Transform",
        "合并": "Merge",
        "分割": "Split",
        "过滤": "Filter",
        "排序": "Sort",
        "比较": "Compare",
        "评估": "Evaluate",
        "优化": "Optimize",
        "测试": "Test",
        "部署": "Deploy",
        "监控": "Monitor",
        "通知": "Notify",
        "审查": "Review",
        "批准": "Approve",
        "拒绝": "Reject",
        "分配": "Assign",
        "输入": "Input",
        "输出": "Output",
        "任务": "Task",
        "步骤": "Step",
    }

    def __init__(self, llm_provider: LLMProvider | None = None):
        self._llm = llm_provider

    @staticmethod
    def _translate_label(label: str) -> str:
        """Translate a Chinese label to English if it contains Chinese characters.

        The LLM typically returns English labels, but this ensures Chinese
        labels are also handled gracefully.
        """
        for cn, en in WorkflowGenerator.CHINESE_LABEL_MAP.items():
            if cn in label:
                label = label.replace(cn, en)
        return label

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
                label=self._translate_label(st.label),
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
