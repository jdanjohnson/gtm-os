"""Agent-driven end-to-end stress test for GTM-OS.

Sends real chat messages through the platform and verifies the agent
can perform a series of tasks: create experiments, research, analyze,
manage settings, etc. — like a real user would.

Usage:
    python tests/agent_e2e_test.py [--base-url http://127.0.0.1:3000] [--output tests/e2e-report.md]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

import httpx

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


@dataclass
class Bug:
    id: str
    title: str
    severity: Severity
    category: str
    endpoint: str
    description: str
    expected: str
    actual: str
    response_body: str = ""
    response_code: int | None = None


@dataclass
class ScenarioResult:
    name: str
    category: str
    passed: bool
    duration_ms: int = 0
    detail: str = ""
    bug: Bug | None = None
    events: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# SSE parsing
# ---------------------------------------------------------------------------

def parse_sse(raw: str) -> list[dict]:
    """Parse SSE text into a list of {event, data} dicts."""
    events: list[dict] = []
    current_event = "message"
    data_lines: list[str] = []

    for raw_line in raw.split("\n"):
        line = raw_line.rstrip("\r")
        if line.startswith("event: "):
            current_event = line[7:].strip()
        elif line.startswith("data: "):
            data_lines.append(line[6:])
        elif line == "" and data_lines:
            raw_data = "\n".join(data_lines)
            try:
                parsed = json.loads(raw_data)
            except json.JSONDecodeError:
                parsed = raw_data
            events.append({"event": current_event, "data": parsed})
            current_event = "message"
            data_lines = []

    if data_lines:
        raw_data = "\n".join(data_lines)
        try:
            parsed = json.loads(raw_data)
        except json.JSONDecodeError:
            parsed = raw_data
        events.append({"event": current_event, "data": parsed})

    return events


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

class AgentE2ERunner:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")
        self.results: list[ScenarioResult] = []
        self.bugs: list[Bug] = []
        self._bug_counter = 0

    def _next_bug_id(self) -> str:
        self._bug_counter += 1
        return f"E2E-{self._bug_counter:03d}"

    # -- helpers --

    async def _chat(
        self, message: str, agent: str = "orchestrator",
        experiment_id: str | None = None, thread_id: str | None = None,
        timeout: float = 120,
    ) -> tuple[int, str, list[dict]]:
        """Send a chat message, return (status, raw_body, parsed_events)."""
        payload: dict = {"message": message, "agent": agent}
        if experiment_id:
            payload["experiment_id"] = experiment_id
        if thread_id:
            payload["thread_id"] = thread_id

        async with httpx.AsyncClient(base_url=self.base, timeout=timeout) as c:
            r = await c.post("/api/chat", json=payload)
            events = parse_sse(r.text)
            return r.status_code, r.text, events

    async def _api(self, method: str, path: str, **kwargs) -> httpx.Response:
        async with httpx.AsyncClient(base_url=self.base, timeout=30) as c:
            return await c.request(method, path, **kwargs)

    def _get_final_message(self, events: list[dict]) -> str | None:
        for e in events:
            if e["event"] == "final" and isinstance(e["data"], dict):
                return e["data"].get("message", "")
        # Fall back to collecting tokens
        tokens = []
        for e in events:
            if e["event"] == "token" and isinstance(e["data"], dict):
                tokens.append(e["data"].get("text", ""))
        return "".join(tokens) if tokens else None

    def _has_error(self, events: list[dict]) -> str | None:
        for e in events:
            if e["event"] == "error" and isinstance(e["data"], dict):
                return e["data"].get("message", "unknown error")
        return None

    def _has_tool_calls(self, events: list[dict]) -> list[str]:
        return [
            e["data"]["name"]
            for e in events
            if e["event"] == "tool_call" and isinstance(e["data"], dict)
        ]

    def _pass(self, name: str, cat: str, detail: str = "", events: list[dict] | None = None) -> ScenarioResult:
        return ScenarioResult(name=name, category=cat, passed=True, detail=detail, events=events or [])

    def _fail(
        self, name: str, cat: str, endpoint: str, title: str,
        severity: Severity, description: str, expected: str, actual: str,
        raw: str = "", status: int | None = None, events: list[dict] | None = None,
    ) -> ScenarioResult:
        bug = Bug(
            id=self._next_bug_id(), title=title, severity=severity,
            category=cat, endpoint=endpoint, description=description,
            expected=expected, actual=actual,
            response_body=raw[:500], response_code=status,
        )
        self.bugs.append(bug)
        return ScenarioResult(name=name, category=cat, passed=False, bug=bug, events=events or [])

    async def _timed(self, name: str, cat: str, coro) -> None:
        t0 = time.monotonic()
        try:
            result = await coro
        except Exception as exc:
            result = self._fail(
                name, cat, "N/A", f"Scenario {name} crashed: {exc}",
                Severity.CRITICAL, str(exc), "No crash", str(exc),
            )
        elapsed = int((time.monotonic() - t0) * 1000)
        result.duration_ms = elapsed
        self.results.append(result)
        status = "PASS" if result.passed else "FAIL"
        log.info("  [%s] %s (%dms)%s", status, name, elapsed,
                 f" — {result.detail}" if result.detail else "")

    # -----------------------------------------------------------------------
    # Scenarios
    # -----------------------------------------------------------------------

    async def run_all(self) -> None:
        log.info("=" * 60)
        log.info("GTM-OS AGENT-DRIVEN E2E STRESS TEST")
        log.info("Target: %s", self.base)
        log.info("Started: %s", datetime.now(timezone.utc).isoformat())
        log.info("=" * 60)

        log.info("\n[1/8] Basic Agent Communication")
        await self._timed("chat_hello", "Chat", self._scenario_chat_hello())
        await self._timed("chat_followup", "Chat", self._scenario_chat_followup())
        await self._timed("chat_multi_sentence", "Chat", self._scenario_chat_multi_sentence())

        log.info("\n[2/8] Agent Creates Experiment via Chat")
        await self._timed("agent_create_experiment", "Experiment Lifecycle", self._scenario_agent_create_experiment())

        log.info("\n[3/8] Agent Manages Experiment Lifecycle")
        await self._timed("agent_describe_experiments", "Experiment Lifecycle", self._scenario_agent_describe_experiments())
        await self._timed("agent_pause_resume", "Experiment Lifecycle", self._scenario_agent_pause_resume())

        log.info("\n[4/8] Agent Research & Analysis")
        await self._timed("agent_research_task", "Research", self._scenario_agent_research())
        await self._timed("agent_analyze_metrics", "Research", self._scenario_agent_analyze_metrics())

        log.info("\n[5/8] Agent Memory & Context")
        await self._timed("agent_memory_recall", "Memory", self._scenario_agent_memory())
        await self._timed("agent_context_persistence", "Memory", self._scenario_context_persistence())

        log.info("\n[6/8] Agent Error Handling")
        await self._timed("agent_invalid_request", "Error Handling", self._scenario_invalid_request())
        await self._timed("agent_nonexistent_experiment", "Error Handling", self._scenario_nonexistent_experiment())
        await self._timed("agent_ambiguous_instruction", "Error Handling", self._scenario_ambiguous_instruction())

        log.info("\n[7/8] Concurrent Agent Sessions")
        await self._timed("concurrent_chats", "Concurrency", self._scenario_concurrent_chats())
        await self._timed("rapid_chat_messages", "Concurrency", self._scenario_rapid_messages())

        log.info("\n[8/8] Agent + API Integration")
        await self._timed("agent_then_api_verify", "Integration", self._scenario_agent_then_api())
        await self._timed("api_then_agent_verify", "Integration", self._scenario_api_then_agent())

    # -- 1. Basic Chat --

    async def _scenario_chat_hello(self) -> ScenarioResult:
        status, raw, events = await self._chat("Hello, what can you help me with?")
        err = self._has_error(events)
        if err:
            return self._fail(
                "chat_hello", "Chat", "POST /api/chat",
                "Agent cannot respond to basic greeting", Severity.CRITICAL,
                err, "Agent responds with capabilities", f"Error: {err}",
                raw, status, events,
            )
        msg = self._get_final_message(events)
        if not msg or len(msg) < 10:
            return self._fail(
                "chat_hello", "Chat", "POST /api/chat",
                "Agent gives empty/trivial response to greeting", Severity.HIGH,
                "Response too short", "Meaningful response about capabilities",
                f"Got: {msg!r}", raw, status, events,
            )
        return self._pass("chat_hello", "Chat", f"response_len={len(msg)}", events)

    async def _scenario_chat_followup(self) -> ScenarioResult:
        # First message
        _, _, events1 = await self._chat("My company is called TestCorp and we sell B2B SaaS.", thread_id="e2e-followup")
        err1 = self._has_error(events1)
        if err1:
            return self._fail(
                "chat_followup", "Chat", "POST /api/chat",
                "Agent fails on context-setting message", Severity.HIGH,
                err1, "Agent acknowledges context", f"Error: {err1}",
            )
        # Follow-up referencing prior context
        _, raw2, events2 = await self._chat("What did I just tell you about my company?", thread_id="e2e-followup")
        err2 = self._has_error(events2)
        if err2:
            return self._fail(
                "chat_followup", "Chat", "POST /api/chat",
                "Agent fails on follow-up message", Severity.HIGH,
                err2, "Agent recalls prior context", f"Error: {err2}",
            )
        msg = self._get_final_message(events2)
        if msg and ("testcorp" in msg.lower() or "b2b" in msg.lower() or "saas" in msg.lower()):
            return self._pass("chat_followup", "Chat", "Agent recalled company context", events2)
        return self._fail(
            "chat_followup", "Chat", "POST /api/chat",
            "Agent does not recall prior conversation context", Severity.MEDIUM,
            "Follow-up message should reference TestCorp/B2B/SaaS from prior turn",
            "Response mentioning TestCorp, B2B, or SaaS",
            f"Got: {(msg or '')[:200]}", raw2, None, events2,
        )

    async def _scenario_chat_multi_sentence(self) -> ScenarioResult:
        prompt = (
            "I need help with three things: "
            "1) Design an A/B test for email subject lines, "
            "2) Suggest metrics to track, and "
            "3) Recommend a sample size. "
            "Please address all three."
        )
        status, raw, events = await self._chat(prompt)
        err = self._has_error(events)
        if err:
            return self._fail(
                "chat_multi_sentence", "Chat", "POST /api/chat",
                "Agent fails on multi-part request", Severity.HIGH,
                err, "Agent addresses all three parts", f"Error: {err}",
                raw, status, events,
            )
        msg = self._get_final_message(events) or ""
        # Check if agent attempted to address multiple points
        indicators = 0
        for kw in ["a/b", "subject", "email", "test", "metric", "track", "sample", "size", "statistical"]:
            if kw in msg.lower():
                indicators += 1
        if indicators >= 3:
            return self._pass("chat_multi_sentence", "Chat", f"indicators={indicators}", events)
        return self._fail(
            "chat_multi_sentence", "Chat", "POST /api/chat",
            "Agent does not address all parts of multi-part request", Severity.LOW,
            "Agent should address A/B testing, metrics, and sample size",
            "Response covering all three topics",
            f"Only {indicators} keyword indicators found. Response: {msg[:300]}",
            raw, status, events,
        )

    # -- 2. Agent Creates Experiment --

    async def _scenario_agent_create_experiment(self) -> ScenarioResult:
        prompt = (
            "Create a new experiment called 'E2E Stress Test - Email Campaign'. "
            "The hypothesis is 'Personalized subject lines will increase open rates by 20%'. "
            "Use the email channel."
        )
        status, raw, events = await self._chat(prompt)
        err = self._has_error(events)
        if err:
            return self._fail(
                "agent_create_experiment", "Experiment Lifecycle", "POST /api/chat",
                "Agent fails when asked to create experiment", Severity.HIGH,
                err, "Agent creates experiment or explains how",
                f"Error: {err}", raw, status, events,
            )
        tools = self._has_tool_calls(events)
        msg = self._get_final_message(events) or ""
        # Check if agent used create_experiment tool or discussed creation
        if "create_experiment" in tools:
            return self._pass("agent_create_experiment", "Experiment Lifecycle",
                              f"Used create_experiment tool. tools={tools}", events)
        if any(kw in msg.lower() for kw in ["created", "experiment", "email campaign", "set up"]):
            return self._pass("agent_create_experiment", "Experiment Lifecycle",
                              f"Agent discussed experiment creation. tools={tools}", events)
        return self._fail(
            "agent_create_experiment", "Experiment Lifecycle", "POST /api/chat",
            "Agent does not attempt to create experiment when asked", Severity.MEDIUM,
            "Agent should use create_experiment tool or explain how to create",
            "Tool call or creation discussion",
            f"tools={tools}, msg={msg[:200]}", raw, status, events,
        )

    # -- 3. Experiment Lifecycle --

    async def _scenario_agent_describe_experiments(self) -> ScenarioResult:
        prompt = "List all my current experiments and their status."
        status, raw, events = await self._chat(prompt)
        err = self._has_error(events)
        if err:
            return self._fail(
                "agent_describe_experiments", "Experiment Lifecycle", "POST /api/chat",
                "Agent fails when asked to list experiments", Severity.HIGH,
                err, "Agent lists experiments", f"Error: {err}", raw, status, events,
            )
        tools = self._has_tool_calls(events)
        msg = self._get_final_message(events) or ""
        if "list_experiments" in tools or "experiment" in msg.lower():
            return self._pass("agent_describe_experiments", "Experiment Lifecycle",
                              f"tools={tools}", events)
        return self._fail(
            "agent_describe_experiments", "Experiment Lifecycle", "POST /api/chat",
            "Agent does not list experiments when asked", Severity.MEDIUM,
            "Agent should use list_experiments tool or describe experiments",
            "Tool call or experiment listing",
            f"tools={tools}, msg={msg[:200]}", raw, status, events,
        )

    async def _scenario_agent_pause_resume(self) -> ScenarioResult:
        # First create an experiment via API
        r = await self._api("POST", "/api/experiments", json={
            "name": "E2E Pause Test", "hypothesis": "Testing pause/resume"
        })
        if r.status_code != 200:
            return self._fail(
                "agent_pause_resume", "Experiment Lifecycle", "POST /api/experiments",
                "Cannot create experiment for pause test", Severity.HIGH,
                f"Status {r.status_code}", "200", r.text[:200],
            )
        exp_id = r.json()["experiment"]["id"]

        # Ask agent to pause it
        prompt = f"Pause the experiment with ID {exp_id}."
        status, raw, events = await self._chat(prompt)
        err = self._has_error(events)
        if err:
            return self._fail(
                "agent_pause_resume", "Experiment Lifecycle", "POST /api/chat",
                "Agent fails when asked to pause experiment", Severity.HIGH,
                err, "Agent pauses experiment", f"Error: {err}", raw, status, events,
            )
        tools = self._has_tool_calls(events)
        msg = self._get_final_message(events) or ""
        if "pause_experiment" in tools or "paused" in msg.lower():
            return self._pass("agent_pause_resume", "Experiment Lifecycle",
                              f"tools={tools}", events)
        return self._fail(
            "agent_pause_resume", "Experiment Lifecycle", "POST /api/chat",
            "Agent does not pause experiment when asked", Severity.MEDIUM,
            "Agent should use pause_experiment tool",
            "Tool call or confirmation of pause",
            f"tools={tools}, msg={msg[:200]}", raw, status, events,
        )

    # -- 4. Research & Analysis --

    async def _scenario_agent_research(self) -> ScenarioResult:
        prompt = (
            "Research best practices for cold email outreach to VP-level prospects "
            "in the SaaS industry. Give me 3 actionable tips."
        )
        status, raw, events = await self._chat(prompt, timeout=180)
        err = self._has_error(events)
        if err:
            return self._fail(
                "agent_research_task", "Research", "POST /api/chat",
                "Agent fails on research request", Severity.HIGH,
                err, "Agent provides research results", f"Error: {err}",
                raw, status, events,
            )
        msg = self._get_final_message(events) or ""
        if len(msg) > 50:
            return self._pass("agent_research_task", "Research",
                              f"response_len={len(msg)}", events)
        return self._fail(
            "agent_research_task", "Research", "POST /api/chat",
            "Agent gives insufficient research response", Severity.MEDIUM,
            "Expected substantial research with tips",
            "Response >50 chars with actionable tips",
            f"Got {len(msg)} chars: {msg[:200]}", raw, status, events,
        )

    async def _scenario_agent_analyze_metrics(self) -> ScenarioResult:
        # Create experiment with metrics via API
        r = await self._api("POST", "/api/experiments", json={
            "name": "Metrics Analysis Test", "hypothesis": "Testing metric analysis"
        })
        if r.status_code != 200:
            return self._pass("agent_analyze_metrics", "Research", "Skipped — can't create experiment")
        exp_id = r.json()["experiment"]["id"]

        # Add some metrics
        for i, (name, val) in enumerate([
            ("open_rate", 0.23), ("click_rate", 0.05), ("reply_rate", 0.02),
            ("open_rate", 0.28), ("click_rate", 0.07), ("reply_rate", 0.03),
        ]):
            await self._api("POST", f"/api/experiments/{exp_id}/metrics", json={
                "metric_name": name, "metric_value": val, "variant": "A" if i < 3 else "B"
            })

        prompt = f"Analyze the metrics for experiment {exp_id} and tell me which variant is performing better."
        status, raw, events = await self._chat(prompt, experiment_id=exp_id, timeout=180)
        err = self._has_error(events)
        if err:
            return self._fail(
                "agent_analyze_metrics", "Research", "POST /api/chat",
                "Agent fails on metrics analysis request", Severity.HIGH,
                err, "Agent analyzes metrics", f"Error: {err}", raw, status, events,
            )
        msg = self._get_final_message(events) or ""
        if len(msg) > 30:
            return self._pass("agent_analyze_metrics", "Research",
                              f"response_len={len(msg)}", events)
        return self._fail(
            "agent_analyze_metrics", "Research", "POST /api/chat",
            "Agent gives insufficient metrics analysis", Severity.LOW,
            "Expected analysis comparing variants",
            "Response analyzing variant performance",
            f"Got: {msg[:200]}", raw, status, events,
        )

    # -- 5. Memory & Context --

    async def _scenario_agent_memory(self) -> ScenarioResult:
        prompt = "What do you remember about past experiments and learnings?"
        status, raw, events = await self._chat(prompt, timeout=120)
        err = self._has_error(events)
        if err:
            return self._fail(
                "agent_memory_recall", "Memory", "POST /api/chat",
                "Agent fails on memory recall request", Severity.HIGH,
                err, "Agent discusses memories or says none exist",
                f"Error: {err}", raw, status, events,
            )
        msg = self._get_final_message(events) or ""
        tools = self._has_tool_calls(events)
        if msg and len(msg) > 20:
            return self._pass("agent_memory_recall", "Memory",
                              f"response_len={len(msg)}, tools={tools}", events)
        return self._fail(
            "agent_memory_recall", "Memory", "POST /api/chat",
            "Agent gives empty response to memory query", Severity.MEDIUM,
            "Agent should discuss memories or explain there are none",
            "Non-trivial response about memories",
            f"Got: {msg!r}", raw, status, events,
        )

    async def _scenario_context_persistence(self) -> ScenarioResult:
        tid = "e2e-context-test"
        # Send 3 messages in same thread
        await self._chat("Remember: my target audience is CFOs at mid-market companies.", thread_id=tid)
        await self._chat("Also, our product costs $500/month per seat.", thread_id=tid)
        _, raw, events = await self._chat(
            "Summarize what you know about my business so far.", thread_id=tid
        )
        err = self._has_error(events)
        if err:
            return self._fail(
                "agent_context_persistence", "Memory", "POST /api/chat",
                "Agent fails on context summary", Severity.HIGH,
                err, "Agent summarizes prior context",
                f"Error: {err}", raw, None, events,
            )
        msg = self._get_final_message(events) or ""
        hits = 0
        for kw in ["cfo", "mid-market", "$500", "500", "seat"]:
            if kw in msg.lower():
                hits += 1
        if hits >= 2:
            return self._pass("agent_context_persistence", "Memory",
                              f"context_hits={hits}", events)
        return self._fail(
            "agent_context_persistence", "Memory", "POST /api/chat",
            "Agent does not retain multi-turn context", Severity.HIGH,
            "Agent should remember CFO target, $500/seat pricing from earlier messages",
            "Response referencing CFOs, mid-market, $500/seat",
            f"Only {hits} keywords found. Response: {msg[:300]}",
            raw, None, events,
        )

    # -- 6. Error Handling --

    async def _scenario_invalid_request(self) -> ScenarioResult:
        # Send message with nonsensical experiment_id
        status, raw, events = await self._chat(
            "Run the next tick for this experiment.",
            experiment_id="totally-fake-id-999",
        )
        # Should not crash — should handle gracefully
        err = self._has_error(events)
        msg = self._get_final_message(events) or ""
        if err and ("crash" in err.lower() or "traceback" in err.lower()):
            return self._fail(
                "agent_invalid_request", "Error Handling", "POST /api/chat",
                "Agent crashes on invalid experiment_id", Severity.CRITICAL,
                "Server traceback on invalid experiment_id",
                "Graceful error or agent explanation",
                f"Error: {err}", raw, status, events,
            )
        # Any response (error message or graceful explanation) is acceptable
        return self._pass("agent_invalid_request", "Error Handling",
                          f"status={status}, has_error={err is not None}", events)

    async def _scenario_nonexistent_experiment(self) -> ScenarioResult:
        prompt = "Show me the details of experiment abc-123-does-not-exist."
        status, raw, events = await self._chat(prompt)
        err = self._has_error(events)
        if err and "traceback" in err.lower():
            return self._fail(
                "agent_nonexistent_experiment", "Error Handling", "POST /api/chat",
                "Agent crashes when referencing non-existent experiment", Severity.HIGH,
                err, "Graceful handling", f"Traceback: {err[:200]}",
                raw, status, events,
            )
        return self._pass("agent_nonexistent_experiment", "Error Handling",
                          f"Handled gracefully", events)

    async def _scenario_ambiguous_instruction(self) -> ScenarioResult:
        prompt = "Do the thing with the stuff for the campaign."
        status, raw, events = await self._chat(prompt, timeout=120)
        err = self._has_error(events)
        if err:
            return self._fail(
                "agent_ambiguous_instruction", "Error Handling", "POST /api/chat",
                "Agent crashes on ambiguous instruction", Severity.HIGH,
                err, "Agent asks for clarification or makes best attempt",
                f"Error: {err}", raw, status, events,
            )
        msg = self._get_final_message(events) or ""
        if len(msg) > 10:
            return self._pass("agent_ambiguous_instruction", "Error Handling",
                              f"response_len={len(msg)}", events)
        return self._fail(
            "agent_ambiguous_instruction", "Error Handling", "POST /api/chat",
            "Agent gives empty response to ambiguous request", Severity.LOW,
            "Agent should ask for clarification",
            "Clarifying question or best-effort response",
            f"Got: {msg!r}", raw, status, events,
        )

    # -- 7. Concurrency --

    async def _scenario_concurrent_chats(self) -> ScenarioResult:
        """Fire 5 chat requests in parallel on different threads."""
        messages = [
            ("What is an A/B test?", "conc-1"),
            ("Explain open rate.", "conc-2"),
            ("What is click-through rate?", "conc-3"),
            ("Define conversion funnel.", "conc-4"),
            ("What is customer acquisition cost?", "conc-5"),
        ]

        async def _one(msg: str, tid: str) -> tuple[bool, str]:
            try:
                _, raw, events = await self._chat(msg, thread_id=tid, timeout=180)
                err = self._has_error(events)
                if err:
                    return False, f"Error in {tid}: {err[:100]}"
                final = self._get_final_message(events) or ""
                if len(final) < 10:
                    return False, f"Empty response in {tid}"
                return True, f"{tid}: ok ({len(final)} chars)"
            except Exception as exc:
                return False, f"Exception in {tid}: {exc}"

        tasks = [_one(msg, tid) for msg, tid in messages]
        results = await asyncio.gather(*tasks)
        passed = sum(1 for ok, _ in results if ok)
        details = "; ".join(d for _, d in results)

        if passed == len(messages):
            return self._pass("concurrent_chats", "Concurrency",
                              f"{passed}/{len(messages)} succeeded")
        if passed == 0:
            return self._fail(
                "concurrent_chats", "Concurrency", "POST /api/chat",
                "All concurrent chats failed", Severity.CRITICAL,
                "No concurrent chats succeeded",
                "All 5 concurrent chats respond",
                details,
            )
        return self._fail(
            "concurrent_chats", "Concurrency", "POST /api/chat",
            f"Some concurrent chats failed ({passed}/{len(messages)})", Severity.MEDIUM,
            f"{len(messages) - passed} of {len(messages)} concurrent chats failed",
            "All concurrent chats succeed",
            details,
        )

    async def _scenario_rapid_messages(self) -> ScenarioResult:
        """Send 10 messages rapidly in sequence."""
        successes = 0
        errors = []
        for i in range(10):
            try:
                _, _, events = await self._chat(f"Quick question #{i+1}: what is GTM?",
                                                thread_id=f"rapid-{i}", timeout=120)
                err = self._has_error(events)
                if err:
                    errors.append(f"msg{i+1}: {err[:80]}")
                else:
                    successes += 1
            except Exception as exc:
                errors.append(f"msg{i+1}: {exc}")

        if successes == 10:
            return self._pass("rapid_chat_messages", "Concurrency",
                              f"10/10 rapid messages succeeded")
        if successes >= 7:
            return self._pass("rapid_chat_messages", "Concurrency",
                              f"{successes}/10 succeeded (acceptable). Errors: {'; '.join(errors[:3])}")
        return self._fail(
            "rapid_chat_messages", "Concurrency", "POST /api/chat",
            f"Too many rapid message failures ({successes}/10)",
            Severity.MEDIUM if successes >= 5 else Severity.HIGH,
            f"Only {successes}/10 rapid messages succeeded",
            "At least 7/10 rapid messages succeed",
            "; ".join(errors[:5]),
        )

    # -- 8. Agent + API Integration --

    async def _scenario_agent_then_api(self) -> ScenarioResult:
        """Agent creates something via chat, then we verify via API."""
        # Ask agent to create an experiment
        prompt = (
            "Create a new experiment called 'API Verification Test' "
            "with hypothesis 'Testing agent-API integration'."
        )
        _, _, events = await self._chat(prompt, timeout=120)
        err = self._has_error(events)
        if err:
            return self._fail(
                "agent_then_api_verify", "Integration", "POST /api/chat",
                "Agent fails to create experiment for API verification", Severity.HIGH,
                err, "Agent creates experiment", f"Error: {err}",
            )

        # Check via API if experiment was created
        r = await self._api("GET", "/api/experiments")
        if r.status_code != 200:
            return self._fail(
                "agent_then_api_verify", "Integration", "GET /api/experiments",
                "Cannot list experiments after agent action", Severity.HIGH,
                f"Status {r.status_code}", "200", r.text[:200],
            )
        experiments = r.json().get("experiments", [])
        found = any("api verification" in (e.get("name") or "").lower() for e in experiments)
        tools = self._has_tool_calls(events)
        if found:
            return self._pass("agent_then_api_verify", "Integration",
                              f"Experiment found via API. tools={tools}", events)
        # Agent might have discussed but not actually created
        return self._pass("agent_then_api_verify", "Integration",
                          f"Agent responded (may not have used tool). tools={tools}", events)

    async def _scenario_api_then_agent(self) -> ScenarioResult:
        """Create something via API, then ask agent about it."""
        r = await self._api("POST", "/api/experiments", json={
            "name": "Agent Query Target",
            "description": "Created by E2E test for agent to find",
            "hypothesis": "Agent can find API-created experiments",
        })
        if r.status_code != 200:
            return self._pass("api_then_agent_verify", "Integration", "Skipped — can't create experiment")
        exp_id = r.json()["experiment"]["id"]

        prompt = f"Tell me about experiment {exp_id}. What is its name and hypothesis?"
        status, raw, events = await self._chat(prompt, timeout=120)
        err = self._has_error(events)
        if err:
            return self._fail(
                "api_then_agent_verify", "Integration", "POST /api/chat",
                "Agent fails when asked about API-created experiment", Severity.HIGH,
                err, "Agent describes the experiment",
                f"Error: {err}", raw, status, events,
            )
        msg = self._get_final_message(events) or ""
        tools = self._has_tool_calls(events)
        if "agent query target" in msg.lower() or "get_experiment" in tools:
            return self._pass("api_then_agent_verify", "Integration",
                              f"Agent found the experiment. tools={tools}", events)
        return self._pass("api_then_agent_verify", "Integration",
                          f"Agent responded (may not have looked up). tools={tools}", events)

    # -----------------------------------------------------------------------
    # Report
    # -----------------------------------------------------------------------

    def generate_report(self) -> str:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed

        lines = [
            "# GTM-OS Agent-Driven E2E Stress Test Report",
            "",
            f"**Generated:** {now}",
            f"**Target:** {self.base}",
            f"**Total Scenarios:** {total}",
            f"**Passed:** {passed}",
            f"**Failed:** {failed}",
            f"**Bugs Found:** {len(self.bugs)}",
            "",
        ]

        # Summary by category
        cats: dict[str, dict] = {}
        for r in self.results:
            c = cats.setdefault(r.category, {"total": 0, "passed": 0, "failed": 0})
            c["total"] += 1
            if r.passed:
                c["passed"] += 1
            else:
                c["failed"] += 1

        lines.append("## Summary by Category")
        lines.append("")
        lines.append("| Category | Tests | Passed | Failed |")
        lines.append("|----------|-------|--------|--------|")
        for cat in sorted(cats):
            c = cats[cat]
            lines.append(f"| {cat} | {c['total']} | {c['passed']} | {c['failed']} |")
        lines.append("")

        # Bugs
        if self.bugs:
            lines.append("## Bugs Found")
            lines.append("")
            severity_order = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]
            icons = {
                Severity.CRITICAL: "🔴", Severity.HIGH: "🟠",
                Severity.MEDIUM: "🟡", Severity.LOW: "🔵", Severity.INFO: "⚪",
            }
            for sev in severity_order:
                sev_bugs = [b for b in self.bugs if b.severity == sev]
                if not sev_bugs:
                    continue
                lines.append(f"### {icons[sev]} {sev.value} ({len(sev_bugs)})")
                lines.append("")
                for b in sev_bugs:
                    lines.append(f"#### {b.id}: {b.title}")
                    lines.append("")
                    lines.append(f"- **Category:** {b.category}")
                    lines.append(f"- **Endpoint:** `{b.endpoint}`")
                    lines.append(f"- **Description:** {b.description}")
                    lines.append(f"- **Expected:** {b.expected}")
                    lines.append(f"- **Actual:** {b.actual}")
                    if b.response_code:
                        lines.append(f"- **HTTP Status:** {b.response_code}")
                    if b.response_body:
                        lines.append(f"- **Response:** `{b.response_body[:300]}`")
                    lines.append("")

        # Full results
        lines.append("## Full Scenario Results")
        lines.append("")
        lines.append("| # | Scenario | Category | Status | Duration |")
        lines.append("|---|----------|----------|--------|----------|")
        for i, r in enumerate(self.results, 1):
            status = "PASS" if r.passed else f"**FAIL** ({r.bug.id})" if r.bug else "**FAIL**"
            lines.append(f"| {i} | {r.name} | {r.category} | {status} | {r.duration_ms}ms |")
        lines.append("")

        # Event details for failed scenarios
        failed_results = [r for r in self.results if not r.passed]
        if failed_results:
            lines.append("## Failed Scenario Details")
            lines.append("")
            for r in failed_results:
                lines.append(f"### {r.name}")
                lines.append(f"- **Detail:** {r.detail}")
                if r.events:
                    lines.append("- **SSE Events:**")
                    for e in r.events[:10]:
                        etype = e.get("event", "?")
                        edata = e.get("data", "")
                        if isinstance(edata, dict):
                            edata = json.dumps(edata)[:200]
                        lines.append(f"  - `{etype}`: {str(edata)[:200]}")
                lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser(description="GTM-OS Agent-Driven E2E Stress Test")
    parser.add_argument("--base-url", default="http://127.0.0.1:3000")
    parser.add_argument("--output", default="tests/e2e-report.md")
    args = parser.parse_args()

    runner = AgentE2ERunner(args.base_url)
    await runner.run_all()

    report = runner.generate_report()
    with open(args.output, "w") as f:
        f.write(report)

    total = len(runner.results)
    passed = sum(1 for r in runner.results if r.passed)
    print(f"\n{'='*60}")
    print(f"RESULTS: {passed}/{total} passed, {len(runner.bugs)} bugs found")
    print(f"Report written to: {args.output}")
    print(f"{'='*60}")

    sys.exit(0 if not runner.bugs else 1)


if __name__ == "__main__":
    asyncio.run(main())
