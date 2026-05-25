# KNOT Workflow Execution Architecture Guide

> A comprehensive technical reference for KNOT's workflow execution pipeline, from natural language input to multi-agent collaboration and tool execution.

---

## 1. Introduction

### 1.1 What is KNOT?

KNOT (Knowledge-enhanced task Orchestration for LLM Tuning) is an intelligent workflow orchestration system that bridges the gap between natural language task descriptions and structured, executable workflows. The name "KNOT" (Chinese: "结" /jié/) symbolizes the weaving together of knowledge and task execution into an integrated fabric.

KNOT addresses three core challenges in deploying Large Language Models (LLMs) in production environments:

1. **Task orchestration complexity** -- Long-duration, multi-step tasks require autonomous planning and dynamic scheduling capabilities that traditional workflow engines lack.
2. **Knowledge hallucination** -- General-purpose LLMs lack domain-specific knowledge grounding, leading to factual errors in their outputs.
3. **Rigid automation workflows** -- Conventional workflow engines execute fixed sequences without intelligent adaptation to context or intermediate results.

### 1.2 High-Level Architecture

KNOT employs a four-layer decoupled architecture:

```
User Input (NL)          Presentation Layer
     |                        (CLI / API / GUI)
     v
Intent Parsing             Orchestration Layer
     |                        (Intent -> DAG -> Execution)
     v
Knowledge Injection        Knowledge Layer
     |                        (RAG / Vector Store)
     v
Tool Execution             Execution Layer
                              (Plugin-based tools)
```

Each layer is independently deployable and communicates through well-defined interfaces. The orchestration layer is the system's central nervous system, responsible for parsing user intent, generating workflow DAGs, scheduling agents, and managing execution state.

---

## 2. Core Architecture

### 2.1 Four-Layer Architecture

KNOT's architecture is designed around strict separation of concerns:

| Layer | Responsibility | Key Components |
|-------|---------------|----------------|
| **Presentation Layer** | User-facing interfaces | API Gateway, CLI, Workflow Editor |
| **Knowledge Layer** | Domain-specific context retrieval | Vector Store, Hybrid Retriever, Context Enhancer |
| **Orchestration Layer** | Task decomposition and scheduling | Intent Parser, Workflow Generator, LangGraph Engine, Agent Scheduler, State Manager |
| **Execution Layer** | Atomic operation execution | BaseTool, ToolRegistry, built-in tools |

### 2.2 Layer Interactions

Data flows through the layers in a controlled, unidirectional manner:

1. **Presentation -> Orchestration**: User submits a natural language request via API, CLI, or GUI.
2. **Orchestration -> LLM**: The Intent Parser uses an LLM to extract structured intent from the natural language request.
3. **Orchestration (internal)**: The Workflow Generator produces a DAG from the intent, the Agent Scheduler assigns agents to nodes, and the Workflow Engine orchestrates execution.
4. **Orchestration -> Knowledge**: During node execution, the engine may trigger knowledge retrieval for context enhancement.
5. **Orchestration -> Execution**: Atomic tasks are dispatched to the appropriate tools via the ToolRegistry.
6. **Execution -> State Manager**: Results flow back into the global state for subsequent node consumption.

### 2.3 Key Design Decisions

**DAG-based Workflows**: KNOT uses directed acyclic graphs (DAGs) rather than linear pipelines. This choice enables natural modeling of parallel execution, conditional branching, and complex dependency relationships between tasks.

**BSP Execution Model**: KNOT adopts the Bulk Synchronous Parallel (BSP) model from Pregel. Nodes at the same topological level execute independently and in parallel. A synchronization barrier occurs between levels, guaranteeing that all dependencies are satisfied before moving to the next level.

**Plugin-based Tools**: Tools are integrated through a unified `BaseTool` interface and registered in a central `ToolRegistry`. The workflow engine does not need to know the internal implementation of any tool -- it only interacts through the abstract interface.

**State Centralization**: Global execution state is managed centrally through the `WorkflowState` class. All agents read from and write to the same state object, avoiding distributed state consistency problems.

---

## 3. Natural Language to Workflow Pipeline

### 3.1 Pipeline Overview

The NL-to-Workflow pipeline is the primary entry point for task creation. It transforms unconstrained natural language into a structured, executable workflow DAG:

```
Natural Language Input
        |
        v
  IntentParser.parse()     <-- Stage 1: Intent Extraction
        |
        v
  Intent object            <-- Structured representation
        |
        v
  WorkflowGenerator.generate() <-- Stage 2: DAG Generation
        |
        v
  Workflow DAG             <-- Executable workflow (nodes + edges)
```

The pipeline is invoked through the convenience function `nl_to_workflow()` in `backend/src/knot/orchestration_layer/intent_understanding.py`.

### 3.2 Stage 1: Intent Parsing

The `IntentParser` class wraps an LLM provider to extract structured task plans.

**`IntentParser.parse(user_request: str) -> Intent`**:
1. Constructs a message containing the `INTENT_PARSE_PROMPT` template with the user request.
2. Sends the prompt to the LLM with `temperature=0.2` for deterministic output.
3. Calls `_parse_response()` to extract JSON from the LLM's response.
4. If parsing fails or yields no subtasks, it retries with a re-parse prompt.
5. If all parsing attempts fail, it falls back to `_create_fallback_intent()`.

**`IntentParser._parse_response()`** handles multiple response formats:

```python
# Handles markdown code blocks
"""json
{"task_description": "...", "subtasks": [...]}
"""

# Handles raw JSON
{"task_description": "...", "subtasks": [...]}

# Handles arrays as top-level
[{"label": "Step1", ...}, {"label": "Step2", ...}]

# Handles single subtask as dict
{"subtasks": {"label": "SingleStep", ...}}
```

**Chinese field name mapping**: The `CHINESE_FIELD_MAP` dictionary maps Chinese field names (e.g., "任务描述", "子任务", "知识域") to their English equivalents. The `_map_chinese_fields()` method recursively applies this mapping to all JSON keys.

**`IntentParser._create_fallback_intent(content: str) -> Intent`**: When LLM parsing fails completely, this method creates a reasonable fallback by:
1. Splitting the input text by punctuation to identify action segments.
2. Mapping Chinese action verbs to English task labels using a predefined dictionary of 50+ verbs.
3. Assigning roles based on keyword detection (e.g., "搜索" -> researcher).
4. Creating a sequential chain of subtasks as a simple DAG.

### 33 LLM Prompt Engineering

**`INTENT_PARSE_PROMPT`**: This system prompt instructs the LLM to:
- Analyze the overall goal, sub-steps, dependencies, required expertise, and expected output.
- Use specific agent roles (planner, researcher, coder, executor, validator, summarizer).
- Use specific node types (input, output, task, condition, loop).
- Break tasks into 2-6 sub-tasks with proper structure (first = input, last = output).
- Respond with valid JSON only (no markdown, no commentary).
- Support both English and Chinese field names.

**`WORKFLOW_GENERATE_PROMPT`**: An optional secondary prompt that enriches subtask configurations with:
- LLM model selection per subtask.
- Timeout settings and max iterations for loop nodes.
- System prompt hints for each subtask.

### 3.4 Stage 2: Workflow DAG Generation

The `WorkflowGenerator` class converts the structured `Intent` into a complete `Workflow` DAG.

**`WorkflowGenerator.generate(intent: Intent, user_request: str) -> Workflow`**:

1. **Node Creation**: For each `SubTask`, creates a `Node` with:
   - `type` mapped from `subtask.node_type` (input/task/output/condition/loop).
   - `agent_id` resolved from `ROLE_TO_AGENT_ID` mapping.
   - `config` populated with agent role, multi-agent mode, knowledge flags, and enriched LLM settings.
   - Chinese labels translated to English via `CHINESE_LABEL_MAP`.

2. **Edge Creation**: For each subtask's dependencies, creates `Edge` objects linking source to target nodes. If no edges are inferred, the generator chains nodes sequentially.

3. **Global Context**: Sets up initial context with `user_request`, `task_description`, `knowledge_domains`, and `global_instructions`.

---

## 4. Agent System and Collaboration

### 4.1 Default Agents

KNOT ships with six default agents, registered via `AgentScheduler.register_default_agents()`:

| Agent ID | Name | Role | Purpose |
|----------|------|------|---------|
| `agent_planner` | Planner | PLANNER | Break down complex tasks into actionable steps |
| `agent_researcher` | Researcher | RESEARCHER | Gather, analyze, and synthesize information |
| `agent_coder` | Coder | CODER | Write clean, efficient, well-documented code |
| `agent_executor` | Executor | EXECUTOR | General-purpose task execution |
| `agent_validator` | Validator | VALIDATOR | Quality checking, validation, and feedback |
| `agent_summarizer` | Summarizer | SUMMARIZER | Synthesize complex information into clear summaries |

### 4.2 Agent Registration and Assignment

The `AgentScheduler` class manages agent registration and task assignment:

- `register_agent(agent)` -- Register a single agent.
- `register_default_agents()` -- Register all six default agents.
- `get_agent(agent_id)` -- Lookup by ID.
- `get_agents_by_role(role)` -- Find all agents matching a role.

**`AgentScheduler.assign_node(node, context) -> Agent | None`**:
1. Checks for an exact `agent_id` match on the node.
2. Falls back to role-based matching using `node.config.get("agent_role", "executor")`.
3. Returns the first agent found for the preferred role.

**`AgentScheduler.assign_team(node, context) -> list[Agent]`**:
- For `SINGLE` mode: Returns a single agent (same as `assign_node`).
- For `PARALLEL` mode: Returns all agents matching the specified role.
- For `DEBATE` mode: Builds a diverse team from multiple roles (default: researcher + coder + validator).

### 4.3 Three Collaboration Modes

KNOT supports three modes of multi-agent collaboration:

**Single Mode**: A single agent executes the task directly. The engine constructs a system prompt (optionally enhanced with knowledge), sends the task, and returns the output.

**Parallel Mode** (`execute_parallel`):
- Phase 1: All assigned agents receive the same task simultaneously using `asyncio.gather()`.
- Phase 2: The `PARALLEL_MERGE_PROMPT` instructs a summarizer to consolidate all agent outputs into a single coherent result.
- Benefits: Multiple perspectives on complex problems, reduced bias.

**Debate Mode** (`execute_debate`):
- Each round, every agent presents their analysis from their role-specific perspective.
- A moderator agent assesses whether consensus has been reached after each round.
- If consensus is reached, the result is returned. Otherwise, the debate continues up to `max_rounds` (default: 3).
- After exhausting rounds without consensus, a summary is generated.
- Each agent uses `DEBATE_AGENT_PROMPT` with discussion history; the moderator uses `DEBATE_MODERATOR_PROMPT`.

### 4.4 Multi-Agent Dispatch

The `dispatch_multi_agent()` function is the central dispatcher:

```python
async def dispatch_multi_agent(
    mode: MultiAgentMode,
    task: str,
    agents: list[Agent],
    context: dict[str, Any],
    llm_provider: LLMProvider,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
```

It routes to the appropriate execution mode based on `MultiAgentMode`, falling back to single-agent execution if the mode is SINGLE.

---

## 5. Workflow Execution Engine

### 5.1 LangGraph StateGraph Integration

The `WorkflowEngine` class wraps LangGraph's `StateGraph` to execute workflow DAGs. LangGraph provides:

- A typed state schema (`LangGraphState`) that flows through all graph nodes.
- Built-in support for conditional edges and graph compilation.
- Async execution via `app.ainvoke()`.

The `LangGraphState` TypedDict defines the execution state:

```python
class LangGraphState(TypedDict):
    workflow_json: str              # Serialized workflow definition
    execution_id: str               # Unique execution ID
    current_node_id: str | None     # Currently executing node
    execution_order: list[str]      # Topological node order
    current_index: int              # Index in execution_order
    node_statuses: dict[str, str]   # Per-node status tracking
    node_results: dict[str, Any]    # Per-node result storage
    global_context: dict[str, Any]  # Shared execution context
    status: str                     # Overall execution status
    error: str | None               # Error info if failed
    trace: list[dict[str, Any]]     # Execution trace for observability
```

### 5.2 Graph Structure

The compiled LangGraph has three nodes and one conditional edge:

```
init --> execute --> execute (conditional loop)
  |                    |
  |                    +--> finalize --> END
  |                    +--> finalize --> END (on error)
```

- **init**: Initializes the state (`build_init_state`).
- **execute**: Executes the current node and advances (`build_execute_node`).
- **route_condition**: After each execute, determines whether to continue, end, or error.
- **finalize**: Sets final status and prepares the result.

### 5.3 BSP Execution Model

KNOT implements a modified Bulk Synchronous Parallel model:

1. A topological sort (`Workflow.topological_sort()`) determines the execution order using Kahn's algorithm.
2. The execution order is stored in `execution_order`.
3. The LangGraph iterate processes nodes sequentially through the order list.
4. Within a single "execute" invocation, the engine processes one node at a time.
5. Since the DAG encodes dependencies, parallel-capable nodes are those with no interdependencies at the same topological level.

### 5.4 Node Execution Logic

The `_execute_node_logic()` function handles five node types:

**INPUT node**: Returns `{"data": state.global_context.get("user_input", "")}`. This is the entry point for data into the workflow.

**OUTPUT node**: Returns `{"output": dict(context)}`. This captures the entire global context as the workflow's final output.

**CONDITION node**: Sends the node's condition expression and current context to the LLM with `temperature=0.1`. Returns `{"condition_met": True/False}` based on the LLM's evaluation.

**TASK node**: The most complex type. The execution flow is:
1. Check `multi_agent_mode` from node config. If parallel or debate, proceed to multi-agent dispatch.
2. Assemble input data by resolving field references from the global context.
3. **Knowledge Enhancement** (if enabled): Call `retriever.retrieve()` to fetch relevant chunks from the vector store, then `enhancer.enhance()` to inject knowledge into the system prompt.
4. For multi-agent modes: Call `scheduler.assign_team()` to build the agent team, then `dispatch_multi_agent()`.
5. For single-agent mode: Call `scheduler.assign_node()` to get the agent, construct messages with system prompt (and knowledge if available), and call `llm_provider.chat()`.
6. Return the result along with any resolved input data.

**LOOP node**: Executes up to `max_iterations` iterations. In each iteration, the LLM receives the accumulated results and current context. The loop breaks early if the LLM responds with "COMPLETE".

### 5.5 Error Handling and Retry

The `build_execute_node()` function wraps execution in a try-except block:

1. **On success**: Updates node status to SUCCESS, stores results, merges into global context, and advances the index.
2. **On failure**: Checks `max_retries` vs `retry_count`. If retries remain, it increments the counter and re-executes the same node (`current_index` stays the same).
3. **After exhausting retries**: Sets workflow status to FAILED, stores the error, and allows the LangGraph to route to the error handler.
4. If `max_retries` is 0, the workflow fails immediately on the first error.

### 5.6 Execution Result

The `execute()` method maps the LangGraph result state back to the `Execution` model:

```python
execution.status = WorkflowStatus(result_state.get("status", "failed"))
execution.node_states = {k: NodeStatus(v) for k, v in result_state["node_statuses"].items()}
execution.global_context = result_state.get("global_context", {})
execution.error = result_state.get("error")
execution.trace = result_state.get("trace", [])
```

The trace includes timestamps, node IDs, types, action types (start/complete/failed), and error messages -- forming a complete audit trail for observability.

---

## 6. Tool Execution System

### 6.1 BaseTool Interface

All executable tools in KNOT implement the `BaseTool` abstract class:

```python
class BaseTool(ABC):
    name: str                       # Tool identifier
    description: str                # Human-readable description
    async def execute(params) -> ToolResult   # Core execution method
    def input_schema() -> dict      # JSON Schema for parameters
    def to_openai_tool() -> dict    # OpenAI-compatible function definition
```

The `ToolResult` dataclass standardizes all tool outputs:

```python
@dataclass
class ToolResult:
    success: bool
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

### 6.2 Six Built-in Tools

| Tool | Name | Purpose |
|------|------|---------|
| `EchoTool` | `echo` | Simple echo for testing and debugging |
| `CalculatorTool` | `calculator` | Safe mathematical expression evaluation |
| `HTTPRequestTool` | `http_request` | Make HTTP GET and POST requests |
| `FileReadTool` | `file_read` | Read files from the filesystem (sandboxed) |
| `CurrentTimeTool` | `current_time` | Get current date/time with timezone |
| `WebSearchTool` | `web_search` | Search the web via configurable search endpoint |

### 6.3 Tool Registration and Invocation

Tools are registered in the global `ToolRegistry` singleton:

```python
from knot.execution_layer.registry import tool_registry

# Register
tool_registry.register(CalculatorTool())

# Execute
result = await tool_registry.execute("calculator", {"expression": "2 + 2 * 3"})
```

The registry supports:
- `register(tool)` -- Register a new tool.
- `get(name)` -- Retrieve a tool by name.
- `execute(name, params)` -- Execute a tool with parameter validation.
- `list_tools()` -- List all registered tools with their schemas.
- `to_openai_tools()` -- Convert all tools to OpenAI-compatible format.

### 6.4 Security Sandboxing

The `FileReadTool` implements path-based sandboxing:

- Only files within `/tmp` or directories specified in the `SAFE_FILE_DIRS` environment variable can be read.
- Paths are resolved to their canonical form (using `Path.resolve()`) before comparison.
- Allowed paths must either match a safe directory exactly or be within it.

The `CalculatorTool` uses restricted `eval()` with only safe builtins:

```python
allowed_names = {
    "abs": abs, "min": min, "max": max,
    "sum": sum, "round": round,
    "float": float, "int": int,
}
result = eval(expression, {"__builtins__": {}}, allowed_names)
```

---

## 7. Data Flow Example: Complete Task Execution

This section walks through a complete execution of the Chinese request: "搜索并分析最新的AI论文，然后生成一份总结报告" (Search and analyze the latest AI papers, then generate a summary report).

### Stage 1: Intent Parsing

**Input**: `"搜索并分析最新的AI论文，然后生成一份总结报告"`

The `IntentParser` sends the `INTENT_PARSE_PROMPT` with this request to the LLM. The expected response:

```json
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
```

### Stage 2: Workflow DAG Generation

The `WorkflowGenerator` converts the intent into a `Workflow` with:

```
Nodes:
  node_xxxx1: INPUT  "SearchLatestPapers"    -> agent_researcher
  node_xxxx2: TASK   "AnalyzeFindings"       -> agent_researcher (parallel mode)
  node_xxxx3: OUTPUT "GenerateSummaryReport" -> agent_summarizer

Edges:
  node_xxxx1 -> node_xxxx2
  node_xxxx2 -> node_xxxx3

Global Context:
  user_request: "搜索并分析最新的AI论文，然后生成一份总结报告"
  task_description: "搜索并分析最新的AI论文并生成总结报告"
  knowledge_domains: ["人工智能", "machine learning", "NLP"]
```

### Stage 3: Workflow Execution

The `WorkflowEngine.execute()`:

1. **Topological sort**: SearchLatestPapers -> AnalyzeFindings -> GenerateSummaryReport.
2. **Initialize LangGraph state**: Sets `execution_order` and initializes `global_context`.
3. **Execute node_xxxx1 (INPUT)**: Returns user input as data. No agent needed.
4. **Execute node_xxxx2 (TASK)**: 
   - Mode: PARALLEL -> `assign_team()` returns all researcher agents.
   - Knowledge enabled: `retriever.retrieve()` searches the "default" collection for AI paper knowledge.
   - `dispatch_multi_agent()` with PARALLEL mode:
     - Phase 1: All researcher agents analyze the papers in parallel via `asyncio.gather()`.
     - Phase 2: Merges results using `PARALLEL_MERGE_PROMPT`.
   - Result stored in global context.
5. **Execute node_xxxx3 (OUTPUT)**: Captures full context as final output.
6. **Finalize**: Sets status to SUCCESS.

### Stage 4: Result

```python
Execution(
    status=WorkflowStatus.SUCCESS,
    node_states={
        "node_xxxx1": NodeStatus.SUCCESS,
        "node_xxxx2": NodeStatus.SUCCESS,
        "node_xxxx3": NodeStatus.SUCCESS,
    },
    global_context={
        "user_request": "...",
        "task_description": "...",
        "output": {
            "consolidated_report": "...merged analysis from parallel agents..."
        }
    },
    trace=[
        {"node_id": "node_xxxx1", "action": "start", ...},
        {"node_id": "node_xxxx1", "action": "complete", ...},
        ...
    ]
)
```

---

## 8. API Reference

### 8.1 Endpoints

KNOT exposes the following REST API endpoints through FastAPI:

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|--------------|----------|
| `POST` | `/api/v1/workflows/from-nl` | Create workflow from NL | `{"description": "..."}` | `Workflow` |
| `POST` | `/api/v1/workflows` | Create workflow directly | `Workflow` | `Workflow` |
| `GET` | `/api/v1/workflows` | List all workflows | -- | `list[Workflow]` |
| `GET` | `/api/v1/workflows/{workflow_id}` | Get workflow by ID | -- | `Workflow` |
| `POST` | `/api/v1/workflows/{workflow_id}/execute` | Execute workflow | `{"context": {...}}` | `Execution` |
| `GET` | `/api/v1/workflows/executions/{execution_id}` | Get execution result | -- | `Execution` |
| `POST` | `/api/v1/knowledge/search` | Search knowledge base | `{"collection": "..", "query": ".."}` | `list[KnowledgeChunk]` |
| `POST` | `/api/v1/knowledge/documents` | Upload document | Multipart form | `{"id": "...", "status": "indexed"}` |
| `GET` | `/api/v1/agents` | List registered agents | -- | `list[Agent]` |

### 8.2 Creating a Workflow from Natural Language

```bash
curl -X POST http://localhost:8000/api/v1/workflows/from-nl \
  -H "Content-Type: application/json" \
  -d '{"description": "搜索并分析最新的AI论文，然后生成一份总结报告"}'
```

Response:
```json
{
  "id": "wf_abc12345",
  "name": "搜索并分析最新的AI论文并生成总结报告",
  "nodes": [...],
  "edges": [...],
  "global_context": {...}
}
```

### 8.3 Executing a Workflow

```bash
curl -X POST http://localhost:8000/api/v1/workflows/wf_abc12345/execute \
  -H "Content-Type: application/json" \
  -d '{"context": {"user_preference": "focus on LLM papers"}}'
```

Response:
```json
{
  "id": "exec_def67890",
  "workflow_id": "wf_abc12345",
  "status": "running",
  "started_at": "2025-06-15T10:30:00Z",
  "node_states": {},
  "trace": []
}
```

### 8.4 Checking Execution Status

```bash
curl http://localhost:8000/api/v1/workflows/executions/exec_def67890
```

Response:
```json
{
  "id": "exec_def67890",
  "status": "success",
  "node_states": {
    "node_xxxx1": "success",
    "node_xxxx2": "success",
    "node_xxxx3": "success"
  },
  "global_context": {"output": "...", "search_results": [...]},
  "trace": [...],
  "completed_at": "2025-06-15T10:31:15Z"
}
```

### 8.5 Authentication

Authentication in KNOT is handled via API key headers. The system validates tokens against configured keys at the API gateway level. The current implementation does not enforce authentication by default but is designed to integrate with standard auth middleware (OAuth2, JWT, etc.).

---

## Appendix: Key Source File Locations

| Component | File Path |
|-----------|-----------|
| Intent Parsing | `backend/src/knot/orchestration_layer/intent_understanding.py` |
| Workflow Engine | `backend/src/knot/orchestration_layer/workflow.py` |
| Agent Scheduler | `backend/src/knot/orchestration_layer/scheduler.py` |
| Multi-Agent Dispatch | `backend/src/knot/orchestration_layer/multi_agent.py` |
| State Management | `backend/src/knot/orchestration_layer/state.py` |
| Core Models | `backend/src/knot/core/models.py` |
| Custom Exceptions | `backend/src/knot/core/exceptions.py` |
| LLM Provider Interface | `backend/src/knot/llm/base.py` |
| Tool Base Interface | `backend/src/knot/execution_layer/base.py` |
| Tool Registry | `backend/src/knot/execution_layer/registry.py` |
| Built-in Tools | `backend/src/knot/execution_layer/tool_executor.py` |
| Vector Store | `backend/src/knot/knowledge_layer/vector_store.py` |
| Hybrid Retriever | `backend/src/knot/knowledge_layer/retriever.py` |
| Context Enhancer | `backend/src/knot/knowledge_layer/enhancer.py` |
| API Workflow Routes | `backend/src/knot/api/routes/workflows.py` |
| Backend Framework | `docs/BACKEND_FRAMEWORK.md` |
| Architecture | `docs/ARCHITECTURE.md` |
