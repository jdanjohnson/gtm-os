"""Integrations REST API — read status, update keys for Composio & Pipedream."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from ...engine.composio_tools import ComposioIntegration
from ...engine.pipedream_tools import PipedreamIntegration

router = APIRouter()
logger = logging.getLogger(__name__)


class IntegrationStatus(BaseModel):
    name: str
    configured: bool
    has_env_key: bool
    docs_url: str
    description: str


class IntegrationKeyUpdate(BaseModel):
    composio_api_key: str | None = None
    pipedream_api_key: str | None = None


def _env_file_path(request: Request) -> Path:
    gtm = request.app.state.gtm
    return gtm.config.project_root / ".env"


def _mask_key(key: str | None) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "***"
    return key[:4] + "…" + key[-4:]


@router.get("/integrations")
async def get_integrations(request: Request) -> dict[str, Any]:
    gtm = request.app.state.gtm
    composio: ComposioIntegration = gtm.composio
    pipedream: PipedreamIntegration = gtm.pipedream

    return {
        "integrations": [
            {
                "name": "composio",
                "label": "Composio",
                "configured": composio.configured,
                "masked_key": _mask_key(composio.api_key),
                "has_env_key": bool(os.environ.get("COMPOSIO_API_KEY")),
                "env_var": "COMPOSIO_API_KEY",
                "docs_url": "https://docs.composio.dev",
                "dashboard_url": "https://app.composio.dev",
                "description": (
                    "Connect 250+ apps (Gmail, Apollo, Slack, HubSpot, etc.) "
                    "for real tool discovery and execution."
                ),
            },
            {
                "name": "pipedream",
                "label": "Pipedream",
                "configured": pipedream.configured,
                "masked_key": _mask_key(pipedream.api_key),
                "has_env_key": bool(os.environ.get("PIPEDREAM_API_KEY")),
                "env_var": "PIPEDREAM_API_KEY",
                "docs_url": "https://pipedream.com/docs",
                "dashboard_url": "https://pipedream.com/apps",
                "description": (
                    "2,400+ app integrations with pre-built actions. "
                    "Run workflows and actions via API."
                ),
            },
        ]
    }


@router.put("/integrations/keys")
async def update_integration_keys(request: Request, body: IntegrationKeyUpdate) -> dict[str, Any]:
    """Persist API keys to .env and hot-reload integrations in memory."""
    gtm = request.app.state.gtm
    env_path = _env_file_path(request)
    updated: list[str] = []

    # Read existing .env lines (preserve other keys).
    existing_lines: list[str] = []
    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()

    key_updates: dict[str, str | None] = {}
    if body.composio_api_key is not None:
        key_updates["COMPOSIO_API_KEY"] = body.composio_api_key
    if body.pipedream_api_key is not None:
        key_updates["PIPEDREAM_API_KEY"] = body.pipedream_api_key

    # Build new .env content.
    new_lines: list[str] = []
    seen_keys: set[str] = set()
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        eq_idx = stripped.find("=")
        if eq_idx == -1:
            new_lines.append(line)
            continue
        env_key = stripped[:eq_idx].strip()
        if env_key in key_updates:
            val = key_updates[env_key]
            if val:  # non-empty → write it
                new_lines.append(f"{env_key}={val}")
            # else: omit the line (key was cleared)
            seen_keys.add(env_key)
        else:
            new_lines.append(line)

    # Append any keys not already in the file.
    for env_key, val in key_updates.items():
        if env_key not in seen_keys and val:
            new_lines.append(f"{env_key}={val}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    # Hot-reload: update the in-memory integrations.
    if body.composio_api_key is not None:
        new_key = body.composio_api_key or None
        os.environ["COMPOSIO_API_KEY"] = body.composio_api_key or ""
        gtm.composio = ComposioIntegration(new_key)
        gtm.runner.composio = gtm.composio
        gtm.config.composio_api_key = new_key
        updated.append("composio")

    if body.pipedream_api_key is not None:
        new_key = body.pipedream_api_key or None
        os.environ["PIPEDREAM_API_KEY"] = body.pipedream_api_key or ""
        gtm.pipedream = PipedreamIntegration(new_key)
        gtm.runner.pipedream = gtm.pipedream
        gtm.config.pipedream_api_key = new_key
        updated.append("pipedream")

    logger.info("Integration keys updated: %s", ", ".join(updated))
    return {"ok": True, "updated": updated}
