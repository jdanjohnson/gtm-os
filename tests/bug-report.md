# GTM-OS Stress Test Bug Report

**Generated:** 2026-05-25T19:35:53+00:00
**Target:** http://127.0.0.1:3000
**Total Tests:** 64
**Passed:** 61
**Failed:** 3
**Bugs Found:** 3

## Summary by Category

| Category | Tests | Passed | Failed |
|----------|-------|--------|--------|
| Brand | 3 | 3 | 0 |
| Chat | 7 | 6 | 1 |
| Edge Cases | 8 | 7 | 1 |
| Experiments | 16 | 15 | 1 |
| Health | 2 | 2 | 0 |
| Integrations | 6 | 6 | 0 |
| Memory | 5 | 5 | 0 |
| Metrics | 4 | 4 | 0 |
| Templates | 5 | 5 | 0 |
| Trust | 8 | 8 | 0 |

## Bugs Found

### 🟡 MEDIUM (2)

#### BUG-001: Server accepts experiment with empty name

- **Category:** Experiments
- **Endpoint:** `POST /api/experiments`
- **Description:** Empty string name should be rejected or handled
- **Expected:** 422 or non-empty name enforcement
- **Actual:** Created experiment with empty name, id=4651c2ab87cb4e23bb60e79918c746cd
- **HTTP Status:** 200
- **Response:** `{"experiment":{"id":"4651c2ab87cb4e23bb60e79918c746cd","name":"","description":null,"hypothesis":null,"phase":"design","play_ids":[],"current_agent":null,"config":{},"schedule_id":null,"token_budget":1000000,"tokens_used":0,"created_at":"2026-05-25T19:35:51+00:00","updated_at":"2026-05-25T19:35:51+0`

#### BUG-003: XSS payload stored verbatim in experiment name

- **Category:** Edge Cases
- **Endpoint:** `POST /api/experiments`
- **Description:** HTML in names should be escaped or stripped
- **Expected:** Escaped or stripped HTML
- **Actual:** Stored as-is: <img src=x onerror="alert(1)">
- **HTTP Status:** 200
- **Response:** `{"experiment":{"id":"300b7e641b4a485b90b84742f31f1d35","name":"<img src=x onerror=\"alert(1)\">","description":null,"hypothesis":null,"phase":"design","play_ids":[],"current_agent":null,"config":{},"schedule_id":null,"token_budget":1000000,"tokens_used":0,"created_at":"2026-05-25T19:35:53+00:00","up`

### ⚪ INFO (1)

#### BUG-002: Chat fails due to missing/invalid API key

- **Category:** Chat
- **Endpoint:** `POST /api/chat`
- **Description:** No valid LLM API key configured — expected in test env without keys. Error is properly surfaced via SSE error event (not a silent hang).
- **Expected:** SSE stream with token events (requires valid API key)
- **Actual:** Auth error in response (expected without key): event: meta
data: {"thread_id": "thread-03250462d90c", "agent": "orchestrator", "experiment_id": null}

event: error
data: {"message": "litellm.AuthenticationError: AnthropicException - b'{\"type\
- **HTTP Status:** 200
- **Response:** `event: meta
data: {"thread_id": "thread-03250462d90c", "agent": "orchestrator", "experiment_id": null}

event: error
data: {"message": "litellm.AuthenticationError: AnthropicException - b'{\"type\":\"error\",\"error\":{\"type\":\"authentication_error\",\"message\":\"invalid x-api-key\"},\"reques`

## Full Test Results

| # | Test | Category | Status | Duration |
|---|------|----------|--------|----------|
| 1 | health_endpoint | Health | PASS | 7ms |
| 2 | health_schema | Health | PASS | 1ms |
| 3 | list_experiments | Experiments | PASS | 14ms |
| 4 | create_experiment_valid | Experiments | PASS | 2ms |
| 5 | create_experiment_missing_name | Experiments | PASS | 2ms |
| 6 | create_experiment_empty_name | Experiments | **FAIL** (BUG-001) | 2ms |
| 7 | get_experiment_valid | Experiments | PASS | 2ms |
| 8 | get_experiment_not_found | Experiments | PASS | 1ms |
| 9 | update_experiment | Experiments | PASS | 2ms |
| 10 | update_experiment_not_found | Experiments | PASS | 2ms |
| 11 | pause_experiment | Experiments | PASS | 2ms |
| 12 | pause_already_paused | Experiments | PASS | 2ms |
| 13 | resume_experiment | Experiments | PASS | 2ms |
| 14 | resume_not_found | Experiments | PASS | 1ms |
| 15 | run_tick | Experiments | PASS | 447ms |
| 16 | schedule_experiment | Experiments | PASS | 9ms |
| 17 | schedule_invalid_cron | Experiments | PASS | 9ms |
| 18 | concurrent_creates | Experiments | PASS | 17ms |
| 19 | list_memory | Memory | PASS | 2ms |
| 20 | list_memory_filter | Memory | PASS | 2ms |
| 21 | search_memory | Memory | PASS | 2ms |
| 22 | search_memory_empty | Memory | PASS | 2ms |
| 23 | primitives | Memory | PASS | 8ms |
| 24 | chat_basic | Chat | **FAIL** (BUG-002) | 164ms |
| 25 | chat_empty_message | Chat | PASS | 2ms |
| 26 | chat_invalid_agent | Chat | PASS | 155ms |
| 27 | chat_long_message | Chat | PASS | 243ms |
| 28 | chat_special_chars | Chat | PASS | 247ms |
| 29 | thread_messages | Chat | PASS | 2ms |
| 30 | thread_not_found | Chat | PASS | 2ms |
| 31 | list_trust_scores | Trust | PASS | 2ms |
| 32 | get_trust_score | Trust | PASS | 2ms |
| 33 | trust_score_not_found | Trust | PASS | 2ms |
| 34 | list_proposed | Trust | PASS | 2ms |
| 35 | list_proposed_filter | Trust | PASS | 2ms |
| 36 | review_proposal_not_found | Trust | PASS | 2ms |
| 37 | simulate_not_found | Trust | PASS | 2ms |
| 38 | approve_not_found | Trust | PASS | 2ms |
| 39 | list_templates | Templates | PASS | 2ms |
| 40 | create_template | Templates | PASS | 2ms |
| 41 | get_template | Templates | PASS | 2ms |
| 42 | get_template_not_found | Templates | PASS | 2ms |
| 43 | create_from_template | Templates | PASS | 2ms |
| 44 | save_metric | Metrics | PASS | 2ms |
| 45 | list_metrics | Metrics | PASS | 2ms |
| 46 | metric_summary | Metrics | PASS | 2ms |
| 47 | save_metric_invalid_exp | Metrics | PASS | 2ms |
| 48 | get_integrations | Integrations | PASS | 2ms |
| 49 | get_tool_keys | Integrations | PASS | 1ms |
| 50 | get_model_keys | Integrations | PASS | 2ms |
| 51 | update_model_config | Integrations | PASS | 5ms |
| 52 | list_apps | Integrations | PASS | 2ms |
| 53 | list_connections | Integrations | PASS | 2ms |
| 54 | get_brand | Brand | PASS | 3ms |
| 55 | update_brand | Brand | PASS | 10ms |
| 56 | update_brand_partial | Brand | PASS | 6ms |
| 57 | 404_unknown_route | Edge Cases | PASS | 2ms |
| 58 | method_not_allowed | Edge Cases | PASS | 2ms |
| 59 | malformed_json | Edge Cases | PASS | 2ms |
| 60 | huge_payload | Edge Cases | PASS | 17ms |
| 61 | sql_injection | Edge Cases | PASS | 20ms |
| 62 | xss_attempt | Edge Cases | **FAIL** (BUG-003) | 2ms |
| 63 | concurrent_reads | Edge Cases | PASS | 286ms |
| 64 | rapid_fire | Edge Cases | PASS | 94ms |
