"""Gallery API — browse, search, and inspect playbooks, workflows, skills, and tools."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ...engine.gallery import Gallery

router = APIRouter(prefix="/gallery", tags=["gallery"])

_gallery: Gallery | None = None


def _get_gallery() -> Gallery:
    global _gallery
    if _gallery is None:
        _gallery = Gallery()
    return _gallery


def init_gallery(gallery_dir: str) -> None:
    global _gallery
    _gallery = Gallery(gallery_dir)


@router.get("")
async def gallery_index(
    kind: str | None = Query(None, description="Filter by kind: playbook, workflow, skill, tool"),
    category: str | None = Query(None, description="Filter by category"),
    tag: str | None = Query(None, description="Filter by tag"),
) -> dict:
    g = _get_gallery()
    items = g.list_all(kind=kind, category=category, tag=tag)
    return {"items": items, "count": len(items), "stats": g.stats}


@router.get("/search")
async def gallery_search(q: str = Query(..., description="Search query")) -> dict:
    g = _get_gallery()
    results = g.search(q)
    return {"results": results, "count": len(results)}


@router.get("/stats")
async def gallery_stats() -> dict:
    g = _get_gallery()
    return g.stats


@router.get("/{kind}/{item_id}")
async def gallery_detail(kind: str, item_id: str) -> dict:
    g = _get_gallery()
    item = g.get(kind, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"{kind}/{item_id} not found")
    return item
