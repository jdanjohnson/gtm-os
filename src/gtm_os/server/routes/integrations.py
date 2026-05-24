"""Integrations REST API — keys, app catalog, connected accounts."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel

from ...engine.composio_tools import ComposioIntegration
from ...engine.pipedream_tools import PipedreamIntegration

router = APIRouter()
logger = logging.getLogger(__name__)

COMPOSIO_API = "https://backend.composio.dev"


class IntegrationStatus(BaseModel):
    name: str
    configured: bool
    has_env_key: bool
    docs_url: str
    description: str


class IntegrationKeyUpdate(BaseModel):
    composio_api_key: str | None = None
    pipedream_api_key: str | None = None


class ConnectRequest(BaseModel):
    toolkit_slug: str
    user_id: str = "default"
    redirect_url: str | None = None


class DisconnectRequest(BaseModel):
    connected_account_id: str


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


# ---------------------------------------------------------------------------
# Composio App Catalog + Connected Accounts
# ---------------------------------------------------------------------------

def _composio_headers(api_key: str) -> dict[str, str]:
    return {"x-api-key": api_key, "Content-Type": "application/json"}


@router.get("/integrations/apps")
async def list_apps(
    request: Request,
    search: str = "",
    category: str = "",
    limit: int = 50,
) -> dict[str, Any]:
    """Return available Composio toolkits (app catalog)."""
    gtm = request.app.state.gtm
    composio: ComposioIntegration = gtm.composio
    if not composio.api_key:
        return {"apps": [], "error": "composio_not_configured"}

    params: dict[str, Any] = {
        "limit": min(limit, 100),
        "sort_by": "usage",
    }
    if search:
        params["search"] = search
    if category:
        params["category"] = category

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{COMPOSIO_API}/api/v3/toolkits",
                headers=_composio_headers(composio.api_key),
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

        items = data.get("items", [])
        apps = [
            {
                "slug": t.get("slug", ""),
                "name": t.get("name", ""),
                "description": t.get("description", ""),
                "logo": t.get("logo", ""),
                "categories": t.get("categories", []),
                "auth_schemes": [
                    s.get("type", "") for s in t.get("auth_schemes", [])
                ],
            }
            for t in items
        ]
        return {"apps": apps}
    except httpx.HTTPStatusError as exc:
        logger.warning("Composio toolkits API error: %s", exc)
        return {"apps": [], "error": f"api_error_{exc.response.status_code}"}
    except Exception as exc:
        logger.exception("Composio toolkits list failed")
        return {"apps": [], "error": str(exc)}


@router.get("/integrations/connections")
async def list_connections(request: Request) -> dict[str, Any]:
    """Return Composio connected accounts for this project."""
    gtm = request.app.state.gtm
    composio: ComposioIntegration = gtm.composio
    if not composio.api_key:
        return {"connections": [], "error": "composio_not_configured"}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{COMPOSIO_API}/api/v3/connected_accounts",
                headers=_composio_headers(composio.api_key),
                params={"limit": 100},
            )
            resp.raise_for_status()
            data = resp.json()

        items = data.get("items", data.get("data", []))
        connections = [
            {
                "id": c.get("id", ""),
                "toolkit_slug": (c.get("toolkit", {}) or {}).get("slug", c.get("appName", "")),
                "toolkit_name": (c.get("toolkit", {}) or {}).get("name", c.get("appName", "")),
                "toolkit_logo": (c.get("toolkit", {}) or {}).get("logo", ""),
                "status": c.get("status", ""),
                "created_at": c.get("createdAt", c.get("created_at", "")),
                "user_id": c.get("member", {}).get("id", "") if c.get("member") else "",
            }
            for c in items
        ]
        return {"connections": connections}
    except httpx.HTTPStatusError as exc:
        logger.warning("Composio connections API error: %s", exc)
        return {"connections": [], "error": f"api_error_{exc.response.status_code}"}
    except Exception as exc:
        logger.exception("Composio connections list failed")
        return {"connections": [], "error": str(exc)}


@router.post("/integrations/connect")
async def initiate_connection(request: Request, body: ConnectRequest) -> dict[str, Any]:
    """Start a Composio connection flow. Returns a redirect URL for OAuth toolkits."""
    gtm = request.app.state.gtm
    composio: ComposioIntegration = gtm.composio
    if not composio.api_key:
        return {"ok": False, "error": "composio_not_configured"}

    try:
        # First, get auth configs for this toolkit to find the right auth_config_id.
        async with httpx.AsyncClient(timeout=30) as client:
            configs_resp = await client.get(
                f"{COMPOSIO_API}/api/v3/auth_configs",
                headers=_composio_headers(composio.api_key),
                params={"toolkit_slug": body.toolkit_slug, "limit": 10},
            )
            configs_resp.raise_for_status()
            configs_data = configs_resp.json()

        configs = configs_data.get("items", [])
        if not configs:
            return {
                "ok": False,
                "error": "no_auth_config",
                "message": f"No auth config found for {body.toolkit_slug}",
            }

        auth_config_id = configs[0].get("id", "")
        auth_scheme = configs[0].get("type", "")

        # Use the link endpoint for OAuth-based connections.
        link_body: dict[str, Any] = {
            "auth_config_id": auth_config_id,
            "user_id": body.user_id,
        }
        if body.redirect_url:
            link_body["callback_url"] = body.redirect_url

        async with httpx.AsyncClient(timeout=30) as client:
            link_resp = await client.post(
                f"{COMPOSIO_API}/api/v3/connected_accounts/link",
                headers=_composio_headers(composio.api_key),
                json=link_body,
            )
            link_resp.raise_for_status()
            link_data = link_resp.json()

        return {
            "ok": True,
            "redirect_url": link_data.get("url", link_data.get("redirect_url", "")),
            "connection_id": link_data.get("id", link_data.get("connectedAccountId", "")),
            "auth_scheme": auth_scheme,
            "status": link_data.get("status", ""),
        }
    except httpx.HTTPStatusError as exc:
        logger.warning("Composio connect error: %s %s", exc, exc.response.text[:500])
        return {"ok": False, "error": f"api_error_{exc.response.status_code}", "detail": exc.response.text[:300]}
    except Exception as exc:
        logger.exception("Composio connect failed")
        return {"ok": False, "error": str(exc)}


@router.delete("/integrations/connections/{connection_id}")
async def disconnect(request: Request, connection_id: str) -> dict[str, Any]:
    """Remove a Composio connected account."""
    gtm = request.app.state.gtm
    composio: ComposioIntegration = gtm.composio
    if not composio.api_key:
        return {"ok": False, "error": "composio_not_configured"}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.delete(
                f"{COMPOSIO_API}/api/v3/connected_accounts/{connection_id}",
                headers=_composio_headers(composio.api_key),
            )
            resp.raise_for_status()
        return {"ok": True, "disconnected": connection_id}
    except httpx.HTTPStatusError as exc:
        logger.warning("Composio disconnect error: %s", exc)
        return {"ok": False, "error": f"api_error_{exc.response.status_code}"}
    except Exception as exc:
        logger.exception("Composio disconnect failed")
        return {"ok": False, "error": str(exc)}
