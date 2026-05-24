"""Composio Router — intelligent tool discovery, routing, and composition.

Upgrades the basic Composio integration with:
1. Full toolkit catalog — discovers all available tools on startup
2. Phase-to-tool mapping — knows which toolkits serve which experiment phases
3. Connection management — prompts for missing connections when needed
4. Tool chain composition — chains tools for multi-step workflows
5. Self-teaching — saves working tool configs as reusable skills
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ..types import Tool
from .composio_tools import ComposioIntegration

logger = logging.getLogger(__name__)

# Maps GTM experiment phases/intents to likely Composio toolkits.
PHASE_TOOLKIT_MAP: dict[str, list[str]] = {
    # Prospecting / research
    "find_people": ["APOLLO", "LINKEDIN", "CLEARBIT", "HUNTER"],
    "find_companies": ["APOLLO", "CRUNCHBASE", "CLEARBIT"],
    "enrich": ["APOLLO", "CLEARBIT", "HUNTER", "LINKEDIN"],
    # Outreach
    "send_email": ["GMAIL", "OUTLOOK", "SENDGRID", "MAILCHIMP"],
    "send_message": ["SLACK", "DISCORD", "TELEGRAM", "TWITTER"],
    "schedule_meeting": ["CALENDLY", "GOOGLE_CALENDAR", "OUTLOOK_CALENDAR"],
    # CRM / tracking
    "crm_update": ["HUBSPOT", "SALESFORCE", "PIPEDRIVE", "AIRTABLE"],
    "track_lead": ["HUBSPOT", "SALESFORCE", "PIPEDRIVE"],
    "log_activity": ["HUBSPOT", "SALESFORCE", "AIRTABLE", "NOTION"],
    # Content / social
    "post_social": ["TWITTER", "LINKEDIN", "FACEBOOK", "INSTAGRAM"],
    "create_content": ["NOTION", "GOOGLE_DOCS", "AIRTABLE"],
    # Data / automation
    "spreadsheet": ["GOOGLE_SHEETS", "AIRTABLE", "EXCEL"],
    "webhook": ["WEBHOOK", "ZAPIER"],
    "scrape": ["FIRECRAWL", "BROWSERLESS", "APIFY"],
}

# Common GTM tool chains (ordered sequences).
TOOL_CHAINS: dict[str, list[str]] = {
    "outbound_sequence": [
        "APOLLO:people_search",
        "APOLLO:enrich_person",
        "GMAIL:send_email",
        "HUBSPOT:create_contact",
    ],
    "inbound_qualify": [
        "HUBSPOT:get_contact",
        "CLEARBIT:enrich_company",
        "SLACK:send_message",
    ],
    "content_distribute": [
        "NOTION:get_page",
        "TWITTER:create_tweet",
        "LINKEDIN:create_post",
    ],
    "meeting_followup": [
        "GOOGLE_CALENDAR:get_event",
        "GMAIL:send_email",
        "HUBSPOT:create_note",
    ],
}


class ComposioRouter:
    """Intelligent routing layer over Composio."""

    def __init__(self, composio: ComposioIntegration, skills_dir: Path | None = None) -> None:
        self.composio = composio
        self.skills_dir = skills_dir
        self._catalog: dict[str, list[dict[str, Any]]] | None = None
        self._connected: set[str] = set()

    @property
    def configured(self) -> bool:
        return self.composio.configured

    async def discover_catalog(self) -> dict[str, list[dict[str, Any]]]:
        """Fetch full tool catalog grouped by toolkit."""
        if self._catalog is not None:
            return self._catalog

        if not self.composio.configured:
            return {}

        catalog: dict[str, list[dict[str, Any]]] = {}
        # Discover tools for common GTM use cases.
        use_cases = [
            "search people and companies",
            "send emails",
            "manage CRM contacts",
            "post on social media",
            "read and write spreadsheets",
            "schedule meetings",
            "scrape websites",
            "send slack messages",
        ]
        for uc in use_cases:
            try:
                tools = await self.composio.discover_tools(uc, limit=20)
                for tool in tools:
                    if isinstance(tool, dict) and "error" not in tool:
                        toolkit = tool.get("appName", tool.get("app", "unknown")).upper()
                        if toolkit not in catalog:
                            catalog[toolkit] = []
                        catalog[toolkit].append(tool)
            except Exception as exc:
                logger.warning("catalog discovery failed for '%s': %s", uc, exc)

        self._catalog = catalog
        return catalog

    def route_intent(self, intent: str) -> list[str]:
        """Given a natural-language intent, return suggested toolkit names."""
        intent_lower = intent.lower()
        suggestions: list[str] = []

        for key, toolkits in PHASE_TOOLKIT_MAP.items():
            # Simple keyword matching on intent.
            keywords = key.replace("_", " ").split()
            if any(kw in intent_lower for kw in keywords):
                suggestions.extend(toolkits)

        # Deduplicate while preserving order.
        seen: set[str] = set()
        result: list[str] = []
        for t in suggestions:
            if t not in seen:
                seen.add(t)
                result.append(t)
        return result

    def suggest_chain(self, goal: str) -> list[str] | None:
        """Suggest a tool chain for a given goal."""
        goal_lower = goal.lower()
        for chain_name, steps in TOOL_CHAINS.items():
            keywords = chain_name.replace("_", " ").split()
            if any(kw in goal_lower for kw in keywords):
                return steps
        return None

    async def check_connections(self, toolkits: list[str]) -> dict[str, bool]:
        """Check which toolkits are connected."""
        status: dict[str, bool] = {}
        for tk in toolkits:
            status[tk] = tk in self._connected
        return status

    def mark_connected(self, toolkit: str) -> None:
        """Mark a toolkit as connected (after user completes OAuth)."""
        self._connected.add(toolkit)

    async def execute_chain(
        self, chain: list[str], initial_params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Execute a tool chain, passing output of each step to the next."""
        results: list[dict[str, Any]] = []
        params = dict(initial_params)

        for step in chain:
            parts = step.split(":", 1)
            toolkit = parts[0]
            action_hint = parts[1] if len(parts) > 1 else ""

            # Discover the specific action.
            tools = await self.composio.discover_tools(
                f"{toolkit} {action_hint}", limit=1
            )
            if not tools or "error" in tools[0]:
                results.append({
                    "step": step,
                    "ok": False,
                    "error": f"Could not find action for {step}",
                })
                break

            action_name = tools[0].get("name", tools[0].get("actionName", ""))
            result = await self.composio.execute_action(action_name, params)
            results.append({"step": step, **result})

            if not result.get("ok", False):
                break

            # Feed result into next step's params.
            if isinstance(result.get("result"), dict):
                params.update(result["result"])

        return results

    def save_skill(self, name: str, config: dict[str, Any]) -> bool:
        """Save a working tool configuration as a reusable skill."""
        if not self.skills_dir:
            return False
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        skill_file = self.skills_dir / f"{name}.json"
        skill_file.write_text(json.dumps(config, indent=2), encoding="utf-8")
        logger.info("saved skill: %s", name)
        return True

    def load_skill(self, name: str) -> dict[str, Any] | None:
        """Load a previously saved skill configuration."""
        if not self.skills_dir:
            return None
        skill_file = self.skills_dir / f"{name}.json"
        if not skill_file.exists():
            return None
        return json.loads(skill_file.read_text(encoding="utf-8"))

    def list_skills(self) -> list[str]:
        """List all saved skills."""
        if not self.skills_dir or not self.skills_dir.exists():
            return []
        return [f.stem for f in self.skills_dir.glob("*.json")]


def build_router_tools(router: ComposioRouter) -> list[Tool]:
    """Higher-level routing tools for the agent."""

    async def _route_intent(intent: str) -> Any:
        toolkits = router.route_intent(intent)
        if not toolkits:
            # Fall back to Composio discovery.
            results = await router.composio.discover_tools(intent, limit=5)
            return {
                "suggested_toolkits": [],
                "discovered_tools": results,
                "hint": "No pre-mapped toolkits. Use composio_discover_tools for more.",
            }
        connections = await router.check_connections(toolkits)
        return {
            "suggested_toolkits": toolkits,
            "connection_status": connections,
            "needs_connection": [tk for tk, ok in connections.items() if not ok],
        }

    async def _suggest_chain(goal: str) -> Any:
        chain = router.suggest_chain(goal)
        if chain:
            return {"chain": chain, "steps": len(chain)}
        return {
            "chain": None,
            "hint": (
                "No pre-built chain for this goal. Break it into steps and use "
                "composio_discover_tools + composio_execute_action for each."
            ),
        }

    async def _execute_chain(chain_name: str, params: dict[str, Any] | None = None) -> Any:
        chain = TOOL_CHAINS.get(chain_name)
        if not chain:
            return {"ok": False, "error": f"Unknown chain: {chain_name}", "available": list(TOOL_CHAINS.keys())}
        return await router.execute_chain(chain, params or {})

    async def _list_toolkits() -> Any:
        catalog = await router.discover_catalog()
        if not catalog:
            return {
                "configured": router.configured,
                "toolkits": [],
                "hint": "Set COMPOSIO_API_KEY to discover available toolkits.",
            }
        return {
            "configured": True,
            "toolkits": [
                {"name": name, "tool_count": len(tools)}
                for name, tools in sorted(catalog.items())
            ],
            "total_tools": sum(len(t) for t in catalog.values()),
        }

    async def _save_skill(name: str, config: dict[str, Any]) -> Any:
        ok = router.save_skill(name, config)
        return {"ok": ok, "name": name}

    async def _load_skill(name: str) -> Any:
        skill = router.load_skill(name)
        if skill:
            return {"ok": True, "name": name, "config": skill}
        return {"ok": False, "error": f"Skill '{name}' not found", "available": router.list_skills()}

    return [
        Tool(
            name="route_intent",
            description=(
                "Given a natural-language intent (e.g. 'find e-commerce founders', "
                "'send cold emails', 'update CRM'), returns the best Composio toolkits "
                "and checks which are connected. Use this FIRST to figure out which "
                "tools you need before executing."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "intent": {
                        "type": "string",
                        "description": "What you want to accomplish.",
                    },
                },
                "required": ["intent"],
            },
            execute=_route_intent,
        ),
        Tool(
            name="suggest_tool_chain",
            description=(
                "Suggest a multi-step tool chain for a GTM goal. Returns an ordered "
                "list of actions like Apollo→Enrich→Gmail→HubSpot. Use for complex "
                "workflows that span multiple tools."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": "The GTM goal (e.g. 'outbound sequence', 'meeting followup').",
                    },
                },
                "required": ["goal"],
            },
            execute=_suggest_chain,
        ),
        Tool(
            name="execute_tool_chain",
            description=(
                "Execute a pre-built tool chain end-to-end, passing data between steps. "
                "Available chains: outbound_sequence, inbound_qualify, content_distribute, "
                "meeting_followup."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "chain_name": {
                        "type": "string",
                        "description": "Name of the chain to execute.",
                    },
                    "params": {
                        "type": "object",
                        "description": "Initial parameters for the first step.",
                        "additionalProperties": True,
                    },
                },
                "required": ["chain_name"],
            },
            execute=_execute_chain,
        ),
        Tool(
            name="list_available_toolkits",
            description=(
                "List all Composio toolkits available to this GTM-OS instance. "
                "Shows which apps are connected and how many tools each has."
            ),
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
            execute=_list_toolkits,
        ),
        Tool(
            name="save_skill",
            description=(
                "Save a working tool configuration as a reusable skill. Use after "
                "you successfully configure and execute a tool — saves it so you "
                "can reuse the exact config next time without re-discovering."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Skill name (snake_case, e.g. 'apollo_founder_search').",
                    },
                    "config": {
                        "type": "object",
                        "description": "The working config to save (action, params, notes).",
                        "additionalProperties": True,
                    },
                },
                "required": ["name", "config"],
            },
            execute=_save_skill,
        ),
        Tool(
            name="load_skill",
            description=(
                "Load a previously saved skill configuration. Use to recall a working "
                "tool setup instead of re-discovering from scratch."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Skill name to load.",
                    },
                },
                "required": ["name"],
            },
            execute=_load_skill,
        ),
    ]
