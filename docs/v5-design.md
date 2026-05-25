# Decomposition Layer — v5

**Status.** Replaces v4. Rebuilt on top of the patterns proven by 9 open-source agent/workflow repos. Same product thesis as v4 — beginners describe work in their own words and the system does the system-thinking — but the *runtime architecture* changes substantially. Most of what changes is what we steal from [openprose/prose](https://github.com/openprose/prose) (Markdown-as-contract, Responsibility, Reactor, bounded activations) and [ComposioHQ/trustclaw](https://github.com/ComposioHQ/trustclaw) (3-layer context management, soul prompt, memory store).

**What didn't change from v4:**
- One Plan = one understandable promise.
- Three-level hierarchy: Program (user-visible tag) / Plan (user-visible paragraph) / Skill (internal) / Agent (internal sub-agent).
- Voice constraint: agent never uses system vocabulary.
- Progressively specific loop: agent picks first valuable slice, writes Plan, offers next slice when current works.
- Sub-agent split when at least two of {cadence, I/O surface, reasoning style} differ.

**What changed:**
- **Product framing.** v4 framed this as "a decomposition layer for canned use cases." v5 frames it as **a system that takes any task and stands it up as a working agentic loop**. The product is the generative meta-system, not a single Plan template. Phase 1 ships *generality*, not a canned demo.
- **Voice ships locked.** Soul prompt is authored by us, tested, CI-gated. Identity auto-inferred. No user-tuning surface in v1 — production-ready means voice ships as a known-good asset, not a configuration.
- The Plan is **a Markdown contract**, not free-form prose. The paragraph the user sees is the rendered view of a 6-section contract that the system reads as truth.
- Plans have **status** (`up / drifting / down / blocked`), not just running/stopped.
- The runtime is **bounded activations**, not long-running agents. Continuity lives in the trail, not a process.
- Context management is the **trustclaw 3-layer pattern** (prune → flush-to-memory → compact).
- Tools are **MCP-first + Composio for breadth**, all dispatched as structured outputs (12-factor factor 4).
- Triggers come from anywhere — chat, schedule, webhook, another Plan's pressure — and the agent doesn't know the channel.
- Every activation leaves a **receipt** (content-addressed audit + composition edge).
- Voice is a **Soul prompt section**, layered separately from Identity and User customization (trustclaw's structure).
- The system ships as **one binary in three deployment shapes** — native install (laptop), self-hosted Docker (user's cloud), and hosted (multi-tenant). Storage / scheduler / OAuth callback are all abstracted so the same Composer + Reactor + runner work in every shape. See §2.

---

## 1. The model in one diagram

```
USER VOICE                              SYSTEM RUNTIME
──────────────                          ──────────────

"every Friday morning, find
 clients who seem stuck and
 draft check-ins for me"
        │
        ▼                               ┌──────────────────────┐
   COMPOSER ────── compiles to ─────►   │ PLAN (Markdown)      │
   (an agent that writes contracts)     │  Goal                │
        │                               │  Continuity          │
        ▼                               │  Criteria            │
   "Every Friday morning, I'll          │  Constraints         │
    read your session notes, find       │  Tools (skills)      │
    clients who seem stuck, and         │  Fulfillment (hint)  │
    draft check-ins for you to          └──────────┬───────────┘
    review. I won't message anyone                 │
    myself."                                       │ reactor wakes on:
        │                                          │   timer ticks
        ▼  (user reads, approves)                  │   webhook
                                                   │   chat input
                                                   │   pressure from another Plan
                                                   ▼
                                          ┌─────────────────────┐
                                          │ BOUNDED ACTIVATION  │
                                          │  - load Plan        │
                                          │  - load memory      │
                                          │  - 3-layer context  │
                                          │  - run sub-agents   │
                                          │  - emit receipt     │
                                          │  - update status    │
                                          └──────────┬──────────┘
                                                     │
                                                     ▼
                                          ┌─────────────────────┐
                                          │  STATUS + RECEIPT   │
                                          │  status ∈ {up,      │
                                          │  drifting, down,    │
                                          │  blocked}           │
                                          └─────────────────────┘
```

Two minds. **User voice** speaks only in work nouns/verbs ("every Friday," "clients who seem stuck," "check-ins"). **System runtime** lives entirely in artifacts: contracts, activations, receipts, statuses, memory. They meet at the Plan paragraph — the only surface the user sees.

---

## 2. Deployment topology

The system ships as **one core binary in three deployment shapes**. The Composer, Reactor, runner, 3-layer context manager, receipts, and memory store are identical in every shape. The shell around the core differs: storage backend, scheduler, OAuth callback handling, secrets storage.

This is the [openhuman](https://github.com/tinyhumansai/openhuman) / [holaOS](https://github.com/holaboss-ai/holaOS) pattern: one core (theirs in Rust), multiple shells (theirs: Tauri / Electron). It's also implicit in [12-factor factor 11](https://github.com/humanlayer/12-factor-agents) (trigger from anywhere) — the agent doesn't care where it runs.

### 2.1 Three shapes, one core

| Shape | Who runs it | When you'd pick it |
|-------|-------------|--------------------|
| **Native** | User on their laptop; single installer (`.dmg` / `.exe` / `.deb`); Tauri-style shell wrapping the core binary | Privacy-sensitive work; offline-first users; the "OS feel" |
| **Self-hosted Docker** | User on their cloud (AWS / GCP / Fly / Railway); single container; user supplies `DATABASE_URL` | Always-on triggers (webhooks, cron), heavier memory tree, team-shared Plans |
| **Hosted** | Us, multi-tenant on top of the same Docker image | Lowest-friction; what we run for early users while they evaluate |

Same code in all three. Shell-specific responsibilities:

- **Native**: Tauri shell — auto-update, native menus, system tray, file pickers, OS keychain for secrets, OAuth callback via `127.0.0.1:<port>`.
- **Docker**: Headless; the browser UI hits a deployed URL; OAuth callbacks via the user's domain.
- **Hosted**: Same Docker image + multi-tenant auth + managed Postgres + our shared OAuth callback domain.

### 2.2 Storage abstraction

The biggest deploy-time difference is the database. Cloud has Postgres + pgvector. A laptop should not require the user to install Postgres. So storage is a `Storage` protocol with two adapters:

| Adapter | Backend | Use case |
|---------|---------|----------|
| `SqliteStorage` | SQLite + `sqlite-vec` | Native install. Ships with the binary. Zero config. |
| `PostgresStorage` | Postgres + pgvector | Docker / hosted. User supplies `DATABASE_URL`. |

Same query interface. Migrations differ in SQL flavor; data model is identical. The Reactor, Composer, runner, and 3-layer context manager are storage-agnostic.

**Embedding model:**
- Native default: a small local model via `fastembed` (BGE-small-en-v1.5, ~130 MB, 384-dim). Opt-in to call out to OpenAI's API for higher recall quality.
- Docker / hosted: OpenAI `text-embedding-3-large` (1024-dim) by default (trustclaw's choice). Configurable.

We normalize on dimension per deployment, not across — embeddings don't transfer.

### 2.3 The scheduler is intermittent-tolerant

Cloud runs always-on; cron is straightforward. A laptop is off when the user sleeps, travels, or closes the lid. The Reactor must handle that.

| Adapter | Behavior |
|---------|----------|
| `CloudScheduler` | Background cron job in the container. Wakes the Reactor on every tick. Standard. |
| `LocalScheduler` | OS-level daemon (launchd / Windows Task Scheduler / systemd user unit) wakes the binary even when the shell is closed. On wake, replay missed ticks — bounded by Continuity policy. |

The Plan's `Continuity` section declares how to handle missed ticks. Examples the Composer might write:

- "Run every Friday at 9 AM Pacific." → fires on the next Friday-9-AM-or-after.
- "Catch up on missed runs if the laptop was offline." → replay missed ticks once with `catch_up=true` in the event payload.
- (Default if not specified) → coalesce all missed runs into one catch-up activation.

The user never sees "scheduler" or "ticks" — they see "this Plan runs every Friday morning" and the system handles the rest.

### 2.4 OAuth and integrations

The trickiest difference. OAuth callbacks need a URL the provider can hit.

| Shape | Pattern |
|-------|---------|
| **Native** | Local listener on `127.0.0.1:<ephemeral-port>`. The shell opens the browser to the provider; the provider redirects to localhost; the shell captures the code and hands it to the core. |
| **Docker** | Deployed callback URL on the user's domain. We give the user a copy-paste snippet for the redirect URI when they set up Composio / Stripe / etc. |
| **Hosted** | Our shared callback URL. Secrets are vaulted per-user in our KMS. |

For native, we use Composio's headless flow where supported; fall back to the local-listener pattern otherwise.

**Secrets storage:**
- Native — OS keychain via the `keyring` crate (macOS Keychain / Windows Credential Manager / GNOME Secret Service / KWallet).
- Docker — env vars or an external secrets manager (Vault, AWS Secrets Manager).
- Hosted — our managed KMS.

### 2.5 What's in the core binary vs the shell

**Core binary** (identical in every shape):
- Composer + Reactor + runner + 3-layer context + memory store + receipt emitter
- Native skills (bundled as embedded resources — holaOS pattern)
- HTTP server for the UI to talk to
- JSON-RPC for the shell to talk to (per-launch bearer token auth)
- MCP client (spawns workspace MCP sidecars on demand)
- Composio client (when configured)

**Shell** (shape-specific):
- UI rendering — same React app in every shape, packaged differently (bundled into the binary's HTTP server natively; served from Next.js in cloud)
- OS integrations: notifications, system tray, file pickers, OAuth callback, keychain
- Auto-update (native only; Docker / hosted updates are deploy-time)

The UI hits identical HTTP + WS endpoints in every shape — `http://127.0.0.1:<port>/api` natively or `https://app.example.com/api` in cloud. The UI does not branch on shape beyond reading a `/api/host` info endpoint.

### 2.6 Portability — the Tenet 6 win

Because the Plan is a Markdown contract and storage is abstracted, a user can:

- Move hosted → native: export contracts + receipts, import on the laptop.
- Move native → Docker: same export/import.
- Move Docker → hosted: vice versa.

Credentials don't transfer (they're shape-specific); integrations need reconnect. But the *intent* (Plans) and the *history* (receipts) move cleanly. This is [prose's Tenet 6](https://github.com/openprose/prose) ("nothing held hostage") in practice.

### 2.7 What we lose with this constraint

Honest tradeoffs:

- **Native install means we ship a binary.** Higher friction than "open this URL." Code signing, notarization, auto-update infrastructure all become real work.
- **SQLite + `sqlite-vec` means linear cosine search.** Performant up to ~100K vectors. Past that, native users would want the Docker upgrade.
- **Local embedding model means lower-quality recall** unless the user opts into the cloud embedder. Many will.
- **`LocalScheduler` needs install rights** to register a daemon. Some corporate laptops won't allow it.
- **Three shapes means three test surfaces.** Native install on three OSes; Docker; multi-tenant hosted. CI from day one is the only sustainable path.

I'd argue the user-trust win from "your work, your machine" justifies the cost — but the multi-shape strategy needs the infrastructure investment up front.

### 2.8 Phase 1 implication

The shapes are not free. Phase 1 should pick **one shape** to prove the loop end-to-end before fanning out.

- **Docker first** (weeks 1-3): faster to ship; mentally the same shape as gtm-os's existing Vercel deploy; container + Postgres + deployed callback. Phase 2 (weeks 4-6) wraps the same core binary in Tauri, swaps the storage adapter to SQLite, adds the local listener. Hosted is "deployment-of-Docker," not a separate build.
- **Native first** (weeks 1-5): proves the "your computer" thesis sooner; ~2-3 more weeks because Tauri shell + code signing + auto-update + keychain integrations + local OAuth flow are all real work. Docker follows in Phase 2.

Either path produces all three shapes eventually. The choice is which thesis you want to demo first. **This is open question Q4 below.**

---

## 3. The Plan is a Markdown contract

This is the single biggest change from v4.

**v4:** "The Plan is a short paragraph the agent writes. It compiles to gtm-os primitives via TrustCall." Problem: the paragraph and the compiled YAML are two surfaces for one intent. They will drift. When they disagree, which one is right? We never said.

**v5, from prose Tenet 1:** *The Markdown is the contract.* Everything else is derived. When derived disagrees with contract, the contract is right. There is no second authored surface for intent.

The contract has six sections (from prose's Responsibility). The user types one paragraph; the Composer compiles it into the six. The user sees the rendered paragraph, never the sections directly — but the agent reads the sections.

### 3.1 The six sections

```markdown
---
name: weekly-client-check-ins
kind: plan
program: coaching-business
voice: en-conversational
---

### Goal

Every Friday, clients who have not been heard from in two weeks receive a
thoughtful, non-generic check-in drafted from their session notes and ready
for the coach to send.

### Continuity

- Run every Friday at 9 AM Pacific.
- Catch up on missed runs if the laptop was offline (run at next launch).
- A check-in is fresh for 7 days; after that, regenerate.

### Criteria

- The check-in references something specific from the most recent session notes,
  not a generic "how have you been?"
- If the notes are too thin (< 100 words), flag the client for review instead
  of drafting.
- The check-in fits in one screen — under 100 words.

### Constraints

- Never send anything; only draft for review.
- Never contact a client twice in one week.
- If a client has been quiet for over a month, escalate to the coach instead
  of drafting silently.

### Tools (Skills)

- read_session_notes
- detect_stale_relationships
- draft_warm_message
- save_to_review_inbox

### Fulfillment

Prefer the local `client-check-in` system if present. Otherwise compile a
fresh activation that uses the four skills above.
```

This is the truth. The paragraph the user reads is rendered from these sections, in the agent's voice, with all system terms stripped:

> "Every Friday morning at 9, I'll read your session notes, find clients who haven't heard from you in two weeks, and draft a check-in for each one — specific to what came up in their last session, not a generic 'how have you been?' I'll set them aside for you to review in your check-in inbox. I won't message anyone myself. If a client's notes are too thin, I'll flag them. If they've been quiet for over a month, I'll bring them to you instead of drafting."

Same intent. Two surfaces. The Markdown is the truth.

### 3.2 Why this matters

Three concrete wins from making Markdown the contract:

1. **Refactor without drift.** If we change the runtime (rebuild on a new orchestrator, swap memory backends, switch model providers), the contracts don't move. They re-derive everything downstream.
2. **Portability** (prose Tenet 6). A contract authored on our platform should run on any Prose-Complete host. If we ever want to give the user "export your Plans and run them somewhere else," this is how.
3. **Inspectability.** A user can ask "show me the contract for this Plan." It's six clear sections. They can edit any section without losing the rest. (We won't show this by default — but it's there.)

### 3.3 Versioning, IDs, fingerprints

Each Plan has a stable ID (`name`) and a content fingerprint (hash of all six sections). When the user approves a change to a Plan, the new fingerprint is recorded; the old one is preserved. This is what lets us say "the Plan changed last Tuesday — here's what was different" without keeping a separate revision log.

---

## 4. The four statuses

From prose. Every Plan reports one of:

| Status | Meaning | What the user sees |
|--------|---------|--------------------|
| `up` | The goal is being met; the most recent activation succeeded and produced evidence the criteria held. | "Running well." Green dot. |
| `drifting` | At risk. The goal could fail without attention. Examples: skipped runs piling up, criteria starting to fail, dependency soft-fail. | "Needs a look." Yellow dot. |
| `down` | The goal is not currently true. The most recent activation failed criteria or could not run at all. | "Not working." Red dot. |
| `blocked` | The system can't determine status without external help. Examples: integration disconnected, credentials expired, ambiguous evidence. | "I need you for a second." Red dot + action item. |

**Why these four, not "running / stopped":**
- `running / stopped` is about the *execution loop*. A Plan can be "running" (cron firing) while the *goal* isn't being met (every run fails criteria).
- The user wants to know about the goal, not the loop.
- `drifting` is the most useful new state. It catches early failure modes (skipped runs, partial failures, soft criteria misses) before they become `down`.

**Status is computed, not set.** Every activation emits evidence. A small judge (prose-style) reads the evidence and writes status. The judge prompt lives in `judge.md` for each Plan kind, derived from Criteria + Continuity. No user-authored judge file is required for v1 — a default judge reads the six sections of the contract and asks the four questions: is the goal true? are continuity requirements met? are criteria satisfied? are constraints violated?

---

## 5. Bounded activations, not long-running agents

v4 implicitly assumed a long-running agent process. Looking at the ecosystem: nobody does this. They all use **bounded activations + durable state**.

### 5.1 The reactor

Every event wakes a bounded activation:

```
event types:
  - timer tick                (every Friday 9 AM)
  - webhook                   (Stripe payment, GitHub star, etc.)
  - chat message              (user typed in the app)
  - pressure                  (another Plan's status went unhealthy)
  - manual                    (user clicked "run now")
  - judge drift               (status went drifting → down, triggers recovery)
  - fulfillment completion    (a sub-Plan finished, parent should reconcile)
```

The reactor's only question:

> Given this event and the current durable state, which Plans need reconciliation now?

Picks the smallest set. Schedules an activation. Activation runs to completion, emits receipt + updated status, exits. **No process stays alive between activations.** Continuity lives entirely in the trail.

This is prose's Tenet 3 and 12-factor's factor 6 (launch/pause/resume) made concrete. The benefits:
- The system can restart at any time without losing work.
- We can replay any past activation from its receipt for debugging.
- We can fork an activation (try a variation) cheaply.
- Webhooks can resume work without deep integration — they just append an event.

### 5.2 What an activation does

```
load_contract(plan_id)          # the Markdown
load_state(plan_id)             # last status, last receipt, memory pointers
load_memory(plan_id, topic)     # relevant memories (cosine over pgvector)
compile_thread(event, state)    # build the context window
run_agent_loop(plan, thread)    # the runner
emit_receipt(activation_id)     # content-addressed audit
update_status(plan_id, status)  # up/drifting/down/blocked
```

The runner is forge-shaped: send messages to the LLM, parse tool calls, validate args, execute (batch-aware), append result, loop until terminal tool or max iterations. The terminal tool for an activation is `done(summary, evidence)` — the activation always ends with a structured summary the judge reads.

### 5.3 Memoization (prose pattern)

If the activation's *input* (contract fingerprint + event + memory pointers) is identical to a recent run, the harness can reuse the verdict for free. This matters for cron-fired Plans where most ticks produce "nothing to do" — we don't want to pay an LLM call for every tick just to learn nothing changed.

Implementation: every activation has an input fingerprint (hash of contract + event + memory snapshot). Receipts are keyed by input fingerprint. On a new activation, we check: does an identical fingerprint exist within the freshness window declared in `Continuity`? If yes, reuse. If no, run.

---

## 6. Three-layer context management (trustclaw pattern)

Once you have a Plan running for months, context-window management is most of the problem. trustclaw's 3-layer pattern is the most production-ready I've seen. We adopt it whole.

| Layer | Trigger | Action |
|-------|---------|--------|
| **L1 — Pruning** | Before every LLM call. Context > 30% of window. | Tool results > 4KB get trimmed to first 1500 + `[trimmed]` + last 1500 chars. Protected zone: last 3 assistant turns never pruned. |
| **L1 — Hard clear** | Context > 50% of window. | Replace oldest tool results > 50KB with `[Old tool result content cleared]`. |
| **L2 — Memory flush** | Approaching compaction threshold. | Single LLM call with only `remember(fact)` and `recall(query)` tools and the recent conversation. Prompt: "save anything durable before this gets summarized away." |
| **L3 — Compaction** | After response. Context > window - 20K reserve. | Walk backwards from newest messages, accumulate token estimates, stop at 20K keep-recent. Snap forward to nearest user/assistant boundary (never split tool-call / tool-result pair). Summarize everything before that. Persist with optimistic lock on `compactionCount`. |

**Storage.** Memory is pgvector with 1024-dim embeddings (OpenAI `text-embedding-3-large`). Cosine similarity for recall. Two namespaces per Plan: `facts` (durable, agent-saved) and `events` (auto-ingested from receipts). Memory is Plan-scoped; cross-Plan sharing happens at the Program tag layer.

**Why this is non-negotiable for v5.** Without it, a Plan running on a weekly cadence will hit context limits within a few months and start dropping memory of the user's preferences silently. trustclaw's whole architecture is built around this; openhuman's archivist module does the same thing. Adopting it now saves us from rebuilding it later.

---

## 7. Voice — Soul (default, locked) + Identity (inferred)

Trustclaw splits its system prompt into Soul / Identity / User. For v1, **we ship only Soul + Identity**. The User layer ("be more direct with me") is *not* exposed in v1. The voice is our product, not the user's to tune; production-ready means the voice ships locked.

| Layer | Content | Authored by | Mutable? |
|-------|---------|-------------|----------|
| **Soul** | The voice rules (V1-V9). "I help this user with their work. I don't speak in system terms. I write paragraphs, not bullet lists. I have opinions. I'm careful with external actions, bold with internal ones." | Us, once. Tested. Locked. | No. CI-gated. |
| **Identity** | The user's work context: what nouns they use, which integrations they've connected, what Plans already exist. Auto-filled from onboarding + accumulated Plan activity. | The system, inferred. | Yes, automatically. |
| **Plan-specific** | The contract's six sections rendered as system-prompt context. | Per-activation. | Per-activation. |
| **Memory** | Top-N cosine matches from `facts` namespace. | Per-activation. | Per-activation. |
| **Tools** | The available skills + their schemas. | Per-activation. | Per-activation. |

The Soul is treated as **a tested, evaluated, locked-down asset** — not a configuration. PraisonAI pattern: 20-30 reference paragraphs the Composer should be able to produce; CI fails if a Soul change drops the score on any reference output. Drift in voice is a regression, not a feature change.

Identity is inferred, never edited directly. As the user accumulates Plans, the Identity layer accumulates their work vocabulary; the Composer reads it on every turn so it speaks in their words instead of generic ones. This is how we get a user-specific voice without exposing a tuning surface.

If, post-v1, evidence shows users *want* to tune voice, we add the User layer back. Until then: don't ship the knob.

### 7.1 The hard voice constraint

The Soul prompt is responsible for this:

> Never use system vocabulary in user-visible text. Never say: step, tool, workflow, rule, play, agent, automation, experiment, integration, trigger, phase, run, tick, prompt, system, configuration, sub-agent, activation, receipt, status. Always say the user's work words: client, session, draft, check-in, Friday, week, inbox, message.

This is mechanically enforceable. Two complementary checks:
1. **Validator on Composer output** — regex check on the rendered paragraph; if any banned word slips through, regenerate.
2. **Eval set** — 30 example user inputs → expected paragraph shapes. CI runs the Composer on them; if any output contains a banned word, the build fails.

---

## 8. Tools — MCP first, Composio for breadth, all structured outputs

Three layers of tool access, from native to fallback:

### 8.1 Native skills

Markdown files in `skills/` (Claude Code / holaOS pattern). Each skill is:

```
skills/
└── draft_warm_message/
    ├── SKILL.md           # Description + when to use + parameters
    ├── prompt.md          # The actual prompt fragment
    └── examples/
        ├── good-1.md
        ├── good-2.md
        └── bad-1.md       # With a comment explaining why
```

Skills are reusable, version-controlled, evaluable. The Composer compiles a Plan's `### Tools` section to the set of skills it needs. Skills declare prerequisites (forge pattern): `draft_warm_message` requires a prior call to `read_session_notes`.

### 8.2 MCP tools

Workspace-scoped MCP servers (holaOS pattern). The Plan's workspace declares which MCP servers it has access to. The runtime spawns the sidecar (if not already running), fetches the tool list, and merges them into the available tool set.

### 8.3 Composio router

For breadth, we use Composio's tool router (trustclaw pattern). Follows trustclaw's exact workflow:

```
COMPOSIO_SEARCH_TOOLS         # search by use case ("send a slack message")
COMPOSIO_MANAGE_CONNECTIONS   # generate OAuth URL if not connected
COMPOSIO_WAIT_FOR_CONNECTIONS # block until user completes OAuth
COMPOSIO_MULTI_EXECUTE_TOOL   # batch execute with reasoning + session_id
COMPOSIO_REMOTE_WORKBENCH     # persistent Python sandbox for processing
```

Composio gives the user 500+ tools without us writing 500+ integrations. The cost: every Composio tool call is structured output that the runner validates and executes.

### 8.4 The contract surface

All three are dispatched through one interface — structured output (12-factor factor 4):

```python
class ToolCall:
    intent: str                 # "draft_warm_message", "stripe.create_payment_link", etc.
    args: dict                  # validated against the tool's Pydantic schema
    thought: str                # the LLM's stated reason

class ToolResult:
    tool: str
    ok: bool
    value: Any | None
    error: str | None
```

The runner doesn't care which layer a tool came from. To the agent, they're all just intents.

---

## 9. Sub-agents (forked context, not nested loops)

When a Plan needs sub-agents (two-of-three rule from v4: cadence, I/O, reasoning style differ), the runtime forks the context. From openhuman's `subagent_runner`:

```
parent_thread
  ├── tool_call: spawn_sub_agent(role="monitor", plan="watch for replies")
  │     │
  │     ▼ fork point — copy system prompt + memory pointers, blank conversation
  │   child_thread
  │     ├── ... runs independently with its own budget ...
  │     └── done(summary, evidence)
  │           │
  │           ▼ result returned as tool result
  │     {summary: "3 new replies, 1 needs your attention", evidence: [...]}
  └── parent continues with the summary
```

**Key properties:**
- Children don't see the parent's full thread, just the parent's instruction + a memory pointer.
- Children can't spawn their own children by default (one level of nesting; explicit opt-in for deeper).
- Children have their own cost / step budget; they can fail without bringing down the parent.
- Children's evidence merges back into the parent's receipt.

**This is not visible to the user.** The user sees one paragraph and one status. The fork is implementation.

---

## 10. Trigger anywhere

12-factor factor 11. trustclaw and multica prove it works in production. Adopt fully:

Every Plan can be triggered by:
- Chat (user types a message)
- Schedule (cron from Continuity section)
- Webhook (declared in `### Triggers` if needed, or auto-derived)
- Pressure (another Plan's status went unhealthy)
- Manual run (user clicks)
- Another Plan completing (dependency edge)

The activation gets a `source` field on the event. The agent uses it for context but does not branch behavior on it — the same Plan, triggered the same way, produces the same outcome regardless of source.

Channel-specific UX (Telegram message format vs web message format) is a *rendering* concern at the edge, not a runtime concern.

---

## 11. Admission gates and safety (multica + prose)

Before launching any scheduled / triggered activation, the reactor runs admission checks:

```python
def can_activate(plan, event):
    # Multica's gate, generalized.
    if plan.archived:
        return Skip(reason="plan archived")
    if not all(integration.connected for integration in plan.required_integrations):
        return Skip(reason=f"{disconnected.first().name} not connected")
    if plan.consecutive_failures >= 3:
        return Skip(reason="auto-paused after 3 consecutive failures, awaiting review")
    if budget_exceeded(plan, current_period):
        return Skip(reason="cost budget exceeded for this period")
    return Go()
```

A skipped activation is *recorded* (so the user sees "we tried but couldn't, here's why") and may produce **pressure** that triggers a recovery flow. Pressure is the prose-style escalation: just strong enough to wake another bounded activation, not a separate workflow language.

**Auto-pause after 3 consecutive failures.** From multica. Standard. The user sees status = `blocked` and is told what failed and what they can do.

**Cost budget per Plan per period.** Plans declare a soft and hard cost ceiling (auto-derived from their cadence + tool usage). Hitting the soft ceiling produces pressure. Hitting the hard ceiling skips.

**Tool-replay budget ledger.** From holaOS / openhuman. If the same tool gets called with the same arguments more than N times in a single activation, the runner bails — we've found a loop.

---

## 12. The Composer (the only user-facing agent)

The Composer is the conversational agent the user talks to. It does four things:

1. **Listen.** User describes work in their own words.
2. **Compile.** Turn that into a Markdown Plan contract (the six sections).
3. **Render.** Translate the contract back into a paragraph in the agent's voice.
4. **Offer next slice.** When the Plan is working, propose the next coherent slice.

**The Composer is a single bounded agent.** It does NOT execute Plans — it only authors them. The reactor + activations execute. This separation is critical: the Composer is short-lived (one turn at a time), Plans are long-lived.

**The Composer's hard rules** (from v4 V1-V9, plus prose tenets):

```
1. Never use system vocabulary.
2. Always produce a Plan, not a clarifying question.
3. When the goal is broad, pick the first coherent slice and write that.
4. End every Plan with a "what's next?" sentence offering the next slice.
5. Never compile a Plan that fails the four trust tests.
6. Never offer to do something the available tools can't do — instead, name
   what's missing in the user's words ("I can't see your Stripe account yet —
   want to connect it?").
7. The Composer doesn't run the Plan. After the user approves, the reactor
   takes over. The Composer is just the writer.
```

---

## 13. Receipts (audit + composition edge)

Every activation produces a receipt. Content-addressed, signed, verifiable.

```yaml
kind: receipt
version: 0
activation_id: 01HRX...
plan_id: weekly-client-check-ins
plan_fingerprint: sha256-...
event:
  type: timer
  scheduled_for: 2026-05-29T09:00-08:00
inputs:
  memory_pointers: [...]
  contract_sha: sha256-...
outputs:
  summary: "Drafted 3 check-ins for review. Flagged Tanya — only 1 session note."
  status: up
  evidence:
    - skill: read_session_notes
      ok: true
      count: 14
    - skill: detect_stale_relationships
      ok: true
      flagged: 3
    - skill: draft_warm_message
      ok: true
      drafts: 3
costs:
  llm_input_tokens: 4231
  llm_output_tokens: 812
  llm_cost_usd: 0.018
  tool_calls: 7
duration_ms: 12318
fingerprint: sha256-...   # this receipt's own hash
```

**Why receipts matter:**
- The audit trail (prose Tenet 5: trust demonstrated, not claimed).
- The composition edge: when one Plan depends on another, the dependent activation passes the upstream receipt as evidence.
- Memoization: if a new activation's input matches an existing receipt's input, the harness can reuse it.
- Debugging: replay any past activation from its receipt to understand what happened.

---

## 14. The user surface

What the user actually sees, end-to-end:

### 14.1 Composer chat

A single chat thread per Program tag, or one if they don't use tags. The Composer's last message is always a Plan paragraph or a "what's next?" offer. No clarifying-question-only messages.

### 14.2 Plans list

A list of Plans the user has approved. Each row shows:
- Plan title (3-7 words, written by the Composer).
- One-line summary of the goal.
- Status dot (green/yellow/red/red-with-action).
- Last activity ("drafted 3 check-ins yesterday at 9 AM").
- (Click to expand.)

### 14.3 Plan detail

When expanded, shows:
- The full paragraph (the rendered contract).
- Status with reason ("up — last 4 runs succeeded").
- Recent activity log (one line per receipt: "Friday May 22 — drafted 3 check-ins, flagged Tanya").
- An inbox of items the Plan produced that need review (drafts to send, flagged clients).
- Edit / Pause / Stop / Delete buttons.
- (Power user toggle: "show the contract.")

### 14.4 Activity inbox

Cross-Plan inbox of things that need the user's attention. Each item is a structured output from an activation: a draft to review, a flagged client, an approval request. Each item has a Plan it belongs to and an action ("send this", "skip this", "tell me more about why").

### 14.5 What's deliberately NOT shown

- Skills.
- Sub-agents.
- Receipts.
- Activations.
- Memory.
- The contract markdown (unless toggled).
- Pressure / drifting in raw form (user sees "needs a look" instead).
- Tool calls.

If a power user wants to see the machinery, there's a developer mode. By default: chat, Plans list, Plan detail, activity inbox. That's it.

---

## 15. Phased build — production-ready v1, then breadth

The product thesis ("a system that takes any task and stands it up as an agentic loop") means **the v1 Composer can't be tuned for one shape of work**. It needs to handle the full surface area on day one. The phasing below sequences *infrastructure*, not use cases — the demo at each phase is whatever arbitrary work you describe live.

v4 phased by use case ("weekly check-ins" → "social media manager" → "coaching business"). v5 phases by capability — generative meta-system from week 1, multi-agent loops in weeks 4-5, polish + observability in week 6-7.

### Phase 1 — Generative loop, single deployment shape (weeks 1–3)

**Goal:** the full Composer → Reactor → runner → receipt loop works against any user-described task, in one deployment shape, with real integrations.

**What ships:**
- Composer (Soul prompt locked; Identity auto-filled; voice eval set passing in CI).
- Six-section contract compiler (user paragraph → Markdown contract → rendered paragraph).
- Reactor with chat, cron, and webhook triggers.
- forge-shaped runner with batched tool calls, retry, terminal tool.
- 3-layer context manager (trustclaw pattern).
- Native skills (~12 covering read-source / classify / draft / save) + MCP client + Composio router (with the Search → Connect → Execute → Clean-up workflow).
- Receipt emission + judge → status (`up / drifting / down / blocked`).
- Admission gates + auto-pause after 3 consecutive failures + cost budget.
- Plans list + Plan detail + activity inbox UI.
- Storage adapter for the chosen shape (Postgres+pgvector for Docker-first; SQLite+sqlite-vec for native-first).
- Scheduler adapter for the chosen shape.
- Health checks, error boundaries, structured logs, one-click "export this Plan + receipts."

**Demo:** live session, you describe N unrelated tasks in plain English. Same system stands up each one. We watch them run on their cadences, produce drafts in the inbox, recover from a forced failure (kill the Composio connection mid-run; system goes to `blocked` cleanly).

**Explicitly NOT in Phase 1:**
- Multi-agent / sub-agent decomposition (Phase 2).
- The second deployment shape (Phase 2).
- Programs (the tag). Plans live in a flat list.
- Cross-Plan pressure / dependency edges.
- Memory tree projections.
- User-layer voice tuning.
- "Show me the contract" power-user toggle.
- Flow / Loop visualization views.

### Phase 2 — Multi-agent + second deployment shape (weeks 4–6)

**Goal:** sub-agent decomposition where it earns its keep, plus the second deployment shape so the same Plans run in both.

**What ships:**
- `subagent_runner` + `fork_context` (openhuman pattern).
- Two-of-three split detection in the Composer (cadence / I/O / reasoning).
- Parent/child receipt merging.
- Second deployment shape (whichever wasn't Phase 1; same core binary, different shell + storage + scheduler + OAuth adapters).
- Migration tooling for moving a Plan between deployment shapes.

**Demo:** live session, you describe work with mixed cadences ("every weekday morning, post the queued content; all day, watch for replies and Telegram me anything urgent; once a week, summarize what worked"). The Composer splits it into sub-agents under one Plan paragraph. We watch one Plan execute as three loops. Then we move the Plan between shapes and watch it keep running.

### Phase 3 — Polish + observability (week 7)

**Goal:** the things that separate "works on demo day" from "production-ready."

**What ships:**
- Replay any past activation from its receipt (debugging affordance).
- Eval suite for Composer voice + contract compilation correctness (Soul drift, banned-vocabulary detection, six-section completeness).
- Per-deployment-shape CI: Docker container tests, native install/uninstall tests on macOS / Windows / Linux, multi-tenant tests.
- Status timeline view (the row of dots showing the last 30 activations' statuses for each Plan).
- Cost telemetry per Plan; soft-budget warning before hard-budget skip.
- One-click reconnect for expired OAuth.

### Beyond v1 (later)

- Programs (the user-visible tag) when there's evidence of Plan-list overload.
- Cross-Plan composition (pressure edges).
- Memory tree projections (openhuman pattern) when recall quality plateaus on flat search.
- Flow + Loop visualization views.
- The third deployment shape if Phase 1 + 2 only covered two.
- User-layer voice tuning if evidence shows users want it.

---

## 16. What's worth pushing back on

Three places where I'm not yes-manning the ecosystem patterns:

**16.1 We do not adopt prose's full ProseScript language.**

ProseScript is the imperative scripting layer for declaring choreography (order, loops, conditionals, parallelism, retries). It's powerful, but it's a *second authored surface* — exactly what Tenet 1 warns against. We adopt prose's Responsibility (the standing-goal Markdown) and Reactor (evented reconciliation) but NOT ProseScript. The Composer + the runner handle order and parallelism automatically; the user never writes choreography.

**16.2 We do not adopt openhuman's full memory tree.**

The memory tree (global / topic / source projections) is great at scale but premature for v1. We start with a flat pgvector store (trustclaw pattern) and grow into tree projections when we have evidence of recall problems.

**16.3 We do not show the contract by default.**

prose makes the contract the primary surface — they're a developer tool. We're a consumer tool. The user sees the paragraph. The contract exists, the user can request it, but it is not the home view. (This is the biggest place we diverge from prose, and it's deliberate.)

---

## 17. Open questions for you

Your latest direction answered the first two questions I had open in the previous draft, so they're folded in here as resolved decisions:

**Resolved — no demo Plan to pick.** The product is generative. The system takes any task and stands it up as an agentic loop. Phase 1's "demo" is whatever arbitrary work you describe live, not a canned use case.

**Resolved — Soul ships as the locked default.** I draft the Soul prompt + the eval set in Phase 1 week 1 so the voice has a tested target from day one. The User-tuning layer is dropped from v1. Identity is auto-inferred.

What's still open:

**Q3 — Where Markdown contracts live.**

- **(a)** Plans as rows in the storage backend; each contract section is a column. Markdown serialization is the export format.
- **(b)** Plans as Markdown files in object storage / a `plans/` directory; thin index in the storage backend.

(a) is faster to query, simpler to migrate, easier to make atomic. (b) is more aligned with [prose's Tenet 6 (portability)](https://github.com/openprose/prose). With "production-ready v1" as the operating principle and SQLite+sqlite-vec on native, I'm leaning **(a) — rows everywhere — with the Markdown serializer as a first-class export**. Promote to (b) only if portability becomes a shipped feature.

**Q4 — Which deployment shape goes first?**

From §2.8:

- **Docker first** (weeks 1-3) — faster end-to-end loop. Native shell wraps the same core in Phase 2 (weeks 4-6).
- **Native first** (weeks 1-5) — proves the "your computer" thesis as the headline; ~2-3 weeks slower because Tauri shell + code signing + auto-update + keychain + local OAuth flow are real work. Docker follows in Phase 2.

My lean: **Docker first** for v1 because the generative loop needs to be reliable before we add the native-shell complexity on top. But if "runs on your machine" is the headline message for v1, native-first is the correct call and Phase 1 stretches accordingly.

Answer Q3 and Q4 and I'll start Phase 1.

---

## 18. Summary — what's changed at the runtime level

| Concept | v4 | v5 |
|---------|-----|-----|
| Product framing | A decomposition layer for canned use cases | A self-configuring system that takes any task and stands up an agentic loop |
| Authored intent | Plan paragraph | Markdown contract with six sections |
| Truth source | Implicit (paragraph + compiled YAML) | Explicit (Markdown only; everything derived) |
| Plan structure | Goal + Boundary | Goal / Continuity / Criteria / Constraints / Tools / Fulfillment |
| Status | Running / Stopped | up / drifting / down / blocked |
| Runtime model | Long-running agent | Bounded activations + durable continuity |
| Trigger model | Schedule + chat | Schedule + chat + webhook + pressure + manual + dependency |
| Context management | "TrustCall" + memory | 3-layer (prune → flush → compact) + pgvector or sqlite-vec |
| Voice | V1-V9 in one block | Soul (locked default, CI-gated) + Identity (auto-inferred). No user-tuning surface in v1. |
| Tools | Composio | Native skills + MCP + Composio, all structured outputs |
| Sub-agents | Two-of-three split, mechanism unspecified | Forked context (openhuman pattern), Phase 2 |
| Audit | Implicit | Content-addressed receipts |
| Safety | "Trust tests" | Admission gates + cost budget + tool-replay ledger + auto-pause |
| Decomposition | Internal to the Plan paragraph | Internal to the contract; cross-Plan composition via pressure |
| Deployment | Implicit Vercel-shape | One core binary, three shapes (native / self-hosted Docker / hosted). Storage / scheduler / OAuth all adapter-shaped. |

What stayed:
- Voice constraint (V1-V9).
- One Plan = one understandable promise.
- Three-level hierarchy (Program tag / Plan / Skill / Agent / Action).
- Progressively specific loop.
- Trust tests (now encoded in the contract: Criteria and Constraints are the formal version of the trust tests).
- The Composer's job: write Plans the user can explain back, never use system vocabulary.

v5 is the same product with a real runtime architecture, deployable on three shapes, generative from week 1. Phase 1 is 3 weeks (generative loop on one shape). Phase 2 is 3 weeks (multi-agent + second shape). Phase 3 is 1 week (polish + observability). **End of week 7** — production-ready v1: arbitrary user-described work stands up as a Plan, runs on cadence in two deployment shapes, recovers from failures cleanly, ships with a CI-gated voice + receipt-based audit.
