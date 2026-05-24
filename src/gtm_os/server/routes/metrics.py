"""Metrics REST API (WS3B)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class SaveMetricBody(BaseModel):
    metric_name: str
    metric_value: float
    run_id: str | None = None
    variant: str | None = None


@router.post("/experiments/{experiment_id}/metrics")
async def save_metric(experiment_id: str, body: SaveMetricBody, request: Request):
    gtm = request.app.state.gtm
    metric_id = gtm.store.save_metric(
        experiment_id=experiment_id,
        metric_name=body.metric_name,
        metric_value=body.metric_value,
        run_id=body.run_id,
        variant=body.variant,
    )
    return {"ok": True, "metric_id": metric_id}


@router.get("/experiments/{experiment_id}/metrics")
async def list_metrics(
    experiment_id: str,
    request: Request,
    metric_name: str | None = None,
    variant: str | None = None,
):
    gtm = request.app.state.gtm
    metrics = gtm.store.list_metrics(
        experiment_id, metric_name=metric_name, variant=variant
    )
    return {"metrics": metrics}


@router.get("/experiments/{experiment_id}/metrics/summary")
async def metric_summary(experiment_id: str, request: Request):
    gtm = request.app.state.gtm
    return gtm.store.get_metric_summary(experiment_id)
