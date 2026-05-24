"""Custom GTM-OS tools the agent can call.

These are the tools that let the agent operate on the GTM-OS state itself: create
experiments, save / search memory, schedule task ticks, transition phases, request
human approval.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from croniter import croniter

from ..types import Tool

if TYPE_CHECKING:  # pragma: no cover
    from .experiment import ExperimentRunner
    from .memory import VectorMemory
    from .store import Store


logger = logging.getLogger(__name__)


PHASES = ["design", "build", "execute", "measure", "learn", "complete", "paused"]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _next_run_from_cron(expr: str) -> str:
    base = datetime.now(UTC)
    itr = croniter(expr, base)
    return itr.get_next(datetime).astimezone(UTC).isoformat(timespec="seconds")


def _next_run_from_interval(seconds: int) -> str:
    return (datetime.now(UTC) + timedelta(seconds=int(seconds))).isoformat(timespec="seconds")


def build_custom_tools(
    *,
    store: Store,
    memory: VectorMemory,
    runner: ExperimentRunner | None = None,
    play_ids: list[str] | None = None,
) -> list[Tool]:
    play_id_enum = play_ids or []

    async def _memory_save(
        content: str,
        type: str = "fact",
        source: str | None = None,
        experiment_id: str | None = None,
        confidence: float = 0.5,
    ) -> dict[str, Any]:
        m = await memory.save(
            content,
            type=type,  # type: ignore[arg-type]
            source=source,
            experiment_id=experiment_id,
            confidence=float(confidence),
        )
        return {"ok": True, "memory_id": m.id, "type": m.type, "confidence": m.confidence}

    async def _memory_search(
        query: str, limit: int = 5, type_filter: str | None = None
    ) -> dict[str, Any]:
        results = await memory.search(query, limit=int(limit), type_filter=type_filter)
        return {
            "ok": True,
            "results": [
                {
                    "id": m.id,
                    "type": m.type,
                    "content": m.content,
                    "confidence": m.confidence,
                    "similarity": m.similarity,
                    "experiment_id": m.experiment_id,
                }
                for m in results
            ],
        }

    async def _create_experiment(
        name: str,
        description: str | None = None,
        hypothesis: str | None = None,
        play_ids: list[str] | None = None,
        channel: str | None = None,
        config: dict[str, Any] | None = None,
        token_budget: int = 200_000,
    ) -> dict[str, Any]:
        cfg = dict(config or {})
        if channel:
            cfg["channel"] = channel
        exp = store.create_experiment(
            name=name,
            description=description,
            hypothesis=hypothesis,
            play_ids=play_ids or [],
            config=cfg,
            token_budget=int(token_budget),
        )
        return {
            "ok": True,
            "experiment_id": exp.id,
            "phase": exp.phase,
            "play_ids": exp.play_ids,
            "config": exp.config,
        }

    async def _update_experiment(
        experiment_id: str,
        phase: str | None = None,
        hypothesis: str | None = None,
        config: dict[str, Any] | None = None,
        play_ids: list[str] | None = None,
        current_agent: str | None = None,
        token_budget: int | None = None,
    ) -> dict[str, Any]:
        fields: dict[str, Any] = {}
        if phase is not None:
            fields["phase"] = phase
        if hypothesis is not None:
            fields["hypothesis"] = hypothesis
        if config is not None:
            fields["config"] = config
        if play_ids is not None:
            fields["play_ids"] = play_ids
        if current_agent is not None:
            fields["current_agent"] = current_agent
        if token_budget is not None:
            fields["token_budget"] = int(token_budget)
        exp = store.update_experiment(experiment_id, **fields)
        if not exp:
            return {"ok": False, "error": "not_found"}
        return {"ok": True, "experiment_id": exp.id, "phase": exp.phase}

    async def _list_experiments(phase_filter: str | None = None, limit: int = 50) -> dict[str, Any]:
        exps = store.list_experiments(phase=phase_filter, limit=int(limit))
        return {
            "ok": True,
            "experiments": [
                {
                    "id": e.id,
                    "name": e.name,
                    "phase": e.phase,
                    "play_ids": e.play_ids,
                    "config": e.config,
                    "tokens_used": e.tokens_used,
                    "token_budget": e.token_budget,
                    "updated_at": e.updated_at,
                }
                for e in exps
            ],
        }

    async def _transition_phase(
        experiment_id: str, new_phase: str, reason: str | None = None
    ) -> dict[str, Any]:
        if new_phase not in PHASES:
            return {"ok": False, "error": f"unknown_phase: {new_phase}"}
        exp = store.update_experiment(experiment_id, phase=new_phase)
        if not exp:
            return {"ok": False, "error": "not_found"}
        await memory.save(
            f"Experiment {exp.name} → phase {new_phase}. {reason or ''}".strip(),
            type="fact",
            source="phase_transition",
            experiment_id=experiment_id,
            confidence=0.6,
        )
        return {"ok": True, "experiment_id": exp.id, "phase": exp.phase}

    async def _schedule_task(
        experiment_id: str,
        type: str = "experiment_tick",
        cron_expr: str | None = None,
        interval_seconds: int | None = None,
        max_cost: float | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from ..types import Schedule
        from .store import _new_id

        if not cron_expr and not interval_seconds:
            return {
                "ok": False,
                "error": "missing_schedule",
                "message": "Provide either cron_expr or interval_seconds.",
            }
        if cron_expr:
            try:
                next_run = _next_run_from_cron(cron_expr)
            except Exception as exc:
                return {"ok": False, "error": "invalid_cron", "message": str(exc)}
        else:
            next_run = _next_run_from_interval(int(interval_seconds or 3600))

        sched = Schedule(
            id=_new_id(),
            experiment_id=experiment_id,
            type=type,
            cron_expr=cron_expr,
            interval_seconds=int(interval_seconds) if interval_seconds else None,
            next_run_at=next_run,
            max_cost=max_cost,
            config=config or {},
        )
        store.insert_schedule(sched)
        store.update_experiment(experiment_id, schedule_id=sched.id)
        return {"ok": True, "schedule_id": sched.id, "next_run_at": sched.next_run_at}

    async def _request_approval(experiment_id: str, message: str) -> dict[str, Any]:
        # Pause the experiment and surface a message; UI will display the pending approval.
        exp = store.update_experiment(experiment_id, phase="paused")
        store.add_message(
            role="system",
            content=f"[APPROVAL REQUESTED] {message}",
            experiment_id=experiment_id,
        )
        await memory.save(
            f"Approval requested for experiment {exp.name if exp else experiment_id}: {message}",
            type="fact",
            source="approval",
            experiment_id=experiment_id,
            confidence=0.6,
        )
        return {"ok": True, "experiment_id": experiment_id, "phase": "paused"}

    async def _list_plays() -> dict[str, Any]:
        return {"ok": True, "plays": play_id_enum}

    play_param = {
        "type": "array",
        "items": {"type": "string"}
        if not play_id_enum
        else {"type": "string", "enum": play_id_enum},
        "description": "Play IDs (subdirectories of primitives/plays/).",
    }

    return [
        Tool(
            name="memory_save",
            description=(
                "Save a fact, learning, preference, or rule to long-term memory. "
                "Use this aggressively — anything you discover that should help future experiments."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["fact", "learning", "preference", "rule"],
                        "default": "fact",
                    },
                    "source": {"type": "string"},
                    "experiment_id": {"type": "string"},
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "default": 0.5,
                    },
                },
                "required": ["content"],
            },
            execute=_memory_save,
        ),
        Tool(
            name="memory_search",
            description=(
                "Semantic search across long-term memory. Use this before designing or "
                "running an experiment to inherit past learnings."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 5},
                    "type_filter": {
                        "type": "string",
                        "enum": ["fact", "learning", "preference", "rule"],
                    },
                },
                "required": ["query"],
            },
            execute=_memory_search,
        ),
        Tool(
            name="create_experiment",
            description=(
                "Create a new experiment (a configured task loop). The experiment starts in "
                "the 'design' phase. Specify play_ids matching primitives/plays/ subdirs."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "hypothesis": {"type": "string"},
                    "play_ids": play_param,
                    "channel": {
                        "type": "string",
                        "description": "Channel (email, linkedin, cold-call, seo, etc.).",
                    },
                    "config": {"type": "object", "additionalProperties": True},
                    "token_budget": {"type": "integer", "default": 200000},
                },
                "required": ["name"],
            },
            execute=_create_experiment,
        ),
        Tool(
            name="update_experiment",
            description="Update an experiment's phase, hypothesis, config, or play list.",
            parameters={
                "type": "object",
                "properties": {
                    "experiment_id": {"type": "string"},
                    "phase": {"type": "string", "enum": PHASES},
                    "hypothesis": {"type": "string"},
                    "config": {"type": "object", "additionalProperties": True},
                    "play_ids": play_param,
                    "current_agent": {"type": "string"},
                    "token_budget": {"type": "integer"},
                },
                "required": ["experiment_id"],
            },
            execute=_update_experiment,
        ),
        Tool(
            name="list_experiments",
            description="List experiments, optionally filtered by phase.",
            parameters={
                "type": "object",
                "properties": {
                    "phase_filter": {"type": "string", "enum": PHASES},
                    "limit": {"type": "integer", "default": 50},
                },
            },
            execute=_list_experiments,
        ),
        Tool(
            name="transition_phase",
            description=(
                "Advance an experiment to a new phase (design → build → execute → measure → learn → complete). "
                "Always include a brief reason."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "experiment_id": {"type": "string"},
                    "new_phase": {"type": "string", "enum": PHASES},
                    "reason": {"type": "string"},
                },
                "required": ["experiment_id", "new_phase"],
            },
            execute=_transition_phase,
        ),
        Tool(
            name="schedule_task",
            description=(
                "Schedule recurring runs for an experiment. Provide either cron_expr (e.g. '0 9 * * *') "
                "or interval_seconds. Optionally set max_cost to auto-pause on budget."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "experiment_id": {"type": "string"},
                    "type": {"type": "string", "default": "experiment_tick"},
                    "cron_expr": {"type": "string"},
                    "interval_seconds": {"type": "integer"},
                    "max_cost": {"type": "number"},
                    "config": {"type": "object", "additionalProperties": True},
                },
                "required": ["experiment_id"],
            },
            execute=_schedule_task,
        ),
        Tool(
            name="request_approval",
            description=(
                "Pause an experiment and request human approval. Use this before the execute phase, "
                "or any time real money/messages would be sent."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "experiment_id": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["experiment_id", "message"],
            },
            execute=_request_approval,
        ),
        Tool(
            name="list_plays",
            description="List the play IDs available for use in experiments.",
            parameters={"type": "object", "properties": {}},
            execute=_list_plays,
        ),
    ]
