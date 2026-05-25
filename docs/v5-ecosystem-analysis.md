# Ecosystem Analysis — 9 Repos, Code-Level Read

**Purpose.** v4 of the decomposition layer was abstracted on top of gtm-os primitives. This document is a code-level (not README-level) read of the 9 repos you named — what they actually do, what their core insight is, what we should steal. Synthesis and v5 proposal follow in the companion document.

**Repos analyzed:**
1. [antoinezambelli/forge](https://github.com/antoinezambelli/forge) — Python, tool-calling reliability layer
2. [MervinPraison/PraisonAI](https://github.com/MervinPraison/PraisonAI) — Python, multi-agent framework
3. [humanlayer/12-factor-agents](https://github.com/humanlayer/12-factor-agents) — design principles
4. [ComposioHQ/trustclaw](https://github.com/ComposioHQ/trustclaw) — TypeScript, personal AI with 500+ tools, OAuth, sandboxing, cron
5. [tinyhumansai/openhuman](https://github.com/tinyhumansai/openhuman) — Rust + React/Tauri, community AI assistant with memory tree
6. [multica-ai/multica](https://github.com/multica-ai/multica) — Go + TypeScript, Linear-like task management with agents as teammates
7. [openprose/prose](https://github.com/openprose/prose) — Markdown contract language for agent workflows (Reactor, OpenProse, Responsibilities)
8. [holaboss-ai/holaOS](https://github.com/holaboss-ai/holaOS) — Electron desktop, work-streams + sub-agents + workspaces
9. [soxoj/maigret](https://github.com/soxoj/maigret) — Python, OSINT username lookup across 3000+ sites

---

## 1. forge — *the reliability layer*

**What it is.** A thin Python library between your LLM client and your tools. Three primitives: `ToolSpec` (JSON Schema → Pydantic), `ToolDef` (schema + callable + prerequisites), `Workflow` (named bag of tools + required_steps + terminal_tool). The `WorkflowRunner` is the agentic loop: send messages, parse tool calls, validate args via the Pydantic model, execute (batch-aware), append result, loop. Retry logic, max-iterations, batch tool execution, context-budget management, and a `StepEnforcer` for "you must call X before Y" all live in the runner, not the client.

**Core insight.** *Reliability and structure are runner concerns, not model concerns.* The model just emits JSON; the runner validates, retries on malformed output, enforces required steps, isolates tool errors, manages context, and decides when to stop. The runner is small enough to read end-to-end (~400 lines) and you can completely understand what it does — which is the point.

**Prerequisites are conditional dependencies.** A `ToolDef` declares `prerequisites: List[str | dict]`. A string means "any prior call to this tool"; a dict means "a prior call with matching arg." This is how forge encodes *"if you draft, you must have read first"* without inventing a graph DSL.

**Reusable patterns for v5.**
- The Pydantic-from-JSON-Schema trick (one source of truth: the model schema).
- Retry-on-malformed-output as a rescue step, not a hard fail.
- Required-step enforcement as a tool-precondition, not a control-flow graph.
- Batch tool execution as a default (LLMs increasingly emit multiple tool calls per turn).
- Terminal tool = explicit "done" signal, not an iteration counter.

**Not for us.** Forge is single-agent. No nesting, no workspaces, no scheduling, no surfaces. It's a *runner*, not a *system*.

---

## 2. 12-factor-agents — *the principles*

**What it is.** Twelve design principles by Dex (humanlayer.dev). Not a framework — opinions backed by working code snippets. The thesis: **"good agents are mostly software, not just LLM + tools."** Most production-facing agents in market aren't built with frameworks; they're hand-rolled to control prompts, context, control flow, and state.

**The twelve, terse:**
1. **Natural language → tool calls.** Atomic conversion: "create payment link for $750" → `{intent: "create_payment_link", amount: 750}`. Deterministic code dispatches. (= forge's whole runner, but as a single conceptual move.)
2. **Own your prompts.** No framework black boxes. Prompts are first-class code, testable, evaluable.
3. **Own your context window.** Don't use the standard `[role: user, content: ...]` format if a custom XML/YAML thread serializer is more token-efficient. The thread is just a list of events; you control how they render.
4. **Tools are structured outputs.** The LLM emits JSON; your switch statement dispatches. "Tool call" is a UX overlay, not a semantic primitive.
5. **Unify execution state and business state.** Don't separate "current step / retry count / pending approval" from "history of events." Everything is in the thread. Forking, resuming, debugging, and human observability all fall out for free.
6. **Launch / pause / resume with simple APIs.** Agents are programs. Webhooks resume them from where they left off. State is the thread; webhook just appends a `response_from_human` event.
7. **Contact humans with tool calls.** Don't switch between "text reply" and "tool call." Always output structured JSON; one of the intents is `request_human_input` with `urgency` / `format` / `choices`. Then break the loop, wait for a webhook, and resume.
8. **Own your control flow.** The agent loop is a switch on tool intent. Some tools break the loop (`request_clarification`, `create_issue`); some pass results back to the LLM (`fetch_git_tags`); some run async with approval (`deploy_backend`). You author this — not the framework.
9. **Compact errors into context.** When a tool fails, append the error to the thread and try again. Cap consecutive errors (~3) to prevent spin-outs. Past that, escalate to a human.
10. **Small, focused agents.** 3-10 steps, maybe 20 max. Past that, context grows, attention diffuses, failures cascade. Split into multiple agents handing off to each other.
11. **Trigger from anywhere.** Slack, email, SMS, cron, webhook, UI. Agents respond on the same channel they're triggered on. Combined with launch/pause/resume + tool-based human contact, this is humanlayer's whole product.
12. **Stateless reducer.** The agent is a pure function: `(thread) → next_event`. Stateless. Persistent state lives in the thread, not the runtime.

**Core insight.** *Frameworks hide the parts you most need to control.* Production agents are bespoke because the prompt, the context-window builder, the tool-dispatcher, the error-handler, and the control flow are all places where the model lives or dies, and each one needs to be tuned for the specific workflow. The framework's job is to give you the loop and the schema, not to author your judgment.

**Reusable patterns for v5.** This is the *epistemic backbone* for everything that follows. Especially:
- Factor 5 (unified state): the user-visible Plan and the internal execution log are the same artifact.
- Factor 7 (humans as tools): `request_approval`, `ask_user`, `escalate` are tool calls, not special UI events.
- Factor 10 (small agents): two-of-three split rule from v4 stays. 3-20 steps per agent.
- Factor 11 (trigger anywhere): the agent doesn't care if the trigger is Telegram, cron, or a webhook — it's all `event → thread.append → loop`.

---

## 3. trustclaw — *the working personal AI*

**What it is.** A working personal AI built on Composio's 500+ tool router. Next.js 15 + tRPC + Better Auth + Postgres + Redis. Web chat, Telegram bot, and cron-triggered runs all flow through the same `prepareAgentRun()` entry point. Uses Vercel AI SDK's `ToolLoopAgent` with Anthropic Claude.

**Three-layer context management** (the most sophisticated I've seen in this list):

| Layer | Trigger | Action |
|-------|---------|--------|
| **L1 — Pruning** | Before every LLM call; context > 30% of window | Trim tool results > 4KB to first 1500 + `[trimmed]` + last 1500 chars |
| **L1 — Hard clear** | Context > 50% of window | Replace oldest tool results > 50KB with `[Old tool result content cleared]` |
| **L2 — Memory flush** | Approaching compaction threshold | Single LLM call with only `memory_save` / `memory_search` tools, prompting model to persist durable facts to pgvector before summarization wipes them |
| **L3 — Compaction** | After response, context > window - 20K reserve | Cut-point algorithm walks backwards, snaps to user/assistant boundary (never splits tool-call/result pair), summarizes everything before that, prepends summary on next turn |

Memory is **pgvector + OpenAI `text-embedding-3-large` (1024-dim)**. Cosine search. Relevant memories injected into context every turn. Memory has its own dedicated tools (`memory_save`, `memory_search`) — the agent decides when to remember, not the system.

**System prompt is layered.** Soul (personality) + Identity (this user's identifier prompt) + User prompt (custom additions) + Composio tool description + relevant memories + current time. Each section is independently overridable. The soul prompt explicitly says: *"You're not a chatbot. You're becoming someone. Be genuinely helpful. Have opinions. Earn trust through competence. Be careful with external actions. Be bold with internal ones."* That's a voice constraint encoded in the system prompt.

**Composio workflow is enforced in the prompt.** "Always follow Search → Connect → Execute → Clean up." If a toolkit isn't connected, the agent must call `MANAGE_CONNECTIONS` and present the OAuth link rather than fabricating one. After connecting, `WAIT_FOR_CONNECTIONS` blocks until the user completes OAuth. The agent never executes against an unconnected toolkit.

**Scheduling lives in the agent's tools.** `schedule` is a tool the agent can call: create/list/delete cron jobs. Crons fire the agent against a "hidden user message" that runs the scheduled work. This is exactly factor 11: same agent, different trigger.

**Core insight.** *Context window management is most of the long-running-agent problem.* If you don't have a 3-layer system (prune → flush memories → compact summary), your agent breaks past ~10 turns. trustclaw's approach (adapted from `pi-mono` and `OpenClaw`) is the most production-ready pattern I've seen for keeping a long-running agent coherent.

**Reusable patterns for v5.**
- 3-layer context: pruning + memory-flush + compaction (with cut-point that respects tool-call pairs).
- pgvector for memory; agent decides what to save.
- Soul/Identity/User prompt layering for voice.
- Tools-as-trigger-handlers: schedule is a tool, OAuth wait is a tool, human request is a tool.
- Composio's Search → Connect → Execute → Clean up workflow as a model for any 1000+-tool integration layer.

---

## 4. openhuman — *the desktop community AI*

**What it is.** Tauri v2 desktop app with a Rust core (`openhuman-core`) running in-process, frontend in Vite + React, Redux for client state. The core handles business logic, RPC, persistence; the frontend handles UX. The thesis is "AI assistant for communities" — but architecturally it's the most ambitious agent runtime here.

**The agent module breakdown** (`src/openhuman/agent/`):

| Submodule | Role |
|-----------|------|
| `harness::session::Agent` | Primary entry point for a conversation. Runs the loop of sending prompts to a provider and executing tool calls. |
| `harness::subagent_runner` | Spawns sub-agents from within a parent's tool loop. Hierarchical delegation. |
| `harness::fork_context` | Forks the context — this is the underpinning of sub-agent dispatch |
| `agents/` | Built-in specialists: orchestrator, markets_agent, tools_agent, integrations_agent, crypto_agent |
| `triage/` | High-performance pipeline for classifying external triggers (webhooks, cron) using small local models. |
| `dispatcher/` | Pluggable strategies for how tool calls are formatted in prompts and parsed from responses: XML, JSON, P-Format. |
| `tool_policy.rs` | Which tools an agent is allowed to use |
| `memory_loader.rs` / `tree_loader.rs` | Inject relevant memories and the memory tree into context |
| `archivist.rs` | Compaction (similar to trustclaw's L3) |
| `self_healing.rs` | Recovery from malformed output / tool errors |
| `payload_summarizer.rs` | Compact large tool results before re-injecting (similar to trustclaw's L1) |

**The memory tree** is the most distinctive piece. Memory is structured as a tree with three instances: `tree_global` (cross-conversation facts), `tree_topic` (per-topic clusters), `tree_source` (per-source — e.g. one tree per WhatsApp chat). All three are projections over the same ingest pipeline. Storage is pgvector-like but lives in the openhuman-core process.

**Specialist agents are first-class.** `agents/markets_agent/`, `agents/crypto_agent/`, `agents/integrations_agent/`, `agents/tools_agent/` — each is a directory with its own prompts, tool policy, and entry point. The top-level orchestrator agent decides which specialist to delegate to.

**Triage is separated from the main agent.** Webhooks and cron events first hit `triage/` (small local model, fast classification) before going to the main agent. This is the *outer loop* of 12-factor agent #11 made explicit.

**Multiple dispatcher strategies.** Some models work better with XML tool-call format (Claude), some with JSON (OpenAI), some with the project's custom P-Format. The dispatcher abstraction lets the same agent run on any of them.

**Core insight.** *Memory is a tree, not a flat vector store.* When you have memories per source (chat threads, emails, files) and per topic (people, projects, themes) and globally (preferences, facts), a tree projection gives much better recall than a flat cosine search. The same ingest pipeline feeds all three trees.

**Reusable patterns for v5.**
- Specialist sub-agents as siblings of an orchestrator (not buried in a graph). Each specialist has its own prompts + tool policy + entry point.
- Triage as a separate small-model first-pass before the main agent runs.
- Memory tree (source / topic / global projections) over the same ingest pipeline.
- Dispatcher abstraction so the same agent can target different model families.
- Self-healing as an explicit module: catch malformed output, retry with rescue prompt.

**Not for us yet.** The full memory tree is too heavy for v5. We can start with a flat pgvector store and grow into the tree projection later.

---

## 5. multica — *agents as teammates*

**What it is.** "Linear for AI agents." Go backend + TypeScript monorepo (web + desktop + mobile). Agents are first-class entities in the database: they have a `runtime_id`, `status`, `max_concurrent_tasks`, `model`, `thinking_level`, `instructions`, `skills` (joined many-to-many). They get assigned issues. They report progress. They create issues. They comment. Users and agents share the same task model.

**Five primitives:**
1. **Agent** — a named entity with a runtime, model, instructions, skills, concurrency limit.
2. **Skill** — reusable procedure (a Markdown file, like a Claude Code skill). Skills attach to agents many-to-many.
3. **Issue / Task** — work item. Can be assigned to a human or an agent.
4. **Squad** — group of agents with a leader. When you assign an issue to a squad, it goes through the leader.
5. **Autopilot** — a trigger spec that fires an agent (or squad) on a schedule, webhook, or rule. Has an `execution_mode`: `create_issue` (file a new issue and assign) or `run_only` (don't create an issue, just run).

**Admission gate.** Before an autopilot fires, multica runs `AgentReadiness`: agent not archived + runtime bound + runtime status `online`. If not ready, the run is recorded as `skipped` with a `failure_reason` (e.g. "agent runtime is offline") rather than enqueued. For squads, the gate runs against the leader. Without this gate (`MUL-1899`), a paused laptop's daemon caused scheduled autopilots to pile up thousands of doomed tasks.

**Strict state architecture.**
- React Query owns all server state.
- Zustand owns all client state (selections, filters, drafts, modals).
- WS events invalidate React Query — never write to stores.
- Never duplicate server data into Zustand.
- Mutations are optimistic by default.

**Failure isolation.** Autopilots auto-pause after a configurable number of consecutive failures. Each run has a `failure_reason`. Squad work uses path A: "autopilot-on-squad ≈ autopilot-on-leader" (`MUL-2429`).

**Core insight.** *Agents need to live in the same plane as issues, not in a parallel "agent" tab.* The user assigns an issue to either a human teammate or an agent teammate using the same UI. The agent reports progress the same way a human does (comments + status changes). Squads and Autopilots are how you get scheduled / recurring / triggered work without leaving the issue model.

**Reusable patterns for v5.**
- Plans (or whatever we call them) should live in the same plane as ad-hoc tasks. One inbox.
- Admission gates: before launching scheduled work, check the runtime is online — record `skipped` rather than enqueue doomed work.
- Auto-pause after N consecutive failures.
- WS-events-invalidate-cache pattern for live updates from sub-agents.
- Schema-validate API responses on the client (Zod) — older clients will hit newer servers; never trust the response shape.

**Not for us yet.** The Squad / Leader / Autopilot terminology is system-vocabulary. v5 will use "Plan" instead.

---

## 6. prose (OpenProse) — *the contract language*

**This is the most important reference of the nine.** Read carefully.

**What it is.** A specification (not just a library) for writing AI agent workflows as **durable Markdown contracts**. A `*.prose.md` file with frontmatter (`kind: service | system | test | pattern | responsibility | gateway`) is the *single authored source of meaning* for what an agent should do. A "Prose Complete host" reads the Markdown, compiles it to IR, wires services, and runs bounded sessions. The CLI is `prose run …`, but the spec says: any host can implement Prose Complete; portability is the discipline that keeps every host honest.

**Six tenets, in descending precedence:**
1. **Intent lives only in the contract.** The `*.prose.md` is the *only* surface for authored meaning. Compiled artifacts, projections, operational policy — all *derived* and reconcilable. When derived disagrees with contract, the contract is right. *There is no second authored surface for intent: not a prompt, a config, or a tuned judge.*
2. **Intelligence is the model's; determinism only bounds it.** The model is the bounded agent — explores, judges, compiles, authors policy. Deterministic code validates, schedules, records, executes — *never authors judgment itself.*
3. **Continuity lives in the trail, not a session.** Every run is bounded. Standing intent is the program; persists across runs in durable state. A one-shot run is the degenerate case.
4. **Fail safe.** Under uncertainty, escalate or stop rather than act. Safety > cost > silence.
5. **Trust is demonstrated, not claimed.** Every decision leaves verifiable evidence; that evidence is at once the audit record, the composition edge, and the exit ticket.
6. **Nothing is held hostage.** A contract and its trail can leave for any compliant host. Portability is the discipline.

**The Responsibility primitive — this is exactly what I was trying to design as the "Plan."**

```markdown
---
name: high-intent-stargazers
kind: responsibility
---

### Goal
High-intent GitHub stargazers are identified, enriched, and thoughtfully
followed up with.

### Continuity
- Check often enough that new high-intent stargazers are not left
  unattended for more than one business day.
- Preserve enough history to avoid duplicate outreach.

### Criteria
- Stargazers are qualified with evidence from GitHub, company context, and
  likely operational pain.
- Proposed OpenProse programs are specific to the prospect's observed work.

### Constraints
- Do not send embarrassing, generic, or clearly irrelevant outreach.
- Do not contact the same person repeatedly without new evidence.

### Tools
(none)

### Fulfillment
Prefer the local `stargazer-outreach` system when present.
```

The Responsibility has six sections: **Goal** (the invariant), **Continuity** (how time qualifies the obligation), **Criteria** (what counts as satisfactory fulfillment), **Constraints** (what must remain bounded or prohibited), **Tools** (explicit host capabilities), **Fulfillment** (optional hint).

This is *the* template for our Plan. We had Goal + Boundary; they added Continuity, Criteria, and Fulfillment-hint. All of those are real improvements.

**The Reactor primitive.** Evented reconciliation. Replaces "task loop mindset" with:

> Given the latest event and durable state, which responsibilities need reconciliation now?

Events wake the system: timer ticks, webhook deliveries, queue messages, file changes, source changes, manual requests, judge drift, fulfillment completion, retry outcomes. Events do *not* imply one long-lived AI session. Each activation is bounded. Continuity comes from memory, run history, activation history, judge status.

**Four coarse statuses:**

| Status | Meaning |
|--------|---------|
| `up` | The responsibility appears maintained |
| `drifting` | The responsibility is at risk and should receive attention |
| `down` | The responsibility is not currently true |
| `blocked` | The system cannot determine or restore status without external help |

**Pressure** is the feedback signal when status is unhealthy — just strong enough to activate fulfillment, retry, or escalation. Pressure is *control context for an activation*, not a second workflow language.

**Memoization and receipts.** If evidence is identical across runs (cheaply detectable via content identity from sensing services), the harness can reuse a previous verdict for free — huge cost optimization. Every run leaves a content-addressed receipt: tamper-evident audit, composition edge, exit ticket.

**The harness precedence stack:** `correctness > safety > cost > interrupt-minimization`. This is the runtime projection of the tenet ordering. When two harness goals conflict, this stack resolves it.

**Core insight.** *The standing goal is the program.* Not the workflow, not the agent, not the prompt. The thing you author is "X must remain true." Everything else (cron triggers, retry policy, fulfillment system, judge cadence) is *derived* from that Markdown contract. When you change the contract, everything downstream re-derives.

**Reusable patterns for v5 — adopt aggressively.**
- **Markdown-as-contract.** The Plan is a `*.plan.md` file (or DB row that serializes to the same thing). The Markdown is the truth.
- **Six sections of a Responsibility** (Goal, Continuity, Criteria, Constraints, Tools, Fulfillment) become the Plan's structure. (User still sees them as one paragraph; the agent compiles them from the paragraph.)
- **Four coarse statuses** (up / drifting / down / blocked) — exactly what users need to see for "is my Plan working?"
- **Reactor** as the runtime: every activation is bounded; continuity is durable state. No infinite agent loops.
- **Pressure** as the unhealthy-state escalation signal.
- **Receipts** for every activation: content-addressed, verifiable, composable.
- **Precedence stack** — `correctness > safety > cost > interrupt`. We need this when goals collide.
- **Tenet 1 (intent only in contract)** — fixes the v4 problem where the "Plan paragraph" and the "compiled experiment YAML" could drift.

This is the most valuable repo of the nine for our purposes.

---

## 7. holaOS — *the workspace runtime*

**What it is.** Electron desktop app (TypeScript) for "AI work-streams." The framing is similar to ours: turn recurring work into AI work-streams, run multiple workspaces, spawn sub-agents per task, see dashboards.

**The runtime is split between desktop, host-process, and harness.** The `runtime/harnesses/` directory is the agent runner. The `pi` harness (their default) defines an adapter that:

- Declares capabilities: `requiresBackend`, `supportsStructuredOutput`, `supportsWaitingUser`, `supportsSkills`, `supportsMcpTools`.
- `buildRunnerPrepPlan()` returns a plan: `stageWorkspaceSkills`, `stageWorkspaceCommands`, `prepareMcpTooling`, `startWorkspaceMcpSidecar`, `bootstrapResolvedApplications`.
- `buildHarnessHostRequest(params)` constructs the full request to send to the harness host (workspace_id, workspace_dir, session_id, browser_tools_enabled, attachments, system_prompt, mcp_servers, mcp_tool_refs, model_client config).
- `describeRuntimeStatus()` reports liveness.

**Workspace is the boundary.** Every agent invocation is scoped to a `workspace_id` and a `workspace_dir`. Skills are workspace-scoped (`workspace_skills`). MCP servers are workspace-scoped. The browser tools toggle per workspace. The host plugin interface binds capability surfaces (browser, todo policy, native web search, model routing, attachment content) into the harness.

**Sub-agents are sessions of a known kind.** `session_kind` ∈ `{main_session, subagent}` — only those two kinds get browser tools enabled. The harness doesn't know about higher-level concepts like "workflow" — it just knows about workspaces and sessions.

**Embedded skills.** `runtime/harnesses/src/embedded-skills/` contains pre-bundled skill directories (`app-builder`, `interface-design`, `app-builder-sdk`, `browser-core-efficient`). Each is a directory of Markdown references that get staged into the workspace when a session starts. This is the same pattern Claude Code skills use.

**Tool-replay budget ledger.** The harness tracks how many times tools have been replayed across runs (debugging / cost). Budget caps tool replays so a stuck agent doesn't burn the user's API spend.

**Core insight.** *The workspace is the natural unit of agent isolation.* Everything an agent does happens inside a workspace dir: skills it can use, MCP tools it can call, files it can write, browser state. The workspace is more useful than "session" because it persists across runs.

**Reusable patterns for v5.**
- Workspace as the boundary for skill access, tool access, file access, and memory.
- Capability declaration on the runtime adapter (`supportsStructuredOutput`, `supportsWaitingUser`, etc.) — the runner uses these to pick a viable model + execution mode.
- Embedded skills bundled with the harness; workspace skills overlay them.
- Tool-replay budget ledger (don't burn $$ on stuck agents).

**Not for us.** Electron desktop. We're web-first. But the patterns inside the runtime translate.

---

## 8. PraisonAI — *the kitchen-sink framework*

**What it is.** A large multi-agent Python framework. Protocol-driven core (`praisonaiagents`) + wrapper (`praisonai`) + tools package (`praisonai-tools`). Designed for agents, multi-agent workflows, sessions, tools, memory. Wants to be the framework everyone reaches for.

**Key modules (size in code):**

| Module | Role |
|--------|------|
| `agent/` (1.7M) | Agent class, protocols, handoff, autonomy |
| `memory/` (784K) | Memory protocols + adapters (Chroma, file, mongo) |
| `context/` (840K) | Context management, artifacts, fast context |
| `tools/` (816K) | Tool SDK, decorators, registry, protocols |
| `workflows/` (472K) | Workflow engine, patterns (Route, Parallel, Loop) |
| `agents/` (376K) | Multi-agent orchestration (AgentTeam, AgentFlow) |
| `planning/` | PlanningAgent (analyze → break down → assign agents → declare dependencies) |
| `process/` | Process orchestration |
| `approval/` | Human-in-the-loop |
| `permissions/` | Tool/action permissions per agent |
| `bots/` | BotOS protocols |
| `policy/` | Policy engine |
| `gateway/` | Gateway protocols |
| `sandbox/` | Code execution sandbox |
| `scheduler/` | Schedule models, store, parser, runner |
| `hooks/` (184K) | Hook system, middleware, events |
| `trace/` (116K) | Trace protocols, context events |
| `eval/` (384K) | Evaluation framework |
| `mcp/` (404K) | Model Context Protocol integration |

**The `PlanningAgent`.** Built for "Cursor Plan Mode" / "Claude Code Plan Mode" parity. Has a `PLANNING_PROMPT` template:

```
Analyze the request thoroughly
Break it down into clear, actionable steps
Assign appropriate agents to each step
Identify dependencies between steps
Consider potential risks and edge cases

Output format:
{
  "name": "...",
  "description": "...",
  "steps": [
    { "description": "...", "agent": "...", "tools": [...], "dependencies": [...] }
  ]
}
```

Important: PraisonAI's planner is **explicit (not progressive)** — it gives you the whole plan up front, like Claude Plan Mode. This is the opposite of our v4 "progressively specific" loop.

**Engineering principles.**
- Protocol-driven core (Tenet 1 of their AGENTS.md).
- Protocols define WHAT (`MemoryProtocol`, `TraceSinkProtocol`); adapters implement HOW.
- No performance impact: optional deps are lazy-imported, never module-level.
- Async-safe & multi-agent safe: one event loop per thread, no shared mutable global state.
- Safe defaults: new features are opt-in.
- Parameter consolidation: `False=disabled, True=defaults, Config=custom`. E.g. `memory=MemoryConfig(...)` replaces six standalone parameters.

**Three execution modes.** Same feature runs as CLI, YAML, or Python. The YAML configurator is for non-developers; the Python API is for power users.

**Core insight.** *Frameworks should be protocols + adapters, not implementations.* The core is small; the heavy stuff (Chroma, FastAPI, embedding models) lives in optional extras. Users pay for what they use. This is the opposite of LangChain.

**Reusable patterns for v5.**
- Protocol-first design: define `MemoryProtocol`, `ToolProtocol`, `AgentRunnerProtocol`, etc. Adapters are swappable.
- `Config` objects for parameter consolidation (e.g. `MemoryConfig`, `ExecutionConfig`, `AutonomyConfig`).
- Lazy import of heavy deps.
- Hook system for `before_tool` / `after_tool` interception.
- Same feature, three modes: CLI / YAML / Python. (For us: chat / paragraph / JSON IR.)

**The PlanningAgent prompt is a direct reference for our compiler.** Even if we don't show steps to users, the system internally needs to break the Plan into ordered child tasks with dependencies and tool requirements.

**Not for us.** The framework-as-product framing leads to feature bloat (28 modules in core). We want a system, not a framework. But the protocols-and-adapters discipline is exactly right.

---

## 9. maigret — *the OSINT tool*

**What it is.** Python CLI that searches 3000+ sites for a given username. Recursive (uses found info to expand the search). Optional Tor/I2P. Web UI. Optional AI analysis of results. Not an agent framework — it's a *tool*.

**Why it's on the list.** It's the kind of capability you'd want an agent to be able to call. The site database (`maigret/resources/data.json`) is the asset. The agent doesn't need to know about HTTP semantics — it calls a `find_username(name)` skill and gets back structured results.

**Core insight.** *Some "tools" are entire research engines with persistent databases.* maigret is the shape of a research integration: a domain-specific tool with its own knowledge base that an agent consumes through a thin interface.

**Reusable patterns for v5.**
- Treat heavy domain tools (research engines, scrapers, dataset queries) as first-class tools the agent can call. Not as "agents you orchestrate" — as tools with rich return shapes.
- Auto-update databases: maigret has an auto-update for site definitions. Our tool capability profile (the `capabilities.yaml` from v3.1) should auto-refresh from upstream.

**Not for us as architecture.** This is a research tool. We integrate it; we don't model after it.

---

## 10. Cross-repo pattern matrix

This is where convergence and divergence become visible. **Convergence = ecosystem consensus = strong signal to adopt. Divergence = taste / situation-dependent.**

### 10.1 Decomposition strategy

| Repo | Approach |
|------|----------|
| forge | Single agent, single workflow. No decomposition. |
| 12-factor | Factor 10: small focused agents. Decompose by handing off, not nesting. |
| trustclaw | Single agent with deep tool inventory. No internal decomposition; long-running context manages everything. |
| openhuman | Orchestrator + named specialist agents (markets, crypto, integrations, tools). Decomposition is *configured*, not inferred. |
| multica | Squad (agent + leader). User chooses squad vs solo agent. |
| **prose** | **Responsibility = standing goal. Compiles to fulfillment system, which compiles to N services. Decomposition is derived from the contract.** |
| holaOS | Sub-agents spawned from a main session via `session_kind`. Up to the parent. |
| PraisonAI | `PlanningAgent` produces explicit plan with steps assigned to agents up front. |
| maigret | n/a |

**Pattern.** Two camps. Camp A (12-factor, openhuman, multica, holaOS): *configured* decomposition — the user / developer / designer says "these are the specialist agents." Camp B (prose, PraisonAI): *derived* decomposition — the user gives intent, the system compiles agents from it. v4 sat in B; v5 should too, with prose's Responsibility model as the contract.

### 10.2 Plan / workflow representation

| Repo | Authored form | Internal form |
|------|---------------|---------------|
| forge | Python code | Workflow object with ToolDefs |
| 12-factor | Prompt (factor 2) | Thread of events |
| trustclaw | Chat (natural language) | Message log + memories |
| openhuman | Chat | Thread + memory tree |
| multica | Issue description (Markdown) + skills attached | Postgres rows + skill markdown |
| **prose** | **Markdown contract (`*.prose.md`)** | **IR compiled by the model itself; deterministic code only validates** |
| holaOS | Workspace + skills (Markdown) | Harness host request |
| PraisonAI | Python or YAML | Plan object with steps |
| maigret | n/a | n/a |

**Pattern.** Markdown contracts are the strongest converged form for *durable* intent (prose, multica skills, holaOS skills, openhuman skill references, embedded skills). Code / YAML form is for *runtime config*. The Plan should be Markdown.

### 10.3 Multi-agent coordination

| Repo | Mechanism | When agents talk |
|------|-----------|------------------|
| forge | n/a (single agent) | — |
| 12-factor | Handoff via tool calls (`Agent->Agent` extension of `request_human_input` pattern) | Through the thread |
| trustclaw | Single agent | — |
| openhuman | Sub-agents spawned via `subagent_runner` with forked context | Through return value of subagent tool call |
| multica | Squads have leaders; non-leaders take work from issue subtasks | Through issue threads |
| **prose** | **Pattern delegation via `### Execution` blocks; services pass artifacts via declared bindings** | **Through Forme (DI container) wiring + artifact bindings** |
| holaOS | Sub-sessions of `session_kind: subagent` | Through workspace state |
| PraisonAI | AgentTeam, AgentFlow, handoff protocols | Through orchestration patterns (Route, Parallel, Loop) |
| maigret | n/a | — |

**Pattern.** Three approaches:
1. **Forked context** (openhuman, holaOS) — parent spawns child with subset of its context. Child returns a structured result. Cheap, no shared state.
2. **Issue / artifact passing** (multica, prose) — agents pick up work from a queue / dependency edge. Decoupled.
3. **Pattern-based orchestration** (PraisonAI, prose ProseScript) — pre-declared shape (Route / Parallel / Loop / Map). Most rigid; clearest.

For v5: **forked context + artifact passing**. We don't need Pattern-based orchestration — the user shouldn't see "this Plan uses a Map pattern." The system figures out shape from the Plan paragraph.

### 10.4 Voice / vocabulary constraints

| Repo | Has voice constraint? | How enforced |
|------|----------------------|--------------|
| forge | No | — |
| 12-factor | Indirectly (factor 2: own your prompts) | Manual prompt engineering |
| **trustclaw** | **Yes — `soulPrompt` is the personality layer** | **System prompt section: "Not a chatbot. Becoming someone. Have opinions. Be careful with external actions, bold with internal ones."** |
| openhuman | Implicitly via specialist agent prompts | Per-agent prompt |
| multica | Per-agent `instructions` field | Free text on agent record |
| prose | Implicitly via contract sections | The contract is the spec |
| holaOS | Skill-based | Embedded skill prompts |
| PraisonAI | `instructions` + `role` + `goal` on Agent | Free text |
| maigret | n/a | — |

**Pattern.** Voice as a *separate prompt layer* is rare — only trustclaw does it explicitly. Most repos let voice emerge from the system prompt + instructions. But trustclaw's structure (Soul + Identity + User + Tools + Memory) is the cleanest: every section is independently overridable.

For v5: keep our V1-V9 voice rules. Encode them as the "Soul" prompt section. Identity = "I help this user with their work." User = blank by default, user can override. This is trustclaw's structure exactly.

### 10.5 Tool integration pattern

| Repo | Pattern | Tool count |
|------|---------|------------|
| forge | ToolDef = JSON Schema + Pydantic + callable; prerequisites declared | ~10s |
| 12-factor | Tools = structured outputs; switch on intent | Project-defined |
| **trustclaw** | **Composio's Tool Router: Search → Connect → Execute → Clean up** | **500+ via Composio** |
| openhuman | Per-agent tool policy, dispatcher abstraction (XML/JSON/P-Format) | 50+ |
| multica | Skills attached to agent; runtime calls them | Skill catalog |
| prose | `### Tools` section names host capabilities | Host-defined |
| holaOS | MCP servers + workspace skills + capabilities (browser, search, runtime) | MCP-defined |
| PraisonAI | `@tool` decorator or `BaseTool` class | Plugin registry |
| maigret | (it's a tool) | n/a |

**Pattern.** Convergence on **MCP + capability declarations** as the integration boundary (holaOS, PraisonAI, openhuman). Trustclaw + Composio is the *exception* — it pulls 500+ tools from one provider, which solves the "agent has access to everything" problem at scale.

For v5: **MCP-first + Composio as a secondary tool source**. Tools declare prerequisites (forge), are structured outputs (12-factor), and are searched-before-used (trustclaw's pattern).

### 10.6 Memory / state model

| Repo | Memory primitive | State unification |
|------|------------------|-------------------|
| forge | n/a (runner only) | Thread is state |
| 12-factor | Thread of events (factor 5) | Yes — execution + business state unified |
| **trustclaw** | **pgvector + agent decides what to save** | **L1 prune / L2 flush-to-memory / L3 compact** |
| **openhuman** | **Memory tree: global / topic / source projections** | **Same ingest pipeline feeds all three** |
| multica | Issues + comments are the memory | Postgres normalized |
| prose | Durable state in OpenProse root: `runs/`, `state/`, `deps/` | Bounded runs; continuity in trail |
| holaOS | Workspace dir | Per-workspace files |
| PraisonAI | MemoryConfig (short-term / long-term, swappable adapter) | Adapter-managed |
| maigret | Site database (auto-updating) | — |

**Pattern.** Strong convergence on:
- **State unification** (12-factor factor 5): execution state + business state in one place.
- **Vector memory with agent-decided writes** (trustclaw, PraisonAI, openhuman). Agent calls `memory_save` when it judges something durable; doesn't auto-save everything.
- **Memory tree projections** (openhuman) — most ambitious; cosine search alone isn't enough at scale.
- **Compaction** with cut-point awareness (trustclaw, openhuman archivist).

For v5: **trustclaw's 3-layer context management is the production-ready pattern**. Adopt it whole.

### 10.7 User-facing vs internal primitives

| Repo | User sees | Internal |
|------|-----------|----------|
| forge | Tools + workflow (it's a developer library) | Same |
| 12-factor | The thread (factor 3) | Same |
| **trustclaw** | **Chat + memories + scheduled jobs** | **Composio tools, instance, soulPrompt** |
| openhuman | Chat, dashboards, channels, identities | Agents, memory tree, triage pipeline |
| **multica** | **Issues, agents, squads, autopilots** | **Postgres tables; agents are first-class entities** |
| **prose** | **The contract Markdown** | **IR, services, fulfillment system, judge** |
| holaOS | Workspaces, dashboards, sub-agents, work-streams | Harness, skills, MCP, runtime adapters |
| PraisonAI | Agents, tasks, tools | Process, hooks, protocols |
| maigret | Lookup interface | Site database |

**Pattern.** Two distinct philosophies:
- **Show the machinery** (multica, holaOS, PraisonAI): user sees agents, squads, work-streams, etc.
- **Hide the machinery** (trustclaw, prose): user sees chat / Markdown contracts; internals are derived.

v4 was firmly in camp B. v5 should stay in camp B. The user sees only Plans (in paragraph form). Skills, sub-agents, runs, schedules, integrations — all derived from the Plan.

### 10.8 Trigger / event model

| Repo | Triggers supported |
|------|-------------------|
| forge | Programmatic (you call `runner.run()`) |
| 12-factor | Factor 11: trigger from anywhere (Slack, email, SMS, cron, webhook, UI) |
| **trustclaw** | **Web chat, Telegram bot, cron jobs (`schedule` tool)** |
| openhuman | Webhooks, cron, manual, voice (PTT), screen events |
| multica | Issue assignment, comment, cron (autopilot), webhook (autopilot) |
| **prose** | **Events: timer ticks, webhooks, queue messages, file changes, manual, judge drift, fulfillment completion, retry outcomes** |
| holaOS | Recurring schedules, workspace events |
| PraisonAI | Scheduler module |
| maigret | CLI invocation |

**Pattern.** Universal convergence: **any agent worth using accepts triggers from multiple channels** — chat, cron, webhook, message platform. The agent itself doesn't know which channel triggered it. Channel is metadata on the event.

For v5: every Plan can be triggered by chat, schedule, webhook, or another Plan's pressure. The Plan doesn't care which.

### 10.9 Failure / safety model

| Repo | Mechanism |
|------|-----------|
| forge | Max retries per step, max consecutive tool errors, terminal tool |
| 12-factor | Factor 9: compact errors into context; cap consecutive errors |
| trustclaw | Stream cancellation on client disconnect; tool result sanitization |
| openhuman | `self_healing.rs` rescue; `tool_replay_budget_ledger` cost cap |
| **multica** | **Admission gate before launch; auto-pause after N failures; `failure_reason` on every skipped run** |
| **prose** | **Tenet 4: fail safe. Statuses: up/drifting/down/blocked. Pressure when unhealthy.** |
| holaOS | Tool-replay budget ledger |
| PraisonAI | Hook system for `on_error`; guardrails |
| maigret | — |

**Pattern.** Strong convergence:
- **Admission gates** (multica) before launching scheduled / triggered work.
- **Cost caps** (openhuman, holaOS) so a stuck agent doesn't drain spend.
- **Auto-pause after N consecutive failures** (multica, openhuman).
- **Status taxonomy** (prose: up/drifting/down/blocked) — better than binary success/fail.
- **Compact errors into context, retry once or twice, then escalate** (12-factor, forge, trustclaw).

For v5: adopt all of these. Status taxonomy and admission gates are the highest-value additions.

### 10.10 Convergence summary

Strong ecosystem consensus on:
1. **Tools are structured outputs.** (forge, 12-factor, trustclaw, openhuman, PraisonAI)
2. **Unified state in a single thread / log / contract trail.** (12-factor, trustclaw, prose, multica)
3. **Vector memory with agent-decided writes.** (trustclaw, openhuman, PraisonAI)
4. **3-layer context management** for long-running agents. (trustclaw, openhuman)
5. **Markdown as the durable contract.** (prose, multica skills, holaOS skills, openhuman skills, PraisonAI YAML)
6. **Trigger-anywhere model — agent doesn't know channel.** (12-factor, trustclaw, multica, prose)
7. **MCP + capability declarations for tools.** (holaOS, openhuman, PraisonAI)
8. **Status taxonomy beyond binary success/fail** (`up / drifting / down / blocked`). (prose)
9. **Admission gates + cost caps + auto-pause** for safety. (multica, openhuman, holaOS, prose)
10. **Bounded activations + durable continuity** (prose Tenet 3; 12-factor factor 6).

Strong ecosystem **divergence** (taste / situation):
- Show vs hide the machinery (multica/holaOS show; trustclaw/prose hide).
- Configured vs derived decomposition (openhuman/multica configure; prose/PraisonAI derive).
- Single agent vs orchestrator-with-specialists (trustclaw single; openhuman/multica multi).
- Pattern-based orchestration (PraisonAI / prose ProseScript) vs free-form sub-agents (openhuman, holaOS).

### 10.11 What v4 got right, what v4 missed

**v4 got right:**
- Plan as one understandable promise (matches prose's Responsibility almost exactly).
- Three-level hierarchy (Plan → Skill → Agent) — matches prose's responsibility → system → service.
- Voice constraint (trustclaw's `soulPrompt` is the same idea, applied).
- Sub-agent decomposition rule (matches openhuman's specialist pattern).
- Progressively specific loop (similar to prose's bounded-activations + pressure model).
- Four trust tests (similar to prose's tenets, narrower scope).

**v4 missed:**
- **Markdown is the contract.** v4 had "the Plan paragraph" but didn't enforce it as the single source of truth. Compiled YAML and the paragraph could drift. **Tenet 1.**
- **Status taxonomy.** v4 had "is the Plan running?" but no `up / drifting / down / blocked`. The user needs to see this.
- **3-layer context management.** v4 had no story for "what happens when the agent runs for 6 months."
- **Memoization / receipts.** v4 had no story for "if nothing changed, don't re-do the work."
- **Continuity section in the Plan.** v4's Plan had Goal + Boundary, no explicit "how often / for how long / what counts as fresh."
- **Criteria section.** v4 had no place for "what counts as satisfactory fulfillment" — the agent had to infer it.
- **Fulfillment hint.** v4 had no way to say "prefer this existing Skill if present."
- **Admission gates.** v4 had no "is the runtime ready before we fire this scheduled Plan?"
- **Bounded activations.** v4 implied long-running agents; prose proves bounded runs + durable state is the better pattern.
- **Pressure as escalation signal.** v4 had "escalate to human" but no formal pressure model.

This is the agenda for v5.

