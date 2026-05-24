import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";

import Chat from "./components/Chat";
import ExperimentList from "./components/ExperimentList";
import ExperimentDetail from "./components/ExperimentDetail";
import MemoryBrowser from "./components/MemoryBrowser";
import {
  Experiment,
  getHealth,
  getPrimitives,
  listExperiments,
  PrimitivesSummary,
} from "./lib/api";

type Tab = "chat" | "experiments" | "memory";

export default function App() {
  const [tab, setTab] = useState<Tab>("chat");
  const [selectedExperiment, setSelectedExperiment] = useState<string | null>(null);
  const [primitives, setPrimitives] = useState<PrimitivesSummary | null>(null);
  const [health, setHealth] = useState<Awaited<ReturnType<typeof getHealth>> | null>(null);
  const [experiments, setExperiments] = useState<Experiment[]>([]);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => null);
    getPrimitives().then(setPrimitives).catch(() => null);
  }, []);

  // Periodically fetch experiments so the name map stays current.
  useEffect(() => {
    function refresh() {
      listExperiments()
        .then(({ experiments }) => setExperiments(experiments))
        .catch(() => null);
    }
    refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, []);

  const experimentNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const e of experiments) {
      map[e.id] = e.name;
    }
    return map;
  }, [experiments]);

  function handleExperimentSelect(id: string | null) {
    setSelectedExperiment(id);
    setTab("experiments");
  }

  function handleChatSwitchExperiment(id: string | null) {
    setSelectedExperiment(id);
  }

  return (
    <div className="flex h-full min-h-screen flex-col bg-slate-950 text-slate-100">
      <header className="flex items-center justify-between border-b border-slate-800 px-6 py-3">
        <div className="flex items-center gap-3">
          <span className="text-lg font-semibold tracking-tight">GTM-OS</span>
          <span className="rounded bg-emerald-900/40 px-2 py-0.5 text-xs text-emerald-300">
            {health?.model ?? "loading…"}
          </span>
          {health?.composio_configured ? (
            <span className="rounded bg-indigo-900/40 px-2 py-0.5 text-xs text-indigo-300">
              composio: on
            </span>
          ) : (
            <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-400">
              composio: off
            </span>
          )}
          {health?.scheduler_running ? (
            <span className="rounded bg-amber-900/40 px-2 py-0.5 text-xs text-amber-300">
              scheduler: running
            </span>
          ) : null}
        </div>
        <nav className="flex gap-1">
          {(["chat", "experiments", "memory"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={clsx(
                "rounded px-3 py-1.5 text-sm",
                tab === t
                  ? "bg-slate-800 text-white"
                  : "text-slate-400 hover:bg-slate-900 hover:text-slate-100",
              )}
            >
              {t}
            </button>
          ))}
        </nav>
      </header>

      <main className="flex flex-1 overflow-hidden">
        <aside className="w-72 shrink-0 border-r border-slate-800 bg-slate-900/40">
          <ExperimentList
            selectedId={selectedExperiment}
            onSelect={handleExperimentSelect}
            primitives={primitives}
          />
        </aside>

        <section className="flex flex-1 overflow-hidden">
          {tab === "chat" && (
            <Chat
              experimentId={selectedExperiment}
              primitives={primitives}
              experimentNames={experimentNames}
              onSwitchExperiment={handleChatSwitchExperiment}
            />
          )}
          {tab === "experiments" && (
            <ExperimentDetail
              experimentId={selectedExperiment}
              onClear={() => setSelectedExperiment(null)}
            />
          )}
          {tab === "memory" && <MemoryBrowser />}
        </section>
      </main>
    </div>
  );
}
