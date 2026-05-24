"""Pipedream Connect integration — discover apps, execute actions.

Like Composio, Pipedream is optional. If no API key is set, the tools return a
clear "not configured" message so the agent can react gracefully.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from ..types import Tool

logger = logging.getLogger(__name__)

PIPEDREAM_API_BASE = "https://api.pipedream.com/v1"


class PipedreamIntegration:
    """Thin wrapper over the Pipedream Connect REST API."""

    def __init__(self, api_key: str | None) -> None:
        self.api_key = api_key

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def list_apps(self, query: str = "", *, limit: int = 10) -> list[dict[str, Any]]:
        if not self.api_key:
            return [
                {
                    "error": "pipedream_not_configured",
                    "message": (
                        "Pipedream isn't configured. Set PIPEDREAM_API_KEY in your "
                        ".env file to enable Pipedream integrations."
                    ),
                }
            ]
        try:
            url = f"{PIPEDREAM_API_BASE}/apps"
            params: dict[str, Any] = {"limit": limit}
            if query:
                params["q"] = query

            def _call() -> list[dict[str, Any]]:
                with httpx.Client(timeout=30) as client:
                    resp = client.get(url, headers=self._headers(), params=params)
                    resp.raise_for_status()
                    data = resp.json()
                    apps = data.get("data", [])
                    return [
                        {
                            "name_slug": a.get("name_slug", ""),
                            "name": a.get("name", ""),
                            "description": a.get("description", ""),
                            "img_src": a.get("img_src", ""),
                        }
                        for a in apps[:limit]
                    ]

            return await asyncio.to_thread(_call)
        except Exception as exc:
            logger.exception("pipedream list_apps failed")
            return [{"error": "list_apps_failed", "message": str(exc)}]

    async def list_components(
        self, app: str, *, component_type: str = "action", limit: int = 10
    ) -> list[dict[str, Any]]:
        if not self.api_key:
            return [{"error": "pipedream_not_configured"}]
        try:
            url = f"{PIPEDREAM_API_BASE}/apps/{app}/components"
            params: dict[str, Any] = {"limit": limit, "type": component_type}

            def _call() -> list[dict[str, Any]]:
                with httpx.Client(timeout=30) as client:
                    resp = client.get(url, headers=self._headers(), params=params)
                    resp.raise_for_status()
                    data = resp.json()
                    components = data.get("data", [])
                    return [
                        {
                            "key": c.get("key", ""),
                            "name": c.get("name", ""),
                            "description": c.get("description", ""),
                            "version": c.get("version", ""),
                        }
                        for c in components[:limit]
                    ]

            return await asyncio.to_thread(_call)
        except Exception as exc:
            logger.exception("pipedream list_components failed")
            return [{"error": "list_components_failed", "message": str(exc)}]

    async def run_action(
        self, component_key: str, params: dict[str, Any], *, account_id: str | None = None
    ) -> dict[str, Any]:
        if not self.api_key:
            return {
                "ok": False,
                "error": "pipedream_not_configured",
                "message": "Pipedream isn't configured.",
            }
        try:
            url = f"{PIPEDREAM_API_BASE}/components/run"
            body: dict[str, Any] = {
                "component_key": component_key,
                "configured_props": params,
            }
            if account_id:
                body["account_id"] = account_id

            def _call() -> dict[str, Any]:
                with httpx.Client(timeout=60) as client:
                    resp = client.post(url, headers=self._headers(), json=body)
                    resp.raise_for_status()
                    return resp.json()

            result = await asyncio.to_thread(_call)
            return {"ok": True, "component_key": component_key, "result": result}
        except Exception as exc:
            logger.exception("pipedream run_action failed")
            return {
                "ok": False,
                "error": "run_action_failed",
                "message": str(exc),
                "component_key": component_key,
            }


def build_pipedream_tools(pipedream: PipedreamIntegration) -> list[Tool]:
    """Tool definitions the agent can call to use Pipedream."""

    async def _list_apps(query: str = "", limit: int = 10) -> Any:
        return await pipedream.list_apps(query, limit=int(limit))

    async def _list_components(app: str, limit: int = 10) -> Any:
        return await pipedream.list_components(app, limit=int(limit))

    async def _run_action(component_key: str, params: dict[str, Any] | None = None) -> Any:
        return await pipedream.run_action(component_key, params or {})

    return [
        Tool(
            name="pipedream_list_apps",
            description=(
                "Search Pipedream's 2,400+ app integrations. Use this to find apps "
                "like Gmail, Slack, HubSpot, Apollo, Google Sheets, etc."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "default": "",
                        "description": "Search query to filter apps (e.g. 'gmail', 'slack').",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 10,
                        "description": "Max number of apps to return.",
                    },
                },
            },
            execute=_list_apps,
        ),
        Tool(
            name="pipedream_list_actions",
            description=(
                "List available actions for a Pipedream app. For example, list actions "
                "for 'gmail' to find send_email, search_emails, etc."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "app": {
                        "type": "string",
                        "description": "App slug (e.g. 'gmail', 'slack', 'hubspot').",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 10,
                        "description": "Max number of actions to return.",
                    },
                },
                "required": ["app"],
            },
            execute=_list_components,
        ),
        Tool(
            name="pipedream_run_action",
            description=(
                "Execute a Pipedream action component. Use pipedream_list_actions first "
                "to find the component key, then run it with the required parameters."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "component_key": {
                        "type": "string",
                        "description": "The Pipedream component key (from pipedream_list_actions).",
                    },
                    "params": {
                        "type": "object",
                        "description": "Parameters for the action.",
                        "additionalProperties": True,
                    },
                },
                "required": ["component_key"],
            },
            execute=_run_action,
        ),
    ]
