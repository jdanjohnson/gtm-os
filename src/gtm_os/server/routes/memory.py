"""Memory browse/search API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel


router = APIRouter()


class SearchBody(BaseModel):
    query: str
    limit: int = 20
    type_filter: str | None = None
    min_confidence: float = 0.0


@router.get("/memory")
async def list_memory(
    request: Request, type_filter: str | None = None, limit: int = 100
) -> dict[str, Any]:
    gtm = request.app.state.gtm
    items = gtm.store.list_memories(type_filter=type_filter, limit=limit)
    return {
        "memories": [
            {
                "id": m.id,
                "type": m.type,
                "content": m.content,
                "source": m.source,
                "experiment_id": m.experiment_id,
                "confidence": m.confidence,
                "reinforced_by": m.reinforced_by,
                "created_at": m.created_at,
                "updated_at": m.updated_at,
            }
            for m in items
        ]
    }


@router.post("/memory/search")
async def search_memory(body: SearchBody, request: Request) -> dict[str, Any]:
    gtm = request.app.state.gtm
    results = await gtm.memory.search(
        body.query,
        limit=body.limit,
        type_filter=body.type_filter,
        min_confidence=body.min_confidence,
    )
    return {
        "results": [
            {
                "id": m.id,
                "type": m.type,
                "content": m.content,
                "source": m.source,
                "experiment_id": m.experiment_id,
                "confidence": m.confidence,
                "similarity": m.similarity,
                "created_at": m.created_at,
            }
            for m in results
        ]
    }


@router.get("/primitives")
async def get_primitives(request: Request) -> dict[str, Any]:
    gtm = request.app.state.gtm
    prim = gtm.runner.load_primitives_cached()
    return {
        "agents": sorted(prim.agents.keys()),
        "plays": sorted(prim.plays.keys()),
        "phase_rules": sorted(prim.rules.phase_rules.keys()),
        "channel_rules": sorted(prim.rules.channel_rules.keys()),
        "brand_loaded": bool(prim.brand.body),
        "schedules": prim.triggers.schedules,
    }
