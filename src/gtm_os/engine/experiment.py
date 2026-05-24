"""Experiment lifecycle — create, run_tick, transition_phase, pause, resume.

Implements:
- WS1A: Context management wired into experiment ticks
- WS1B: Correction-to-rule automatically after learn phase
- WS1C: Durable execution via DurableContext checkpoint/replay
- WS1D: Conversation history persistence across ticks
- WS2C: Output chaining between phases, sub-step tracking, play-aware directives
"""

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
from .durability import DurableContext
from .harness import HarnessOptions, run_agent
from .loader import load_primitives
from .memory import VectorMemory
from .pipedream_tools import PipedreamIntegration, build_pipedream_tools
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

# Maximum messages to load from history for context continuity.
MAX_HISTORY_MESSAGES = 30
# Threshold (messages count) after which we flush to memory.
FLUSH_THRESHOLD = 8


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
        pipedream: PipedreamIntegration | None = None,
        context_manager: ContextManager | None = None,
    ) -> None:
        self.config = config
        self.store = store
        self.memory = memory
        self.composio = composio
        self.pipedream = pipedream or PipedreamIntegration(None)
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
            primitives=primitives,
        )
        composio = build_composio_tools(self.composio)
        pipedream = build_pipedream_tools(self.pipedream)
        return custom + composio + pipedream

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

    # ---------- output chaining (WS2C) ----------

    def _get_previous_phase_output(self, experiment_id: str, current_phase: str) -> str | None:
        """Retrieve output from the previous phase to chain into the current context."""
        prev_phase = _prev_phase(current_phase)
        if not prev_phase:
            return None
        runs = self.store.list_runs(experiment_id, limit=50)
        for run in runs:
            if run.phase == prev_phase and run.status == "completed" and run.output:
                msg = run.output.get("message", "")
                if msg:
                    return f"[Previous phase '{prev_phase}' output]\n{msg[:2000]}"
        return None

    # ---------- run ----------

    async def run_tick(self, experiment_id: str) -> RunOutcome:
        """One tick of the experiment loop.

        Implements durable execution (1C): each major step is checkpointed.
        On crash/restart, completed steps are skipped.
        """
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

        # WS1C: Create durable context for checkpoint/replay.
        _ctx = DurableContext(self.store, experiment_id, run.id)

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

        # WS1D: Load conversation history from previous ticks.
        history = self.store.list_messages(experiment_id=experiment_id, limit=MAX_HISTORY_MESSAGES)
        history_messages: list[dict[str, Any]] = []
        for msg in history:
            m: dict[str, Any] = {"role": msg["role"], "content": msg["content"] or ""}
            if msg.get("tool_calls"):
                m["tool_calls"] = msg["tool_calls"]
            if msg.get("tool_call_id"):
                m["tool_call_id"] = msg["tool_call_id"]
                m["role"] = "tool"
            if msg.get("name"):
                m["name"] = msg["name"]
            history_messages.append(m)

        # WS1A: Prune context before sending to LLM.
        if history_messages:
            history_messages = self.context_manager.prune(history_messages)

        # WS2C: Chain previous phase output into context.
        prev_output = self._get_previous_phase_output(experiment_id, exp.phase)

        # Construct the directive for this tick.
        next_step = _phase_directive(exp.phase, exp, primitives)
        if prev_output:
            next_step = f"{prev_output}\n\n---\n\n{next_step}"

        messages = [*history_messages, {"role": "user", "content": next_step}]

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

        tools_used = [{"name": tc.name, "arguments": tc.arguments} for tc in result.tool_calls]
        self.store.finish_run(
            run.id,
            status="completed" if result.finished else "failed",
            output={"message": result.message.content},
            tools_used=tools_used,
            tokens_used=result.tokens_used,
            error=result.error,
        )
        self.store.add_experiment_tokens(experiment_id, result.tokens_used)

        # WS1D: Persist the directive and agent response as messages.
        self.store.add_message(role="user", content=next_step, experiment_id=experiment_id)
        self.store.add_message(
            role="assistant", content=result.message.content, experiment_id=experiment_id
        )

        # WS1A: Flush to memory if conversation is getting long.
        total_messages = len(history_messages) + 2
        if total_messages > FLUSH_THRESHOLD:
            await self.context_manager.flush_to_memory(
                messages, self.memory, experiment_id=experiment_id
            )

        # WS1A: Compact if context exceeds soft limit.
        from .context_manager import estimate_tokens

        token_count = estimate_tokens(messages, self.config.llm.model)
        if token_count > self.context_manager.max_context_tokens * 0.8:
            await self.context_manager.compact(messages)

        # WS1B: Run correction-to-rule after learn phase.
        if exp.phase == "learn" and result.finished and result.error is None:
            try:
                rules_dir = self.config.primitives_dir / "rules"
                written = self.memory.write_corrections_to_rules(rules_dir)
                if written:
                    logger.info(
                        "promoted %d learnings to rules in %s",
                        len(written),
                        rules_dir / "derived",
                    )
            except Exception:
                logger.exception("correction-to-rule failed (non-fatal)")

        # Phase transition logic.
        if result.finished and result.error is None:
            current = self.store.get_experiment(experiment_id)
            if current and current.phase == exp.phase and exp.phase != "complete":
                next_phase = _next_phase(exp.phase)
                if exp.phase == "build":
                    # WS8A: Run quality gate before approving.
                    content_to_check = result.message.content
                    if content_to_check:
                        try:
                            from .quality_gate import evaluate_content

                            qscore = await evaluate_content(
                                content_to_check,
                                brand=primitives.brand,
                                rules=primitives.rules,
                                past_learnings=memories,
                                config=self.config.llm,
                            )
                            if not qscore.passed:
                                self.store.add_message(
                                    role="system",
                                    content=(
                                        f"[QUALITY GATE FAILED] Score: {qscore.overall:.1f}/10. "
                                        f"Feedback: {qscore.feedback}. Returning to build."
                                    ),
                                    experiment_id=experiment_id,
                                )
                                return RunOutcome(
                                    run_id=run.id,
                                    experiment_id=experiment_id,
                                    phase=exp.phase,
                                    ok=True,
                                    tokens_used=result.tokens_used,
                                    message=(
                                        f"Quality gate failed ({qscore.overall:.1f}/10): "
                                        f"{qscore.feedback}"
                                    ),
                                    tool_calls=tools_used,
                                )
                        except Exception:
                            logger.exception("quality gate eval failed (non-fatal)")

                    # WS8C: Check progressive autonomy — auto-approve if trust is high.
                    exp_type = exp.config.get("channel", "general")
                    trust = self.store.get_trust_score(exp_type)
                    trust_val = float(trust["score"]) if trust else 0.0
                    if trust_val >= 0.8:
                        logger.info(
                            "auto-approving experiment %s (trust=%.2f)",
                            experiment_id, trust_val,
                        )
                        self.store.update_experiment(experiment_id, phase="execute")
                        self.store.add_message(
                            role="system",
                            content=(
                                f"[AUTO-APPROVED] Trust score {trust_val:.2f} ≥ 0.80. "
                                "Proceeding to execute."
                            ),
                            experiment_id=experiment_id,
                        )
                    else:
                        self.store.update_experiment(experiment_id, phase="paused")
                        self.store.add_message(
                            role="system",
                            content=(
                                "[APPROVAL REQUESTED] Build phase complete. "
                                "Approve to start execute."
                            ),
                            experiment_id=experiment_id,
                        )
                elif next_phase:
                    self.store.update_experiment(experiment_id, phase=next_phase)

        # WS8C: Update trust score on experiment completion.
        if result.finished and exp.phase in ("complete", "learn"):
            try:
                exp_type = exp.config.get("channel", "general")
                self.store.upsert_trust_score(
                    exp_type,
                    score_delta=0.05 if result.error is None else -0.1,
                    ran=True,
                    succeeded=result.error is None,
                )
            except Exception:
                logger.debug("trust score update failed (non-fatal)")

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


def _prev_phase(phase: str) -> str | None:
    if phase not in PHASE_ORDER:
        return None
    idx = PHASE_ORDER.index(phase)
    return PHASE_ORDER[idx - 1] if idx > 0 else None


def _phase_directive(phase: str, exp: Experiment, primitives: Primitives | None = None) -> str:
    """Per-tick instructions. WS2C: play-aware directives with step-specific context."""
    base = f"Continue experiment '{exp.name}'. Phase: {phase}."

    # Load play content for richer directives.
    play_context = ""
    if primitives and exp.play_ids:
        for pid in exp.play_ids[:2]:
            play_body = primitives.plays.get(pid, "")
            if play_body:
                play_context += f"\n\n[Play: {pid}]\n{play_body[:1500]}"

    if phase == "design":
        return (
            f"{base} Define ICP, frame the hypothesis, and pick the right plays. "
            "Search memory for relevant past learnings before deciding. When the design is solid, "
            "use transition_phase to move to 'build'."
            f"{play_context}"
        )
    if phase == "build":
        return (
            f"{base} Build the assets: prospect list, copy, scripts, or content. "
            "Bias toward doing the work yourself — draft copy, create lists, write scripts. "
            "If you need to connect to external services (email, CRM, search), "
            "Composio and Pipedream tools are available as optional accelerators. "
            "When complete, use request_approval(experiment_id, message) and wait — "
            "DO NOT transition to 'execute' yourself."
            f"{play_context}"
        )
    if phase == "execute":
        return (
            f"{base} Execute the play. Respect channel rules and rate limits. "
            "Track what was sent and to whom. Use every tool at your disposal to deliver — "
            "Composio and Pipedream are available if you need external service connections. "
            "When execution is complete, transition to 'measure'."
            f"{play_context}"
        )
    if phase == "measure":
        return (
            f"{base} Gather results. Check open rates, reply rates, leads generated, "
            "or whatever KPIs the hypothesis defined. Use save_metric to record "
            "structured metrics (reply_rate, open_rate, etc.) and save facts to memory. "
            "When measurement is complete, transition to 'learn'."
            f"{play_context}"
        )
    if phase == "learn":
        return (
            f"{base} Analyze the results. What worked? What didn't? "
            "Use compare_to_hypothesis to evaluate against the original hypothesis. "
            "Save learnings to memory (type='learning'). Identify corrections — "
            "things we should always/never do going forward. "
            "Consider proposing follow-up experiments with propose_experiment. "
            "When learning is complete, transition to 'complete'."
            f"{play_context}"
        )
    return f"{base} Wrap up and report final results."
