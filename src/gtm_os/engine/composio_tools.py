"""Composio SDK integration — discover, connect, execute.

We treat Composio as optional: if the SDK isn't installed or no API key is set, we still
expose `composio_discover_tools` / `composio_execute_action` tools that return a clear
"not configured" message so the agent can react gracefully.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..types import Tool

logger = logging.getLogger(__name__)


class ComposioIntegration:
    """Thin wrapper over composio-core. Lazy-imports the SDK so this module always loads."""

    def __init__(self, api_key: str | None) -> None:
        self.api_key = api_key
        self._toolset: Any | None = None

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _ensure_toolset(self) -> Any | None:
        if self._toolset is not None:
            return self._toolset
        if not self.api_key:
            return None
        try:
            from composio import ComposioToolSet  # type: ignore

            self._toolset = ComposioToolSet(api_key=self.api_key)
            return self._toolset
        except Exception as exc:  # pragma: no cover — optional dependency
            logger.warning("composio not available: %s", exc)
            return None

    async def discover_tools(
        self, use_case: str, *, apps: list[str] | None = None, limit: int = 10,
    ) -> list[dict[str, Any]]:
        ts = self._ensure_toolset()
        if ts is None:
            return [
                {
                    "error": "composio_not_configured",
                    "message": (
                        "Composio isn't configured. Install `composio-core` and set "
                        "COMPOSIO_API_KEY to enable real tool discovery."
                    ),
                }
            ]
        try:
            app_args = [a.upper() for a in apps] if apps else []
            # Prefer get_action_schemas when filtering by app — it returns full
            # action metadata and respects connected accounts. Fall back to
            # find_actions_by_use_case for pure use-case search without apps.
            if app_args:
                fn = getattr(ts, "get_action_schemas", None)
                if fn is not None:
                    schemas = await asyncio.to_thread(
                        fn, apps=app_args, check_connected_accounts=False,
                    )
                    return _normalize_actions(schemas)[:limit]
            fn = getattr(ts, "find_actions_by_use_case", None)
            if fn is None:
                return [{"error": "unsupported_sdk_method"}]
            actions = await asyncio.to_thread(fn, *app_args, use_case=use_case)
            return _normalize_actions(actions)[:limit]
        except Exception as exc:
            logger.exception("composio discover failed")
            return [{"error": "discover_failed", "message": str(exc)}]

    async def execute_action(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        ts = self._ensure_toolset()
        if ts is None:
            return {
                "ok": False,
                "error": "composio_not_configured",
                "message": "Composio isn't configured.",
                "action": action,
                "echo": params,
            }
        try:
            fn = getattr(ts, "execute_action", None)
            if fn is None:
                return {"ok": False, "error": "unsupported_sdk_method"}
            result = await asyncio.to_thread(fn, action=action, params=params)
            return {"ok": True, "action": action, "result": _normalize_value(result)}
        except Exception as exc:
            logger.exception("composio execute failed")
            return {
                "ok": False,
                "error": "execute_failed",
                "message": str(exc),
                "action": action,
            }

    async def manage_connection(self, toolkit: str) -> dict[str, Any]:
        ts = self._ensure_toolset()
        if ts is None:
            return {
                "ok": False,
                "error": "composio_not_configured",
                "message": "Composio isn't configured.",
            }
        try:
            fn = getattr(ts, "initiate_connection", None)
            if fn is None:
                return {"ok": False, "error": "unsupported_sdk_method"}
            result = await asyncio.to_thread(fn, app=toolkit.upper())
            return {"ok": True, "toolkit": toolkit, "result": _normalize_value(result)}
        except Exception as exc:
            logger.exception("composio connect failed")
            return {"ok": False, "error": "connect_failed", "message": str(exc)}


def _normalize_actions(actions: Any) -> list[dict[str, Any]]:
    if actions is None:
        return []
    if isinstance(actions, list):
        return [_normalize_value(a) for a in actions]
    return [_normalize_value(actions)]


def _normalize_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict") and callable(value.dict):
        return value.dict()
    if isinstance(value, dict):
        return {k: _normalize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_value(v) for v in value]
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    return str(value)


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
                "first if you don't know the action name."
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
