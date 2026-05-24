import { useCallback, useEffect, useMemo, useState } from "react";
import clsx from "clsx";

import Sidebar from "./components/Sidebar";
import ExperimentTabs from "./components/ExperimentTabs";
import StatusBar from "./components/StatusBar";
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

  const experimentPhases = useMemo(() => {
    const map: Record<string, string> = {};
    for (const e of experiments) map[e.id] = e.phase;
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
        return <PlaysLibrary primitives={primitives} />;
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
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-[#0F0F0F] text-[#FAFAFA]">
      {/* Top bar: experiment tabs */}
      <ExperimentTabs
        openTabs={openTabs}
        activeTab={activeTab}
        experimentNames={experimentNames}
        experimentPhases={experimentPhases}
        onSelectTab={setActiveTab}
        onCloseTab={closeTab}
        onNewExperiment={() => {
          setActiveTab(null);
          setSidebarView("dashboard");
        }}
        health={health}
      />

      {/* Main three-panel layout */}
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
        <main className="flex-1 overflow-y-auto bg-[#0F0F0F]">
          {renderContent()}
        </main>

        {/* Right chat panel */}
        {chatCollapsed ? (
          <button
            onClick={() => setChatCollapsed(false)}
            className="flex w-8 flex-col items-center justify-center border-l border-[#2A2A2A] bg-[#1A1A1A] text-xs text-[#A1A1AA] hover:text-white"
          >
            <span className="writing-vertical-lr rotate-180 whitespace-nowrap tracking-wider">
              Chat
            </span>
          </button>
        ) : (
          <aside className="flex w-[380px] shrink-0 flex-col border-l border-[#2A2A2A] bg-[#1A1A1A]">
            <div className="flex items-center justify-between border-b border-[#2A2A2A] px-3 py-1.5">
              <span className="text-xs font-medium text-[#A1A1AA]">Chat</span>
              <button
                onClick={() => setChatCollapsed(true)}
                className="rounded p-1 text-[#A1A1AA] hover:bg-[#2A2A2A] hover:text-white"
              >
                <span className="text-xs">−</span>
              </button>
            </div>
            <Chat
              experimentId={activeTab}
              primitives={primitives}
              experimentNames={experimentNames}
              onSwitchExperiment={(id) => {
                if (id) openExperimentTab(id);
                else setActiveTab(null);
              }}
            />
          </aside>
        )}
      </div>

      {/* Bottom status bar */}
      <StatusBar
        avgTrust={avgTrust}
        activeExperimentCount={activeExperiments.length}
        memoryCount={memoryCount}
        model={health?.model}
      />
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
    <div className="p-6">
      <h1 className="mb-4 text-xl font-semibold">Experiments</h1>
      {experiments.length === 0 ? (
        <p className="text-sm text-[#A1A1AA]">No experiments yet. Create one from the dashboard or chat.</p>
      ) : (
        <div className="space-y-2">
          {experiments.map((e) => (
            <button
              key={e.id}
              onClick={() => onSelect(e.id)}
              className="flex w-full items-center justify-between rounded-lg border border-[#2A2A2A] bg-[#1A1A1A] px-4 py-3 text-left hover:border-[#3A3A3A]"
            >
              <div>
                <div className="font-medium">{e.name}</div>
                <div className="mt-0.5 text-xs text-[#A1A1AA]">
                  {e.hypothesis || "No hypothesis"}
                </div>
              </div>
              <div className="flex items-center gap-3 text-xs">
                <span className={phaseColor(e.phase)}>{e.phase}</span>
                <span className="text-[#A1A1AA]">
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


function phaseColor(phase: string) {
  const map: Record<string, string> = {
    design: "text-yellow-400",
    build: "text-blue-400",
    execute: "text-green-400",
    measure: "text-orange-400",
    learn: "text-purple-400",
    complete: "text-gray-400",
    paused: "text-red-400",
  };
  return map[phase] ?? "text-gray-400";
}
