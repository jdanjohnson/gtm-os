import { useEffect, useState } from "react";
import clsx from "clsx";
import {
  LayoutDashboard,
  FlaskConical,
  BookOpen,
  Brain,
  Users,
  Zap,
  MessageSquare,
  ChevronDown,
  ChevronUp,
  Activity,
  Shield,
} from "lucide-react";

import Chat from "./components/Chat";
import Dashboard from "./components/Dashboard";
import ExperimentList from "./components/ExperimentList";
import ExperimentDetail from "./components/ExperimentDetail";
import PlaysLibrary from "./components/PlaysLibrary";
import MemoryBrowser from "./components/MemoryBrowser";
import AgentsView from "./components/AgentsView";
import AutomationsView from "./components/AutomationsView";
import { getHealth, getPrimitives, PrimitivesSummary } from "./lib/api";

type View = "dashboard" | "experiments" | "plays" | "memory" | "agents" | "automations";

const NAV_ITEMS: { id: View; label: string; icon: typeof LayoutDashboard }[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "experiments", label: "Experiments", icon: FlaskConical },
  { id: "plays", label: "Plays", icon: BookOpen },
  { id: "memory", label: "Memory", icon: Brain },
  { id: "agents", label: "Agents", icon: Users },
  { id: "automations", label: "Automations", icon: Zap },
];

export default function App() {
  const [view, setView] = useState<View>("dashboard");
  const [selectedExperiment, setSelectedExperiment] = useState<string | null>(null);
  const [primitives, setPrimitives] = useState<PrimitivesSummary | null>(null);
  const [health, setHealth] = useState<Awaited<ReturnType<typeof getHealth>> | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatAgent, setChatAgent] = useState("orchestrator");

  useEffect(() => {
    getHealth().then(setHealth).catch(() => null);
    getPrimitives().then(setPrimitives).catch(() => null);
  }, []);

  function handleExperimentSelect(id: string | null) {
    setSelectedExperiment(id);
    setView("experiments");
  }

  const trustScore = 0.6;

  return (
    <div className="flex h-full min-h-screen text-slate-100">
      {/* ── Sidebar ────────────────────────────────── */}
      <aside className="glass-sidebar flex w-60 shrink-0 flex-col">
        {/* Logo */}
        <div className="flex items-center gap-3 px-5 py-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500/15 text-emerald-400">
            <Activity size={20} />
          </div>
          <div>
            <span className="text-base font-semibold tracking-tight">GTM-OS</span>
            <div className="text-[10px] text-slate-500">autonomous engine</div>
          </div>
        </div>

        {/* Trust Score */}
        <div className="mx-4 mb-4 glass-card !rounded-xl px-3 py-2.5">
          <div className="flex items-center justify-between text-[11px]">
            <span className="flex items-center gap-1.5 text-slate-400">
              <Shield size={12} />
              Trust Score
            </span>
            <span className="font-semibold text-emerald-400">{(trustScore * 100).toFixed(0)}%</span>
          </div>
          <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-slate-800/80">
            <div
              className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-emerald-400 transition-all"
              style={{ width: `${trustScore * 100}%` }}
            />
          </div>
        </div>

        {/* Nav items */}
        <nav className="flex-1 px-3 space-y-0.5">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = view === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setView(item.id)}
                className={clsx(
                  "flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-all",
                  active
                    ? "glass text-emerald-300 glow-emerald"
                    : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.03]",
                )}
              >
                <Icon size={18} className={active ? "text-emerald-400" : ""} />
                {item.label}
              </button>
            );
          })}
        </nav>

        {/* Status pills */}
        <div className="px-4 pb-4 space-y-2">
          <div className="flex items-center gap-2 text-[11px] text-slate-500">
            <span className={clsx(
              "h-1.5 w-1.5 rounded-full",
              health?.scheduler_running ? "bg-emerald-400 animate-pulse-glow" : "bg-slate-600"
            )} />
            scheduler: {health?.scheduler_running ? "running" : "stopped"}
          </div>
          <div className="flex items-center gap-2 text-[11px] text-slate-500">
            <span className={clsx(
              "h-1.5 w-1.5 rounded-full",
              health?.composio_configured ? "bg-indigo-400" : "bg-slate-600"
            )} />
            composio: {health?.composio_configured ? "connected" : "off"}
          </div>
          <div className="glass-pill inline-block text-slate-400">
            {health?.model ?? "loading..."}
          </div>
        </div>
      </aside>

      {/* ── Main Content ───────────────────────────── */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <header className="glass-header flex items-center justify-between px-6 py-3">
          <h1 className="text-sm font-medium text-slate-300">
            {NAV_ITEMS.find((n) => n.id === view)?.label ?? "Dashboard"}
          </h1>
          <button
            onClick={() => setChatOpen((v) => !v)}
            className={clsx(
              "flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm transition-all",
              chatOpen
                ? "glass text-emerald-300"
                : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.03]",
            )}
          >
            <MessageSquare size={16} />
            Chat
            {chatOpen ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
          </button>
        </header>

        {/* Content + Chat split */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Main view area */}
          <main className={clsx(
            "flex-1 overflow-y-auto transition-all",
            chatOpen ? "" : "",
          )}>
            {view === "dashboard" && (
              <Dashboard
                onSelectExperiment={handleExperimentSelect}
                primitives={primitives}
                health={health}
              />
            )}
            {view === "experiments" && (
              <div className="flex h-full">
                <div className="w-72 shrink-0 border-r border-white/[0.06]">
                  <ExperimentList
                    selectedId={selectedExperiment}
                    onSelect={handleExperimentSelect}
                    primitives={primitives}
                  />
                </div>
                <div className="flex-1">
                  <ExperimentDetail
                    experimentId={selectedExperiment}
                    onClear={() => setSelectedExperiment(null)}
                  />
                </div>
              </div>
            )}
            {view === "plays" && <PlaysLibrary primitives={primitives} />}
            {view === "memory" && <MemoryBrowser />}
            {view === "agents" && <AgentsView primitives={primitives} onSwitchToChat={(agent) => {
              setChatAgent(agent);
              setChatOpen(true);
            }} />}
            {view === "automations" && <AutomationsView />}
          </main>

          {/* Persistent Chat Panel */}
          {chatOpen && (
            <div className="glass-chat-panel animate-fade-in" style={{ height: "340px", minHeight: "280px" }}>
              <Chat
                experimentId={selectedExperiment}
                primitives={primitives}
                defaultAgent={chatAgent}
                onAgentChange={setChatAgent}
                compact
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
