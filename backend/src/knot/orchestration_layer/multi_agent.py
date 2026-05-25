"""Multi-agent collaboration patterns: parallel execution & debate."""

from __future__ import annotations

import json
import logging
from typing import Any

from knot.core.models import Agent, MultiAgentMode
from knot.llm import LLMProvider
from knot.llm.base import LLMMessage
from knot.orchestration_layer.scheduler import AgentScheduler

logger = logging.getLogger(__name__)

# ─── Prompts for each collaboration mode ──────────────────────────────────

PARALLEL_MERGE_PROMPT = """\
You are a result merger. Multiple AI agents have independently analyzed the same task.
Your job is to review all their outputs and produce a single consolidated result.

Focus on:
1. Identifying the strongest arguments and insights from each agent
2. Resolving any contradictions between agents
3. Producing a coherent, complete final answer

Agent outputs:
{agent_outputs}

Provide a consolidated result that captures the best of all agents' work.
"""

DEBATE_MODERATOR_PROMPT = """\
You are a debate moderator. Multiple AI agents are discussing a question.
Your job is to facilitate the discussion and determine when consensus is reached.

Rules:
- Each round, each agent presents their analysis
- After each round, you assess whether consensus has been reached
- If agents disagree, they should address specific points of disagreement
- Maximum {max_rounds} rounds of discussion

Question: {task}

Begin the discussion. After each round, state whether consensus is reached.
"""

DEBATE_AGENT_PROMPT = """\
You are {agent_name}, a {agent_role} agent participating in a multi-agent discussion.

Your task: {task}

Discussion so far:
{discussion_history}

Provide your analysis and perspective for this round. Be specific, reference prior points,
and either build consensus or identify remaining disagreements.
"""


# ─── Parallel Execution ──────────────────────────────────────────────────


async def execute_parallel(
    task: str,
    agents: list[Agent],
    context: dict[str, Any],
    llm_provider: LLMProvider,
) -> dict[str, Any]:
    """Execute a task across multiple agents in parallel, then merge results.

    Each agent independently processes the same task. All results are then
    merged by a summarizer agent into a single coherent output.
    """
    logger.info("Parallel execution: %d agents on task: %.50s", len(agents), task)

    # Phase 1: All agents execute independently
    async def run_agent(agent: Agent) -> dict[str, Any]:
        messages = [
            LLMMessage(role="system", content=agent.system_prompt or "You are a helpful AI assistant."),
            LLMMessage(
                role="user",
                content=f"Task: {task}\nContext: {json.dumps(context, ensure_ascii=False)}",
            ),
        ]
        response = await llm_provider.chat(messages, model=agent.model)
        return {"agent_id": agent.id, "agent_name": agent.name, "output": response.content}

    import asyncio

    results = await asyncio.gather(*[run_agent(a) for a in agents], return_exceptions=True)

    # Separate successful results from errors
    agent_outputs = []
    for r in results:
        if isinstance(r, dict):
            agent_outputs.append(r)
        else:
            logger.warning("Parallel agent failed: %s", r)

    if not agent_outputs:
        return {"output": "All agents failed", "parallel_results": []}

    # Phase 2: Merge results
    outputs_text = "\n\n---\n\n".join(
        f"[Agent: {a['agent_name']}]\n{a['output']}" for a in agent_outputs
    )

    merge_messages = [
        LLMMessage(role="system", content=PARALLEL_MERGE_PROMPT.format(agent_outputs=outputs_text)),
    ]
    merge_response = await llm_provider.chat(merge_messages, temperature=0.3)

    return {
        "output": merge_response.content,
        "parallel_results": agent_outputs,
        "merged": True,
    }


# ─── Debate Execution ────────────────────────────────────────────────────


async def execute_debate(
    task: str,
    agents: list[Agent],
    context: dict[str, Any],
    llm_provider: LLMProvider,
    max_rounds: int = 3,
) -> dict[str, Any]:
    """Multiple agents debate a topic iteratively until consensus.

    Each round, every agent contributes their perspective. The moderator
    assesses consensus after each round.
    """
    logger.info("Debate execution: %d agents, %d max rounds, task: %.50s",
                len(agents), max_rounds, task)

    discussion_history: list[str] = []
    consensus_reached = False

    for round_num in range(1, max_rounds + 1):
        logger.info("Debate round %d/%d", round_num, max_rounds)
        round_contributions: list[str] = []

        for agent in agents:
            history_text = "\n".join(discussion_history[-6:]) if discussion_history else "No prior discussion."

            messages = [
                LLMMessage(
                    role="system",
                    content=DEBATE_AGENT_PROMPT.format(
                        agent_name=agent.name,
                        agent_role=agent.role.value,
                        task=task,
                        discussion_history=history_text,
                    ),
                ),
                LLMMessage(
                    role="user",
                    content=f"Round {round_num}/{max_rounds}. "
                    f"Context: {json.dumps(context, ensure_ascii=False)}",
                ),
            ]
            response = await llm_provider.chat(messages, model=agent.model, temperature=0.7)
            contribution = f"[Round {round_num}] {agent.name} ({agent.role.value}):\n{response.content}"
            round_contributions.append(contribution)
            discussion_history.append(contribution)

        # Moderator assesses consensus
        mod_messages = [
            LLMMessage(role="system", content=DEBATE_MODERATOR_PROMPT.format(
                max_rounds=max_rounds, task=task,
            )),
            LLMMessage(
                role="user",
                content=f"Round {round_num} discussion:\n" + "\n".join(round_contributions)
                + "\n\nHas consensus been reached? Answer YES or NO and provide the final consensus if YES.",
            ),
        ]
        mod_response = await llm_provider.chat(mod_messages, temperature=0.2)
        mod_text = mod_response.content.strip()

        if mod_text.startswith("YES") or "CONSENSUS REACHED" in mod_text.upper():
            consensus_reached = True
            # Extract consensus (content after YES/NO line)
            consensus = mod_text
            logger.info("Debate consensus reached at round %d", round_num)
            return {
                "output": consensus,
                "debate_rounds": round_num,
                "consensus_reached": True,
                "discussion_history": discussion_history,
            }

    # No consensus after max rounds — summarize debate
    summary_messages = [
        LLMMessage(role="system", content="Summarize the key points from this multi-agent discussion."),
        LLMMessage(role="user", content="Discussion:\n" + "\n".join(discussion_history)),
    ]
    summary = await llm_provider.chat(summary_messages, temperature=0.3)

    logger.info("Debate ended after %d rounds without full consensus", max_rounds)
    return {
        "output": summary.content,
        "debate_rounds": max_rounds,
        "consensus_reached": False,
        "discussion_history": discussion_history,
    }


# ─── Multi-Agent Dispatcher ──────────────────────────────────────────────


async def dispatch_multi_agent(
    mode: MultiAgentMode,
    task: str,
    agents: list[Agent],
    context: dict[str, Any],
    llm_provider: LLMProvider,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Dispatch a task to multiple agents using the specified collaboration mode."""
    cfg = config or {}

    if mode == MultiAgentMode.PARALLEL:
        return await execute_parallel(task, agents, context, llm_provider)

    if mode == MultiAgentMode.DEBATE:
        max_rounds = cfg.get("max_debate_rounds", 3)
        return await execute_debate(task, agents, context, llm_provider, max_rounds)

    # Single agent mode — use the first agent
    logger.info("Single agent mode: %s on task: %.50s", agents[0].name if agents else "none", task)
    agent = agents[0] if agents else None
    messages = [
        LLMMessage(role="system", content=agent.system_prompt if agent else "You are a helpful AI assistant."),
        LLMMessage(role="user", content=f"Task: {task}\nContext: {json.dumps(context, ensure_ascii=False)}"),
    ]
    response = await llm_provider.chat(messages, model=agent.model if agent else None)
    return {"output": response.content}
