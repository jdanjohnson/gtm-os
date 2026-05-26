#!/usr/bin/env python3
"""GTM-OS Stress Testing Framework.

Systematically tests every API endpoint, edge case, and integration point.
Generates a structured bug report in Markdown with severity ratings.

Usage:
    # Start server first:  uv run gtm-os start
    python tests/stress_test.py [--base-url http://127.0.0.1:3000]
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
from pathlib import Path
from typing import Any

import httpx

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("stress_test")


# ---------------------------------------------------------------------------
# Bug model
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    CRITICAL = "critical"   # App crash, data loss, security issue
    HIGH = "high"           # Feature completely broken
    MEDIUM = "medium"       # Feature partially broken or wrong behavior
    LOW = "low"             # Cosmetic, minor UX issue
    INFO = "info"           # Observation, not necessarily a bug


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
    steps: list[str] = field(default_factory=list)
    response_code: int | None = None
    response_body: str | None = None


@dataclass
class TestResult:
    name: str
    category: str
    passed: bool
    duration_ms: float
    detail: str = ""
    bug: Bug | None = None


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

class StressTestRunner:
    def __init__(self, base_url: str) -> None:
        self.base = base_url.rstrip("/")
        self.results: list[TestResult] = []
        self.bugs: list[Bug] = []
        self._bug_counter = 0
        self._created_experiment_ids: list[str] = []
        self._created_template_ids: list[str] = []

    def _bug_id(self) -> str:
        self._bug_counter += 1
        return f"BUG-{self._bug_counter:03d}"

    def _record(self, result: TestResult) -> None:
        self.results.append(result)
        if result.bug:
            self.bugs.append(result.bug)
        status = "PASS" if result.passed else "FAIL"
        logger.info(f"  [{status}] {result.name} ({result.duration_ms:.0f}ms)")

    async def run_all(self) -> None:
        async with httpx.AsyncClient(base_url=self.base, timeout=30.0) as c:
            self.client = c
            logger.info("=" * 60)
            logger.info("GTM-OS STRESS TEST FRAMEWORK")
            logger.info(f"Target: {self.base}")
            logger.info(f"Started: {datetime.now(timezone.utc).isoformat()}")
            logger.info("=" * 60)

            # --- Category 1: Health & Core ---
            logger.info("\n[1/9] Health & Core")
            await self._test_health()
            await self._test_health_response_schema()

            # --- Category 2: Experiments CRUD ---
            logger.info("\n[2/9] Experiments CRUD")
            await self._test_list_experiments()
            await self._test_create_experiment_valid()
            await self._test_create_experiment_missing_name()
            await self._test_create_experiment_empty_name()
            await self._test_get_experiment_valid()
            await self._test_get_experiment_not_found()
            await self._test_update_experiment()
            await self._test_update_experiment_not_found()
            await self._test_pause_experiment()
            await self._test_pause_already_paused()
            await self._test_resume_experiment()
            await self._test_resume_not_found()
            await self._test_run_tick()
            await self._test_schedule_experiment()
            await self._test_schedule_invalid_cron()
            await self._test_experiment_concurrent_creates()

            # --- Category 3: Memory ---
            logger.info("\n[3/9] Memory")
            await self._test_list_memory()
            await self._test_list_memory_filter()
            await self._test_search_memory()
            await self._test_search_memory_empty_query()
            await self._test_primitives()

            # --- Category 4: Chat / SSE ---
            logger.info("\n[4/9] Chat & SSE")
            await self._test_chat_basic()
            await self._test_chat_empty_message()
            await self._test_chat_invalid_agent()
            await self._test_chat_long_message()
            await self._test_chat_special_characters()
            await self._test_thread_messages()
            await self._test_thread_messages_not_found()

            # --- Category 5: Trust & Proposals ---
            logger.info("\n[5/9] Trust & Proposals")
            await self._test_list_trust_scores()
            await self._test_get_trust_score()
            await self._test_get_trust_score_not_found()
            await self._test_list_proposed()
            await self._test_list_proposed_filter()
            await self._test_review_proposal_not_found()
            await self._test_simulate_not_found()
            await self._test_approve_not_found()

            # --- Category 6: Templates ---
            logger.info("\n[6/9] Templates")
            await self._test_list_templates()
            await self._test_create_template()
            await self._test_get_template()
            await self._test_get_template_not_found()
            await self._test_create_from_template()

            # --- Category 7: Metrics ---
            logger.info("\n[7/9] Metrics")
            await self._test_save_metric()
            await self._test_list_metrics()
            await self._test_metric_summary()
            await self._test_save_metric_invalid_experiment()

            # --- Category 8: Integrations ---
            logger.info("\n[8/9] Integrations")
            await self._test_get_integrations()
            await self._test_get_tool_keys()
            await self._test_get_model_keys()
            await self._test_update_model_config()
            await self._test_list_apps()
            await self._test_list_connections()

            # --- Category 9: Brand ---
            logger.info("\n[9/9] Brand")
            await self._test_get_brand()
            await self._test_update_brand()
            await self._test_update_brand_partial()

            # --- Category 10: Edge Cases & Stress ---
            logger.info("\n[BONUS] Edge Cases & Stress")
            await self._test_404_unknown_route()
            await self._test_method_not_allowed()
            await self._test_malformed_json()
            await self._test_huge_payload()
            await self._test_sql_injection_attempt()
            await self._test_xss_attempt()
            await self._test_concurrent_requests()
            await self._test_rapid_fire()

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    async def _req(self, method: str, path: str, **kwargs) -> httpx.Response:
        return await self.client.request(method, path, **kwargs)

    async def _timed_test(
        self,
        name: str,
        category: str,
        coro,
    ) -> TestResult:
        t0 = time.monotonic()
        try:
            result = await coro
            duration = (time.monotonic() - t0) * 1000
            if isinstance(result, TestResult):
                result.duration_ms = duration
                self._record(result)
                return result
            # If coro returned None, it passed
            tr = TestResult(name=name, category=category, passed=True, duration_ms=duration)
            self._record(tr)
            return tr
        except Exception as exc:
            duration = (time.monotonic() - t0) * 1000
            bug = Bug(
                id=self._bug_id(),
                title=f"Uncaught exception in {name}",
                severity=Severity.HIGH,
                category=category,
                endpoint=name,
                description=f"Test raised unexpected exception: {exc}",
                expected="Test should complete without exception",
                actual=str(exc),
            )
            tr = TestResult(
                name=name, category=category, passed=False,
                duration_ms=duration, detail=str(exc), bug=bug,
            )
            self._record(tr)
            return tr

    def _fail(
        self,
        name: str,
        category: str,
        endpoint: str,
        title: str,
        severity: Severity,
        description: str,
        expected: str,
        actual: str,
        resp: httpx.Response | None = None,
    ) -> TestResult:
        bug = Bug(
            id=self._bug_id(),
            title=title,
            severity=severity,
            category=category,
            endpoint=endpoint,
            description=description,
            expected=expected,
            actual=actual,
            response_code=resp.status_code if resp else None,
            response_body=resp.text[:500] if resp else None,
        )
        return TestResult(name=name, category=category, passed=False, duration_ms=0, bug=bug)

    def _pass(self, name: str, category: str, detail: str = "") -> TestResult:
        return TestResult(name=name, category=category, passed=True, duration_ms=0, detail=detail)

    # -----------------------------------------------------------------------
    # 1. Health & Core
    # -----------------------------------------------------------------------

    async def _test_health(self) -> None:
        async def _run():
            r = await self._req("GET", "/api/health")
            if r.status_code != 200:
                return self._fail(
                    "health_endpoint", "Health", "GET /api/health",
                    "Health endpoint returns non-200",
                    Severity.CRITICAL,
                    f"Health check returned {r.status_code}",
                    "200 OK with JSON body",
                    f"{r.status_code}: {r.text[:200]}",
                    r,
                )
            data = r.json()
            if not data.get("ok"):
                return self._fail(
                    "health_ok_false", "Health", "GET /api/health",
                    "Health endpoint returns ok=false",
                    Severity.HIGH,
                    "Server reports unhealthy state",
                    "ok: true",
                    f"ok: {data.get('ok')}",
                    r,
                )
            return self._pass("health_endpoint", "Health", f"model={data.get('model')}")
        await self._timed_test("health_endpoint", "Health", _run())

    async def _test_health_response_schema(self) -> None:
        async def _run():
            r = await self._req("GET", "/api/health")
            data = r.json()
            required_keys = ["ok", "version", "model", "scheduler_running",
                             "composio_configured", "pipedream_configured",
                             "cua_configured", "primitives_dir"]
            missing = [k for k in required_keys if k not in data]
            if missing:
                return self._fail(
                    "health_schema", "Health", "GET /api/health",
                    f"Health response missing keys: {missing}",
                    Severity.MEDIUM,
                    f"Health response is missing expected keys: {missing}",
                    f"Keys present: {required_keys}",
                    f"Missing: {missing}",
                    r,
                )
            return self._pass("health_schema", "Health")
        await self._timed_test("health_schema", "Health", _run())

    # -----------------------------------------------------------------------
    # 2. Experiments CRUD
    # -----------------------------------------------------------------------

    async def _test_list_experiments(self) -> None:
        async def _run():
            r = await self._req("GET", "/api/experiments")
            if r.status_code != 200:
                return self._fail(
                    "list_experiments", "Experiments", "GET /api/experiments",
                    "List experiments fails", Severity.HIGH,
                    f"Status {r.status_code}", "200 with experiments array", r.text[:200], r,
                )
            data = r.json()
            if "experiments" not in data:
                return self._fail(
                    "list_experiments", "Experiments", "GET /api/experiments",
                    "Missing 'experiments' key in response", Severity.HIGH,
                    "Missing key", "{ experiments: [...] }", json.dumps(list(data.keys())), r,
                )
            return self._pass("list_experiments", "Experiments", f"count={len(data['experiments'])}")
        await self._timed_test("list_experiments", "Experiments", _run())

    async def _test_create_experiment_valid(self) -> None:
        async def _run():
            body = {
                "name": "stress-test-exp",
                "description": "Created by stress test",
                "hypothesis": "Testing creates work",
            }
            r = await self._req("POST", "/api/experiments", json=body)
            if r.status_code not in (200, 201):
                return self._fail(
                    "create_experiment_valid", "Experiments", "POST /api/experiments",
                    "Create experiment fails with valid data", Severity.CRITICAL,
                    f"Status {r.status_code}", "200/201 with experiment", r.text[:200], r,
                )
            data = r.json()
            exp = data.get("experiment", {})
            if not exp.get("id"):
                return self._fail(
                    "create_experiment_valid", "Experiments", "POST /api/experiments",
                    "Created experiment has no ID", Severity.CRITICAL,
                    "Experiment should have an ID", "No ID in response",
                    json.dumps(exp)[:200], r,
                )
            self._created_experiment_ids.append(exp["id"])
            # Validate returned fields match input
            issues = []
            if exp.get("name") != "stress-test-exp":
                issues.append(f"name mismatch: {exp.get('name')}")
            if exp.get("description") != "Created by stress test":
                issues.append(f"description mismatch: {exp.get('description')}")
            if exp.get("phase") != "design":
                issues.append(f"default phase should be 'design', got '{exp.get('phase')}'")
            if issues:
                return self._fail(
                    "create_experiment_valid", "Experiments", "POST /api/experiments",
                    "Created experiment field mismatches",
                    Severity.MEDIUM,
                    "; ".join(issues),
                    "Fields match input + default phase=design",
                    "; ".join(issues), r,
                )
            return self._pass("create_experiment_valid", "Experiments", f"id={exp['id']}")
        await self._timed_test("create_experiment_valid", "Experiments", _run())

    async def _test_create_experiment_missing_name(self) -> None:
        async def _run():
            r = await self._req("POST", "/api/experiments", json={"description": "no name"})
            if r.status_code == 422:
                return self._pass("create_experiment_missing_name", "Experiments", "422 as expected")
            if r.status_code in (200, 201):
                return self._fail(
                    "create_experiment_missing_name", "Experiments", "POST /api/experiments",
                    "Server accepts experiment without required 'name' field",
                    Severity.HIGH,
                    "Name is required but server accepted without it",
                    "422 Validation Error",
                    f"{r.status_code}: {r.text[:200]}", r,
                )
            return self._pass("create_experiment_missing_name", "Experiments",
                              f"rejected with {r.status_code}")
        await self._timed_test("create_experiment_missing_name", "Experiments", _run())

    async def _test_create_experiment_empty_name(self) -> None:
        async def _run():
            r = await self._req("POST", "/api/experiments", json={"name": ""})
            if r.status_code in (200, 201):
                data = r.json()
                exp = data.get("experiment", {})
                if exp.get("name") == "":
                    return self._fail(
                        "create_experiment_empty_name", "Experiments", "POST /api/experiments",
                        "Server accepts experiment with empty name",
                        Severity.MEDIUM,
                        "Empty string name should be rejected or handled",
                        "422 or non-empty name enforcement",
                        f"Created experiment with empty name, id={exp.get('id')}", r,
                    )
            return self._pass("create_experiment_empty_name", "Experiments")
        await self._timed_test("create_experiment_empty_name", "Experiments", _run())

    async def _test_get_experiment_valid(self) -> None:
        async def _run():
            if not self._created_experiment_ids:
                return self._pass("get_experiment_valid", "Experiments", "skipped—no experiments")
            eid = self._created_experiment_ids[0]
            r = await self._req("GET", f"/api/experiments/{eid}")
            if r.status_code != 200:
                return self._fail(
                    "get_experiment_valid", "Experiments", f"GET /api/experiments/{eid}",
                    "Cannot fetch created experiment", Severity.HIGH,
                    f"Status {r.status_code}", "200 with experiment + runs", r.text[:200], r,
                )
            data = r.json()
            if "experiment" not in data or "runs" not in data:
                return self._fail(
                    "get_experiment_valid", "Experiments", f"GET /api/experiments/{eid}",
                    "Missing 'experiment' or 'runs' key", Severity.MEDIUM,
                    "Missing keys", "{ experiment: {...}, runs: [...] }",
                    json.dumps(list(data.keys())), r,
                )
            return self._pass("get_experiment_valid", "Experiments")
        await self._timed_test("get_experiment_valid", "Experiments", _run())

    async def _test_get_experiment_not_found(self) -> None:
        async def _run():
            r = await self._req("GET", "/api/experiments/nonexistent-id-12345")
            if r.status_code != 404:
                return self._fail(
                    "get_experiment_not_found", "Experiments",
                    "GET /api/experiments/nonexistent-id",
                    f"Expected 404 for missing experiment, got {r.status_code}",
                    Severity.MEDIUM,
                    "Fetching non-existent experiment should return 404",
                    "404 Not Found",
                    f"{r.status_code}: {r.text[:200]}", r,
                )
            return self._pass("get_experiment_not_found", "Experiments")
        await self._timed_test("get_experiment_not_found", "Experiments", _run())

    async def _test_update_experiment(self) -> None:
        async def _run():
            if not self._created_experiment_ids:
                return self._pass("update_experiment", "Experiments", "skipped")
            eid = self._created_experiment_ids[0]
            r = await self._req("PATCH", f"/api/experiments/{eid}",
                                json={"description": "updated by stress test"})
            if r.status_code != 200:
                return self._fail(
                    "update_experiment", "Experiments", f"PATCH /api/experiments/{eid}",
                    f"Update experiment fails: {r.status_code}", Severity.HIGH,
                    f"Status {r.status_code}", "200 with updated experiment", r.text[:200], r,
                )
            exp = r.json().get("experiment", {})
            if exp.get("description") != "updated by stress test":
                return self._fail(
                    "update_experiment", "Experiments", f"PATCH /api/experiments/{eid}",
                    "Update did not persist", Severity.HIGH,
                    "Description should be 'updated by stress test'",
                    "Field not updated",
                    f"description={exp.get('description')}", r,
                )
            return self._pass("update_experiment", "Experiments")
        await self._timed_test("update_experiment", "Experiments", _run())

    async def _test_update_experiment_not_found(self) -> None:
        async def _run():
            r = await self._req("PATCH", "/api/experiments/nonexistent-999",
                                json={"description": "ghost"})
            if r.status_code != 404:
                return self._fail(
                    "update_experiment_not_found", "Experiments",
                    "PATCH /api/experiments/nonexistent",
                    f"Expected 404, got {r.status_code}", Severity.MEDIUM,
                    "Updating non-existent experiment should 404",
                    "404", f"{r.status_code}", r,
                )
            return self._pass("update_experiment_not_found", "Experiments")
        await self._timed_test("update_experiment_not_found", "Experiments", _run())

    async def _test_pause_experiment(self) -> None:
        async def _run():
            if not self._created_experiment_ids:
                return self._pass("pause_experiment", "Experiments", "skipped")
            eid = self._created_experiment_ids[0]
            r = await self._req("POST", f"/api/experiments/{eid}/pause")
            if r.status_code != 200:
                return self._fail(
                    "pause_experiment", "Experiments", f"POST /api/experiments/{eid}/pause",
                    f"Pause fails: {r.status_code}", Severity.HIGH,
                    f"Status {r.status_code}", "200", r.text[:200], r,
                )
            exp = r.json().get("experiment", {})
            if exp.get("phase") != "paused":
                return self._fail(
                    "pause_experiment", "Experiments", f"POST /api/experiments/{eid}/pause",
                    "Phase not set to 'paused' after pause", Severity.HIGH,
                    "Pause should set phase='paused'",
                    "phase=paused", f"phase={exp.get('phase')}", r,
                )
            return self._pass("pause_experiment", "Experiments")
        await self._timed_test("pause_experiment", "Experiments", _run())

    async def _test_pause_already_paused(self) -> None:
        async def _run():
            if not self._created_experiment_ids:
                return self._pass("pause_already_paused", "Experiments", "skipped")
            eid = self._created_experiment_ids[0]
            r = await self._req("POST", f"/api/experiments/{eid}/pause")
            # Should succeed idempotently or return appropriate error
            if r.status_code == 200:
                return self._pass("pause_already_paused", "Experiments", "idempotent pause OK")
            if r.status_code >= 500:
                return self._fail(
                    "pause_already_paused", "Experiments",
                    f"POST /api/experiments/{eid}/pause",
                    "Server error when pausing already-paused experiment",
                    Severity.MEDIUM,
                    "Double-pause should be idempotent or return 4xx",
                    "200 or 4xx", f"{r.status_code}", r,
                )
            return self._pass("pause_already_paused", "Experiments", f"status={r.status_code}")
        await self._timed_test("pause_already_paused", "Experiments", _run())

    async def _test_resume_experiment(self) -> None:
        async def _run():
            if not self._created_experiment_ids:
                return self._pass("resume_experiment", "Experiments", "skipped")
            eid = self._created_experiment_ids[0]
            r = await self._req("POST", f"/api/experiments/{eid}/resume?target_phase=design")
            if r.status_code != 200:
                return self._fail(
                    "resume_experiment", "Experiments", f"POST /api/experiments/{eid}/resume",
                    f"Resume fails: {r.status_code}", Severity.HIGH,
                    f"Status {r.status_code}", "200", r.text[:200], r,
                )
            exp = r.json().get("experiment", {})
            if exp.get("phase") != "design":
                return self._fail(
                    "resume_experiment", "Experiments", f"POST /api/experiments/{eid}/resume",
                    "Phase not set to target after resume", Severity.HIGH,
                    "Resume to 'design' should set phase='design'",
                    "phase=design", f"phase={exp.get('phase')}", r,
                )
            return self._pass("resume_experiment", "Experiments")
        await self._timed_test("resume_experiment", "Experiments", _run())

    async def _test_resume_not_found(self) -> None:
        async def _run():
            r = await self._req("POST", "/api/experiments/ghost-id-999/resume")
            if r.status_code != 404:
                return self._fail(
                    "resume_not_found", "Experiments", "POST /api/experiments/ghost/resume",
                    f"Expected 404, got {r.status_code}", Severity.MEDIUM,
                    "Resuming non-existent experiment should 404",
                    "404", f"{r.status_code}", r,
                )
            return self._pass("resume_not_found", "Experiments")
        await self._timed_test("resume_not_found", "Experiments", _run())

    async def _test_run_tick(self) -> None:
        async def _run():
            if not self._created_experiment_ids:
                return self._pass("run_tick", "Experiments", "skipped")
            eid = self._created_experiment_ids[0]
            r = await self._req("POST", f"/api/experiments/{eid}/run-tick")
            if r.status_code == 200:
                data = r.json()
                if "ok" not in data:
                    return self._fail(
                        "run_tick", "Experiments", f"POST /api/experiments/{eid}/run-tick",
                        "run-tick response missing 'ok' field", Severity.MEDIUM,
                        "Response should include 'ok' boolean",
                        "{ ok: bool, ... }", json.dumps(list(data.keys())), r,
                    )
                return self._pass("run_tick", "Experiments",
                                  f"ok={data.get('ok')}, phase={data.get('phase')}")
            if r.status_code >= 500:
                return self._fail(
                    "run_tick", "Experiments", f"POST /api/experiments/{eid}/run-tick",
                    f"run-tick server error: {r.status_code}", Severity.HIGH,
                    "run-tick should not crash the server",
                    "200", f"{r.status_code}: {r.text[:200]}", r,
                )
            return self._pass("run_tick", "Experiments", f"status={r.status_code}")
        await self._timed_test("run_tick", "Experiments", _run())

    async def _test_schedule_experiment(self) -> None:
        async def _run():
            if not self._created_experiment_ids:
                return self._pass("schedule_experiment", "Experiments", "skipped")
            eid = self._created_experiment_ids[0]
            r = await self._req("POST", f"/api/experiments/{eid}/schedule",
                                json={"interval_seconds": 3600})
            if r.status_code == 200:
                return self._pass("schedule_experiment", "Experiments")
            if r.status_code >= 500:
                return self._fail(
                    "schedule_experiment", "Experiments",
                    f"POST /api/experiments/{eid}/schedule",
                    f"Schedule endpoint server error: {r.status_code}", Severity.HIGH,
                    "Scheduling should not crash", "200", f"{r.status_code}: {r.text[:200]}", r,
                )
            return self._pass("schedule_experiment", "Experiments", f"status={r.status_code}")
        await self._timed_test("schedule_experiment", "Experiments", _run())

    async def _test_schedule_invalid_cron(self) -> None:
        async def _run():
            if not self._created_experiment_ids:
                return self._pass("schedule_invalid_cron", "Experiments", "skipped")
            eid = self._created_experiment_ids[0]
            r = await self._req("POST", f"/api/experiments/{eid}/schedule",
                                json={"cron_expr": "not a cron expression"})
            if r.status_code >= 500:
                return self._fail(
                    "schedule_invalid_cron", "Experiments",
                    f"POST /api/experiments/{eid}/schedule",
                    "Invalid cron expression causes server error",
                    Severity.HIGH,
                    "Invalid cron should return 4xx, not crash",
                    "400/422", f"{r.status_code}: {r.text[:200]}", r,
                )
            return self._pass("schedule_invalid_cron", "Experiments", f"status={r.status_code}")
        await self._timed_test("schedule_invalid_cron", "Experiments", _run())

    async def _test_experiment_concurrent_creates(self) -> None:
        async def _run():
            bodies = [{"name": f"concurrent-{i}"} for i in range(10)]
            tasks = [self._req("POST", "/api/experiments", json=b) for b in bodies]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            errors = [r for r in responses if isinstance(r, Exception)]
            server_errors = [r for r in responses
                            if isinstance(r, httpx.Response) and r.status_code >= 500]
            if errors:
                return self._fail(
                    "concurrent_creates", "Experiments", "POST /api/experiments (x10)",
                    f"{len(errors)} exceptions during concurrent creates",
                    Severity.HIGH,
                    "Concurrent creates should not raise exceptions",
                    "All 200s", f"{len(errors)} exceptions", None,
                )
            if server_errors:
                return self._fail(
                    "concurrent_creates", "Experiments", "POST /api/experiments (x10)",
                    f"{len(server_errors)} server errors during concurrent creates",
                    Severity.HIGH,
                    "Concurrent creates should not cause 500s",
                    "All 200s", f"{len(server_errors)} 5xx errors", server_errors[0],
                )
            ok_count = sum(1 for r in responses
                          if isinstance(r, httpx.Response) and r.status_code in (200, 201))
            return self._pass("concurrent_creates", "Experiments", f"{ok_count}/10 succeeded")
        await self._timed_test("concurrent_creates", "Experiments", _run())

    # -----------------------------------------------------------------------
    # 3. Memory
    # -----------------------------------------------------------------------

    async def _test_list_memory(self) -> None:
        async def _run():
            r = await self._req("GET", "/api/memory")
            if r.status_code != 200:
                return self._fail(
                    "list_memory", "Memory", "GET /api/memory",
                    f"List memory fails: {r.status_code}", Severity.HIGH,
                    f"Status {r.status_code}", "200", r.text[:200], r,
                )
            data = r.json()
            if "memories" not in data:
                return self._fail(
                    "list_memory", "Memory", "GET /api/memory",
                    "Missing 'memories' key", Severity.HIGH,
                    "Missing key", "{ memories: [...] }", json.dumps(list(data.keys())), r,
                )
            return self._pass("list_memory", "Memory", f"count={len(data['memories'])}")
        await self._timed_test("list_memory", "Memory", _run())

    async def _test_list_memory_filter(self) -> None:
        async def _run():
            r = await self._req("GET", "/api/memory?type_filter=learning")
            if r.status_code != 200:
                return self._fail(
                    "list_memory_filter", "Memory", "GET /api/memory?type_filter=learning",
                    f"Memory filter fails: {r.status_code}", Severity.MEDIUM,
                    f"Status {r.status_code}", "200", r.text[:200], r,
                )
            return self._pass("list_memory_filter", "Memory")
        await self._timed_test("list_memory_filter", "Memory", _run())

    async def _test_search_memory(self) -> None:
        async def _run():
            r = await self._req("POST", "/api/memory/search",
                                json={"query": "test query", "limit": 5})
            if r.status_code != 200:
                return self._fail(
                    "search_memory", "Memory", "POST /api/memory/search",
                    f"Memory search fails: {r.status_code}", Severity.HIGH,
                    f"Status {r.status_code}", "200", r.text[:200], r,
                )
            data = r.json()
            if "results" not in data:
                return self._fail(
                    "search_memory", "Memory", "POST /api/memory/search",
                    "Missing 'results' key", Severity.MEDIUM,
                    "Missing key", "{ results: [...] }", json.dumps(list(data.keys())), r,
                )
            return self._pass("search_memory", "Memory", f"results={len(data['results'])}")
        await self._timed_test("search_memory", "Memory", _run())

    async def _test_search_memory_empty_query(self) -> None:
        async def _run():
            r = await self._req("POST", "/api/memory/search",
                                json={"query": "", "limit": 5})
            if r.status_code >= 500:
                return self._fail(
                    "search_memory_empty", "Memory", "POST /api/memory/search",
                    "Empty query causes server error", Severity.MEDIUM,
                    "Empty query should be handled gracefully",
                    "200 or 422", f"{r.status_code}: {r.text[:200]}", r,
                )
            return self._pass("search_memory_empty", "Memory", f"status={r.status_code}")
        await self._timed_test("search_memory_empty", "Memory", _run())

    async def _test_primitives(self) -> None:
        async def _run():
            r = await self._req("GET", "/api/primitives")
            if r.status_code != 200:
                return self._fail(
                    "primitives", "Memory", "GET /api/primitives",
                    f"Primitives fails: {r.status_code}", Severity.HIGH,
                    f"Status {r.status_code}", "200", r.text[:200], r,
                )
            data = r.json()
            expected_keys = ["agents", "plays", "plays_meta", "phase_rules",
                             "channel_rules", "brand_loaded", "schedules"]
            missing = [k for k in expected_keys if k not in data]
            if missing:
                return self._fail(
                    "primitives", "Memory", "GET /api/primitives",
                    f"Primitives response missing: {missing}", Severity.MEDIUM,
                    f"Missing keys: {missing}", f"All of: {expected_keys}",
                    f"Present: {list(data.keys())}", r,
                )
            return self._pass("primitives", "Memory",
                              f"agents={len(data.get('agents', []))}, plays={len(data.get('plays', []))}")
        await self._timed_test("primitives", "Memory", _run())

    # -----------------------------------------------------------------------
    # 4. Chat & SSE
    # -----------------------------------------------------------------------

    async def _test_chat_basic(self) -> None:
        async def _run():
            r = await self._req("POST", "/api/chat",
                                json={"message": "hello", "agent": "orchestrator"},
                                headers={"Accept": "text/event-stream"})
            if r.status_code != 200:
                return self._fail(
                    "chat_basic", "Chat", "POST /api/chat",
                    f"Chat endpoint fails: {r.status_code}", Severity.CRITICAL,
                    f"Status {r.status_code}", "200 SSE stream", r.text[:300], r,
                )
            body = r.text
            # SSE should have events
            if "event:" not in body and "data:" not in body:
                return self._fail(
                    "chat_basic", "Chat", "POST /api/chat",
                    "Chat response is not SSE format", Severity.HIGH,
                    "Response should be SSE with event:/data: lines",
                    "SSE stream with events",
                    f"Body starts with: {body[:200]}", r,
                )
            # Check for error event — distinguish auth errors from real bugs
            if 'event: error' in body:
                if 'AuthenticationError' in body or 'invalid x-api-key' in body or 'invalid api key' in body.lower():
                    return self._fail(
                        "chat_basic", "Chat", "POST /api/chat",
                        "Chat fails due to missing/invalid API key",
                        Severity.INFO,
                        "No valid LLM API key configured — expected in test env without keys. "
                        "Error is properly surfaced via SSE error event (not a silent hang).",
                        "SSE stream with token events (requires valid API key)",
                        f"Auth error in response (expected without key): {body[:200]}", r,
                    )
                return self._fail(
                    "chat_basic", "Chat", "POST /api/chat",
                    "Chat returns unexpected error event", Severity.HIGH,
                    "Chat should return meta/token/final events on success",
                    "No error events",
                    f"Error in response: {body[:300]}", r,
                )
            return self._pass("chat_basic", "Chat", f"response_len={len(body)}")
        await self._timed_test("chat_basic", "Chat", _run())

    async def _test_chat_empty_message(self) -> None:
        async def _run():
            r = await self._req("POST", "/api/chat",
                                json={"message": "", "agent": "orchestrator"})
            if r.status_code >= 500:
                return self._fail(
                    "chat_empty_message", "Chat", "POST /api/chat",
                    "Empty message causes server error", Severity.HIGH,
                    "Empty message should be rejected with 4xx or handled gracefully",
                    "4xx or graceful handling", f"{r.status_code}: {r.text[:200]}", r,
                )
            return self._pass("chat_empty_message", "Chat", f"status={r.status_code}")
        await self._timed_test("chat_empty_message", "Chat", _run())

    async def _test_chat_invalid_agent(self) -> None:
        async def _run():
            r = await self._req("POST", "/api/chat",
                                json={"message": "hi", "agent": "nonexistent_agent_xyz"})
            if r.status_code >= 500:
                return self._fail(
                    "chat_invalid_agent", "Chat", "POST /api/chat",
                    "Invalid agent name causes server error", Severity.HIGH,
                    "Invalid agent should be rejected or default to orchestrator",
                    "4xx or fallback", f"{r.status_code}: {r.text[:200]}", r,
                )
            return self._pass("chat_invalid_agent", "Chat", f"status={r.status_code}")
        await self._timed_test("chat_invalid_agent", "Chat", _run())

    async def _test_chat_long_message(self) -> None:
        async def _run():
            long_msg = "A" * 50_000
            r = await self._req("POST", "/api/chat",
                                json={"message": long_msg, "agent": "orchestrator"})
            if r.status_code >= 500:
                return self._fail(
                    "chat_long_message", "Chat", "POST /api/chat",
                    "Very long message (50k chars) causes server error", Severity.MEDIUM,
                    "Long messages should be handled (truncated or rejected)",
                    "4xx or graceful handling", f"{r.status_code}", r,
                )
            return self._pass("chat_long_message", "Chat", f"status={r.status_code}")
        await self._timed_test("chat_long_message", "Chat", _run())

    async def _test_chat_special_characters(self) -> None:
        async def _run():
            msg = 'Hello <script>alert("xss")</script> "quotes" \'single\' \n\t\0 emoji: 🔥'
            r = await self._req("POST", "/api/chat",
                                json={"message": msg, "agent": "orchestrator"})
            if r.status_code >= 500:
                return self._fail(
                    "chat_special_chars", "Chat", "POST /api/chat",
                    "Special characters in message cause server error", Severity.HIGH,
                    "Special chars should be handled safely",
                    "200 or 4xx", f"{r.status_code}: {r.text[:200]}", r,
                )
            return self._pass("chat_special_chars", "Chat", f"status={r.status_code}")
        await self._timed_test("chat_special_chars", "Chat", _run())

    async def _test_thread_messages(self) -> None:
        async def _run():
            r = await self._req("GET", "/api/threads/test-thread-123/messages")
            if r.status_code == 200:
                data = r.json()
                if "messages" not in data:
                    return self._fail(
                        "thread_messages", "Chat", "GET /api/threads/{id}/messages",
                        "Missing 'messages' key", Severity.MEDIUM,
                        "Missing key", "{ thread_id, messages }", json.dumps(list(data.keys())), r,
                    )
                return self._pass("thread_messages", "Chat")
            if r.status_code == 404:
                return self._pass("thread_messages", "Chat", "404 for empty thread is OK")
            if r.status_code >= 500:
                return self._fail(
                    "thread_messages", "Chat", "GET /api/threads/{id}/messages",
                    f"Server error: {r.status_code}", Severity.HIGH,
                    "Should return 200 or 404", "200/404", f"{r.status_code}", r,
                )
            return self._pass("thread_messages", "Chat", f"status={r.status_code}")
        await self._timed_test("thread_messages", "Chat", _run())

    async def _test_thread_messages_not_found(self) -> None:
        async def _run():
            r = await self._req("GET", "/api/threads/definitely-not-real/messages")
            if r.status_code >= 500:
                return self._fail(
                    "thread_not_found", "Chat", "GET /api/threads/{id}/messages",
                    "Non-existent thread causes server error", Severity.MEDIUM,
                    "Should return empty list or 404",
                    "200 (empty) or 404", f"{r.status_code}", r,
                )
            return self._pass("thread_not_found", "Chat", f"status={r.status_code}")
        await self._timed_test("thread_not_found", "Chat", _run())

    # -----------------------------------------------------------------------
    # 5. Trust & Proposals
    # -----------------------------------------------------------------------

    async def _test_list_trust_scores(self) -> None:
        async def _run():
            r = await self._req("GET", "/api/trust-scores")
            if r.status_code != 200:
                return self._fail(
                    "list_trust_scores", "Trust", "GET /api/trust-scores",
                    f"Trust scores fails: {r.status_code}", Severity.HIGH,
                    f"Status {r.status_code}", "200", r.text[:200], r,
                )
            return self._pass("list_trust_scores", "Trust")
        await self._timed_test("list_trust_scores", "Trust", _run())

    async def _test_get_trust_score(self) -> None:
        async def _run():
            r = await self._req("GET", "/api/trust-scores/email")
            if r.status_code == 200:
                return self._pass("get_trust_score", "Trust")
            if r.status_code == 404:
                return self._pass("get_trust_score", "Trust", "404 expected if no email experiments")
            if r.status_code >= 500:
                return self._fail(
                    "get_trust_score", "Trust", "GET /api/trust-scores/email",
                    f"Server error: {r.status_code}", Severity.MEDIUM,
                    "Should return 200 or 404", "200/404", f"{r.status_code}", r,
                )
            return self._pass("get_trust_score", "Trust", f"status={r.status_code}")
        await self._timed_test("get_trust_score", "Trust", _run())

    async def _test_get_trust_score_not_found(self) -> None:
        async def _run():
            r = await self._req("GET", "/api/trust-scores/nonexistent_type_xyz")
            if r.status_code >= 500:
                return self._fail(
                    "trust_score_not_found", "Trust",
                    "GET /api/trust-scores/nonexistent",
                    "Non-existent trust score type causes server error", Severity.MEDIUM,
                    "Should return 404 or empty", "404/200", f"{r.status_code}", r,
                )
            return self._pass("trust_score_not_found", "Trust", f"status={r.status_code}")
        await self._timed_test("trust_score_not_found", "Trust", _run())

    async def _test_list_proposed(self) -> None:
        async def _run():
            r = await self._req("GET", "/api/proposed-experiments")
            if r.status_code != 200:
                return self._fail(
                    "list_proposed", "Trust", "GET /api/proposed-experiments",
                    f"Status {r.status_code}", Severity.HIGH,
                    "Should return 200", "200", f"{r.status_code}", r,
                )
            return self._pass("list_proposed", "Trust")
        await self._timed_test("list_proposed", "Trust", _run())

    async def _test_list_proposed_filter(self) -> None:
        async def _run():
            r = await self._req("GET", "/api/proposed-experiments?status=pending")
            if r.status_code != 200:
                return self._fail(
                    "list_proposed_filter", "Trust",
                    "GET /api/proposed-experiments?status=pending",
                    f"Status {r.status_code}", Severity.MEDIUM,
                    "Should filter by status", "200", f"{r.status_code}", r,
                )
            return self._pass("list_proposed_filter", "Trust")
        await self._timed_test("list_proposed_filter", "Trust", _run())

    async def _test_review_proposal_not_found(self) -> None:
        async def _run():
            r = await self._req("POST", "/api/proposed-experiments/ghost-id/review",
                                json={"approved": True})
            if r.status_code >= 500:
                return self._fail(
                    "review_proposal_not_found", "Trust",
                    "POST /api/proposed-experiments/{id}/review",
                    "Non-existent proposal causes server error", Severity.MEDIUM,
                    "Should return 404", "404", f"{r.status_code}: {r.text[:200]}", r,
                )
            return self._pass("review_proposal_not_found", "Trust", f"status={r.status_code}")
        await self._timed_test("review_proposal_not_found", "Trust", _run())

    async def _test_simulate_not_found(self) -> None:
        async def _run():
            r = await self._req("POST", "/api/experiments/ghost-id/simulate")
            if r.status_code >= 500:
                return self._fail(
                    "simulate_not_found", "Trust",
                    "POST /api/experiments/{id}/simulate",
                    "Simulating non-existent experiment causes server error",
                    Severity.MEDIUM,
                    "Should return 404", "404", f"{r.status_code}", r,
                )
            return self._pass("simulate_not_found", "Trust", f"status={r.status_code}")
        await self._timed_test("simulate_not_found", "Trust", _run())

    async def _test_approve_not_found(self) -> None:
        async def _run():
            r = await self._req("POST", "/api/experiments/ghost-id/approve",
                                json={"feedback": "test"})
            if r.status_code >= 500:
                return self._fail(
                    "approve_not_found", "Trust",
                    "POST /api/experiments/{id}/approve",
                    "Approving non-existent experiment causes server error",
                    Severity.MEDIUM,
                    "Should return 404", "404", f"{r.status_code}", r,
                )
            return self._pass("approve_not_found", "Trust", f"status={r.status_code}")
        await self._timed_test("approve_not_found", "Trust", _run())

    # -----------------------------------------------------------------------
    # 6. Templates
    # -----------------------------------------------------------------------

    async def _test_list_templates(self) -> None:
        async def _run():
            r = await self._req("GET", "/api/templates")
            if r.status_code != 200:
                return self._fail(
                    "list_templates", "Templates", "GET /api/templates",
                    f"Status {r.status_code}", Severity.HIGH,
                    "Should return 200", "200", f"{r.status_code}", r,
                )
            return self._pass("list_templates", "Templates")
        await self._timed_test("list_templates", "Templates", _run())

    async def _test_create_template(self) -> None:
        async def _run():
            body = {
                "name": "stress-test-template",
                "description": "Created by stress test",
                "play_ids": [],
                "hypothesis_pattern": "If we {action} then {outcome}",
                "token_budget": 100000,
            }
            r = await self._req("POST", "/api/templates", json=body)
            if r.status_code not in (200, 201):
                return self._fail(
                    "create_template", "Templates", "POST /api/templates",
                    f"Create template fails: {r.status_code}", Severity.HIGH,
                    f"Status {r.status_code}", "200/201", r.text[:200], r,
                )
            data = r.json()
            # API returns {ok, template_id} not {template: {id}}
            tid = data.get("template_id") or data.get("template", {}).get("id")
            if tid:
                self._created_template_ids.append(tid)
            return self._pass("create_template", "Templates", f"id={tid}")
        await self._timed_test("create_template", "Templates", _run())

    async def _test_get_template(self) -> None:
        async def _run():
            if not self._created_template_ids:
                return self._pass("get_template", "Templates", "skipped")
            tid = self._created_template_ids[0]
            r = await self._req("GET", f"/api/templates/{tid}")
            if r.status_code != 200:
                return self._fail(
                    "get_template", "Templates", f"GET /api/templates/{tid}",
                    f"Get template fails: {r.status_code}", Severity.HIGH,
                    f"Status {r.status_code}", "200", r.text[:200], r,
                )
            return self._pass("get_template", "Templates")
        await self._timed_test("get_template", "Templates", _run())

    async def _test_get_template_not_found(self) -> None:
        async def _run():
            r = await self._req("GET", "/api/templates/nonexistent-tmpl-id")
            if r.status_code != 404:
                if r.status_code >= 500:
                    return self._fail(
                        "get_template_not_found", "Templates",
                        "GET /api/templates/nonexistent",
                        "Non-existent template causes server error", Severity.MEDIUM,
                        "Should 404", "404", f"{r.status_code}", r,
                    )
            return self._pass("get_template_not_found", "Templates", f"status={r.status_code}")
        await self._timed_test("get_template_not_found", "Templates", _run())

    async def _test_create_from_template(self) -> None:
        async def _run():
            if not self._created_template_ids:
                return self._pass("create_from_template", "Templates", "skipped")
            tid = self._created_template_ids[0]
            r = await self._req("POST", f"/api/templates/{tid}/create-experiment",
                                json={"name": "from-stress-template"})
            if r.status_code not in (200, 201):
                return self._fail(
                    "create_from_template", "Templates",
                    f"POST /api/templates/{tid}/create-experiment",
                    f"Create from template fails: {r.status_code}", Severity.HIGH,
                    f"Status {r.status_code}", "200/201", r.text[:200], r,
                )
            return self._pass("create_from_template", "Templates")
        await self._timed_test("create_from_template", "Templates", _run())

    # -----------------------------------------------------------------------
    # 7. Metrics
    # -----------------------------------------------------------------------

    async def _test_save_metric(self) -> None:
        async def _run():
            if not self._created_experiment_ids:
                return self._pass("save_metric", "Metrics", "skipped")
            eid = self._created_experiment_ids[0]
            body = {"metric_name": "open_rate", "metric_value": 0.42, "variant": "A"}
            r = await self._req("POST", f"/api/experiments/{eid}/metrics", json=body)
            if r.status_code not in (200, 201):
                return self._fail(
                    "save_metric", "Metrics", f"POST /api/experiments/{eid}/metrics",
                    f"Save metric fails: {r.status_code}", Severity.HIGH,
                    f"Status {r.status_code}", "200/201", r.text[:200], r,
                )
            return self._pass("save_metric", "Metrics")
        await self._timed_test("save_metric", "Metrics", _run())

    async def _test_list_metrics(self) -> None:
        async def _run():
            if not self._created_experiment_ids:
                return self._pass("list_metrics", "Metrics", "skipped")
            eid = self._created_experiment_ids[0]
            r = await self._req("GET", f"/api/experiments/{eid}/metrics")
            if r.status_code != 200:
                return self._fail(
                    "list_metrics", "Metrics", f"GET /api/experiments/{eid}/metrics",
                    f"List metrics fails: {r.status_code}", Severity.HIGH,
                    f"Status {r.status_code}", "200", r.text[:200], r,
                )
            return self._pass("list_metrics", "Metrics")
        await self._timed_test("list_metrics", "Metrics", _run())

    async def _test_metric_summary(self) -> None:
        async def _run():
            if not self._created_experiment_ids:
                return self._pass("metric_summary", "Metrics", "skipped")
            eid = self._created_experiment_ids[0]
            r = await self._req("GET", f"/api/experiments/{eid}/metrics/summary")
            if r.status_code != 200:
                return self._fail(
                    "metric_summary", "Metrics",
                    f"GET /api/experiments/{eid}/metrics/summary",
                    f"Metric summary fails: {r.status_code}", Severity.HIGH,
                    f"Status {r.status_code}", "200", r.text[:200], r,
                )
            return self._pass("metric_summary", "Metrics")
        await self._timed_test("metric_summary", "Metrics", _run())

    async def _test_save_metric_invalid_experiment(self) -> None:
        async def _run():
            body = {"metric_name": "ctr", "metric_value": 0.1}
            r = await self._req("POST", "/api/experiments/nonexistent-id/metrics", json=body)
            if r.status_code >= 500:
                return self._fail(
                    "save_metric_invalid_exp", "Metrics",
                    "POST /api/experiments/nonexistent/metrics",
                    "Saving metric for non-existent experiment causes server error",
                    Severity.MEDIUM,
                    "Should return 404 or reject", "404", f"{r.status_code}", r,
                )
            return self._pass("save_metric_invalid_exp", "Metrics", f"status={r.status_code}")
        await self._timed_test("save_metric_invalid_exp", "Metrics", _run())

    # -----------------------------------------------------------------------
    # 8. Integrations
    # -----------------------------------------------------------------------

    async def _test_get_integrations(self) -> None:
        async def _run():
            r = await self._req("GET", "/api/integrations")
            if r.status_code != 200:
                return self._fail(
                    "get_integrations", "Integrations", "GET /api/integrations",
                    f"Status {r.status_code}", Severity.HIGH,
                    "Should return 200", "200", f"{r.status_code}", r,
                )
            data = r.json()
            if "integrations" not in data:
                return self._fail(
                    "get_integrations", "Integrations", "GET /api/integrations",
                    "Missing 'integrations' key", Severity.MEDIUM,
                    "Missing key", "{ integrations: [...] }", json.dumps(list(data.keys())), r,
                )
            return self._pass("get_integrations", "Integrations",
                              f"count={len(data['integrations'])}")
        await self._timed_test("get_integrations", "Integrations", _run())

    async def _test_get_tool_keys(self) -> None:
        async def _run():
            r = await self._req("GET", "/api/integrations/tool-keys")
            if r.status_code != 200:
                return self._fail(
                    "get_tool_keys", "Integrations", "GET /api/integrations/tool-keys",
                    f"Status {r.status_code}", Severity.HIGH,
                    "Should return 200", "200", f"{r.status_code}", r,
                )
            return self._pass("get_tool_keys", "Integrations")
        await self._timed_test("get_tool_keys", "Integrations", _run())

    async def _test_get_model_keys(self) -> None:
        async def _run():
            r = await self._req("GET", "/api/integrations/model-keys")
            if r.status_code != 200:
                return self._fail(
                    "get_model_keys", "Integrations", "GET /api/integrations/model-keys",
                    f"Status {r.status_code}", Severity.HIGH,
                    "Should return 200", "200", f"{r.status_code}", r,
                )
            data = r.json()
            expected = ["providers", "available_models", "current_model",
                        "current_temperature", "current_max_tokens"]
            missing = [k for k in expected if k not in data]
            if missing:
                return self._fail(
                    "get_model_keys", "Integrations", "GET /api/integrations/model-keys",
                    f"Missing keys: {missing}", Severity.MEDIUM,
                    f"Missing: {missing}", f"All of: {expected}",
                    f"Present: {list(data.keys())}", r,
                )
            return self._pass("get_model_keys", "Integrations",
                              f"model={data.get('current_model')}")
        await self._timed_test("get_model_keys", "Integrations", _run())

    async def _test_update_model_config(self) -> None:
        async def _run():
            # Read current config first
            r1 = await self._req("GET", "/api/integrations/model-keys")
            if r1.status_code != 200:
                return self._pass("update_model_config", "Integrations", "skipped—can't read config")
            current_temp = r1.json().get("current_temperature", 0.4)
            # Set and then restore
            r = await self._req("PUT", "/api/integrations/model-config",
                                json={"temperature": 0.5})
            if r.status_code != 200:
                return self._fail(
                    "update_model_config", "Integrations",
                    "PUT /api/integrations/model-config",
                    f"Update model config fails: {r.status_code}", Severity.HIGH,
                    f"Status {r.status_code}", "200", r.text[:200], r,
                )
            # Restore
            await self._req("PUT", "/api/integrations/model-config",
                            json={"temperature": current_temp})
            return self._pass("update_model_config", "Integrations")
        await self._timed_test("update_model_config", "Integrations", _run())

    async def _test_list_apps(self) -> None:
        async def _run():
            r = await self._req("GET", "/api/integrations/apps")
            if r.status_code != 200:
                # May fail if Composio not configured — that's OK
                if r.status_code >= 500:
                    return self._fail(
                        "list_apps", "Integrations", "GET /api/integrations/apps",
                        f"Server error: {r.status_code}", Severity.MEDIUM,
                        "Should handle missing Composio gracefully",
                        "200 or 4xx", f"{r.status_code}", r,
                    )
            return self._pass("list_apps", "Integrations", f"status={r.status_code}")
        await self._timed_test("list_apps", "Integrations", _run())

    async def _test_list_connections(self) -> None:
        async def _run():
            r = await self._req("GET", "/api/integrations/connections")
            if r.status_code >= 500:
                return self._fail(
                    "list_connections", "Integrations", "GET /api/integrations/connections",
                    f"Server error: {r.status_code}", Severity.MEDIUM,
                    "Should handle gracefully", "200 or 4xx", f"{r.status_code}", r,
                )
            return self._pass("list_connections", "Integrations", f"status={r.status_code}")
        await self._timed_test("list_connections", "Integrations", _run())

    # -----------------------------------------------------------------------
    # 9. Brand
    # -----------------------------------------------------------------------

    async def _test_get_brand(self) -> None:
        async def _run():
            r = await self._req("GET", "/api/brand")
            if r.status_code != 200:
                return self._fail(
                    "get_brand", "Brand", "GET /api/brand",
                    f"Status {r.status_code}", Severity.HIGH,
                    "Should return 200", "200", f"{r.status_code}", r,
                )
            return self._pass("get_brand", "Brand")
        await self._timed_test("get_brand", "Brand", _run())

    async def _test_update_brand(self) -> None:
        async def _run():
            body = {
                "company_name": "Stress Test Corp",
                "tagline": "Testing all the things",
                "website": "https://test.example.com",
                "product_description": "A stress testing product",
                "social": {"twitter": "https://x.com/test"},
                "icp": "Test engineers",
                "icp_negative": "Nobody",
                "voice": ["professional", "direct"],
                "avoid": ["jargon"],
                "prefer": ["clarity"],
                "email_max_sentences": 5,
                "email_max_words": 100,
            }
            r = await self._req("PUT", "/api/brand", json=body)
            if r.status_code != 200:
                return self._fail(
                    "update_brand", "Brand", "PUT /api/brand",
                    f"Update brand fails: {r.status_code}", Severity.HIGH,
                    f"Status {r.status_code}", "200", r.text[:200], r,
                )
            # Verify persistence
            r2 = await self._req("GET", "/api/brand")
            data = r2.json()
            if data.get("company_name") != "Stress Test Corp":
                return self._fail(
                    "update_brand", "Brand", "PUT /api/brand",
                    "Brand update did not persist", Severity.HIGH,
                    "company_name should persist after PUT",
                    "Stress Test Corp", f"{data.get('company_name')}", r2,
                )
            return self._pass("update_brand", "Brand")
        await self._timed_test("update_brand", "Brand", _run())

    async def _test_update_brand_partial(self) -> None:
        async def _run():
            # Send partial update — missing required fields
            r = await self._req("PUT", "/api/brand", json={"company_name": "Partial"})
            if r.status_code >= 500:
                return self._fail(
                    "update_brand_partial", "Brand", "PUT /api/brand",
                    "Partial brand update causes server error", Severity.MEDIUM,
                    "Partial updates should be handled gracefully",
                    "422 or graceful handling", f"{r.status_code}: {r.text[:200]}", r,
                )
            return self._pass("update_brand_partial", "Brand", f"status={r.status_code}")
        await self._timed_test("update_brand_partial", "Brand", _run())

    # -----------------------------------------------------------------------
    # Edge Cases & Stress
    # -----------------------------------------------------------------------

    async def _test_404_unknown_route(self) -> None:
        async def _run():
            r = await self._req("GET", "/api/totally-fake-route")
            # FastAPI catchall might serve index.html for non-API routes
            # but /api/ prefix should 404 or fall through
            return self._pass("404_unknown_route", "Edge Cases", f"status={r.status_code}")
        await self._timed_test("404_unknown_route", "Edge Cases", _run())

    async def _test_method_not_allowed(self) -> None:
        async def _run():
            r = await self._req("DELETE", "/api/health")
            if r.status_code == 405:
                return self._pass("method_not_allowed", "Edge Cases", "405 as expected")
            if r.status_code >= 500:
                return self._fail(
                    "method_not_allowed", "Edge Cases", "DELETE /api/health",
                    "Wrong method causes server error", Severity.LOW,
                    "Should return 405", "405", f"{r.status_code}", r,
                )
            return self._pass("method_not_allowed", "Edge Cases", f"status={r.status_code}")
        await self._timed_test("method_not_allowed", "Edge Cases", _run())

    async def _test_malformed_json(self) -> None:
        async def _run():
            r = await self._req("POST", "/api/experiments",
                                content=b"{not valid json!!!",
                                headers={"Content-Type": "application/json"})
            if r.status_code >= 500:
                return self._fail(
                    "malformed_json", "Edge Cases", "POST /api/experiments",
                    "Malformed JSON causes server error", Severity.HIGH,
                    "Should return 422 or 400", "4xx", f"{r.status_code}: {r.text[:200]}", r,
                )
            return self._pass("malformed_json", "Edge Cases", f"status={r.status_code}")
        await self._timed_test("malformed_json", "Edge Cases", _run())

    async def _test_huge_payload(self) -> None:
        async def _run():
            huge = {"name": "A" * 1_000_000}
            try:
                r = await self._req("POST", "/api/experiments", json=huge)
                if r.status_code >= 500:
                    return self._fail(
                        "huge_payload", "Edge Cases", "POST /api/experiments",
                        "1MB name causes server error", Severity.MEDIUM,
                        "Should handle large payloads gracefully",
                        "4xx or truncation", f"{r.status_code}", r,
                    )
                return self._pass("huge_payload", "Edge Cases", f"status={r.status_code}")
            except Exception as e:
                return self._pass("huge_payload", "Edge Cases", f"rejected: {type(e).__name__}")
        await self._timed_test("huge_payload", "Edge Cases", _run())

    async def _test_sql_injection_attempt(self) -> None:
        async def _run():
            # Try SQL injection in experiment name
            body = {"name": "'; DROP TABLE experiments; --"}
            r = await self._req("POST", "/api/experiments", json=body)
            if r.status_code >= 500:
                return self._fail(
                    "sql_injection", "Edge Cases", "POST /api/experiments",
                    "SQL injection string causes server error", Severity.CRITICAL,
                    "SQL injection should be harmless (parameterized queries)",
                    "200 (created safely)", f"{r.status_code}: {r.text[:200]}", r,
                )
            # Verify experiments table still works
            r2 = await self._req("GET", "/api/experiments")
            if r2.status_code != 200:
                return self._fail(
                    "sql_injection", "Edge Cases", "POST /api/experiments",
                    "SQL injection may have damaged the database",
                    Severity.CRITICAL,
                    "Experiments endpoint broken after injection attempt",
                    "200", f"{r2.status_code}", r2,
                )
            return self._pass("sql_injection", "Edge Cases", "injection harmless, DB intact")
        await self._timed_test("sql_injection", "Edge Cases", _run())

    async def _test_xss_attempt(self) -> None:
        async def _run():
            body = {"name": '<img src=x onerror="alert(1)">'}
            r = await self._req("POST", "/api/experiments", json=body)
            if r.status_code in (200, 201):
                data = r.json()
                exp_name = data.get("experiment", {}).get("name", "")
                if "<" in exp_name and "onerror" in exp_name:
                    return self._fail(
                        "xss_attempt", "Edge Cases", "POST /api/experiments",
                        "XSS payload stored verbatim in experiment name",
                        Severity.MEDIUM,
                        "HTML in names should be escaped or stripped",
                        "Escaped or stripped HTML",
                        f"Stored as-is: {exp_name[:100]}", r,
                    )
            return self._pass("xss_attempt", "Edge Cases", f"status={r.status_code}")
        await self._timed_test("xss_attempt", "Edge Cases", _run())

    async def _test_concurrent_requests(self) -> None:
        async def _run():
            # 20 concurrent reads
            tasks = [self._req("GET", "/api/experiments") for _ in range(20)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            errors = sum(1 for r in results if isinstance(r, Exception))
            server_errors = sum(1 for r in results
                                if isinstance(r, httpx.Response) and r.status_code >= 500)
            if errors > 0:
                return self._fail(
                    "concurrent_reads", "Edge Cases", "GET /api/experiments (x20)",
                    f"{errors} exceptions under concurrent load", Severity.HIGH,
                    "Concurrent reads should all succeed",
                    "0 exceptions", f"{errors} exceptions", None,
                )
            if server_errors > 0:
                return self._fail(
                    "concurrent_reads", "Edge Cases", "GET /api/experiments (x20)",
                    f"{server_errors} server errors under concurrent load", Severity.HIGH,
                    "Concurrent reads should all return 200",
                    "0 5xx", f"{server_errors} 5xx errors", None,
                )
            return self._pass("concurrent_reads", "Edge Cases", "20/20 succeeded")
        await self._timed_test("concurrent_reads", "Edge Cases", _run())

    async def _test_rapid_fire(self) -> None:
        async def _run():
            # 50 rapid sequential requests
            errors = 0
            for i in range(50):
                try:
                    r = await self._req("GET", "/api/health")
                    if r.status_code >= 500:
                        errors += 1
                except Exception:
                    errors += 1
            if errors > 0:
                return self._fail(
                    "rapid_fire", "Edge Cases", "GET /api/health (x50)",
                    f"{errors}/50 failures under rapid fire", Severity.MEDIUM,
                    "Rapid sequential requests should all succeed",
                    "0 failures", f"{errors} failures", None,
                )
            return self._pass("rapid_fire", "Edge Cases", "50/50 succeeded")
        await self._timed_test("rapid_fire", "Edge Cases", _run())

    # -----------------------------------------------------------------------
    # Report generation
    # -----------------------------------------------------------------------

    def generate_report(self) -> str:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed

        lines = [
            f"# GTM-OS Stress Test Bug Report",
            f"",
            f"**Generated:** {now}",
            f"**Target:** {self.base}",
            f"**Total Tests:** {total}",
            f"**Passed:** {passed}",
            f"**Failed:** {failed}",
            f"**Bugs Found:** {len(self.bugs)}",
            f"",
        ]

        # Summary table
        lines.append("## Summary by Category\n")
        lines.append("| Category | Tests | Passed | Failed |")
        lines.append("|----------|-------|--------|--------|")
        categories: dict[str, dict[str, int]] = {}
        for r in self.results:
            cat = categories.setdefault(r.category, {"total": 0, "passed": 0, "failed": 0})
            cat["total"] += 1
            if r.passed:
                cat["passed"] += 1
            else:
                cat["failed"] += 1
        for cat_name, counts in sorted(categories.items()):
            lines.append(f"| {cat_name} | {counts['total']} | {counts['passed']} | {counts['failed']} |")
        lines.append("")

        # Bug listing
        if self.bugs:
            lines.append("## Bugs Found\n")

            # Group by severity
            for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]:
                sev_bugs = [b for b in self.bugs if b.severity == severity]
                if not sev_bugs:
                    continue
                emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}
                lines.append(f"### {emoji.get(severity.value, '')} {severity.value.upper()} ({len(sev_bugs)})\n")
                for bug in sev_bugs:
                    lines.append(f"#### {bug.id}: {bug.title}\n")
                    lines.append(f"- **Category:** {bug.category}")
                    lines.append(f"- **Endpoint:** `{bug.endpoint}`")
                    lines.append(f"- **Description:** {bug.description}")
                    lines.append(f"- **Expected:** {bug.expected}")
                    lines.append(f"- **Actual:** {bug.actual}")
                    if bug.response_code:
                        lines.append(f"- **HTTP Status:** {bug.response_code}")
                    if bug.response_body:
                        lines.append(f"- **Response:** `{bug.response_body[:300]}`")
                    lines.append("")
        else:
            lines.append("## No Bugs Found! 🎉\n")
            lines.append("All tests passed successfully.\n")

        # Full test results
        lines.append("## Full Test Results\n")
        lines.append("| # | Test | Category | Status | Duration |")
        lines.append("|---|------|----------|--------|----------|")
        for i, r in enumerate(self.results, 1):
            status = "PASS" if r.passed else f"**FAIL** ({r.bug.id if r.bug else ''})"
            lines.append(f"| {i} | {r.name} | {r.category} | {status} | {r.duration_ms:.0f}ms |")
        lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser(description="GTM-OS Stress Test Framework")
    parser.add_argument("--base-url", default="http://127.0.0.1:3000",
                        help="Base URL of the GTM-OS server")
    parser.add_argument("--output", default="tests/bug-report.md",
                        help="Output path for the bug report")
    args = parser.parse_args()

    runner = StressTestRunner(args.base_url)
    await runner.run_all()

    report = runner.generate_report()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report)

    total = len(runner.results)
    passed = sum(1 for r in runner.results if r.passed)
    bugs = len(runner.bugs)

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed}/{total} passed, {bugs} bugs found")
    print(f"Report written to: {output_path}")
    print("=" * 60)

    return 1 if bugs > 0 else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
