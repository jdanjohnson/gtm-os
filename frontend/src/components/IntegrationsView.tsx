import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AppInfo,
  Connection,
  Integration,
  disconnectApp,
  getIntegrations,
  initiateConnect,
  listApps,
  listConnections,
  updateIntegrationKeys,
  getHealth,
} from "../lib/api";

/* ─── tab type ─────────────────────────────────────────────────────────────── */
type Tab = "catalog" | "connected" | "setup";

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

  /* ── app catalog ───────────────────────────────────────────────────────── */
  const [apps, setApps] = useState<AppInfo[]>([]);
  const [appsLoading, setAppsLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All");

  /* ── connections ───────────────────────────────────────────────────────── */
  const [connections, setConnections] = useState<Connection[]>([]);
  const [connsLoading, setConnsLoading] = useState(false);

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
  }, []);

  /* ── load apps when tab switches or search changes ─────────────────────── */
  useEffect(() => {
    if (!composioConfigured) return;
    setAppsLoading(true);
    listApps(search, category === "All" ? "" : category)
      .then((r) => setApps(r.apps))
      .catch(() => setApps([]))
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
      void hRes; // health used elsewhere
    } catch (e) {
      console.error("Failed to save keys:", e);
    } finally {
      setKeySaving(false);
    }
  }, [keyDrafts]);

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
      <div className="max-w-5xl p-7 space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-xl font-bold text-gray-900">Integrations</h1>
          <p className="mt-1 text-sm text-gray-500">
            Connect tools and services so your GTM agents can execute campaigns,
            send emails, manage CRM data, and more.
          </p>
        </div>

        {/* Tab bar */}
        <div className="flex items-center gap-1 border-b border-black/[0.06]">
          {(
            [
              { key: "catalog" as Tab, label: "App Catalog", count: apps.length },
              { key: "connected" as Tab, label: "Connected", count: connections.filter((c) => c.status === "ACTIVE").length },
              { key: "setup" as Tab, label: "Platform Keys", count: undefined as number | undefined },
            ]
          ).map(({ key, label, count }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                tab === key
                  ? "border-coral text-gray-900"
                  : "border-transparent text-gray-500 hover:text-gray-900"
              }`}
            >
              {label}
              {count !== undefined && (
                <span className="ml-1.5 text-xs text-gray-500">({count})</span>
              )}
            </button>
          ))}
        </div>

        {/* ── Setup Tab ─────────────────────────────────────────────────── */}
        {tab === "setup" && (
          <div className="space-y-4">
            <p className="text-sm text-gray-500">
              Enter your platform API keys to unlock the integration catalog.
              Composio provides 250+ app connections; Pipedream adds 2,400+
              pre-built actions.
            </p>
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
                className="rounded-md bg-coral px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-coral-hover disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {keySaving ? "Saving…" : "Save Keys"}
              </button>
            )}
            {keySaved && (
              <span className="text-xs text-emerald-600">
                Keys saved & reloaded
              </span>
            )}
          </div>
        )}

        {/* ── Catalog Tab ───────────────────────────────────────────────── */}
        {tab === "catalog" && (
          <div className="space-y-4">
            {!composioConfigured ? (
              <div className="glass-heavy rounded-2xl p-6 text-center">
                <p className="text-sm text-gray-500">
                  Add your Composio API key in{" "}
                  <button
                    onClick={() => setTab("setup")}
                    className="text-coral hover:underline"
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
                      className="w-full rounded-md border border-black/[0.06] glass-heavy px-3 py-2 pl-9 text-sm text-gray-900 placeholder-gray-400 outline-none focus:border-coral/40 transition-colors"
                    />
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">
                      🔍
                    </span>
                  </div>
                  <button
                    onClick={refreshConnections}
                    className="rounded-md border border-black/[0.06] px-3 py-2 text-xs text-gray-500 hover:bg-black/[0.04] transition-colors"
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
                          ? "bg-coral text-white"
                          : "glass-heavy border border-black/[0.06] text-gray-500 hover:text-gray-700 hover:border-black/[0.08]"
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>

                {/* App grid */}
                {appsLoading ? (
                  <div className="py-12 text-center text-sm text-gray-500">
                    Loading apps…
                  </div>
                ) : apps.length === 0 ? (
                  <div className="py-12 text-center text-sm text-gray-500">
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
              <div className="glass-heavy rounded-2xl p-6 text-center">
                <p className="text-sm text-gray-500">
                  Add your Composio API key to manage connected apps.
                </p>
              </div>
            ) : connsLoading ? (
              <div className="py-12 text-center text-sm text-gray-500">
                Loading connections…
              </div>
            ) : connections.length === 0 ? (
              <div className="glass-heavy rounded-2xl p-8 text-center">
                <p className="text-sm text-gray-500">
                  No connected apps yet. Browse the{" "}
                  <button
                    onClick={() => setTab("catalog")}
                    className="text-coral hover:underline"
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
    <div className="flex flex-col gap-3 glass-heavy rounded-2xl p-4 transition-colors hover:border-black/[0.08]">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          {app.logo ? (
            <img
              src={app.logo}
              alt={app.name}
              className="h-9 w-9 rounded-lg bg-black/[0.04] object-contain p-1"
            />
          ) : (
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-black/[0.04] text-lg">
              🔌
            </div>
          )}
          <div>
            <div className="text-sm font-medium">{app.name}</div>
            {app.categories.length > 0 && (
              <span className="text-[10px] text-gray-500">
                {app.categories.slice(0, 2).join(" · ")}
              </span>
            )}
          </div>
        </div>
        {connected ? (
          <span className="rounded-full bg-emerald-900/50 px-2 py-0.5 text-[10px] font-medium text-emerald-600">
            Connected
          </span>
        ) : null}
      </div>
      <p className="flex-1 text-xs text-gray-500 line-clamp-2">
        {app.description || "Connect this app to your GTM agents."}
      </p>
      <button
        onClick={onConnect}
        disabled={connecting}
        className={`w-full rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
          connected
            ? "border border-black/[0.06] text-gray-500 hover:bg-black/[0.04]"
            : "bg-coral text-white hover:bg-coral-hover"
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
    <div className="flex items-center justify-between glass-heavy rounded-2xl px-4 py-3">
      <div className="flex items-center gap-3">
        {connection.toolkit_logo ? (
          <img
            src={connection.toolkit_logo}
            alt={connection.toolkit_name}
            className="h-8 w-8 rounded-lg bg-black/[0.04] object-contain p-1"
          />
        ) : (
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-black/[0.04] text-base">
            🔌
          </div>
        )}
        <div>
          <div className="text-sm font-medium">
            {connection.toolkit_name || connection.toolkit_slug}
          </div>
          <div className="text-[10px] text-gray-500">
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
              ? "bg-emerald-500/10 text-emerald-600"
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
    <div className="glass-heavy rounded-2xl p-4 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{platform.label}</span>
          <span
            className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
              platform.configured
                ? "bg-emerald-500/10 text-emerald-600"
                : "bg-black/[0.04] text-gray-500"
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
            className="text-[10px] text-gray-500 hover:text-gray-900 transition-colors"
          >
            Docs
          </a>
          <a
            href={platform.dashboard_url}
            target="_blank"
            rel="noreferrer"
            className="text-[10px] text-gray-500 hover:text-gray-900 transition-colors"
          >
            Dashboard
          </a>
        </div>
      </div>
      <p className="text-xs text-gray-500">{platform.description}</p>
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
          className="flex-1 rounded-md border border-black/[0.06] bg-black/[0.03] px-3 py-1.5 text-sm text-gray-900 placeholder-gray-400 outline-none focus:border-coral/40 transition-colors font-mono"
        />
        <button
          onClick={() => setShowKey((p) => !p)}
          className="rounded px-2 py-1 text-xs text-gray-500 hover:bg-black/[0.04] transition-colors"
        >
          {showKey ? "Hide" : "Show"}
        </button>
      </div>
    </div>
  );
}
