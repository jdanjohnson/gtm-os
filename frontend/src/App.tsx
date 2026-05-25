import { useCallback, useEffect, useMemo, useState } from "react";
import clsx from "clsx";

import Sidebar from "./components/Sidebar";
import Chat from "./components/Chat";
import Dashboard from "./components/Dashboard";
import ExperimentDetail from "./components/ExperimentDetail";
import PlaysLibrary from "./components/PlaysLibrary";
import MemoryBrowser from "./components/MemoryBrowser";
import AgentsView from "./components/AgentsView";
import AutomationsView from "./components/AutomationsView";
import RulesView from "./components/RulesView";
import IntegrationsView from "./components/IntegrationsView";
import Settings from "./components/Settings";
import {
  Experiment,
  PlayMeta,
  getHealth,
  getPrimitives,
  listExperiments,
  listMemory,
  PrimitivesSummary,
} from "./lib/api";

export type SidebarView =
  | "dashboard"
  | "experiments"
  | "plays"
  | "memory"
  | "agents"
  | "automations"
  | "rules"
  | "integrations"
  | "settings";

export default function App() {
  const [sidebarView, setSidebarView] = useState<SidebarView>("dashboard");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const [openTabs, setOpenTabs] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<string | null>(null);
  const [primitives, setPrimitives] = useState<PrimitivesSummary | null>(null);
  const [health, setHealth] = useState<Awaited<ReturnType<typeof getHealth>> | null>(null);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [memoryCount, setMemoryCount] = useState(0);
  const [trustScores, setTrustScores] = useState<Record<string, number>>({});
  const [pendingChatMessage, setPendingChatMessage] = useState<string | null>(null);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => null);
    getPrimitives().then(setPrimitives).catch(() => null);
    listMemory().then((d) => setMemoryCount(d.memories.length)).catch(() => null);
  }, []);

  // Periodically fetch experiments.
  useEffect(() => {
    function refresh() {
      listExperiments()
        .then(({ experiments: exps }) => setExperiments(exps))
        .catch(() => null);
    }
    refresh();
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, []);

  // Fetch trust scores.
  useEffect(() => {
    fetch("/api/trust-scores")
      .then((r) => r.json())
      .then((d) => {
        const map: Record<string, number> = {};
        for (const ts of d.trust_scores || []) {
          map[ts.experiment_type] = parseFloat(ts.score);
        }
        setTrustScores(map);
      })
      .catch(() => null);
    const t = setInterval(() => {
      fetch("/api/trust-scores")
        .then((r) => r.json())
        .then((d) => {
          const map: Record<string, number> = {};
          for (const ts of d.trust_scores || []) {
            map[ts.experiment_type] = parseFloat(ts.score);
          }
          setTrustScores(map);
        })
        .catch(() => null);
    }, 10000);
    return () => clearInterval(t);
  }, []);

  const experimentNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const e of experiments) map[e.id] = e.name;
    return map;
  }, [experiments]);

  const avgTrust = useMemo(() => {
    const vals = Object.values(trustScores);
    if (vals.length === 0) return 0;
    return vals.reduce((a, b) => a + b, 0) / vals.length;
  }, [trustScores]);

  const activeExperiments = useMemo(
    () => experiments.filter((e) => !["complete", "paused"].includes(e.phase)),
    [experiments],
  );

  // Open experiment as tab.
  const openExperimentTab = useCallback(
    (id: string) => {
      if (!openTabs.includes(id)) {
        setOpenTabs((tabs) => [...tabs, id]);
      }
      setActiveTab(id);
      setSidebarView("experiments");
    },
    [openTabs],
  );

  const closeTab = useCallback(
    (id: string) => {
      setOpenTabs((tabs) => tabs.filter((t) => t !== id));
      if (activeTab === id) {
        setActiveTab(null);
      }
    },
    [activeTab],
  );

  // Determine what to show in the content area.
  const renderContent = () => {
    // If an experiment tab is active, show that experiment's detail.
    if (activeTab) {
      return (
        <ExperimentDetail
          experimentId={activeTab}
          onClear={() => setActiveTab(null)}
        />
      );
    }
    switch (sidebarView) {
      case "dashboard":
        return (
          <Dashboard
            experiments={experiments}
            activeExperiments={activeExperiments}
            trustScores={trustScores}
            avgTrust={avgTrust}
            memoryCount={memoryCount}
            onOpenExperiment={openExperimentTab}
          />
        );
      case "experiments":
        return (
          <ExperimentListView
            experiments={experiments}
            onSelect={openExperimentTab}
          />
        );
      case "plays":
        return (
          <PlaysLibrary
            primitives={primitives}
            onUsePlay={(play: PlayMeta, mode: "use" | "fork") => {
              const verb = mode === "fork" ? "Fork and customize" : "Use";
              const msg = `${verb} the "${play.name}" play (${play.id}). ${play.description}`;
              setPendingChatMessage(msg);
              setChatCollapsed(false);
            }}
          />
        );
      case "memory":
        return <MemoryBrowser />;
      case "agents":
        return <AgentsView primitives={primitives} />;
      case "automations":
        return <AutomationsView />;
      case "rules":
        return <RulesView />;
      case "integrations":
        return <IntegrationsView />;
      case "settings":
        return <Settings />;
      default:
        return null;
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden text-gray-900">
      {/* Three-panel layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar */}
        <Sidebar
          activeView={sidebarView}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed((v) => !v)}
          onNavigate={(view) => {
            setSidebarView(view);
            setActiveTab(null);
          }}
          avgTrust={avgTrust}
          experimentCount={activeExperiments.length}
        />

        {/* Content area */}
        <main className="flex-1 overflow-y-auto">
          {renderContent()}
        </main>

        {/* Right chat panel */}
        {chatCollapsed ? (
          <button
            onClick={() => setChatCollapsed(false)}
            className="flex w-8 flex-col items-center justify-center border-l border-black/[0.06] glass-subtle text-xs text-gray-400 hover:text-gray-700"
          >
            <span className="writing-vertical-lr rotate-180 whitespace-nowrap tracking-wider">
              Chat
            </span>
          </button>
        ) : (
          <aside className="flex w-[380px] shrink-0 flex-col border-l border-white/30 glass">
            <div className="flex items-center justify-between border-b border-black/[0.05] px-4 py-2">
              <div className="flex items-center gap-2.5">
                <span className="text-[14px] font-semibold text-gray-900">Chat</span>
                <span className="flex items-center gap-1 rounded-full bg-emerald-500/[0.08] px-2.5 py-[2px] text-[10px] font-semibold text-emerald-600">
                  <span className="h-[5px] w-[5px] rounded-full bg-emerald-500 animate-pulse" />
                  Online
                </span>
              </div>
              <button
                onClick={() => setChatCollapsed(true)}
                className="flex h-7 w-7 items-center justify-center rounded-lg text-gray-400 transition hover:bg-black/[0.04] hover:text-gray-700"
              >
                <span className="text-xs">−</span>
              </button>
            </div>
            <Chat
              experimentId={activeTab}
              primitives={primitives}
              experimentNames={experimentNames}
              pendingMessage={pendingChatMessage}
              onPendingMessageConsumed={() => setPendingChatMessage(null)}
              onSwitchExperiment={(id) => {
                if (id) openExperimentTab(id);
                else setActiveTab(null);
              }}
            />
          </aside>
        )}
      </div>
    </div>
  );
}

// ─── Inline sub-views ────────────────────────────────────────────────────────

function ExperimentListView({
  experiments,
  onSelect,
}: {
  experiments: Experiment[];
  onSelect: (id: string) => void;
}) {
  return (
    <div className="p-7">
      <h1 className="mb-5 text-xl font-bold text-gray-900">Experiments</h1>
      {experiments.length === 0 ? (
        <div className="glass-heavy flex flex-col items-center rounded-2xl p-10 text-center">
          <div className="mb-3 flex h-16 w-16 items-center justify-center rounded-full text-3xl glass">
            🧪
          </div>
          <div className="text-[15px] font-semibold text-gray-900">No experiments yet</div>
          <div className="mt-1 text-[12px] text-gray-500">Create one from the dashboard or chat.</div>
        </div>
      ) : (
        <div className="space-y-2">
          {experiments.map((e) => (
            <button
              key={e.id}
              onClick={() => onSelect(e.id)}
              className="flex w-full items-center justify-between rounded-2xl p-4 text-left transition-all glass-heavy hover:-translate-y-0.5 hover:shadow-[0_8px_40px_rgba(0,0,0,0.08)]"
            >
              <div className="min-w-0 flex-1">
                <div className="font-semibold text-gray-900">{e.name}</div>
                <div className="mt-0.5 truncate text-xs text-gray-500">
                  {e.hypothesis || "No hypothesis"}
                </div>
              </div>
              <div className="flex items-center gap-3 text-xs">
                <span className={clsx("rounded-full px-2.5 py-[2px] text-[11px] font-semibold", phaseStyle(e.phase))}>
                  {e.phase}
                </span>
                <span className="text-gray-400">
                  {e.tokens_used.toLocaleString()} / {e.token_budget.toLocaleString()}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function phaseStyle(phase: string): string {
  const map: Record<string, string> = {
    design: "bg-amber-500/10 text-amber-600",
    build: "bg-blue-500/10 text-blue-600",
    execute: "bg-emerald-500/10 text-emerald-600",
    measure: "bg-orange-500/10 text-orange-600",
    learn: "bg-purple-500/10 text-purple-600",
    complete: "bg-gray-400/10 text-gray-500",
    paused: "bg-red-400/10 text-red-500",
  };
  return map[phase] ?? "bg-gray-400/10 text-gray-500";
}
