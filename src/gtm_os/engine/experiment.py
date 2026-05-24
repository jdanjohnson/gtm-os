"""Experiment lifecycle — create, run_tick, transition_phase, pause, resume."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ..config import Config
from ..types import Experiment, Primitives
from .composio_tools import ComposioIntegration, build_composio_tools
from .context import assemble_context
from .context_manager import ContextManager
from .custom_tools import build_custom_tools
from .harness import HarnessOptions, run_agent
from .loader import load_primitives
from .memory import VectorMemory
from .store import Store

logger = logging.getLogger(__name__)


PHASE_ORDER = ["design", "build", "execute", "measure", "learn", "complete"]
PHASE_AGENT = {
    "design": "researcher",
    "build": "copywriter",
    "execute": "operator",
    "measure": "analyst",
    "learn": "analyst",
    "complete": "orchestrator",
    "paused": "orchestrator",
}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class RunOutcome:
    run_id: str
    experiment_id: str
    phase: str
    ok: bool
    tokens_used: int = 0
    error: str | None = None
    message: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class ExperimentRunner:
    """Drives experiment ticks, owns context assembly, and coordinates tools."""

    def __init__(
        self,
        *,
        config: Config,
        store: Store,
        memory: VectorMemory,
        composio: ComposioIntegration,
        context_manager: ContextManager | None = None,
    ) -> None:
        self.config = config
        self.store = store
        self.memory = memory
        self.composio = composio
        self.context_manager = context_manager or ContextManager(config.llm)
        self._primitives_cache: tuple[float, Primitives] | None = None

    # ---------- primitives ----------

    def load_primitives_cached(self) -> Primitives:
        """Reload primitives if any file on disk has changed since last load."""
        latest = 0.0
        try:
            for p in self.config.primitives_dir.rglob("*"):
                if p.is_file():
                    latest = max(latest, p.stat().st_mtime)
        except FileNotFoundError:
            latest = 0.0
        if self._primitives_cache and self._primitives_cache[0] >= latest:
            return self._primitives_cache[1]
        prim = load_primitives(self.config.primitives_dir)
        self._primitives_cache = (latest, prim)
        return prim

    # ---------- tools ----------

    def build_tools(self, primitives: Primitives) -> list:
        play_ids = sorted(primitives.plays.keys())
        custom = build_custom_tools(
            store=self.store,
            memory=self.memory,
            runner=self,
            play_ids=play_ids,
        )
        composio = build_composio_tools(self.composio)
        return custom + composio

    # ---------- create / mutate ----------

    def create(
        self,
        *,
        name: str,
        description: str | None = None,
        hypothesis: str | None = None,
        play_ids: list[str] | None = None,
        config: dict[str, Any] | None = None,
        token_budget: int | None = None,
    ) -> Experiment:
        return self.store.create_experiment(
            name=name,
            description=description,
            hypothesis=hypothesis,
            play_ids=play_ids or [],
            config=config or {},
            token_budget=token_budget or self.config.budgets.default_experiment_token_budget,
        )

    def transition_phase(
        self, experiment_id: str, new_phase: str, reason: str | None = None
    ) -> Experiment | None:
        if new_phase not in [*PHASE_ORDER, "paused"]:
            raise ValueError(f"unknown phase: {new_phase}")
        return self.store.update_experiment(experiment_id, phase=new_phase)

    def pause(self, experiment_id: str, reason: str | None = None) -> Experiment | None:
        if reason:
            self.store.add_message(
                role="system", content=f"[PAUSED] {reason}", experiment_id=experiment_id
            )
        return self.store.update_experiment(experiment_id, phase="paused")

    def resume(self, experiment_id: str, *, target_phase: str = "design") -> Experiment | None:
        return self.store.update_experiment(experiment_id, phase=target_phase)

    # ---------- run ----------

    async def run_tick(self, experiment_id: str) -> RunOutcome:
        """One tick of the experiment loop."""
        exp = self.store.get_experiment(experiment_id)
        if not exp:
            return RunOutcome(
                run_id="", experiment_id=experiment_id, phase="", ok=False, error="not_found"
            )

        if exp.phase in {"complete", "paused"}:
            return RunOutcome(
                run_id="",
                experiment_id=experiment_id,
                phase=exp.phase,
                ok=False,
                error=f"experiment is {exp.phase}",
            )

        if exp.tokens_used >= exp.token_budget:
            self.store.update_experiment(experiment_id, phase="paused")
            return RunOutcome(
                run_id="",
                experiment_id=experiment_id,
                phase="paused",
                ok=False,
                error="token_budget_exceeded",
            )

        primitives = self.load_primitives_cached()
        run = self.store.start_run(
            experiment_id=experiment_id,
            phase=exp.phase,
            input_context={"agent": PHASE_AGENT.get(exp.phase, "orchestrator")},
        )

        # Build context.
        agent_name = PHASE_AGENT.get(exp.phase, "orchestrator")
        memories = await self.memory.search(
            query=f"{exp.name} {exp.hypothesis or ''} {exp.config.get('channel', '')}",
            limit=8,
        )
        system_prompt = assemble_context(
            primitives,
            agent_name=agent_name,
            experiment=exp,
            phase=exp.phase,
            relevant_memories=memories,
        )

        # Build tools.
        tools = self.build_tools(primitives)

        # Construct first user message for this tick.
        next_step = _phase_directive(exp.phase, exp)
        messages = [{"role": "user", "content": next_step}]

        try:
            result = await run_agent(
                system_prompt=system_prompt,
                messages=messages,
                tools=tools,
                config=self.config.llm,
                options=HarnessOptions(max_iterations=15),
            )
        except Exception as exc:
            logger.exception("agent run failed")
            self.store.finish_run(run.id, status="failed", error=str(exc))
            return RunOutcome(
                run_id=run.id,
                experiment_id=experiment_id,
                phase=exp.phase,
                ok=False,
                error=str(exc),
            )

        tools_used = [
            {"name": tc.name, "arguments": tc.arguments}
            for tc in result.tool_calls
        ]
        self.store.finish_run(
            run.id,
            status="completed" if result.finished else "failed",
            output={"message": result.message.content},
            tools_used=tools_used,
            tokens_used=result.tokens_used,
            error=result.error,
        )
        self.store.add_experiment_tokens(experiment_id, result.tokens_used)

        # If the agent didn't transition the phase itself, advance automatically when finished.
        if result.finished and result.error is None:
            current = self.store.get_experiment(experiment_id)
            if current and current.phase == exp.phase and exp.phase != "complete":
                next_phase = _next_phase(exp.phase)
                if exp.phase == "build":
                    # Build → execute requires approval; pause instead.
                    self.store.update_experiment(experiment_id, phase="paused")
                    self.store.add_message(
                        role="system",
                        content="[APPROVAL REQUESTED] Build phase complete. Approve to start execute.",
                        experiment_id=experiment_id,
                    )
                elif next_phase:
                    self.store.update_experiment(experiment_id, phase=next_phase)

        return RunOutcome(
            run_id=run.id,
            experiment_id=experiment_id,
            phase=exp.phase,
            ok=result.error is None,
            tokens_used=result.tokens_used,
            error=result.error,
            message=result.message.content,
            tool_calls=tools_used,
        )


def _next_phase(phase: str) -> str | None:
    if phase not in PHASE_ORDER:
        return None
    idx = PHASE_ORDER.index(phase)
    return PHASE_ORDER[idx + 1] if idx + 1 < len(PHASE_ORDER) else None


def _phase_directive(phase: str, exp: Experiment) -> str:
    """Per-tick instructions for the agent. Borrowed pattern from PraisonAI workflow steps."""
    base = f"Continue experiment '{exp.name}'. Phase: {phase}."
    if phase == "design":
        return (
            f"{base} Define ICP, frame the hypothesis, and pick the right plays. "
            "Search memory for relevant past learnings before deciding. When the design is solid, "
            "use transition_phase to move to 'build'."
        )
    if phase == "build":
        return (
            f"{base} Build the assets: prospect list, copy, scripts, or content. "
            "Use composio_discover_tools / composio_execute_action for real integrations. "
            "When complete, use request_approval(experiment_id, message) and wait — DO NOT transition to 'execute' yourself."
        )
    if phase == "execute":
        return (
            f"{base} Execute the play. Respect channel rules and rate limits. "
            "Save outcomes to memory as you go. When all sends are complete (or the time window is done), transition to 'measure'."
        )
    if phase == "measure":
        return (
            f"{base} Pull metrics, compare to the hypothesis. Save concrete learnings to memory. "
            "Then transition to 'learn'."
        )
    if phase == "learn":
        return (
            f"{base} Codify the learnings (use memory_save with type='learning'). Propose follow-up "
            "experiments. Then transition to 'complete'."
        )
    return f"{base} Continue the work."
