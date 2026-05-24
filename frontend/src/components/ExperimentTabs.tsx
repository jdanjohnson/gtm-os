import clsx from "clsx";

interface Props {
  openTabs: string[];
  activeTab: string | null;
  experimentNames: Record<string, string>;
  experimentPhases: Record<string, string>;
  onSelectTab: (id: string | null) => void;
  onCloseTab: (id: string) => void;
  onNewExperiment: () => void;
  health: { model?: string; composio_configured?: boolean; scheduler_running?: boolean } | null;
}

const PHASE_DOTS: Record<string, string> = {
  design: "bg-yellow-400",
  build: "bg-blue-400",
  execute: "bg-green-400",
  measure: "bg-orange-400",
  learn: "bg-purple-400",
  complete: "bg-gray-400",
  paused: "bg-red-400",
};

export default function ExperimentTabs({
  openTabs,
  activeTab,
  experimentNames,
  experimentPhases,
  onSelectTab,
  onCloseTab,
  onNewExperiment,
  health,
}: Props) {
  return (
    <header className="flex items-center border-b border-[#2A2A2A] bg-[#1A1A1A]">
      {/* Logo chip */}
      <div className="flex items-center gap-2 border-r border-[#2A2A2A] px-4 py-2">
        <span className="text-sm font-bold tracking-tight">GTM-OS</span>
        {health?.model && (
          <span className="rounded bg-emerald-900/50 px-1.5 py-0.5 text-[10px] text-emerald-300">
            {health.model.split("/").pop()}
          </span>
        )}
      </div>

      {/* Tab strip */}
      <div className="flex flex-1 items-center gap-0.5 overflow-x-auto px-1 py-1">
        {openTabs.map((id) => {
          const name = experimentNames[id] ?? id.slice(0, 8);
          const phase = experimentPhases[id] ?? "design";
          const isActive = id === activeTab;
          return (
            <button
              key={id}
              onClick={() => onSelectTab(id)}
              className={clsx(
                "group flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs transition-colors",
                isActive
                  ? "bg-[#2A2A2A] text-white"
                  : "text-[#A1A1AA] hover:bg-[#2A2A2A]/50 hover:text-white",
              )}
            >
              <span className={clsx("h-2 w-2 rounded-full", PHASE_DOTS[phase] ?? "bg-gray-400")} />
              <span className="max-w-[140px] truncate">{name}</span>
              <span
                onClick={(e) => {
                  e.stopPropagation();
                  onCloseTab(id);
                }}
                className="ml-1 hidden rounded p-0.5 text-[#A1A1AA] hover:bg-[#3A3A3A] hover:text-white group-hover:inline"
              >
                ✕
              </span>
            </button>
          );
        })}

        {/* New experiment button */}
        <button
          onClick={onNewExperiment}
          className="ml-1 rounded-md px-2 py-1.5 text-xs text-[#A1A1AA] hover:bg-[#2A2A2A]/50 hover:text-white"
        >
          + New Experiment
        </button>
      </div>

      {/* Status chips */}
      <div className="flex items-center gap-2 border-l border-[#2A2A2A] px-3 py-2">
        {health?.composio_configured && (
          <span className="rounded bg-indigo-900/40 px-1.5 py-0.5 text-[10px] text-indigo-300">
            composio
          </span>
        )}
        {health?.scheduler_running && (
          <span className="rounded bg-amber-900/40 px-1.5 py-0.5 text-[10px] text-amber-300">
            scheduler
          </span>
        )}
      </div>
    </header>
  );
}
