# GTM-OS

> **Self-hosted, autonomous Go-To-Market operating system.**
>
> Run experiments. Use real tools. Compound learnings.

GTM-OS is a Python application that runs autonomously on your own machine (or a per-company VM). You define your **Brand**, **Rules**, and **Plays** once. The engine then runs experiments on a schedule — designing, building, executing, measuring, and learning — using real integrations (Gmail, Apollo, Slack, HubSpot, …) through [Composio](https://composio.dev).

It is **not** a chatbot. The chat UI is for setup and monitoring. The agents actually *do* the work.

It is **not** email-specific. The engine is channel-agnostic. The Play defines the channel.

---

## What's inside

Six primitives drive everything (PRD §4):

| Primitive   | Location                  | What it is |
|-------------|---------------------------|------------|
| **Brand**   | `primitives/brand/`       | Voice, tone, example copy |
| **Agents**  | `primitives/agents/`      | Markdown personas (orchestrator, researcher, copywriter, analyst, operator) |
| **Rules**   | `primitives/rules/`       | Global + phase + channel guardrails |
| **Plays**   | `primitives/plays/`       | The actual GTM playbooks (seeded from GTMbrain) |
| **Memory**  | `primitives/memory/` + SQLite | Facts, learnings, preferences, rules (vector-searchable) |
| **Triggers**| `primitives/triggers/`    | Schedules + hooks |

An **Experiment** is *not* a document — it is a configured task loop. It has a Brand, an Agent, Rules, a Play, Memory, Triggers, and Integrations. It runs on a schedule until complete or paused.

---

## Quick start

```bash
# 1. Install (Python 3.11+)
uv pip install -e .

# 2. Set your provider's API key (litellm-compatible: OpenAI, Anthropic, Groq, Ollama, …)
export OPENAI_API_KEY=sk-...
# optional, for real GTM tools:
export COMPOSIO_API_KEY=...

# 3. Scaffold primitives + config
gtm-os init

# 4. Start it
gtm-os start

# A browser opens at http://127.0.0.1:3000. Chat with your team.
```

Other commands:

```bash
gtm-os status                # show experiments + schedules + config
gtm-os run-tick <exp-id>     # manually tick one experiment
```

---

## Architecture

```
   CLI ──▶ FastAPI ──▶ Agent Runtime ──▶ Tools (Custom + Composio)
                          │
                          ├── Primitives (markdown on disk)
                          ├── SQLite store (experiments, runs, memory, schedules)
                          └── Scheduler (daemon polling loop)
```

- **No agent framework dependency.** No LangChain, no CrewAI, no OpenAI Agents SDK. Just a thin tool loop over `litellm`.
- **SQLite + optional `sqlite-vec`** for state and vector memory. No Postgres needed.
- **Polling daemon thread** for scheduling. Auto-pauses after 3 consecutive failures. Recovery sweep for orphaned runs.
- **3-layer context management** (prune → flush-to-memory → compact) keeps long sessions inside the model's window.
- **Correction-to-rule:** learnings reinforced by 3+ experiments at confidence ≥ 0.8 are promoted to standing rule files in `primitives/rules/derived/`.

---

## Configuration

Everything lives in `gtm-os.config.yaml` (see `gtm-os.config.yaml.example`). You can swap models without touching code — any litellm-compatible model works:

```yaml
llm:
  model: anthropic/claude-3-5-sonnet-20241022   # or openai/gpt-4o, ollama/llama3.1, …
  embedding_model: openai/text-embedding-3-small
```

API keys come from environment variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `COMPOSIO_API_KEY`, …).

---

## Customizing your team

- **Edit the Brand.** Update `primitives/brand/BRAND.md` and `tone.yaml`.
- **Add a play.** Drop a new `primitives/plays/<your-play>/PLAY.md` and reference it when creating an experiment.
- **Tighten the Rules.** Add a phase or channel rule file. The engine reloads primitives whenever the filesystem changes.
- **Add a new agent.** Drop a markdown file in `primitives/agents/` and reference it by `agent` when calling the chat API.

The engine never hardcodes a channel. "Email" is not special. If you write a LinkedIn play, the engine will discover and execute LinkedIn tools via Composio automatically.

---

## Development

```bash
# Backend
uv pip install -e ".[dev,composio,vec]"
pytest

# Frontend (Vite dev server with API proxy)
cd frontend
npm install
npm run dev          # http://127.0.0.1:5173 — proxies /api to :3000

# Production build (FastAPI serves the static bundle)
npm run build
```

---

## Status

Phase 1 (foundation) and Phase 2 (autonomy) are implemented:

- [x] `gtm-os init` scaffolds primitives + config
- [x] `gtm-os start` launches FastAPI + serves the React UI
- [x] Streamed chat (SSE) with tool-call visibility
- [x] Experiment CRUD + per-experiment run history
- [x] SQLite store with WAL + checkpoints
- [x] Vector memory (embeddings + cosine search) with keyword fallback
- [x] Scheduler daemon (cron + interval), auto-pause, orphan recovery
- [x] 3-layer context manager (prune / flush / compact)
- [x] Composio tools (discover / execute / connect) — gracefully no-ops when not configured
- [x] 10 default plays seeded from GTMbrain
- [x] Correction-to-rule: confident learnings get promoted to rule files
- [x] Human approval gate before the `execute` phase

---

## License

MIT.
