import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AppInfo,
  AvailableModel,
  Connection,
  Integration,
  ModelProviderInfo,
  NoKeyTool,
  ToolKeyInfo,
  disconnectApp,
  getIntegrations,
  getModelKeys,
  getToolKeys,
  initiateConnect,
  listApps,
  listConnections,
  updateIntegrationKeys,
  updateModelConfig,
  updateModelKeys,
  updateToolKeys,
  getHealth,
} from "../lib/api";

/* ─── tab type ─────────────────────────────────────────────────────────────── */
type Tab = "catalog" | "connected" | "setup" | "models";

/* ─── Category pills shown above the grid ──────────────────────────────────── */
const CATEGORIES = [
  "All",
  "CRM",
  "Communication",
  "Marketing",
  "Developer Tools",
  "Productivity",
  "Social Media",
  "Sales",
  "Finance",
];

export default function IntegrationsView() {
  /* ── platform-level keys (Composio / Pipedream) ────────────────────────── */
  const [platforms, setPlatforms] = useState<Integration[]>([]);
  const [keyDrafts, setKeyDrafts] = useState<Record<string, string>>({});
  const [keySaving, setKeySaving] = useState(false);
  const [keySaved, setKeySaved] = useState(false);

  /* ── research tool keys ─────────────────────────────────────────────────── */
  const [toolKeys, setToolKeys] = useState<ToolKeyInfo[]>([]);
  const [noKeyTools, setNoKeyTools] = useState<NoKeyTool[]>([]);
  const [toolKeyDrafts, setToolKeyDrafts] = useState<Record<string, string>>({});
  const [toolKeySaving, setToolKeySaving] = useState(false);
  const [toolKeySaved, setToolKeySaved] = useState(false);

  /* ── app catalog ───────────────────────────────────────────────────────── */
  const [apps, setApps] = useState<AppInfo[]>([]);
  const [appsLoading, setAppsLoading] = useState(false);
  const [appsError, setAppsError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All");

  /* ── connections ───────────────────────────────────────────────────────── */
  const [connections, setConnections] = useState<Connection[]>([]);
  const [connsLoading, setConnsLoading] = useState(false);

  /* ── model provider keys ────────────────────────────────────────────────── */
  const [modelProviders, setModelProviders] = useState<ModelProviderInfo[]>([]);
  const [availableModels, setAvailableModels] = useState<AvailableModel[]>([]);
  const [currentModel, setCurrentModel] = useState("");
  const [modelKeyDrafts, setModelKeyDrafts] = useState<Record<string, string>>({});
  const [modelKeySaving, setModelKeySaving] = useState(false);
  const [modelKeySaved, setModelKeySaved] = useState(false);
  const [modelSwitching, setModelSwitching] = useState(false);

  /* ── ui state ──────────────────────────────────────────────────────────── */
  const [connecting, setConnecting] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("catalog");
  const [composioConfigured, setComposioConfigured] = useState(false);

  /* ── initial load ──────────────────────────────────────────────────────── */
  useEffect(() => {
    getIntegrations()
      .then((r) => {
        setPlatforms(r.integrations);
        const composio = r.integrations.find((i) => i.name === "composio");
        setComposioConfigured(!!composio?.configured);
        if (composio?.configured) {
          setTab("catalog");
        } else {
          setTab("setup");
        }
      })
      .catch(() => null);
    getToolKeys()
      .then((r) => {
        setToolKeys(r.tool_keys);
        setNoKeyTools(r.no_key_tools);
      })
      .catch(() => null);
    getModelKeys()
      .then((r) => {
        setModelProviders(r.providers);
        setAvailableModels(r.available_models);
        setCurrentModel(r.current_model);
      })
      .catch(() => null);
  }, []);

  /* ── load apps when tab switches or search changes ─────────────────────── */
  useEffect(() => {
    if (!composioConfigured) return;
    setAppsLoading(true);
    setAppsError(null);
    listApps(search, category === "All" ? "" : category)
      .then((r) => {
        setApps(r.apps ?? []);
        if (r.error) setAppsError(r.error);
      })
      .catch((err) => {
        setApps([]);
        setAppsError(String(err));
      })
      .finally(() => setAppsLoading(false));
  }, [composioConfigured, search, category]);

  /* ── load connections ──────────────────────────────────────────────────── */
  const refreshConnections = useCallback(() => {
    if (!composioConfigured) return;
    setConnsLoading(true);
    listConnections()
      .then((r) => setConnections(r.connections))
      .catch(() => setConnections([]))
      .finally(() => setConnsLoading(false));
  }, [composioConfigured]);

  useEffect(() => {
    refreshConnections();
  }, [refreshConnections]);

  /* ── connected slug set for quick lookup ───────────────────────────────── */
  const connectedSlugs = useMemo(() => {
    const set = new Set<string>();
    for (const c of connections) {
      if (c.status === "ACTIVE") set.add(c.toolkit_slug);
    }
    return set;
  }, [connections]);

  /* ── save platform keys ────────────────────────────────────────────────── */
  const savePlatformKeys = useCallback(async () => {
    setKeySaving(true);
    try {
      const payload: Record<string, string> = {};
      for (const [name, val] of Object.entries(keyDrafts)) {
        if (name === "composio") payload.composio_api_key = val;
        if (name === "pipedream") payload.pipedream_api_key = val;
        if (name === "cua") payload.cua_api_key = val;
      }
      await updateIntegrationKeys(payload);
      setKeyDrafts({});
      setKeySaved(true);
      const [intRes, hRes] = await Promise.all([
        getIntegrations(),
        getHealth(),
      ]);
      setPlatforms(intRes.integrations);
      const composio = intRes.integrations.find((i) => i.name === "composio");
      if (composio?.configured) {
        setComposioConfigured(true);
        setTab("catalog");
      }
      void hRes;
    } catch (e) {
      console.error("Failed to save keys:", e);
    } finally {
      setKeySaving(false);
    }
  }, [keyDrafts]);

  /* ── save research tool keys ────────────────────────────────────────────── */
  const saveToolKeys = useCallback(async () => {
    setToolKeySaving(true);
    try {
      const payload: Record<string, string> = {};
      for (const [name, val] of Object.entries(toolKeyDrafts)) {
        if (name === "serper") payload.serper_api_key = val;
        if (name === "brave") payload.brave_search_api_key = val;
        if (name === "youtube") payload.youtube_api_key = val;
      }
      await updateToolKeys(payload);
      setToolKeyDrafts({});
      setToolKeySaved(true);
      const r = await getToolKeys();
      setToolKeys(r.tool_keys);
      setNoKeyTools(r.no_key_tools);
    } catch (e) {
      console.error("Failed to save tool keys:", e);
    } finally {
      setToolKeySaving(false);
    }
  }, [toolKeyDrafts]);

  /* ── save model provider keys ──────────────────────────────────────────── */
  const saveModelKeys = useCallback(async () => {
    setModelKeySaving(true);
    try {
      const payload: Record<string, string> = {};
      for (const [name, val] of Object.entries(modelKeyDrafts)) {
        if (name === "deepseek") payload.deepseek_api_key = val;
        if (name === "moonshot") payload.moonshot_api_key = val;
        if (name === "openai") payload.openai_api_key = val;
        if (name === "anthropic") payload.anthropic_api_key = val;
        if (name === "groq") payload.groq_api_key = val;
        if (name === "google") payload.google_api_key = val;
      }
      await updateModelKeys(payload);
      setModelKeyDrafts({});
      setModelKeySaved(true);
      const r = await getModelKeys();
      setModelProviders(r.providers);
      setAvailableModels(r.available_models);
      setCurrentModel(r.current_model);
    } catch (e) {
      console.error("Failed to save model keys:", e);
    } finally {
      setModelKeySaving(false);
    }
  }, [modelKeyDrafts]);

  /* ── switch model ──────────────────────────────────────────────────────── */
  const handleModelSwitch = useCallback(async (modelId: string) => {
    setModelSwitching(true);
    try {
      const res = await updateModelConfig({ model: modelId });
      setCurrentModel(res.model);
    } catch (e) {
      console.error("Failed to switch model:", e);
    } finally {
      setModelSwitching(false);
    }
  }, []);

  /* ── connect to an app ─────────────────────────────────────────────────── */
  const handleConnect = useCallback(async (slug: string) => {
    setConnecting(slug);
    try {
      const res = await initiateConnect(slug, window.location.origin + "/integrations/callback");
      if (res.ok && res.redirect_url) {
        window.open(res.redirect_url, "_blank", "width=600,height=700");
      }
      // Poll for connection after a short delay.
      setTimeout(() => refreshConnections(), 3000);
      setTimeout(() => refreshConnections(), 8000);
      setTimeout(() => refreshConnections(), 15000);
    } catch (e) {
      console.error("Connect failed:", e);
    } finally {
      setConnecting(null);
    }
  }, [refreshConnections]);

  /* ── disconnect ────────────────────────────────────────────────────────── */
  const handleDisconnect = useCallback(
    async (connId: string) => {
      try {
        await disconnectApp(connId);
        refreshConnections();
      } catch (e) {
        console.error("Disconnect failed:", e);
      }
    },
    [refreshConnections],
  );

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-5xl p-6 space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-xl font-semibold">Integrations</h1>
          <p className="mt-1 text-sm text-[#A1A1AA]">
            Connect tools and services so your GTM agents can execute campaigns,
            send emails, manage CRM data, and more.
          </p>
        </div>

        {/* Tab bar */}
        <div className="flex items-center gap-1 border-b border-[#2A2A2A]">
          {(
            [
              { key: "catalog" as Tab, label: "App Catalog", count: apps.length },
              { key: "connected" as Tab, label: "Connected", count: connections.filter((c) => c.status === "ACTIVE").length },
              { key: "setup" as Tab, label: "Platform Keys", count: undefined as number | undefined },
              { key: "models" as Tab, label: "Models", count: modelProviders.filter((p) => p.configured).length },
            ]
          ).map(({ key, label, count }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                tab === key
                  ? "border-emerald-400 text-white"
                  : "border-transparent text-[#A1A1AA] hover:text-white"
              }`}
            >
              {label}
              {count !== undefined && (
                <span className="ml-1.5 text-xs text-[#777]">({count})</span>
              )}
            </button>
          ))}
        </div>

        {/* ── Setup Tab ─────────────────────────────────────────────────── */}
        {tab === "setup" && (
          <div className="space-y-6">
            {/* Platform Keys */}
            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-semibold text-[#A1A1AA] uppercase tracking-wider mb-1">Platform Keys</h3>
                <p className="text-xs text-[#777]">
                  Composio provides 250+ app connections; Pipedream adds 2,400+ pre-built actions.
                </p>
              </div>
              {platforms.map((p) => (
                <PlatformKeyCard
                  key={p.name}
                  platform={p}
                  draft={keyDrafts[p.name] ?? ""}
                  onDraftChange={(val) => {
                    setKeyDrafts((prev) => ({ ...prev, [p.name]: val }));
                    setKeySaved(false);
                  }}
                />
              ))}
              {Object.keys(keyDrafts).length > 0 && (
                <button
                  onClick={savePlatformKeys}
                  disabled={keySaving}
                  className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {keySaving ? "Saving…" : "Save Platform Keys"}
                </button>
              )}
              {keySaved && (
                <span className="text-xs text-emerald-400">
                  Keys saved & reloaded
                </span>
              )}
            </div>

            {/* Research Tool Keys */}
            <div className="space-y-4 border-t border-[#2A2A2A] pt-6">
              <div>
                <h3 className="text-sm font-semibold text-[#A1A1AA] uppercase tracking-wider mb-1">Research Tool Keys</h3>
                <p className="text-xs text-[#777]">
                  API keys for research tools used during experiments. Tools without keys listed below work out of the box.
                </p>
              </div>
              {toolKeys.map((tk) => (
                <ToolKeyCard
                  key={tk.name}
                  toolKey={tk}
                  draft={toolKeyDrafts[tk.name] ?? ""}
                  onDraftChange={(val) => {
                    setToolKeyDrafts((prev) => ({ ...prev, [tk.name]: val }));
                    setToolKeySaved(false);
                  }}
                />
              ))}
              {toolKeys.length === 0 && (
                <p className="text-xs text-[#555] italic">Loading tool keys…</p>
              )}
              {Object.keys(toolKeyDrafts).length > 0 && (
                <button
                  onClick={saveToolKeys}
                  disabled={toolKeySaving}
                  className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {toolKeySaving ? "Saving…" : "Save Research Keys"}
                </button>
              )}
              {toolKeySaved && (
                <span className="text-xs text-emerald-400">
                  Keys saved & reloaded
                </span>
              )}
              {noKeyTools.length > 0 && (
                <div className="border-t border-[#2A2A2A] pt-3">
                  <p className="mb-2 text-xs text-[#A1A1AA] uppercase tracking-wider">No Key Required</p>
                  <div className="flex flex-wrap gap-2">
                    {noKeyTools.map((t) => (
                      <span
                        key={t.name}
                        className="inline-flex items-center gap-1 rounded-full bg-emerald-900/30 px-2.5 py-0.5 text-[11px] text-emerald-400"
                      >
                        <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400" />
                        {t.label}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Catalog Tab ───────────────────────────────────────────────── */}
        {tab === "catalog" && (
          <div className="space-y-4">
            {!composioConfigured ? (
              <div className="rounded-lg border border-[#2A2A2A] bg-[#1A1A1A] p-6 text-center">
                <p className="text-sm text-[#A1A1AA]">
                  Add your Composio API key in{" "}
                  <button
                    onClick={() => setTab("setup")}
                    className="text-emerald-400 hover:underline"
                  >
                    Platform Keys
                  </button>{" "}
                  to browse and connect 250+ apps.
                </p>
              </div>
            ) : (
              <>
                {/* Search + category filter */}
                <div className="flex flex-wrap items-center gap-3">
                  <div className="relative flex-1 min-w-[200px]">
                    <input
                      type="text"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder="Search apps…"
                      className="w-full rounded-md border border-[#2A2A2A] bg-[#1A1A1A] px-3 py-2 pl-9 text-sm text-[#FAFAFA] placeholder-[#555] outline-none focus:border-emerald-600 transition-colors"
                    />
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[#555] text-sm">
                      🔍
                    </span>
                  </div>
                  <button
                    onClick={refreshConnections}
                    className="rounded-md border border-[#2A2A2A] px-3 py-2 text-xs text-[#A1A1AA] hover:bg-[#2A2A2A] transition-colors"
                    title="Refresh connections"
                  >
                    ↻ Refresh
                  </button>
                </div>

                {/* Category pills */}
                <div className="flex flex-wrap gap-2">
                  {CATEGORIES.map((cat) => (
                    <button
                      key={cat}
                      onClick={() => setCategory(cat)}
                      className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                        category === cat
                          ? "bg-emerald-600 text-white"
                          : "bg-[#1A1A1A] border border-[#2A2A2A] text-[#A1A1AA] hover:text-white hover:border-[#3A3A3A]"
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>

                {/* App grid */}
                {appsLoading ? (
                  <div className="py-12 text-center text-sm text-[#A1A1AA]">
                    Loading apps…
                  </div>
                ) : appsError ? (
                  <div className="rounded-lg border border-red-900/50 bg-red-900/10 p-4 text-center">
                    <p className="text-sm text-red-400">
                      Failed to load apps: {appsError}
                    </p>
                    <p className="mt-1 text-xs text-[#777]">
                      Check your Composio API key or try refreshing.
                    </p>
                  </div>
                ) : apps.length === 0 ? (
                  <div className="py-12 text-center text-sm text-[#A1A1AA]">
                    {search
                      ? `No apps found for "${search}"`
                      : "No apps available. Check your Composio API key."}
                  </div>
                ) : (
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {apps.map((app) => (
                      <AppCard
                        key={app.slug}
                        app={app}
                        connected={connectedSlugs.has(app.slug)}
                        connecting={connecting === app.slug}
                        onConnect={() => handleConnect(app.slug)}
                      />
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* ── Connected Tab ─────────────────────────────────────────────── */}
        {tab === "connected" && (
          <div className="space-y-4">
            {!composioConfigured ? (
              <div className="rounded-lg border border-[#2A2A2A] bg-[#1A1A1A] p-6 text-center">
                <p className="text-sm text-[#A1A1AA]">
                  Add your Composio API key to manage connected apps.
                </p>
              </div>
            ) : connsLoading ? (
              <div className="py-12 text-center text-sm text-[#A1A1AA]">
                Loading connections…
              </div>
            ) : connections.length === 0 ? (
              <div className="rounded-lg border border-[#2A2A2A] bg-[#1A1A1A] p-8 text-center">
                <p className="text-sm text-[#A1A1AA]">
                  No connected apps yet. Browse the{" "}
                  <button
                    onClick={() => setTab("catalog")}
                    className="text-emerald-400 hover:underline"
                  >
                    App Catalog
                  </button>{" "}
                  to connect your first tool.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {connections.map((conn) => (
                  <ConnectionRow
                    key={conn.id}
                    connection={conn}
                    onDisconnect={() => handleDisconnect(conn.id)}
                  />
                ))}
              </div>
            )}
          </div>
        )}
        {/* ── Models Tab ────────────────────────────────────────────────── */}
        {tab === "models" && (
          <div className="space-y-6">
            {/* Active Model Selector */}
            <div className="rounded-lg border border-[#2A2A2A] bg-[#1A1A1A] p-4 space-y-3">
              <h3 className="text-sm font-semibold text-[#A1A1AA] uppercase tracking-wider">Active Model</h3>
              <div className="flex items-center gap-3">
                <select
                  value={currentModel}
                  onChange={(e) => handleModelSwitch(e.target.value)}
                  disabled={modelSwitching}
                  className="flex-1 rounded-md border border-[#2A2A2A] bg-[#0F0F0F] px-3 py-2 text-sm text-[#FAFAFA] outline-none focus:border-emerald-600 transition-colors"
                >
                  <option value={currentModel}>{currentModel}</option>
                  {availableModels
                    .filter((m) => m.id !== currentModel)
                    .map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.id} ({m.provider})
                      </option>
                    ))}
                </select>
                {modelSwitching && (
                  <span className="text-xs text-[#A1A1AA]">Switching...</span>
                )}
              </div>
              <p className="text-xs text-[#777]">
                Switch the LLM used by all agents. Only models with configured API keys are shown.
                Changes take effect immediately.
              </p>
            </div>

            {/* Provider API Keys */}
            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-semibold text-[#A1A1AA] uppercase tracking-wider mb-1">LLM Provider Keys</h3>
                <p className="text-xs text-[#777]">
                  Add API keys for LLM providers. Models become available in the selector above once their provider key is configured.
                </p>
              </div>
              {modelProviders.map((provider) => (
                <ModelProviderCard
                  key={provider.name}
                  provider={provider}
                  draft={modelKeyDrafts[provider.name] ?? ""}
                  onDraftChange={(val) => {
                    setModelKeyDrafts((prev) => ({ ...prev, [provider.name]: val }));
                    setModelKeySaved(false);
                  }}
                />
              ))}
              {Object.keys(modelKeyDrafts).length > 0 && (
                <button
                  onClick={saveModelKeys}
                  disabled={modelKeySaving}
                  className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {modelKeySaving ? "Saving..." : "Save Model Keys"}
                </button>
              )}
              {modelKeySaved && (
                <span className="text-xs text-emerald-400">
                  Keys saved & models updated
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Sub-components ──────────────────────────────────────────────────────── */

function AppCard({
  app,
  connected,
  connecting,
  onConnect,
}: {
  app: AppInfo;
  connected: boolean;
  connecting: boolean;
  onConnect: () => void;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-[#2A2A2A] bg-[#1A1A1A] p-4 transition-colors hover:border-[#3A3A3A]">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          {app.logo ? (
            <img
              src={app.logo}
              alt={app.name}
              className="h-9 w-9 rounded-lg bg-[#2A2A2A] object-contain p-1"
            />
          ) : (
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#2A2A2A] text-lg">
              🔌
            </div>
          )}
          <div>
            <div className="text-sm font-medium">{app.name}</div>
            {app.categories.length > 0 && (
              <span className="text-[10px] text-[#777]">
                {app.categories.slice(0, 2).join(" · ")}
              </span>
            )}
          </div>
        </div>
        {connected ? (
          <span className="rounded-full bg-emerald-900/50 px-2 py-0.5 text-[10px] font-medium text-emerald-400">
            Connected
          </span>
        ) : null}
      </div>
      <p className="flex-1 text-xs text-[#777] line-clamp-2">
        {app.description || "Connect this app to your GTM agents."}
      </p>
      <button
        onClick={onConnect}
        disabled={connecting}
        className={`w-full rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
          connected
            ? "border border-[#2A2A2A] text-[#A1A1AA] hover:bg-[#2A2A2A]"
            : "bg-emerald-600 text-white hover:bg-emerald-500"
        } disabled:opacity-40 disabled:cursor-not-allowed`}
      >
        {connecting
          ? "Connecting…"
          : connected
            ? "Reconnect"
            : "Connect"}
      </button>
    </div>
  );
}

function ConnectionRow({
  connection,
  onDisconnect,
}: {
  connection: Connection;
  onDisconnect: () => void;
}) {
  const isActive = connection.status === "ACTIVE";
  return (
    <div className="flex items-center justify-between rounded-lg border border-[#2A2A2A] bg-[#1A1A1A] px-4 py-3">
      <div className="flex items-center gap-3">
        {connection.toolkit_logo ? (
          <img
            src={connection.toolkit_logo}
            alt={connection.toolkit_name}
            className="h-8 w-8 rounded-lg bg-[#2A2A2A] object-contain p-1"
          />
        ) : (
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#2A2A2A] text-base">
            🔌
          </div>
        )}
        <div>
          <div className="text-sm font-medium">
            {connection.toolkit_name || connection.toolkit_slug}
          </div>
          <div className="text-[10px] text-[#777]">
            {connection.created_at
              ? `Connected ${new Date(connection.created_at).toLocaleDateString()}`
              : ""}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <span
          className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
            isActive
              ? "bg-emerald-900/50 text-emerald-400"
              : "bg-yellow-900/50 text-yellow-400"
          }`}
        >
          {connection.status}
        </span>
        <button
          onClick={onDisconnect}
          className="rounded px-2 py-1 text-xs text-red-400 hover:bg-red-900/20 transition-colors"
        >
          Disconnect
        </button>
      </div>
    </div>
  );
}

function PlatformKeyCard({
  platform,
  draft,
  onDraftChange,
}: {
  platform: Integration;
  draft: string;
  onDraftChange: (val: string) => void;
}) {
  const [showKey, setShowKey] = useState(false);
  return (
    <div className="rounded-lg border border-[#2A2A2A] bg-[#1A1A1A] p-4 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{platform.label}</span>
          <span
            className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
              platform.configured
                ? "bg-emerald-900/50 text-emerald-400"
                : "bg-[#2A2A2A] text-[#777]"
            }`}
          >
            {platform.configured ? "Connected" : "Not configured"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <a
            href={platform.docs_url}
            target="_blank"
            rel="noreferrer"
            className="text-[10px] text-[#A1A1AA] hover:text-[#FAFAFA] transition-colors"
          >
            Docs
          </a>
          <a
            href={platform.dashboard_url}
            target="_blank"
            rel="noreferrer"
            className="text-[10px] text-[#A1A1AA] hover:text-[#FAFAFA] transition-colors"
          >
            Dashboard
          </a>
        </div>
      </div>
      <p className="text-xs text-[#777]">{platform.description}</p>
      <div className="flex items-center gap-2">
        <input
          type={showKey ? "text" : "password"}
          value={draft}
          onChange={(e) => onDraftChange(e.target.value)}
          placeholder={
            platform.configured
              ? `Current: ${platform.masked_key} — enter new key to update`
              : "Paste your API key…"
          }
          className="flex-1 rounded-md border border-[#2A2A2A] bg-[#0F0F0F] px-3 py-1.5 text-sm text-[#FAFAFA] placeholder-[#555] outline-none focus:border-emerald-600 transition-colors font-mono"
        />
        <button
          onClick={() => setShowKey((p) => !p)}
          className="rounded px-2 py-1 text-xs text-[#A1A1AA] hover:bg-[#2A2A2A] transition-colors"
        >
          {showKey ? "Hide" : "Show"}
        </button>
      </div>
    </div>
  );
}

function ToolKeyCard({
  toolKey,
  draft,
  onDraftChange,
}: {
  toolKey: ToolKeyInfo;
  draft: string;
  onDraftChange: (val: string) => void;
}) {
  const [showKey, setShowKey] = useState(false);
  return (
    <div className="rounded-lg border border-[#2A2A2A] bg-[#1A1A1A] p-4 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{toolKey.label}</span>
          <span
            className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
              toolKey.configured
                ? "bg-emerald-900/50 text-emerald-400"
                : "bg-amber-900/50 text-amber-400"
            }`}
          >
            {toolKey.configured ? "Active" : "Missing"}
          </span>
        </div>
        <span className="text-[10px] text-[#555]">
          Used by: {toolKey.required_by.join(", ")}
        </span>
      </div>
      <p className="text-xs text-[#777]">{toolKey.description}</p>
      <div>
        <label className="mb-1 block text-xs text-[#A1A1AA]">
          {toolKey.env_var}
          {toolKey.masked_key && (
            <span className="ml-2 text-[#555]">Current: {toolKey.masked_key}</span>
          )}
        </label>
        <div className="flex items-center gap-2">
          <input
            type={showKey ? "text" : "password"}
            value={draft}
            onChange={(e) => onDraftChange(e.target.value)}
            placeholder={toolKey.configured ? "Enter new key to update…" : "Paste your API key…"}
            className="flex-1 rounded-md border border-[#2A2A2A] bg-[#0F0F0F] px-3 py-1.5 text-sm text-[#FAFAFA] placeholder-[#555] outline-none focus:border-emerald-600 transition-colors font-mono"
          />
          <button
            onClick={() => setShowKey((p) => !p)}
            className="rounded px-2 py-1 text-xs text-[#A1A1AA] hover:bg-[#2A2A2A] transition-colors"
          >
            {showKey ? "Hide" : "Show"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ModelProviderCard({
  provider,
  draft,
  onDraftChange,
}: {
  provider: ModelProviderInfo;
  draft: string;
  onDraftChange: (val: string) => void;
}) {
  const [showKey, setShowKey] = useState(false);
  return (
    <div className="rounded-lg border border-[#2A2A2A] bg-[#1A1A1A] p-4 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{provider.label}</span>
          <span
            className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
              provider.configured
                ? "bg-emerald-900/50 text-emerald-400"
                : "bg-[#2A2A2A] text-[#777]"
            }`}
          >
            {provider.configured ? "Active" : "Not configured"}
          </span>
        </div>
        <a
          href={provider.docs_url}
          target="_blank"
          rel="noreferrer"
          className="text-[10px] text-[#A1A1AA] hover:text-[#FAFAFA] transition-colors"
        >
          Get API Key
        </a>
      </div>
      <p className="text-xs text-[#777]">{provider.description}</p>
      <div className="flex flex-wrap gap-1.5">
        {provider.models.map((m) => (
          <span
            key={m}
            className="rounded-full bg-[#2A2A2A] px-2 py-0.5 text-[10px] text-[#A1A1AA] font-mono"
          >
            {m}
          </span>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <input
          type={showKey ? "text" : "password"}
          value={draft}
          onChange={(e) => onDraftChange(e.target.value)}
          placeholder={
            provider.configured
              ? `Current: ${provider.masked_key} — enter new key to update`
              : "Paste your API key..."
          }
          className="flex-1 rounded-md border border-[#2A2A2A] bg-[#0F0F0F] px-3 py-1.5 text-sm text-[#FAFAFA] placeholder-[#555] outline-none focus:border-emerald-600 transition-colors font-mono"
        />
        <button
          onClick={() => setShowKey((p) => !p)}
          className="rounded px-2 py-1 text-xs text-[#A1A1AA] hover:bg-[#2A2A2A] transition-colors"
        >
          {showKey ? "Hide" : "Show"}
        </button>
      </div>
    </div>
  );
}
