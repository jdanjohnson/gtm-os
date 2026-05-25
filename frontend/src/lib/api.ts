import {
  fetchEventSource,
  EventSourceMessage,
} from "@microsoft/fetch-event-source";

export type ExperimentPhase =
  | "design"
  | "build"
  | "execute"
  | "measure"
  | "learn"
  | "complete"
  | "paused";

export interface Experiment {
  id: string;
  name: string;
  description?: string | null;
  hypothesis?: string | null;
  phase: ExperimentPhase;
  play_ids: string[];
  config: Record<string, unknown>;
  current_agent?: string | null;
  token_budget: number;
  tokens_used: number;
  schedule_id?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface Run {
  id: string;
  phase: string;
  status: string;
  tokens_used: number;
  started_at?: string;
  completed_at?: string;
  tools_used?: { name: string; arguments: Record<string, unknown> }[];
  error?: string | null;
}

export interface MemoryItem {
  id: string;
  type: string;
  content: string;
  source?: string | null;
  experiment_id?: string | null;
  confidence: number;
  similarity?: number | null;
  reinforced_by?: string[];
  created_at?: string;
  updated_at?: string;
}

export interface PlayMeta {
  id: string;
  name: string;
  kind: string; // playbook | workflow | skill | tool | play
  description: string;
  category: string;
  tags: string[];
  channel: string;
}

export interface PrimitivesSummary {
  agents: string[];
  plays: string[];
  plays_meta: PlayMeta[];
  phase_rules: string[];
  channel_rules: string[];
  brand_loaded: boolean;
  schedules: Record<string, unknown>;
}

export interface ThreadMessage {
  id: string;
  role: string;
  content: string;
  tool_calls?: unknown;
  experiment_id?: string | null;
  thread_id?: string | null;
  created_at?: string;
}

const base = "";

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(base + path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${await res.text()}`);
  }
  return (await res.json()) as T;
}

export async function getHealth() {
  return json<{
    ok: boolean;
    version: string;
    model: string;
    scheduler_running: boolean;
    composio_configured: boolean;
    pipedream_configured: boolean;
    cua_configured: boolean;
    primitives_dir: string;
  }>("/api/health");
}

export async function listExperiments() {
  return json<{ experiments: Experiment[] }>("/api/experiments");
}

export async function getExperiment(id: string) {
  return json<{ experiment: Experiment; runs: Run[] }>(`/api/experiments/${id}`);
}

export async function createExperiment(body: {
  name: string;
  description?: string;
  hypothesis?: string;
  play_ids?: string[];
  channel?: string;
  config?: Record<string, unknown>;
  token_budget?: number;
}) {
  return json<{ experiment: Experiment }>("/api/experiments", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function pauseExperiment(id: string) {
  return json<{ experiment: Experiment }>(`/api/experiments/${id}/pause`, {
    method: "POST",
  });
}

export async function resumeExperiment(id: string, target_phase = "design") {
  return json<{ experiment: Experiment }>(
    `/api/experiments/${id}/resume?target_phase=${encodeURIComponent(target_phase)}`,
    { method: "POST" },
  );
}

export async function runTick(id: string) {
  return json<{
    ok: boolean;
    run_id: string;
    phase: string;
    tokens_used: number;
    error?: string;
    message?: string;
    tool_calls?: { name: string; arguments: Record<string, unknown> }[];
  }>(`/api/experiments/${id}/run-tick`, { method: "POST" });
}

export async function scheduleExperiment(
  id: string,
  body: {
    cron_expr?: string;
    interval_seconds?: number;
    max_cost?: number;
    type?: string;
  },
) {
  return json<{ schedule: unknown }>(`/api/experiments/${id}/schedule`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function listMemory(typeFilter?: string) {
  const q = typeFilter ? `?type_filter=${encodeURIComponent(typeFilter)}` : "";
  return json<{ memories: MemoryItem[] }>(`/api/memory${q}`);
}

export async function searchMemory(query: string, type_filter?: string) {
  return json<{ results: MemoryItem[] }>(`/api/memory/search`, {
    method: "POST",
    body: JSON.stringify({ query, type_filter, limit: 25 }),
  });
}

export async function getPrimitives() {
  return json<PrimitivesSummary>("/api/primitives");
}

export interface BrandIdentity {
  company_name: string;
  tagline: string;
  website: string;
  product_description: string;
  social: Record<string, string>;
  icp: string;
  icp_negative: string;
  voice: string[];
  avoid: string[];
  prefer: string[];
  email_max_sentences: number;
  email_max_words: number;
  brand_body?: string;
}

export async function getBrand() {
  return json<BrandIdentity>("/api/brand");
}

export async function updateBrand(body: Omit<BrandIdentity, "brand_body">) {
  return json<BrandIdentity>("/api/brand", {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function getThreadMessages(threadId: string) {
  return json<{ thread_id: string; messages: ThreadMessage[] }>(
    `/api/threads/${threadId}/messages`,
  );
}

export interface Integration {
  name: string;
  label: string;
  configured: boolean;
  masked_key: string;
  has_env_key: boolean;
  env_var: string;
  docs_url: string;
  dashboard_url: string;
  description: string;
}

export async function getIntegrations() {
  return json<{ integrations: Integration[] }>("/api/integrations");
}

export async function updateIntegrationKeys(keys: {
  composio_api_key?: string;
  pipedream_api_key?: string;
  cua_api_key?: string;
}) {
  return json<{ ok: boolean; updated: string[] }>("/api/integrations/keys", {
    method: "PUT",
    body: JSON.stringify(keys),
  });
}

// --- LLM Model Provider Keys ---

export interface ModelProviderInfo {
  name: string;
  label: string;
  env_var: string;
  configured: boolean;
  masked_key: string;
  models: string[];
  description: string;
  docs_url: string;
}

export interface AvailableModel {
  id: string;
  provider: string;
}

export async function getModelKeys() {
  return json<{
    providers: ModelProviderInfo[];
    available_models: AvailableModel[];
    current_model: string;
    current_temperature: number;
    current_max_tokens: number;
  }>("/api/integrations/model-keys");
}

export async function updateModelKeys(keys: {
  deepseek_api_key?: string;
  moonshot_api_key?: string;
  openai_api_key?: string;
  anthropic_api_key?: string;
  groq_api_key?: string;
  google_api_key?: string;
}) {
  return json<{ ok: boolean; updated: string[] }>("/api/integrations/model-keys", {
    method: "PUT",
    body: JSON.stringify(keys),
  });
}

export async function updateModelConfig(config: {
  model?: string;
  temperature?: number;
  max_tokens?: number;
}) {
  return json<{
    ok: boolean;
    changes: string[];
    model: string;
    temperature: number;
    max_tokens: number;
  }>("/api/integrations/model-config", {
    method: "PUT",
    body: JSON.stringify(config),
  });
}

// --- Research Tool API Keys ---

export interface ToolKeyInfo {
  name: string;
  label: string;
  env_var: string;
  configured: boolean;
  masked_key: string;
  required_by: string[];
  description: string;
}

export interface NoKeyTool {
  name: string;
  label: string;
  status: string;
}

export async function getToolKeys() {
  return json<{ tool_keys: ToolKeyInfo[]; no_key_tools: NoKeyTool[] }>(
    "/api/integrations/tool-keys",
  );
}

export async function updateToolKeys(keys: {
  serper_api_key?: string;
  brave_search_api_key?: string;
  youtube_api_key?: string;
}) {
  return json<{ ok: boolean; updated: string[] }>("/api/integrations/tool-keys", {
    method: "PUT",
    body: JSON.stringify(keys),
  });
}

// --- App catalog & connections (Composio) ---

export interface AppInfo {
  slug: string;
  name: string;
  description: string;
  logo: string;
  categories: string[];
  auth_schemes: string[];
}

export interface Connection {
  id: string;
  toolkit_slug: string;
  toolkit_name: string;
  toolkit_logo: string;
  status: string;
  created_at: string;
  user_id: string;
}

export async function listApps(search = "", category = "", limit = 50) {
  const params = new URLSearchParams();
  if (search) params.set("search", search);
  if (category) params.set("category", category);
  params.set("limit", String(limit));
  return json<{ apps: AppInfo[]; error?: string }>(
    `/api/integrations/apps?${params}`,
  );
}

export async function listConnections() {
  return json<{ connections: Connection[]; error?: string }>(
    "/api/integrations/connections",
  );
}

export async function initiateConnect(toolkit_slug: string, redirect_url?: string) {
  return json<{
    ok: boolean;
    redirect_url?: string;
    connection_id?: string;
    auth_scheme?: string;
    error?: string;
    detail?: string;
  }>("/api/integrations/connect", {
    method: "POST",
    body: JSON.stringify({ toolkit_slug, redirect_url }),
  });
}

export async function disconnectApp(connectionId: string) {
  return json<{ ok: boolean; error?: string }>(
    `/api/integrations/connections/${connectionId}`,
    { method: "DELETE" },
  );
}

export interface ChatEvent {
  type: "meta" | "token" | "tool_call" | "tool_result" | "final" | "error";
  payload: unknown;
}

export async function streamChat(
  body: {
    message: string;
    thread_id?: string | null;
    experiment_id?: string | null;
    agent?: string | null;
  },
  handlers: {
    onMeta?: (meta: { thread_id: string; agent: string; experiment_id?: string | null }) => void;
    onToken?: (text: string) => void;
    onToolCall?: (name: string, args: Record<string, unknown>) => void;
    onToolResult?: (name: string, ok: boolean, result: unknown) => void;
    onFinal?: (data: { message: string; tokens: number; tool_calls: unknown[] }) => void;
    onError?: (msg: string) => void;
  },
  signal?: AbortSignal,
): Promise<void> {
  await fetchEventSource(base + "/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
    openWhenHidden: true,
    onmessage(ev: EventSourceMessage) {
      const data = ev.data ? safeParse(ev.data) : null;
      switch (ev.event) {
        case "meta":
          handlers.onMeta?.(data);
          break;
        case "token":
          handlers.onToken?.(data?.text ?? "");
          break;
        case "tool_call":
          handlers.onToolCall?.(data?.name, data?.arguments ?? {});
          break;
        case "tool_result":
          handlers.onToolResult?.(data?.name, !!data?.ok, data?.result);
          break;
        case "final":
          handlers.onFinal?.(data);
          break;
        case "error":
          handlers.onError?.(data?.message ?? "stream error");
          break;
      }
    },
    onerror(err) {
      handlers.onError?.(String(err));
      throw err;
    },
  });
}

function safeParse(s: string) {
  try {
    return JSON.parse(s);
  } catch {
    return s;
  }
}
