# GTM-OS Agent-Driven E2E Stress Test Report

**Generated:** 2026-05-25T20:14:58+00:00
**Target:** http://127.0.0.1:3000
**Total Scenarios:** 17
**Passed:** 17
**Failed:** 0
**Bugs Found:** 0

## Summary by Category

| Category | Tests | Passed | Failed |
|----------|-------|--------|--------|
| Chat | 3 | 3 | 0 |
| Concurrency | 2 | 2 | 0 |
| Error Handling | 3 | 3 | 0 |
| Experiment Lifecycle | 3 | 3 | 0 |
| Integration | 2 | 2 | 0 |
| Memory | 2 | 2 | 0 |
| Research | 2 | 2 | 0 |

## Full Scenario Results

| # | Scenario | Category | Status | Duration |
|---|----------|----------|--------|----------|
| 1 | chat_hello | Chat | PASS | 3422ms |
| 2 | chat_followup | Chat | PASS | 7346ms |
| 3 | chat_multi_sentence | Chat | PASS | 16392ms |
| 4 | agent_create_experiment | Experiment Lifecycle | PASS | 16533ms |
| 5 | agent_describe_experiments | Experiment Lifecycle | PASS | 12392ms |
| 6 | agent_pause_resume | Experiment Lifecycle | PASS | 10674ms |
| 7 | agent_research_task | Research | PASS | 11550ms |
| 8 | agent_analyze_metrics | Research | PASS | 14797ms |
| 9 | agent_memory_recall | Memory | PASS | 9942ms |
| 10 | agent_context_persistence | Memory | PASS | 7203ms |
| 11 | agent_invalid_request | Error Handling | PASS | 17871ms |
| 12 | agent_nonexistent_experiment | Error Handling | PASS | 8424ms |
| 13 | agent_ambiguous_instruction | Error Handling | PASS | 12839ms |
| 14 | concurrent_chats | Concurrency | PASS | 4620ms |
| 15 | rapid_chat_messages | Concurrency | PASS | 21199ms |
| 16 | agent_then_api_verify | Integration | PASS | 17855ms |
| 17 | api_then_agent_verify | Integration | PASS | 6414ms |
