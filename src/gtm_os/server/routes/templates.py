"""Templates REST API (WS3D)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator

from ..validation import sanitize_text

router = APIRouter()


class SaveTemplateBody(BaseModel):
    name: str
    description: str | None = None
    play_ids: list[str] | None = None
    config: dict[str, Any] | None = None
    hypothesis_pattern: str | None = None
    token_budget: int = 200_000

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = sanitize_text(v)
        if not v:
            raise ValueError("name must not be empty")
        return v

    @field_validator("description", "hypothesis_pattern", mode="before")
    @classmethod
    def sanitize_optional_text(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return sanitize_text(v)


class CreateFromTemplateBody(BaseModel):
    name: str
    overrides: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = sanitize_text(v)
        if not v:
            raise ValueError("name must not be empty")
        return v


@router.get("/templates")
async def list_templates(request: Request, limit: int = 50):
    gtm = request.app.state.gtm
    return {"templates": gtm.store.list_templates(limit=limit)}


@router.post("/templates")
async def save_template(body: SaveTemplateBody, request: Request):
    gtm = request.app.state.gtm
    template_id = gtm.store.save_template(
        name=body.name,
        description=body.description,
        play_ids=body.play_ids,
        config=body.config,
        hypothesis_pattern=body.hypothesis_pattern,
        token_budget=body.token_budget,
    )
    return {"ok": True, "template_id": template_id}


@router.get("/templates/{template_id}")
async def get_template(template_id: str, request: Request):
    gtm = request.app.state.gtm
    tmpl = gtm.store.get_template(template_id)
    if not tmpl:
        raise HTTPException(404, "template not found")
    return {"template": tmpl}


@router.post("/templates/{template_id}/create-experiment")
async def create_from_template(template_id: str, body: CreateFromTemplateBody, request: Request):
    gtm = request.app.state.gtm
    tmpl = gtm.store.get_template(template_id)
    if not tmpl:
        raise HTTPException(404, "template not found")

    import json

    play_ids = json.loads(tmpl["play_ids"]) if isinstance(tmpl["play_ids"], str) else (tmpl["play_ids"] or [])
    config = json.loads(tmpl["config"]) if isinstance(tmpl["config"], str) else (tmpl["config"] or {})

    overrides = body.overrides or {}
    play_ids = overrides.get("play_ids", play_ids)
    config = {**config, **overrides.get("config", {})}
    hypothesis = overrides.get("hypothesis", tmpl.get("hypothesis_pattern"))
    budget = int(overrides.get("token_budget", tmpl.get("token_budget") or 200_000))

    exp = gtm.runner.create(
        name=body.name,
        hypothesis=hypothesis,
        play_ids=play_ids,
        config=config,
        token_budget=budget,
    )
    return {"ok": True, "experiment_id": exp.id, "phase": exp.phase}
