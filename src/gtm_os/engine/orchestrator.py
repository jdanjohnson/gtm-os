"""Multi-agent orchestrator — routes work to specialist agents, manages handoffs.

Implements WS3A:
- Real delegation: orchestrator decides which agent(s) handle each phase
- Sequential agent chaining: pass output from one agent as context to the next
- Handoff state tracking: which agent ran, what they produced, what's next
- Failure escalation: retry same agent or escalate to orchestrator
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ..config import Config
from ..types import AgentMessage, AgentResult, Primitives
from .context import assemble_context
from .harness import HarnessOptions, run_agent
from .memory import VectorMemory
from .store import Store

logger = logging.getLogger(__name__)


# Phase → ordered list of specialist agents to run.
# Multiple agents in a phase run sequentially; each receives prior agent's output.
PHASE_AGENTS: dict[str, list[str]] = {
    "design": ["researcher"],
    "build": ["researcher", "copywriter"],
    "execute": ["operator"],
    "measure": ["analyst"],
    "learn": ["analyst"],
    "complete": ["orchestrator"],
    "paused": ["orchestrator"],
}


@dataclass
class HandoffState:
    """Tracks what happened during a multi-agent phase tick."""

    phase: str
    agents_run: list[str] = field(default_factory=list)
    agent_outputs: dict[str, str] = field(default_factory=dict)
    total_tokens: int = 0
    last_error: str | None = None
    all_tool_calls: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class OrchestrationResult:
    """Outcome of a full orchestrated tick."""

    handoff: HandoffState
    final_result: AgentResult
    ok: bool = True


class Orchestrator:
    """Routes work to specialist agents and manages handoffs."""

    def __init__(
        self,
        *,
        config: Config,
        store: Store,
        memory: VectorMemory,
    ) -> None:
        self.config = config
        self.store = store
        self.memory = memory

    async def run_phase_tick(
        self,
        *,
        experiment_id: str,
        phase: str,
        primitives: Primitives,
        tools: list,
        base_messages: list[dict[str, Any]],
        directive: str,
    ) -> OrchestrationResult:
        """Orchestrate a full tick: decide which agent(s) to run, chain them."""
        agents = PHASE_AGENTS.get(phase, ["orchestrator"])
        handoff = HandoffState(phase=phase)

        final_result: AgentResult | None = None
        accumulated_context = directive

        for i, agent_name in enumerate(agents):
            handoff.agents_run.append(agent_name)

            # Build agent-specific context with handoff info from prior agents.
            if i > 0 and handoff.agent_outputs:
                prior_summary = "\n".join(
                    f"[{name} output]: {output[:1500]}"
                    for name, output in handoff.agent_outputs.items()
                )
                accumulated_context = (
                    f"{prior_summary}\n\n---\n\n"
                    f"You are the {agent_name}. Build on the above work.\n\n"
                    f"{directive}"
                )

            system_prompt = assemble_context(
                primitives,
                agent_name=agent_name,
                experiment=self.store.get_experiment(experiment_id),
                phase=phase,
                relevant_memories=await self.memory.search(
                    query=accumulated_context[:200], limit=5
                ),
            )

            messages = [*base_messages, {"role": "user", "content": accumulated_context}]

            try:
                result = await run_agent(
                    system_prompt=system_prompt,
                    messages=messages,
                    tools=tools,
                    config=self.config.llm,
                    options=HarnessOptions(max_iterations=50),
                )
            except Exception as exc:
                logger.exception("agent %s failed in phase %s", agent_name, phase)
                handoff.last_error = str(exc)

                # If not the last agent, try to continue with remaining agents.
                if i < len(agents) - 1:
                    logger.info("continuing to next agent despite %s failure", agent_name)
                    continue

                # Last agent failed — return error result.
                return OrchestrationResult(
                    handoff=handoff,
                    final_result=AgentResult(
                        message=AgentMessage(role="assistant", content=""),
                        error=str(exc),
                        finished=False,
                    ),
                    ok=False,
                )

            handoff.agent_outputs[agent_name] = result.message.content
            handoff.total_tokens += result.tokens_used
            handoff.all_tool_calls.extend(
                {"name": tc.name, "arguments": tc.arguments} for tc in result.tool_calls
            )

            final_result = result

            # If agent hit doom loop, stop chaining.
            if result.error == "doom_loop":
                handoff.last_error = "doom_loop"
                return OrchestrationResult(
                    handoff=handoff, final_result=result, ok=False
                )

        # Record handoff state in experiment config.
        exp = self.store.get_experiment(experiment_id)
        if exp:
            cfg = dict(exp.config)
            cfg["last_handoff"] = {
                "phase": phase,
                "agents_run": handoff.agents_run,
                "tokens": handoff.total_tokens,
            }
            self.store.update_experiment(experiment_id, config=cfg)

        return OrchestrationResult(
            handoff=handoff,
            final_result=final_result or AgentResult(
                message=AgentMessage(role="assistant", content=""),
                finished=True,
            ),
            ok=final_result is not None and final_result.error is None,
        )
