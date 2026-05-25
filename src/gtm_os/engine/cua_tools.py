"""CUA (Computer-Use Agent) integration — browser automation via cua.ai sandboxes.

Gives agents their own virtual computer to interact with GUIs (LinkedIn, CRMs,
web forms, etc.) when API-based tools aren't sufficient.

Like Composio/Pipedream, CUA is optional: if no API key is set, the tools return
a clear "not configured" message so the agent can react gracefully.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from ..types import Tool

logger = logging.getLogger(__name__)


class CUAIntegration:
    """Thin wrapper over the CUA SDK. Lazy-imports so this module always loads."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("CUA_API_KEY")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def run_computer_task(
        self,
        task: str,
        *,
        model: str = "anthropic/claude-sonnet-4-20250514",
        max_steps: int = 30,
        start_url: str | None = None,
    ) -> dict[str, Any]:
        """Spin up an ephemeral CUA sandbox and run a computer-use task."""
        if not self.api_key:
            return {
                "ok": False,
                "error": "cua_not_configured",
                "message": (
                    "CUA (Computer-Use Agent) isn't configured. "
                    "Set CUA_API_KEY in your .env or Integrations page to enable "
                    "browser/GUI automation."
                ),
            }

        try:
            from cua import Computer, ComputerAgent  # type: ignore[import-untyped]
        except ImportError:
            return {
                "ok": False,
                "error": "cua_not_installed",
                "message": (
                    "CUA SDK is not installed. Install with: pip install cua-computer cua-agent"
                ),
            }

        try:
            computer = Computer(
                api_key=self.api_key,
                os="linux",
            )
            async with computer:
                agent = ComputerAgent(
                    model=model,
                    computer=computer,
                    max_steps=max_steps,
                )
                instructions = task
                if start_url:
                    instructions = f"First navigate to {start_url}. Then: {task}"

                result_text = ""
                steps_taken = 0
                async for event in agent.run(instructions):
                    steps_taken += 1
                    if hasattr(event, "text"):
                        result_text = event.text
                    elif isinstance(event, dict):
                        result_text = event.get("text", event.get("message", str(event)))

                return {
                    "ok": True,
                    "task": task,
                    "steps_taken": steps_taken,
                    "result": result_text or "Task completed",
                }
        except Exception as exc:
            logger.exception("CUA task failed: %s", task[:100])
            return {
                "ok": False,
                "error": "cua_execution_failed",
                "message": str(exc),
                "task": task,
            }

    async def browse_and_extract(
        self,
        url: str,
        extraction_instructions: str,
    ) -> dict[str, Any]:
        """Navigate to a URL and extract structured data."""
        task = (
            f"Navigate to {url} and extract the following information: "
            f"{extraction_instructions}. "
            "Return the extracted data in a clear, structured format."
        )
        return await self.run_computer_task(task, start_url=url)

    async def fill_form(
        self,
        url: str,
        form_data: dict[str, str],
        submit: bool = False,
    ) -> dict[str, Any]:
        """Navigate to a URL and fill in a form."""
        fields = "\n".join(f"- {k}: {v}" for k, v in form_data.items())
        task = (
            f"Navigate to {url} and fill in the form with these values:\n{fields}"
        )
        if submit:
            task += "\nThen submit the form."
        else:
            task += "\nDo NOT submit the form yet."
        return await self.run_computer_task(task, start_url=url)


def build_cua_tools(cua: CUAIntegration) -> list[Tool]:
    """Tool definitions the agent can call to use CUA browser automation."""

    async def _computer_task(
        task: str,
        start_url: str = "",
        max_steps: int = 30,
    ) -> Any:
        return await cua.run_computer_task(
            task,
            start_url=start_url or None,
            max_steps=int(max_steps),
        )

    async def _browse_extract(
        url: str,
        extraction_instructions: str,
    ) -> Any:
        return await cua.browse_and_extract(url, extraction_instructions)

    async def _fill_form(
        url: str,
        form_data: dict[str, str],
        submit: bool = False,
    ) -> Any:
        return await cua.fill_form(url, form_data, submit=bool(submit))

    return [
        Tool(
            name="computer_use",
            description=(
                "Use a virtual computer to complete a task that requires browser/GUI "
                "interaction. The agent gets its own screen, mouse, and keyboard. "
                "Use for: LinkedIn research, CRM updates, web form filling, scraping "
                "sites that block APIs, or any task requiring visual interaction. "
                "Provide a clear, specific task description."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": (
                            "Clear description of what to do on the computer. "
                            "Be specific about URLs, actions, and what data to return."
                        ),
                    },
                    "start_url": {
                        "type": "string",
                        "description": "Optional URL to navigate to first before starting the task.",
                        "default": "",
                    },
                    "max_steps": {
                        "type": "integer",
                        "description": "Maximum interaction steps (default 30).",
                        "default": 30,
                    },
                },
                "required": ["task"],
            },
            execute=_computer_task,
        ),
        Tool(
            name="browse_and_extract",
            description=(
                "Navigate to a URL and extract structured data from the page using "
                "visual understanding. Better than web scraping for dynamic/JS-heavy pages, "
                "pages behind login walls, or complex layouts."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to navigate to"},
                    "extraction_instructions": {
                        "type": "string",
                        "description": (
                            "What data to extract (e.g. 'company name, employee count, "
                            "and recent blog post titles')"
                        ),
                    },
                },
                "required": ["url", "extraction_instructions"],
            },
            execute=_browse_extract,
        ),
        Tool(
            name="fill_web_form",
            description=(
                "Navigate to a URL and fill in a web form with provided data. "
                "Use for CRM data entry, sign-up forms, or any web form interaction."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL of the form page"},
                    "form_data": {
                        "type": "object",
                        "description": "Field name → value pairs to fill in",
                        "additionalProperties": {"type": "string"},
                    },
                    "submit": {
                        "type": "boolean",
                        "description": "Whether to submit the form after filling (default false)",
                        "default": False,
                    },
                },
                "required": ["url", "form_data"],
            },
            execute=_fill_form,
        ),
    ]
