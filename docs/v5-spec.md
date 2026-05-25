# GTM-OS v5 — Implementation Spec (for the three parallel tracks)

This document is the **single source of truth** for the v5 decomposition-layer work. Three sub-agents (Foundation, Runtime, Surface) are building this in parallel; this spec exists so they don't drift.

The product framing, the design rationale, and the full ecosystem analysis live next door in:
- [`docs/v5-design.md`](./v5-design.md) — the v5 proposal (read this first if you're new to the work)
- [`docs/v5-ecosystem-analysis.md`](./v5-ecosystem-analysis.md) — code-level read of the 9 reference repos (forge, 12-factor, trustclaw, openhuman, multica, prose, holaOS, PraisonAI, maigret)

This file is the **contract** between tracks. If your track needs to deviate, message the parent session before doing so.

---

## 0. TL;DR

GTM-OS already ships:
- Python + FastAPI backend, React frontend, single-binary local-runnable shape ("open http://127.0.0.1:3000").
- SQLite + optional `sqlite-vec` for state and vector memory.
- Polling-daemon scheduler, auto-pause after 3 consecutive failures, durability/recovery sweep.
- 3-layer context management (prune → flush → compact).
- Composio integration; tool-loop harness over `litellm`.
- Six primitives on disk (Brand, Agents, Rules, Plays, Memory, Triggers).
- `Experiment` as the runtime task-loop dataclass.

v5 **adds a decomposition layer on top of this runtime**, not a rewrite. The user no longer touches Experiments directly — they describe work in plain English to a **Composer** agent, which produces a **Plan** (Markdown contract). The Plan compiles down to one or more `Experiment` records that gtm-os already knows how to run.

The new concepts (Plan, Composer, Reactor, Receipt, Status taxonomy, Soul/Identity prompt layers) all live as new modules; existing modules are extended, not replaced.

---

## 1. The three tracks at a glance

| Track | Scope | Branch | Primary owner |
|-------|-------|--------|---------------|
| **Foundation** | Plan dataclass + DB tables + Composer agent + Soul/Identity prompts + voice validator + eval set + Plan→Experiment compiler + Receipt schema + Status judge | `devin/v5-foundation` | Sub-agent 1 |
| **Runtime** | Reactor (bounded activations) + trigger sources (cron/webhook/chat/manual/pressure) + structured-output tool dispatch + admission gates + sub-agent forking (Phase 2) + receipt emission integration | `devin/v5-runtime` | Sub-agent 2 |
| **Surface** | Composer chat UI + Plans list + Plan detail + Activity inbox + Status timeline + native-shell polish (local OAuth callback, system tray, browser launch) + Phase 3 observability | `devin/v5-surface` | Sub-agent 3 |

Each track branches off `devin/v5-spec`. Each track pushes to its own branch and opens a PR back to `main`. Integration is the parent's job.

---

## 2. File ownership (avoid merge conflicts)

Each track has primary ownership over a set of files. Shared files have **carved sections** so two tracks can edit a file without colliding.

### Foundation track owns
```
src/gtm_os/engine/composer.py         (NEW)
src/gtm_os/engine/plan.py             (NEW — Plan dataclass + Markdown serdes)
src/gtm_os/engine/voice.py            (NEW — Soul + Identity prompt builder)
src/gtm_os/engine/voice_validator.py  (NEW — V1-V9 banned-vocabulary check)
src/gtm_os/engine/voice_eval.py       (NEW — eval-set runner for CI)
src/gtm_os/engine/status_judge.py     (NEW — up/drifting/down/blocked judge)
src/gtm_os/engine/receipts.py         (NEW — content-addressed receipt emitter)
src/gtm_os/server/routes/plans.py     (NEW — Plan CRUD API)
src/gtm_os/server/routes/composer.py  (NEW — Composer chat SSE endpoint)
src/gtm_os/server/routes/receipts.py  (NEW — Receipt read API)
primitives/voice/soul.md              (NEW — V1-V9 voice rules)
primitives/voice/banned_vocabulary.json (NEW)
primitives/eval/composer_examples.yaml  (NEW — 30 reference examples)
tests/test_composer.py                (NEW)
tests/test_plan.py                    (NEW)
tests/test_voice_validator.py         (NEW)
tests/test_status_judge.py            (NEW)
tests/test_receipts.py                (NEW)
```

### Runtime track owns
```
src/gtm_os/engine/reactor.py          (NEW — bounded-activation Reactor)
src/gtm_os/engine/activation.py       (NEW — ActivationRecord + emit)
src/gtm_os/engine/admission.py        (NEW — admission gates)
src/gtm_os/engine/subagent_fork.py    (NEW — context fork for sub-agents, Phase 2)
src/gtm_os/engine/triggers/           (NEW — per-trigger-source modules)
  ├── cron.py
  ├── webhook.py
  ├── chat.py
  ├── manual.py
  └── pressure.py
src/gtm_os/server/routes/triggers.py  (NEW — webhook endpoint + manual-trigger endpoint)
tests/test_reactor.py                 (NEW)
tests/test_activation.py              (NEW)
tests/test_admission.py               (NEW)
tests/test_subagent_fork.py           (NEW)
```

Runtime track **modifies** (carved sections only):
- `src/gtm_os/engine/harness.py` — extend tool dispatch to enforce structured outputs (12-factor factor 4)
- `src/gtm_os/engine/scheduler.py` — emit cron events into the Reactor instead of directly running experiments
- `src/gtm_os/engine/durability.py` — emit ActivationRecord on every activation start/end
- `src/gtm_os/engine/composio_tools.py` — ensure all dispatches go through structured-output validation

### Surface track owns
```
frontend/src/components/Composer/     (NEW)
  ├── ComposerChat.tsx                (replaces what Chat.tsx does for new-plan flow)
  ├── PlanPreview.tsx                 (renders Markdown contract preview)
  └── ComposerSidebar.tsx
frontend/src/components/Plans/        (NEW)
  ├── PlansList.tsx
  ├── PlanDetail.tsx
  ├── PlanStatusBadge.tsx
  ├── StatusTimeline.tsx              (last 30 activations as colored dots)
  └── ActivityInbox.tsx               (drafts to review across all Plans)
frontend/src/lib/api/plans.ts         (NEW — Plan + Composer API client)
frontend/src/lib/api/receipts.ts      (NEW — Receipt API client)
src/gtm_os/server/frontend_dist/      (rebuilt React bundle, committed)
```

Surface track **modifies** (carved sections only):
- `frontend/src/App.tsx` — add Plans + Composer routes
- `frontend/src/components/Sidebar.tsx` — add Plans nav entry (above Experiments)
- `frontend/src/components/Chat.tsx` — preserve existing experiment-setup flow; new Composer is a separate component

### Shared files (all tracks must coordinate)

These files will be edited by multiple tracks. Each track edits **only its named section** marked with `# V5-FOUNDATION:`, `# V5-RUNTIME:`, `# V5-SURFACE:` comments.

```
src/gtm_os/types.py
src/gtm_os/engine/store.py
src/gtm_os/server/app.py
```

If you need to edit outside your section, message the parent session first.

---

## 3. Data model additions

### 3.1 Plan dataclass (Foundation track owns)

Added to `src/gtm_os/types.py` in the `# V5-FOUNDATION:` section:

```python
PlanStatus = Literal["draft", "active", "paused", "archived"]
ActivationStatus = Literal["up", "drifting", "down", "blocked"]

@dataclass
class Plan:
    id: str                                    # ULID
    name: str                                  # auto-derived from Goal section
    rendered_paragraph: str                    # what the user reads
    goal: str                                  # § Goal
    continuity: str                            # § Continuity (cadence)
    criteria: str                              # § Criteria
    constraints: str                           # § Constraints
    tools: str                                 # § Tools (skills referenced)
    fulfillment: str                           # § Fulfillment (hint about what success looks like)
    status: PlanStatus = "draft"
    activation_status: ActivationStatus | None = None  # judged from receipts
    program_tag: str | None = None             # post-v1 grouping; nullable for v1
    experiment_ids: list[str] = field(default_factory=list)  # what this Plan compiled into
    fingerprint: str = ""                      # sha256 of full contract — used for memoization
    version: int = 1
    created_at: str | None = None
    updated_at: str | None = None

@dataclass
class ActivationRecord:
    id: str                                    # ULID
    plan_id: str
    experiment_id: str | None                  # nullable for Composer activations
    trigger_source: str                        # "cron" | "chat" | "webhook" | "manual" | "pressure"
    trigger_payload: dict[str, Any] = field(default_factory=dict)
    input_fingerprint: str = ""                # sha256 of trigger payload + Plan fingerprint
    started_at: str = ""
    completed_at: str | None = None
    outcome: str = "running"                   # "running" | "success" | "skipped" | "failed" | "blocked"
    skip_reason: str | None = None             # set when admission gates skip
    tokens_used: int = 0
    cost_usd: float = 0.0
    receipt_id: str | None = None              # set when receipt is emitted

@dataclass
class Receipt:
    id: str                                    # ULID
    activation_id: str
    plan_id: str
    content_hash: str                          # sha256 of yaml_body — content-addressed
    yaml_body: str                             # the full YAML receipt
    evidence_uris: list[str] = field(default_factory=list)  # references to other receipts (composition)
    created_at: str = ""
```

### 3.2 SQLite schema additions (Foundation declares; Runtime + Surface read)

```sql
-- in store.py, V5-FOUNDATION section
CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    rendered_paragraph TEXT NOT NULL,
    goal TEXT NOT NULL,
    continuity TEXT NOT NULL,
    criteria TEXT NOT NULL,
    constraints TEXT NOT NULL,
    tools TEXT NOT NULL,
    fulfillment TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    activation_status TEXT,
    program_tag TEXT,
    experiment_ids TEXT NOT NULL DEFAULT '[]',  -- JSON array
    fingerprint TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activation_records (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    experiment_id TEXT,
    trigger_source TEXT NOT NULL,
    trigger_payload TEXT NOT NULL DEFAULT '{}',
    input_fingerprint TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    outcome TEXT NOT NULL DEFAULT 'running',
    skip_reason TEXT,
    tokens_used INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0,
    receipt_id TEXT,
    FOREIGN KEY (plan_id) REFERENCES plans(id)
);

CREATE TABLE IF NOT EXISTS receipts (
    id TEXT PRIMARY KEY,
    activation_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    content_hash TEXT NOT NULL UNIQUE,
    yaml_body TEXT NOT NULL,
    evidence_uris TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    FOREIGN KEY (activation_id) REFERENCES activation_records(id),
    FOREIGN KEY (plan_id) REFERENCES plans(id)
);

CREATE INDEX IF NOT EXISTS idx_activation_plan_started ON activation_records(plan_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_receipts_plan ON receipts(plan_id, created_at DESC);
```

Foundation track writes the migration. Runtime + Surface read.

---

## 4. The Plan Markdown contract (Foundation track owns format)

Plans are stored as rows (decision Q3: rows-everywhere with Markdown export). The Markdown serialization is the canonical export format.

```markdown
# {name}

> {rendered_paragraph}

## Goal
{goal — one sentence stating what the Plan exists for, in the user's nouns/verbs}

## Continuity
{cadence + freshness rules — e.g. "Every Friday at 9 AM Pacific. Catch up on missed runs if the laptop was offline."}

## Criteria
{specific tests for success — e.g. "Drafts must reference at least one note from the last 30 days. If no notes exist, skip the client and flag them in the summary."}

## Constraints
{what the system won't do — e.g. "Never send a message without user approval. Never include calendar links unless the user has uploaded a current one."}

## Tools
{the skills + integrations needed — e.g. "Skills: read_session_notes, classify_client_state, draft_warm_message, save_to_drafts. Integrations: Gmail (drafts only), Google Drive (notes)."}

## Fulfillment
{a hint to the runtime about what "good" looks like — e.g. "A drafts folder with N items where N = number of active clients with notes. Each draft references at least one specific moment from a recent session."}
```

The `rendered_paragraph` is what the user sees. The six sections are what the system reads.

**Hard rule (V1-V9 voice constraint, enforced by `voice_validator.py`):**
The `rendered_paragraph` must NEVER contain any of: `step, tool, workflow, rule, play, agent, automation, experiment, integration, trigger, phase, run, tick, prompt, system, configuration, sub-agent, activation, receipt, status`. The validator regenerates the paragraph if any banned word appears.

---

## 5. REST API surface (Foundation defines; Surface consumes)

All under `/api`. Foundation track exposes these; Surface track consumes them.

### Composer
```
POST   /api/composer/chat                   SSE — sends a user message, streams composer reply
GET    /api/composer/sessions               list recent composer sessions
GET    /api/composer/sessions/{id}          get one session's transcript
POST   /api/composer/sessions/{id}/compile  finalize the current draft into a Plan
```

### Plans
```
GET    /api/plans                           list all plans (filter by status, program_tag)
POST   /api/plans                           create a Plan (typically called by Composer compile)
GET    /api/plans/{id}                      get one Plan + recent activations
PATCH  /api/plans/{id}                      update Plan (pause/archive/rename)
DELETE /api/plans/{id}                      archive (soft delete)
GET    /api/plans/{id}/markdown             export as Markdown
GET    /api/plans/{id}/activations          list recent activations (last 30)
POST   /api/plans/{id}/run                  manually trigger an activation
```

### Receipts
```
GET    /api/receipts/{id}                   one receipt (YAML body)
GET    /api/plans/{id}/receipts             list receipts for a Plan
GET    /api/activations/{id}/receipt        get the receipt for an activation
```

### Triggers (Runtime track owns)
```
POST   /api/triggers/webhook/{plan_id}      external webhook entry point
POST   /api/triggers/pressure               internal — one Plan's drift wakes another
```

---

## 6. Composer agent contract (Foundation track owns)

The Composer is the only user-facing agent. It:

1. Reads the user's message.
2. Builds its context: Soul prompt + Identity prompt + recent Composer session transcript + relevant Plans (vector recall).
3. Drafts a six-section Plan contract.
4. Renders the `rendered_paragraph` from the contract.
5. Runs `voice_validator` over the paragraph; if banned vocab appears, regenerate up to 3 times. After 3, log an error and emit the closest-passing version with the banned word redacted.
6. Streams the paragraph to the UI.
7. On `POST /api/composer/sessions/{id}/compile`: persist the Plan, compute the fingerprint, set status `active`, and call `runtime.reactor.register(plan)`.

### Soul prompt skeleton

`primitives/voice/soul.md` (Foundation authors). High-level shape:

```markdown
# Soul

I help this user with their work. I write the way they write, in their own nouns and verbs.

## How I write
- I write paragraphs. Not bullet lists, not numbered steps, not headers.
- I write in the first person — "I'll draft," "I'll watch," "I'll send."
- I'm specific. "Every Friday at 9 AM" beats "regularly."
- I'm honest about what I won't do. I name boundaries plainly.

## What I never say
{banned-vocabulary table loaded from banned_vocabulary.json — referenced inline so the validator and Soul stay in sync}

## How I behave
- I draft Plans the user can explain to a friend. If I can't pass that test, I'm not done.
- I never ask the user to learn a system. I just propose the work, in their words.
- If the user gives me too broad a goal, I pick the most valuable first slice and write *that* Plan. I offer the next slice when the current one is working.
```

### Identity prompt (auto-inferred)

The system maintains a running `Identity` doc per user, accumulated from:
- Onboarding answers ("what kind of work do you do?")
- Plan history (the user's nouns/verbs across their Plans)
- Connected integrations

Foundation track writes the inferring logic; it runs after every compile.

### Voice eval (Foundation track owns; CI-gated)

`primitives/eval/composer_examples.yaml` contains 30 reference user inputs and the **shape** the Composer's output must match (regex-checkable). The eval runs in CI; if any banned word appears in any output, or if the rendered paragraph fails to match the expected shape, the build fails.

---

## 7. Reactor + Activation contract (Runtime track owns)

### 7.1 Reactor

`reactor.py` listens to N event sources and, for each event, launches a bounded activation:

```python
class Reactor:
    def register(self, plan: Plan) -> None: ...
    def unregister(self, plan_id: str) -> None: ...
    def handle_event(self, event: TriggerEvent) -> ActivationRecord: ...
    # Internal: launches a bounded activation; calls admission gates; emits ActivationRecord.
```

Event sources (each in `engine/triggers/`):
- `cron.py` — wraps existing `scheduler.py`; emits an event per scheduled tick.
- `webhook.py` — POST endpoint; emits an event per webhook hit.
- `chat.py` — user chat-to-Plan event; lets a user say "run this now."
- `manual.py` — UI button; emits an event with `trigger_source="manual"`.
- `pressure.py` — internal — one Plan's status drift can wake another (Phase 2+, scaffolded in v1).

### 7.2 Bounded activation

An activation is the unit of work. It is short-lived. It produces a Receipt before it exits. It is *not* a long-running process.

```python
def run_activation(plan: Plan, event: TriggerEvent) -> ActivationRecord:
    record = activation.start(plan, event)
    if not admission.gate(plan, event):
        return activation.skip(record, reason=...)
    try:
        # Load 3-layer context (existing context_manager.py)
        ctx = context.load(plan, event, memory)
        # Run experiment(s) under this plan — existing experiment.py runner
        outputs = experiment.run(plan, ctx, event)
        # Emit content-addressed receipt
        receipt = receipts.emit(record, outputs, ctx)
        activation.complete(record, receipt)
        return record
    except Exception as e:
        return activation.fail(record, e)
```

### 7.3 Admission gates (Runtime track owns)

Before any activation runs, the admission gate checks:
1. Plan status is `active` (not paused/archived).
2. All required integrations are connected.
3. < 3 consecutive failures (auto-pause threshold — already exists in `scheduler.py`; re-use).
4. Cost budget not exceeded for the day/week.
5. Tool-replay ledger has remaining budget for this Plan's tools.

If any gate fails, activation is `skipped` with `skip_reason` set. The Surface track renders skipped activations distinctly so the user sees "we tried, here's why we didn't run."

---

## 8. Receipts (Foundation track owns format; Runtime track emits)

A Receipt is a YAML document, content-addressed by sha256. Shape:

```yaml
schema: gtm-os/receipt/v1
activation_id: act_01J...
plan_id: pln_01J...
plan_fingerprint: sha256:abc...
trigger:
  source: cron
  payload: {tick_at: "2026-05-29T09:00:00-07:00"}
started_at: "2026-05-29T09:00:01Z"
completed_at: "2026-05-29T09:01:42Z"
outcome: success            # success | skipped | failed | blocked
tokens_used: 12431
cost_usd: 0.083
inputs:
  - kind: vector_recall
    namespace: facts
    matches: 7
outputs:
  - kind: draft
    uri: "drafts/2026-05-29/ada.md"
    sha: sha256:def...
evidence_uris:              # other receipts this one referenced
  - "receipts/rcpt_01J..."
notes: ""
```

`content_hash` is `sha256(yaml_body)`. Two activations with the same `input_fingerprint` should produce the same `content_hash` — that's the **memoization** edge (prose pattern).

---

## 9. Status judge (Foundation track owns)

A small judge that reads the last N activations for a Plan and writes `activation_status`:

| Status | Condition |
|--------|-----------|
| `up` | Last activation succeeded; expected cadence is being met. |
| `drifting` | At least one of: last activation partially failed, expected cadence is being missed, or admission gates skipped > 30% of recent ticks. |
| `down` | Last activation failed, or auto-paused. |
| `blocked` | Integration disconnected, credentials expired, or admission gates have skipped 100% of recent ticks for a reason the user can fix. |

The judge runs after every activation. Surface renders the status as a small colored badge on the Plan list.

---

## 10. Voice rules (Foundation track owns)

The Soul prompt enforces V1-V9. The validator backstops it.

| Rule | Concrete check |
|------|---------------|
| V1 — No system vocabulary | Regex check against `banned_vocabulary.json` |
| V2 — First person | Output must contain "I'll" or "I" as the actor |
| V3 — Specific cadence | If Plan has a recurring cadence, the paragraph must name a time (regex for `[Mm]on/[Tt]ues/.../[Ss]un` or `[Mm]orning/etc` or time-of-day) |
| V4 — Boundary stated | The paragraph must contain "I won't" or "I will not" or "I'll only" (the "what I won't do" line) |
| V5 — One paragraph | No `\n\n` in `rendered_paragraph` (single paragraph) |
| V6 — No system structure | No bullet markers (`-`, `*`, `1.`, `2.`) in `rendered_paragraph` |
| V7 — User's nouns | Identity-derived nouns must appear if available |
| V8 — Length | 2–8 sentences |
| V9 — Trust tests | Criteria + Constraints sections must each be non-empty |

The CI eval runs all 9 rules over 30 reference inputs.

---

## 11. Sub-agent forking (Phase 2 — Runtime track owns)

When a Plan needs sub-agents (two-of-three on cadence / I/O / reasoning differ), the Composer compiles the Plan into N `Experiment` records. The Reactor launches them as sub-activations. Forking pattern:

```python
def fork_context(parent: ActivationRecord, child_role: str) -> Context:
    """openhuman pattern: child gets system prompt + memory pointers, blank conversation."""
    return Context(
        soul=parent.soul,
        identity=parent.identity,
        plan=parent.plan,
        memory_pointers=parent.memory_pointers,  # references, not full content
        conversation=[],                          # blank
        parent_activation_id=parent.id,
    )
```

Children can't fork further (one level of nesting in v1). Children's receipts merge into parent receipt's `evidence_uris`.

This is **Phase 2** work. Foundation + Runtime scaffold the dataclasses but the forking codepath is gated behind a feature flag `V5_SUBAGENT_FORK` defaulting to false until Phase 2.

---

## 12. Frontend contract (Surface track owns)

### 12.1 New navigation

The Sidebar gains a `Plans` entry, placed **above** Experiments. The Plans view becomes the default home (replacing the existing default — Surface track decides which existing view to keep).

### 12.2 Composer chat

`ComposerChat.tsx` replaces `Chat.tsx`'s role for *new-Plan creation*. The existing chat-to-experiment flow stays — it just isn't the default flow anymore. Composer chat:
- Streams via SSE from `/api/composer/chat`.
- Shows the rendered paragraph in a card the user can edit-by-asking ("can you make it daily instead of weekly?").
- Has a single primary CTA: "Set this up" → calls `compile`, which creates the Plan and redirects to its detail view.

### 12.3 Plans list

Card-per-Plan grid. Each card:
- Plan name (auto-derived from Goal).
- Status badge (colored dot: green=up, yellow=drifting, red=down, gray=blocked).
- Last-activated timestamp.
- Next-scheduled timestamp.
- 30-dot status timeline (one dot per recent activation).

### 12.4 Plan detail

- The rendered paragraph at the top.
- Status timeline (30 most recent activations).
- Activity feed (drafts produced, decisions made, messages sent).
- A "what went wrong?" panel when status is drifting/down/blocked — surfaces skip_reason / error from receipts.
- Buttons: Pause, Run now, Archive.

### 12.5 Activity inbox

Cross-Plan view. Shows everything-that-needs-the-user (drafts to review, integration reconnects needed, manual approvals). Sorted by created_at desc. The user's daily entry point.

### 12.6 Hidden in v1

The existing AgentsView, RulesView, PlaysLibrary, MemoryBrowser, AutomationsView, IntegrationsView — **don't delete them**; just don't show them in the default sidebar. Power-user route `/settings/advanced` exposes them. v5's user surface is Plans + Activity + Settings (Composer + integrations).

### 12.7 Native shell polish (Surface track owns)

- Browser launch: `gtm-os start` opens the default browser at `127.0.0.1:<port>` (already works; verify cross-platform).
- OAuth callback: `127.0.0.1:<port>/oauth/callback` works for Composio's Connect flow.
- System tray on macOS/Linux/Windows: optional in v1, scaffolded for Phase 3.

---

## 13. Phase boundaries

### Phase 1 (weeks 1–3) — all three tracks in parallel

Foundation:
- Plan + Composer + Soul + voice validator + eval set + Plan→Experiment compile + Status judge + Receipt schema + emitter.

Runtime:
- Reactor + cron/chat/manual triggers + admission gates + receipt emission integration + structured-output tool dispatch.
- Webhook + pressure triggers are scaffolded but not user-facing.
- Sub-agent forking is scaffolded behind feature flag.

Surface:
- Composer chat UI, Plans list, Plan detail, Activity inbox, Status timeline, native-shell polish (browser launch + OAuth callback verified).

End of Phase 1: live session where you describe N unrelated tasks; each becomes a working Plan; we watch a Plan run on cron, produce drafts, recover from a forced failure.

### Phase 2 (weeks 4–6) — narrowing parallelism

- Sub-agent forking enabled (Runtime).
- Webhook + pressure triggers user-facing (Runtime).
- Activity inbox actions wired to real workflows (Surface).
- Foundation: identity inference accumulating nouns from accumulated Plans.

### Phase 3 (week 7) — polish + observability

- Replay any past activation from its receipt (Foundation + Runtime).
- Status timeline view richer (Surface).
- Per-Plan cost telemetry; soft-budget warning (Foundation + Surface).
- One-click reconnect for expired OAuth (Surface).

---

## 14. Definition of done per track

### Foundation
- `make test` passes, including new `tests/test_*.py` files.
- CI eval runs all 30 reference inputs through Composer; zero V1-V9 violations.
- A new user can run `gtm-os start`, open chat, type "every Friday morning, find clients who seem stuck and draft check-ins," and the system writes a Plan that passes all four trust tests.
- `/api/plans` GET returns the new Plan; `/api/plans/{id}/markdown` exports it correctly.
- Receipt is emitted after a forced run; `content_hash` matches recomputation.
- Status judge correctly transitions a Plan from `up` → `drifting` after a forced skip.

### Runtime
- A registered Plan with a cron continuity fires on schedule; the Reactor launches a bounded activation; the receipt lands in the DB.
- Admission gates correctly skip an activation when the Plan is paused, integrations are disconnected, or budget is exceeded.
- Manual trigger works from the UI and from `gtm-os run-tick <plan-id>`.
- Structured-output tool dispatch is enforced; a malformed tool call from the LLM is caught and retried, not crashed.
- Sub-agent forking is scaffolded but flagged off (Phase 2 gate).

### Surface
- The default route is `/plans`. The sidebar shows Plans, Activity, Settings.
- Creating a Plan via Composer chat redirects to its detail view.
- The Plans list shows status badges that match the backend's `activation_status`.
- The Activity inbox shows all drafts/approvals across all Plans.
- Native-shell smoke: `gtm-os start` opens the browser to the new Plans home on macOS/Linux/Windows.
- The existing power-user views are reachable from `/settings/advanced` but not in the default nav.

---

## 15. Coordination protocol

- **Sync points**: each track pushes nightly. Parent session reviews diffs and lands cross-track integration commits.
- **Shared-file edits**: only edit your `# V5-<TRACK>:` section. If you need to edit outside it, message the parent session.
- **API contract changes**: if a track wants to change a route or dataclass field after Phase 1 starts, message the parent session first; parent updates this spec, all tracks pull.
- **Test contract**: each track's tests must run green standalone. Integration tests are the parent's job.

---

## 16. What this spec deliberately does not say

- **Branding/visual polish** — Surface track picks tasteful defaults; v5 is shipping working, not pretty.
- **The full V1-V9 wording** — Foundation track drafts `soul.md`; parent session reviews.
- **Composio scope** — Runtime track wires up the existing `composio_tools.py`; which 5-10 toolkits to expose by default is parent's call.
- **Docker / hosted shapes** — out of scope for v1 native-first; both are downstream of this work.

---

## 17. Reference: the v5 design doc

If a question isn't answered here, read [`docs/v5-design.md`](./v5-design.md). If it's still not answered, message the parent session.
