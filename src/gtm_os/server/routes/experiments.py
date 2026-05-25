"""Experiments REST API."""

from __future__ import annotations

from datetime import UTC
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator

from ..validation import sanitize_text

router = APIRouter()


class CreateExperimentBody(BaseModel):
    name: str
    description: str | None = None
    hypothesis: str | None = None
    play_ids: list[str] | None = None
    channel: str | None = None
    config: dict[str, Any] | None = None
    token_budget: int | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = sanitize_text(v)
        if not v:
            raise ValueError("name must not be empty")
        return v

    @field_validator("description", "hypothesis", mode="before")
    @classmethod
    def sanitize_optional_text(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return sanitize_text(v)


class UpdateExperimentBody(BaseModel):
    name: str | None = None
    description: str | None = None
    hypothesis: str | None = None
    phase: str | None = None
    play_ids: list[str] | None = None
    config: dict[str, Any] | None = None
    current_agent: str | None = None
    token_budget: int | None = None

    @field_validator("name", mode="before")
    @classmethod
    def name_not_empty(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = sanitize_text(v)
        if not v:
            raise ValueError("name must not be empty")
        return v

    @field_validator("description", "hypothesis", mode="before")
    @classmethod
    def sanitize_optional_text(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return sanitize_text(v)


class ScheduleBody(BaseModel):
    cron_expr: str | None = None
    interval_seconds: int | None = None
    max_cost: float | None = None
    type: str = "experiment_tick"


def _serialize_experiment(e) -> dict[str, Any]:
    return {
        "id": e.id,
        "name": e.name,
        "description": e.description,
        "hypothesis": e.hypothesis,
        "phase": e.phase,
        "play_ids": e.play_ids,
        "current_agent": e.current_agent,
        "config": e.config,
        "schedule_id": e.schedule_id,
        "token_budget": e.token_budget,
        "tokens_used": e.tokens_used,
        "created_at": e.created_at,
        "updated_at": e.updated_at,
    }


@router.get("/experiments")
async def list_experiments(request: Request, phase: str | None = None, limit: int = 100):
    gtm = request.app.state.gtm
    return {
        "experiments": [
            _serialize_experiment(e) for e in gtm.store.list_experiments(phase=phase, limit=limit)
        ]
    }


@router.post("/experiments")
async def create_experiment(body: CreateExperimentBody, request: Request):
    gtm = request.app.state.gtm
    cfg = dict(body.config or {})
    if body.channel:
        cfg["channel"] = body.channel
    exp = gtm.runner.create(
        name=body.name,
        description=body.description,
        hypothesis=body.hypothesis,
        play_ids=body.play_ids or [],
        config=cfg,
        token_budget=body.token_budget,
    )
    return {"experiment": _serialize_experiment(exp)}


@router.get("/experiments/{experiment_id}")
async def get_experiment(experiment_id: str, request: Request):
    gtm = request.app.state.gtm
    exp = gtm.store.get_experiment(experiment_id)
    if not exp:
        raise HTTPException(404, "experiment not found")
    runs = gtm.store.list_runs(experiment_id, limit=20)
    return {
        "experiment": _serialize_experiment(exp),
        "runs": [
            {
                "id": r.id,
                "phase": r.phase,
                "status": r.status,
                "tokens_used": r.tokens_used,
                "started_at": r.started_at,
                "completed_at": r.completed_at,
                "tools_used": r.tools_used,
                "error": r.error,
            }
            for r in runs
        ],
    }


@router.patch("/experiments/{experiment_id}")
async def update_experiment(experiment_id: str, body: UpdateExperimentBody, request: Request):
    gtm = request.app.state.gtm
    fields = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    exp = gtm.store.update_experiment(experiment_id, **fields)
    if not exp:
        raise HTTPException(404, "experiment not found")
    return {"experiment": _serialize_experiment(exp)}


@router.post("/experiments/{experiment_id}/run-tick")
async def run_tick(experiment_id: str, request: Request):
    gtm = request.app.state.gtm
    outcome = await gtm.runner.run_tick(experiment_id)
    return {
        "ok": outcome.ok,
        "run_id": outcome.run_id,
        "phase": outcome.phase,
        "tokens_used": outcome.tokens_used,
        "error": outcome.error,
        "message": outcome.message,
        "tool_calls": outcome.tool_calls,
    }


@router.post("/experiments/{experiment_id}/pause")
async def pause_experiment(experiment_id: str, request: Request):
    gtm = request.app.state.gtm
    exp = gtm.runner.pause(experiment_id, reason="paused via API")
    if not exp:
        raise HTTPException(404, "experiment not found")
    return {"experiment": _serialize_experiment(exp)}


@router.post("/experiments/{experiment_id}/resume")
async def resume_experiment(experiment_id: str, request: Request, target_phase: str = "design"):
    gtm = request.app.state.gtm
    exp = gtm.runner.resume(experiment_id, target_phase=target_phase)
    if not exp:
        raise HTTPException(404, "experiment not found")
    return {"experiment": _serialize_experiment(exp)}


@router.post("/experiments/{experiment_id}/schedule")
async def schedule_experiment(experiment_id: str, body: ScheduleBody, request: Request):
    from datetime import datetime, timedelta

    from croniter import croniter

    from ...engine.store import _new_id
    from ...types import Schedule

    gtm = request.app.state.gtm
    if not body.cron_expr and not body.interval_seconds:
        raise HTTPException(400, "provide cron_expr or interval_seconds")
    if body.cron_expr:
        try:
            next_run = (
                croniter(body.cron_expr, datetime.now(UTC))
                .get_next(datetime)
                .astimezone(UTC)
                .isoformat(timespec="seconds")
            )
        except Exception as exc:
            raise HTTPException(400, f"invalid cron: {exc}") from exc
    else:
        next_run = (datetime.now(UTC) + timedelta(seconds=int(body.interval_seconds))).isoformat(
            timespec="seconds"
        )

    sched = Schedule(
        id=_new_id(),
        experiment_id=experiment_id,
        type=body.type,
        cron_expr=body.cron_expr,
        interval_seconds=body.interval_seconds,
        next_run_at=next_run,
        max_cost=body.max_cost,
        config={},
    )
    gtm.store.insert_schedule(sched)
    gtm.store.update_experiment(experiment_id, schedule_id=sched.id)
    return {
        "schedule": {
            "id": sched.id,
            "experiment_id": sched.experiment_id,
            "cron_expr": sched.cron_expr,
            "interval_seconds": sched.interval_seconds,
            "next_run_at": sched.next_run_at,
            "max_cost": sched.max_cost,
            "enabled": sched.enabled,
        }
    }
