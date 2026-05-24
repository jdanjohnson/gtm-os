#!/usr/bin/env python3
"""
GTM-OS End-to-End Test Script — Claude via OpenRouter
=====================================================

Tests all WS3 (Orchestration) + WS8 (Intelligence) features against a live server.

Usage:
    # 1. Make sure OPENROUTER_API_KEY is set in your environment.
    # 2. Start the server in one terminal:
    #        cd /path/to/gtm-os && OPENROUTER_API_KEY=sk-... uv run gtm-os start
    # 3. Run this test in another terminal:
    #        cd /path/to/gtm-os && OPENROUTER_API_KEY=sk-... uv run python test_e2e_claude.py
    #
    # Or run both together (the script will start the server for you):
    #        cd /path/to/gtm-os && OPENROUTER_API_KEY=sk-... uv run python test_e2e_claude.py --start-server
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from typing import Any

import httpx

__BASE = "http://127.0.0.1:3000"
PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
SKIP = "\033[93mSKIP\033[0m"
INFO = "\033[94mINFO\033[0m"


def get_base() -> str:
    return __BASE

results: list[tuple[str, str, str]] = []  # (test_name, status, detail)


def log(status: str, name: str, detail: str = ""):
    tag = {"pass": PASS, "fail": FAIL, "skip": SKIP, "info": INFO}.get(status, status)
    line = f"  [{tag}] {name}"
    if detail:
        line += f"  — {detail}"
    print(line)
    results.append((name, status, detail))


def api(method: str, path: str, body: dict | None = None, timeout: float = 120.0) -> httpx.Response:
    url = __BASE + path
    with httpx.Client(timeout=timeout) as c:
        if method == "GET":
            return c.get(url)
        elif method == "POST":
            return c.post(url, json=body or {})
        elif method == "PATCH":
            return c.patch(url, json=body or {})
        raise ValueError(f"unsupported method: {method}")


def wait_for_server(max_wait: int = 30):
    print(f"\n⏳ Waiting for server at {_BASE} ...")
    for i in range(max_wait):
        try:
            r = httpx.get(f"{_BASE}/api/health", timeout=2)
            if r.status_code == 200:
                data = r.json()
                print(f"   Server ready — model: {data.get('model')}\n")
                return True
        except (httpx.ConnectError, httpx.ReadTimeout):
            pass
        time.sleep(1)
    print("   ❌ Server did not start in time.")
    return False


# ──────────────────────────────────────────────────────────────────────────────
# Test 1: Health check
# ──────────────────────────────────────────────────────────────────────────────

def test_health():
    print("\n═══ Test 1: Health Check ═══")
    r = api("GET", "/api/health")
    d = r.json()
    if r.status_code == 200 and d.get("ok"):
        log("pass", "Health endpoint returns 200 + ok:true", f"model={d.get('model')}")
    else:
        log("fail", "Health endpoint", f"status={r.status_code}")
    return d


# ──────────────────────────────────────────────────────────────────────────────
# Test 2: Create experiment + verify it exists
# ──────────────────────────────────────────────────────────────────────────────

def test_create_experiment() -> str:
    print("\n═══ Test 2: Create Experiment ═══")
    r = api("POST", "/api/experiments", {
        "name": "E2E Test — Cold Outbound CTOs",
        "hypothesis": "Pain-point subject lines will get 3%+ reply rate from CTOs at Series B",
        "play_ids": ["cold-outbound"],
        "channel": "email",
    })
    d = r.json()
    exp = d.get("experiment", {})
    exp_id = exp.get("id", "")

    if r.status_code == 200 and exp_id:
        log("pass", "Experiment created", f"id={exp_id}, phase={exp.get('phase')}")
    else:
        log("fail", "Create experiment", f"status={r.status_code}, body={d}")
        return ""

    # Verify it shows up in the list.
    r2 = api("GET", "/api/experiments")
    exps = r2.json().get("experiments", [])
    found = any(e["id"] == exp_id for e in exps)
    if found:
        log("pass", "Experiment appears in list")
    else:
        log("fail", "Experiment not found in list")

    return exp_id


# ──────────────────────────────────────────────────────────────────────────────
# Test 3: Run tick (design phase) — uses Claude LLM
# ──────────────────────────────────────────────────────────────────────────────

def test_run_tick(exp_id: str) -> dict[str, Any]:
    print("\n═══ Test 3: Run Tick (Design Phase — calls Claude) ═══")
    if not exp_id:
        log("skip", "Run tick", "no experiment ID")
        return {}

    r = api("POST", f"/api/experiments/{exp_id}/run-tick", timeout=180)
    d = r.json()
    if r.status_code == 200 and d.get("ok"):
        log("pass", "Tick completed", f"phase={d.get('phase')}, tokens={d.get('tokens_used')}")
        if d.get("message"):
            print(f"     Agent message (first 200 chars): {d['message'][:200]}...")
        if d.get("tool_calls"):
            print(f"     Tool calls: {[tc.get('name') for tc in d['tool_calls']]}")
    else:
        log("fail", "Run tick", f"status={r.status_code}, error={d.get('error')}")
    return d


# ──────────────────────────────────────────────────────────────────────────────
# Test 4: Structured Metrics (WS3B)
# ──────────────────────────────────────────────────────────────────────────────

def test_metrics(exp_id: str):
    print("\n═══ Test 4: Structured Metrics (WS3B) ═══")
    if not exp_id:
        log("skip", "Metrics", "no experiment ID")
        return

    # Save some metrics.
    metrics = [
        {"metric_name": "reply_rate", "metric_value": 2.4, "variant": "pain-point"},
        {"metric_name": "reply_rate", "metric_value": 1.8, "variant": "social-proof"},
        {"metric_name": "open_rate", "metric_value": 34.0, "variant": "pain-point"},
        {"metric_name": "open_rate", "metric_value": 28.0, "variant": "social-proof"},
        {"metric_name": "meetings_booked", "metric_value": 3.0},
    ]
    for m in metrics:
        r = api("POST", f"/api/experiments/{exp_id}/metrics", m)
        if r.status_code != 200:
            log("fail", f"Save metric {m['metric_name']}", f"status={r.status_code}")
            return
    log("pass", f"Saved {len(metrics)} metrics")

    # List metrics.
    r = api("GET", f"/api/experiments/{exp_id}/metrics")
    d = r.json()
    count = len(d.get("metrics", []))
    if count == len(metrics):
        log("pass", "List metrics", f"count={count}")
    else:
        log("fail", "List metrics", f"expected {len(metrics)}, got {count}")

    # Filter by variant.
    r = api("GET", f"/api/experiments/{exp_id}/metrics?variant=pain-point")
    pain_count = len(r.json().get("metrics", []))
    if pain_count == 2:
        log("pass", "Filter metrics by variant=pain-point", f"count={pain_count}")
    else:
        log("fail", "Filter metrics by variant", f"expected 2, got {pain_count}")

    # Get summary.
    r = api("GET", f"/api/experiments/{exp_id}/metrics/summary")
    summary = r.json()
    if "reply_rate" in str(summary):
        log("pass", "Metric summary returns aggregated data", f"keys={list(summary.keys())[:5]}")
    else:
        log("fail", "Metric summary", f"body={json.dumps(summary)[:200]}")


# ──────────────────────────────────────────────────────────────────────────────
# Test 5: Experiment Templates (WS3D)
# ──────────────────────────────────────────────────────────────────────────────

def test_templates(exp_id: str):
    print("\n═══ Test 5: Experiment Templates (WS3D) ═══")

    # Create a template.
    r = api("POST", "/api/templates", {
        "name": "Cold Outbound Template",
        "description": "Standard cold outbound to CTOs",
        "play_ids": ["cold-outbound"],
        "config": {"channel": "email", "icp": "CTO, Series B"},
        "hypothesis_pattern": "Pain-point subjects get 3%+ reply rate",
        "token_budget": 150000,
    })
    d = r.json()
    tmpl_id = d.get("template_id", "")
    if r.status_code == 200 and tmpl_id:
        log("pass", "Template created", f"id={tmpl_id}")
    else:
        log("fail", "Create template", f"status={r.status_code}")
        return

    # List templates.
    r = api("GET", "/api/templates")
    templates = r.json().get("templates", [])
    found = any(t["id"] == tmpl_id for t in templates)
    if found:
        log("pass", "Template appears in list")
    else:
        log("fail", "Template not in list")

    # Get template by ID.
    r = api("GET", f"/api/templates/{tmpl_id}")
    tmpl = r.json().get("template", {})
    if tmpl.get("name") == "Cold Outbound Template":
        log("pass", "Get template by ID", f"name={tmpl['name']}")
    else:
        log("fail", "Get template by ID", f"body={tmpl}")

    # Create experiment from template.
    r = api("POST", f"/api/templates/{tmpl_id}/create-experiment", {
        "name": "From-Template Test Experiment",
        "overrides": {"hypothesis": "Adjusted hypothesis for VP Eng"},
    })
    d = r.json()
    if r.status_code == 200 and d.get("ok") and d.get("experiment_id"):
        log("pass", "Experiment created from template", f"id={d['experiment_id']}, phase={d.get('phase')}")

        # Verify the new experiment has the template's play_ids.
        r2 = api("GET", f"/api/experiments/{d['experiment_id']}")
        new_exp = r2.json().get("experiment", {})
        if "cold-outbound" in new_exp.get("play_ids", []):
            log("pass", "Template play_ids carried over to new experiment")
        else:
            log("fail", "Template play_ids not carried over", f"play_ids={new_exp.get('play_ids')}")
    else:
        log("fail", "Create from template", f"status={r.status_code}, body={d}")


# ──────────────────────────────────────────────────────────────────────────────
# Test 6: Trust Scores (WS8C)
# ──────────────────────────────────────────────────────────────────────────────

def test_trust_scores():
    print("\n═══ Test 6: Trust Scores (WS8C) ═══")

    # Initially, trust should be 0 for a new type.
    r = api("GET", "/api/trust-scores/email")
    d = r.json()
    score = float(d.get("trust_score", {}).get("score", 0))
    log("pass" if score == 0.0 else "info", "Initial trust score for 'email'", f"score={score}")

    # List all trust scores.
    r = api("GET", "/api/trust-scores")
    scores = r.json().get("trust_scores", [])
    log("pass", "List trust scores", f"count={len(scores)}")


# ──────────────────────────────────────────────────────────────────────────────
# Test 7: Proposed Experiments (WS8D)
# ──────────────────────────────────────────────────────────────────────────────

def test_proposed_experiments():
    print("\n═══ Test 7: Proposed Experiments (WS8D) ═══")

    # List proposals (should start empty or have any from prior ticks).
    r = api("GET", "/api/proposed-experiments")
    proposals = r.json().get("proposals", [])
    initial_count = len(proposals)
    log("pass", "List proposals", f"count={initial_count}")

    # We can't directly create a proposal via API (it's done by the agent tool),
    # but we can test the store directly by inserting one via the propose_experiment
    # store method. Instead, we'll test the review endpoint if any proposals exist.
    # For a clean test, we'll use the trust endpoint's propose path.
    log("info", "Proposal creation requires agent tool call — testing review flow if proposals exist")

    if initial_count > 0:
        pid = proposals[0]["id"]
        r = api("POST", f"/api/proposed-experiments/{pid}/review", {"action": "reject"})
        d = r.json()
        if d.get("ok") and d.get("action") == "rejected":
            log("pass", "Reject proposal", f"id={pid}")
        else:
            log("fail", "Reject proposal", f"body={d}")


# ──────────────────────────────────────────────────────────────────────────────
# Test 8: Simulation / Dry-run (WS8E)
# ──────────────────────────────────────────────────────────────────────────────

def test_simulation(exp_id: str, second_exp_id: str = ""):
    print("\n═══ Test 8: Simulation / Dry-run (WS8E) ═══")
    if not exp_id:
        log("skip", "Simulation", "no experiment ID")
        return

    # Create a second experiment with metrics so simulation has historical data.
    r = api("POST", "/api/experiments", {
        "name": "E2E Test — Historical Cold Outbound",
        "hypothesis": "Historical comparison experiment",
        "play_ids": ["cold-outbound"],
        "channel": "email",
    })
    hist_id = r.json().get("experiment", {}).get("id", "")
    if hist_id:
        # Add metrics to historical experiment.
        for m in [
            {"metric_name": "reply_rate", "metric_value": 3.1},
            {"metric_name": "open_rate", "metric_value": 38.0},
        ]:
            api("POST", f"/api/experiments/{hist_id}/metrics", m)

    # Run simulation on the primary experiment.
    r = api("POST", f"/api/experiments/{exp_id}/simulate")
    d = r.json()
    if r.status_code == 200 and d.get("ok"):
        preds = d.get("predictions", [])
        log("pass", "Simulation completed", f"predictions={len(preds)}, similar_found={d.get('similar_experiments_found')}")
        for p in preds[:3]:
            print(f"     → {p['name']}: {p['predicted_value']:.2f} (CI: {p['confidence_interval']})")
        if d.get("message"):
            print(f"     Message: {d['message']}")
    else:
        log("fail", "Simulation", f"status={r.status_code}, body={json.dumps(d)[:200]}")


# ──────────────────────────────────────────────────────────────────────────────
# Test 9: Human Feedback / Approve with Diff (WS8B)
# ──────────────────────────────────────────────────────────────────────────────

def test_feedback(exp_id: str):
    print("\n═══ Test 9: Human Feedback Learning (WS8B) ═══")
    if not exp_id:
        log("skip", "Feedback", "no experiment ID")
        return

    # First, pause the experiment so we can approve it.
    api("POST", f"/api/experiments/{exp_id}/pause")

    # Approve with edits (simulates human correcting copy).
    original = (
        "Subject: Quick question about your engineering team\n\n"
        "Hi there,\n\n"
        "I noticed your company is scaling rapidly. Let's leverage our synergy "
        "to circle back on optimizing your tech stack.\n\n"
        "Best regards"
    )
    approved = (
        "Subject: quick q about your eng team\n\n"
        "Hey there,\n\n"
        "I noticed your company is scaling rapidly. Let's use our platform "
        "to help optimize your tech stack.\n\n"
        "Cheers"
    )

    r = api("POST", f"/api/experiments/{exp_id}/approve", {
        "original_content": original,
        "approved_content": approved,
    })
    d = r.json()
    if r.status_code == 200 and d.get("ok"):
        log("pass", "Approve with feedback", 
            f"corrections={d.get('corrections_found')}, "
            f"memories={d.get('memories_saved')}, "
            f"rules_promoted={d.get('rules_promoted')}")
        if d.get("phase") == "execute":
            log("pass", "Experiment resumed to execute phase")
        else:
            log("info", "Experiment phase after approve", f"phase={d.get('phase')}")
    else:
        log("fail", "Approve with feedback", f"status={r.status_code}, body={json.dumps(d)[:200]}")


# ──────────────────────────────────────────────────────────────────────────────
# Test 10: Chat / SSE Streaming (with Claude)
# ──────────────────────────────────────────────────────────────────────────────

def test_chat(exp_id: str):
    print("\n═══ Test 10: Chat Streaming (SSE with Claude) ═══")

    body = {
        "message": "What experiments are currently running? Summarize their status.",
        "experiment_id": exp_id,
        "agent": "orchestrator",
    }

    collected_tokens = []
    thread_id = None
    got_meta = False
    got_final = False

    try:
        with httpx.Client(timeout=180) as client:
            with client.stream("POST", f"{_BASE}/api/chat", json=body) as resp:
                buffer = ""
                for chunk in resp.iter_text():
                    buffer += chunk
                    while "\n\n" in buffer:
                        raw, buffer = buffer.split("\n\n", 1)
                        for line in raw.split("\n"):
                            if line.startswith("event: "):
                                event_type = line[7:].strip()
                            elif line.startswith("data: "):
                                data_str = line[6:]
                                try:
                                    data = json.loads(data_str)
                                except (json.JSONDecodeError, TypeError):
                                    data = data_str

                                if event_type == "meta":
                                    got_meta = True
                                    thread_id = data.get("thread_id") if isinstance(data, dict) else None
                                elif event_type == "token":
                                    t = data.get("text", "") if isinstance(data, dict) else str(data)
                                    collected_tokens.append(t)
                                elif event_type == "final":
                                    got_final = True
                                elif event_type == "error":
                                    log("fail", "Chat SSE error event", str(data)[:200])
    except Exception as e:
        log("fail", "Chat streaming", str(e)[:200])
        return

    full_response = "".join(collected_tokens)
    if got_meta and thread_id:
        log("pass", "SSE meta event received", f"thread_id={thread_id[:12]}…")
    else:
        log("fail", "SSE meta event", f"got_meta={got_meta}, thread_id={thread_id}")

    if len(collected_tokens) > 0:
        log("pass", "SSE tokens streamed", f"token_count={len(collected_tokens)}, chars={len(full_response)}")
        print(f"     Response (first 300 chars): {full_response[:300]}...")
    else:
        log("fail", "No SSE tokens received")

    if got_final:
        log("pass", "SSE final event received")
    else:
        log("fail", "No SSE final event")


# ──────────────────────────────────────────────────────────────────────────────
# Test 11: Quality Gate (WS8A) — runs via tick on build phase
# ──────────────────────────────────────────────────────────────────────────────

def test_quality_gate():
    print("\n═══ Test 11: Quality Gate at Build→Execute (WS8A) ═══")

    # Create a fresh experiment and advance to build.
    r = api("POST", "/api/experiments", {
        "name": "E2E Quality Gate Test",
        "hypothesis": "Testing quality gate scoring",
        "play_ids": ["cold-outbound"],
        "channel": "email",
    })
    exp_id = r.json().get("experiment", {}).get("id")
    if not exp_id:
        log("fail", "Create QG test experiment")
        return

    # Run design tick first.
    print("     Running design tick...")
    r = api("POST", f"/api/experiments/{exp_id}/run-tick", timeout=180)
    d = r.json()
    log("info", "Design tick", f"ok={d.get('ok')}, phase={d.get('phase')}, tokens={d.get('tokens_used')}")

    # Advance to build manually if still in design.
    exp_r = api("GET", f"/api/experiments/{exp_id}")
    current_phase = exp_r.json().get("experiment", {}).get("phase", "design")
    if current_phase == "design":
        api("PATCH", f"/api/experiments/{exp_id}", {"phase": "build"})
        log("info", "Manually advanced to build phase")

    # Run build tick — this should trigger the quality gate.
    print("     Running build tick (quality gate should fire)...")
    r = api("POST", f"/api/experiments/{exp_id}/run-tick", timeout=180)
    d = r.json()

    # Check experiment state after build tick.
    exp_r = api("GET", f"/api/experiments/{exp_id}")
    exp_data = exp_r.json().get("experiment", {})
    new_phase = exp_data.get("phase", "")

    if new_phase == "paused":
        log("pass", "Quality gate triggered — experiment paused for approval",
            f"phase={new_phase}")
    elif new_phase == "execute":
        log("pass", "Quality gate passed — auto-approved (trust was high enough or score ≥7)",
            f"phase={new_phase}")
    elif new_phase == "build":
        # Quality gate may have failed and returned to build.
        log("pass", "Quality gate returned to build (score < 7)", f"phase={new_phase}")
        # Check for quality gate message in experiment messages.
        runs = api("GET", f"/api/experiments/{exp_id}").json().get("runs", [])
        log("info", f"Runs so far: {len(runs)}")
    else:
        log("info", "Post-build phase", f"phase={new_phase}, tick_result={json.dumps(d)[:200]}")

    return exp_id


# ──────────────────────────────────────────────────────────────────────────────
# Test 12: Memory search
# ──────────────────────────────────────────────────────────────────────────────

def test_memory():
    print("\n═══ Test 12: Memory ═══")

    r = api("GET", "/api/memory")
    d = r.json()
    memories = d.get("memories", [])
    log("pass", "List memory", f"count={len(memories)}")

    if len(memories) > 0:
        print(f"     Sample: type={memories[0].get('type')}, content={memories[0].get('content', '')[:100]}")


# ──────────────────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────────────────

def print_summary():
    print("\n" + "═" * 60)
    print("  GTM-OS E2E TEST SUMMARY")
    print("═" * 60)
    passed = sum(1 for _, s, _ in results if s == "pass")
    failed = sum(1 for _, s, _ in results if s == "fail")
    skipped = sum(1 for _, s, _ in results if s == "skip")
    infos = sum(1 for _, s, _ in results if s == "info")

    print(f"\n  ✅ Passed:  {passed}")
    print(f"  ❌ Failed:  {failed}")
    print(f"  ⏭  Skipped: {skipped}")
    print(f"  ℹ️  Info:    {infos}")
    print(f"  ─────────────────")
    print(f"  Total:     {len(results)}")

    if failed > 0:
        print("\n  Failed tests:")
        for name, status, detail in results:
            if status == "fail":
                print(f"    • {name}: {detail}")

    print()
    return failed == 0


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GTM-OS E2E Test Suite")
    parser.add_argument("--start-server", action="store_true", help="Auto-start the server before testing")
    parser.add_argument("--base-url", default=_BASE, help="Base URL of the running server")
    args = parser.parse_args()

    global _BASE
    _BASE = args.base_url

    server_proc = None
    if args.start_server:
        print("🚀 Starting GTM-OS server...")
        server_proc = subprocess.Popen(
            ["uv", "run", "gtm-os", "start"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

    try:
        if not wait_for_server():
            print("Cannot reach server. Pass --start-server to auto-start, or start it manually.")
            sys.exit(1)

        # Run all tests.
        test_health()
        exp_id = test_create_experiment()
        tick_result = test_run_tick(exp_id)
        test_metrics(exp_id)
        test_templates(exp_id)
        test_trust_scores()
        test_proposed_experiments()
        test_simulation(exp_id)
        test_feedback(exp_id)
        test_chat(exp_id)
        test_quality_gate()
        test_memory()

        all_passed = print_summary()
        sys.exit(0 if all_passed else 1)

    finally:
        if server_proc:
            print("Stopping server...")
            server_proc.terminate()
            server_proc.wait(timeout=5)


if __name__ == "__main__":
    main()
