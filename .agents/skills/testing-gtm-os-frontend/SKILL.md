---
name: testing-gtm-os-frontend
description: Test the GTM-OS frontend three-panel layout, sidebar navigation, experiment tabs, chat with Claude, panel collapse/expand, and brand configuration. Use when verifying UI changes to the GTM-OS dashboard or Settings page.
---

# Testing GTM-OS Frontend

## Prerequisites
- Server running: `uv run gtm-os start` from the repo root
- `ANTHROPIC_API_KEY` in `.env` file (or environment)
- `gtm-os.config.yaml` in repo root with valid model ID

## Devin Secrets Needed
- `ANTHROPIC_API_KEY` — Anthropic API key for LLM calls

## Config Setup
Create `.env` in repo root (gitignored) with your API key:
```
ANTHROPIC_API_KEY=sk-ant-...
```

Create `gtm-os.config.yaml` in repo root (gitignored):
```yaml
llm:
  model: "anthropic/claude-sonnet-4"
  embedding_model: "openai/text-embedding-3-small"
  temperature: 0.4
  max_tokens: 4096
  request_timeout_seconds: 120
server:
  host: "127.0.0.1"
  port: 3000
scheduler:
  enabled: false
```

The server auto-loads `.env` on startup — no need to export keys manually.

## Starting the Server
```bash
cd /home/ubuntu/repos/gtm-os
uv run gtm-os start
```
Use a separate shell session for the server. Verify with:
```bash
curl -s http://127.0.0.1:3000/api/health
```

## Test Procedure

### 1. Three-panel layout
- Open http://localhost:3000 in browser
- Verify: sidebar (left), content area (center), chat panel (right), status bar (bottom)
- Status bar should show: trust score, experiment count, memory count, model name

### 2. Sidebar navigation (all 8 views)
Click each in order: Dashboard, Experiments, Plays, Memory, Agents, Automations, Rules, Settings
- Dashboard: "Good morning" heading, Active Experiments grid, System Overview stats
- Experiments: list with phase badges and token counts
- Plays: filter tabs (All/Email/Social/Seo), play cards with Use/Fork buttons
- Memory: search input, type filter buttons (All/Learning/Rule/Correction/Context)
- Agents: 5 persona cards (orchestrator, researcher, copywriter, analyst, operator)
- Automations: filter tabs (All/Active/Paused)
- Rules: filter tabs (All/Manual/Auto-generated)
- Settings: model name, Composio status, Scheduler status, Primitives path

### 3. Experiment tab
- From Dashboard, click an experiment card
- Verify: tab appears in top bar with phase-colored dot
- ExperimentDetail shows: phase pipeline, token usage, hypothesis, action buttons

### 4. Chat with Claude
- Type a message in chat textarea, click Send
- Verify: user message bubble appears, Claude streams a response via SSE
- Agent selector should default to "orchestrator"
- Tool calls (if any) should show with result

### 5. Sidebar collapse/expand
- Click GTM-OS logo in sidebar header to collapse
- Verify: icon-only rail, no text labels
- Click again to expand back

### 6. Chat panel collapse/expand
- Click "−" button in chat header
- Verify: narrow rail with vertical "Chat" text
- Click rail to expand back

### 7. Brand Configuration (Settings page)
- Navigate to Settings via sidebar
- **Initial state:** Brand Identity fields empty with placeholders, Voice & Tone pre-populated from tone.yaml, Save button disabled
- **Edit + Save:** Fill in Company Name, Tagline, Website, Product Description, social links. Save button should enable on first edit. Click Save → button shows "Saving…" → "Saved" (disabled).
- **Persistence:** Navigate to Dashboard and back to Settings. All fields should retain saved values. Save button should be disabled (not dirty).
- **Files on disk:** Check `primitives/brand/brand.yaml` has `company_name`, `primitives/brand/BRAND.md` references the brand name, `primitives/brand/tone.yaml` has voice/avoid/prefer arrays.
- **Agent integration:** Send a chat message asking about the brand (e.g., "What company are you helping?"). Agent should reference the configured brand name and tagline — this confirms cache invalidation worked.
- **Editable lists:** Click "+ Add" on Voice traits → new empty input appears. Type a new trait. Click ✕ on an existing trait → removed. Save and verify persistence.

**Scrolling tip:** The Settings page is long. The Voice & Tone section may be offscreen. Use `xdotool key Page_Down` to scroll the main content area if the browser scroll action doesn't work on the `<main>` element.

## Known Issues
- Chat SSE errors are silent in the UI — if the LLM call fails (e.g., invalid model ID), the chat shows "..." loading indefinitely with no error message. Check server logs if chat seems stuck.
- The server might exit if a previous process is still holding port 3000. Use `pkill -f "gtm-os start"` before restarting.
- LiteLLM warnings about botocore/sagemaker are benign — they only affect AWS-specific providers.
- After page refresh, in-memory chat state (React state) is lost. Chat session persistence is for switching between experiments within the same page session, not across refreshes.
