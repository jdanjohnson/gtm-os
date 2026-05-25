"""Composio REST API v3.1 integration — discover, connect, execute.

Uses the Composio REST API directly instead of the composio-core SDK, which
relies on retired v2 endpoints (HTTP 410). The v3.1 API is the current
stable endpoint for tool discovery and execution.

If no API key is set, all tools return a clear "not configured" message so the
agent can react gracefully.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any

import httpx

from ..types import Tool

logger = logging.getLogger(__name__)

COMPOSIO_API = "https://backend.composio.dev"


class ComposioIntegration:
    """Thin wrapper over the Composio v3.1 REST API."""

    def __init__(self, api_key: str | None) -> None:
        self.api_key = api_key

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self.api_key or "", "Content-Type": "application/json"}

    async def _get_connected_account_id(self, app_slug: str) -> str | None:
        """Find the first ACTIVE connected account for a given app."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{COMPOSIO_API}/api/v3/connected_accounts",
                    headers=self._headers(),
                    params={"limit": 100},
                )
                resp.raise_for_status()
                data = resp.json()
            items = data.get("items", data.get("data", []))
            for c in items:
                toolkit = c.get("toolkit", {}) or {}
                slug = toolkit.get("slug", c.get("appName", ""))
                if slug.lower() == app_slug.lower() and c.get("status") == "ACTIVE":
                    return c["id"]
        except Exception as exc:
            logger.warning("Failed to fetch connected accounts: %s", exc)
        return None

    async def discover_tools(
        self, use_case: str, *, apps: list[str] | None = None, limit: int = 10,
    ) -> list[dict[str, Any]]:
        if not self.api_key:
            return [
                {
                    "error": "composio_not_configured",
                    "message": (
                        "Composio isn't configured. Set COMPOSIO_API_KEY to "
                        "enable real tool discovery."
                    ),
                }
            ]
        try:
            params: dict[str, Any] = {"limit": min(limit, 100)}
            if use_case:
                params["search"] = use_case
            if apps:
                params["toolkits"] = ",".join(a.lower() for a in apps)

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{COMPOSIO_API}/api/v3.1/tools",
                    headers=self._headers(),
                    params=params,
                )
                resp.raise_for_status()
                data = resp.json()

            items = data if isinstance(data, list) else (
                data.get("items") or data.get("tools") or data.get("data") or []
            )
            return [
                {
                    "action": t.get("slug", t.get("name", "")),
                    "display_name": t.get("display_name", t.get("name", "")),
                    "description": t.get("description", ""),
                    "app": t.get("toolkit", {}).get("slug", "") if isinstance(t.get("toolkit"), dict) else "",
                }
                for t in items[:limit]
                if isinstance(t, dict)
            ]
        except Exception as exc:
            logger.exception("composio discover failed")
            return [{"error": "discover_failed", "message": str(exc)}]

    async def execute_action(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            return {
                "ok": False,
                "error": "composio_not_configured",
                "message": "Composio isn't configured.",
                "action": action,
                "echo": params,
            }

        # Derive app slug from action name (e.g. GMAIL_SEND_EMAIL -> gmail).
        app_slug = action.split("_")[0].lower() if "_" in action else ""
        conn_id = await self._get_connected_account_id(app_slug) if app_slug else None

        try:
            payload: dict[str, Any] = {"arguments": params}
            if conn_id:
                payload["connected_account_id"] = conn_id
                payload["entity_id"] = "default"

            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{COMPOSIO_API}/api/v3.1/tools/execute/{action}",
                    headers=self._headers(),
                    json=payload,
                )
                resp.raise_for_status()
                result = resp.json()

            successful = result.get("successful") or result.get("successfull", False)
            return {
                "ok": successful,
                "action": action,
                "result": result.get("data", result),
                "error": result.get("error"),
            }
        except httpx.HTTPStatusError as exc:
            error_body = {}
            with contextlib.suppress(Exception):
                error_body = exc.response.json()
            error_msg = (
                error_body.get("error", {}).get("message", "")
                if isinstance(error_body.get("error"), dict)
                else str(error_body.get("error", exc))
            )
            logger.exception("composio execute failed: %s", error_msg)
            return {
                "ok": False,
                "error": "execute_failed",
                "message": error_msg,
                "action": action,
            }
        except Exception as exc:
            logger.exception("composio execute failed")
            return {
                "ok": False,
                "error": "execute_failed",
                "message": str(exc),
                "action": action,
            }

    async def manage_connection(self, toolkit: str) -> dict[str, Any]:
        if not self.api_key:
            return {
                "ok": False,
                "error": "composio_not_configured",
                "message": "Composio isn't configured.",
            }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{COMPOSIO_API}/api/v3/connected_accounts/link",
                    headers=self._headers(),
                    json={
                        "toolkit_slug": toolkit.lower(),
                        "user_id": "default",
                    },
                )
                resp.raise_for_status()
                result = resp.json()
            return {"ok": True, "toolkit": toolkit, "result": result}
        except Exception as exc:
            logger.exception("composio connect failed")
            return {"ok": False, "error": "connect_failed", "message": str(exc)}


def build_composio_tools(composio: ComposioIntegration) -> list[Tool]:
    """Tool definitions the agent can call to use Composio."""

    async def _discover(
        use_case: str, apps: list[str] | None = None, limit: int = 10,
    ) -> Any:
        return await composio.discover_tools(use_case, apps=apps, limit=int(limit))

    async def _execute(action: str, params: dict[str, Any] | None = None) -> Any:
        return await composio.execute_action(action, params or {})

    async def _connect(toolkit: str) -> Any:
        return await composio.manage_connection(toolkit)

    return [
        Tool(
            name="composio_discover_tools",
            description=(
                "Search Composio for actions that match a use-case description. "
                "IMPORTANT: Always pass the 'apps' parameter to filter results to "
                "specific apps (e.g. ['GMAIL', 'SLACK']). Without 'apps', results "
                "will be unfocused. Use this to find tools like 'send email via "
                "gmail', 'search people on apollo', 'post to slack', etc."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "use_case": {
                        "type": "string",
                        "description": "Plain-English description of what you want to do.",
                    },
                    "apps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Filter to specific Composio apps (e.g. ['GMAIL', 'SLACK', "
                            "'APOLLO', 'HUBSPOT']). Strongly recommended for relevant results."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "default": 10,
                        "description": "Max number of actions to return.",
                    },
                },
                "required": ["use_case"],
            },
            execute=_discover,
        ),
        Tool(
            name="composio_execute_action",
            description=(
                "Execute a specific Composio action (e.g. GMAIL_SEND_EMAIL, "
                "APOLLO_PEOPLE_SEARCH, SLACK_SEND_MESSAGE). Call composio_discover_tools "
                "first if you don't know the action name. For GMAIL_SEND_EMAIL, params "
                "should include: recipient_email, subject, body."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "The exact Composio action ID (often UPPERCASE_WITH_UNDERSCORES).",
                    },
                    "params": {
                        "type": "object",
                        "description": "Parameters for the action.",
                        "additionalProperties": True,
                    },
                },
                "required": ["action"],
            },
            execute=_execute,
        ),
        Tool(
            name="composio_manage_connection",
            description=(
                "Start the OAuth / connection flow for a Composio toolkit "
                "(e.g. GMAIL, APOLLO, SLACK). Returns the URL the user must visit."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "toolkit": {
                        "type": "string",
                        "description": "Toolkit name (e.g. GMAIL, APOLLO, SLACK, HUBSPOT).",
                    }
                },
                "required": ["toolkit"],
            },
            execute=_connect,
        ),
    ]
