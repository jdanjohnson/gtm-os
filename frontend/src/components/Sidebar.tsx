import clsx from "clsx";
import type { SidebarView } from "../App";

interface Props {
  activeView: SidebarView;
  collapsed: boolean;
  onToggleCollapse: () => void;
  onNavigate: (view: SidebarView) => void;
  avgTrust: number;
  experimentCount: number;
}

const NAV_ITEMS: { view: SidebarView; icon: string; label: string }[] = [
  { view: "dashboard", icon: "📊", label: "Dashboard" },
  { view: "experiments", icon: "🧪", label: "Experiments" },
  { view: "plays", icon: "📋", label: "Plays" },
  { view: "memory", icon: "🧠", label: "Memory" },
  { view: "agents", icon: "🤖", label: "Agents" },
  { view: "automations", icon: "⏰", label: "Automations" },
  { view: "rules", icon: "📏", label: "Rules" },
  { view: "integrations", icon: "🔌", label: "Integrations" },
];

function trustColor(score: number): string {
  if (score >= 0.7) return "bg-green-500";
  if (score >= 0.5) return "bg-yellow-500";
  if (score >= 0.3) return "bg-orange-500";
  return "bg-red-500";
}

export default function Sidebar({
  activeView,
  collapsed,
  onToggleCollapse,
  onNavigate,
  avgTrust,
  experimentCount,
}: Props) {
  return (
    <aside
      className={clsx(
        "flex shrink-0 flex-col border-r border-[#2A2A2A] bg-[#1A1A1A] transition-all duration-200",
        collapsed ? "w-[52px]" : "w-[200px]",
      )}
    >
      {/* Logo */}
      <div
        className="flex cursor-pointer items-center gap-2 border-b border-[#2A2A2A] px-3 py-3"
        onClick={onToggleCollapse}
      >
        <span className="text-base">🏠</span>
        {!collapsed && (
          <span className="text-sm font-semibold tracking-tight">GTM-OS</span>
        )}
      </div>

      {/* Nav items */}
      <nav className="flex-1 py-2">
        {NAV_ITEMS.map(({ view, icon, label }) => (
          <button
            key={view}
            onClick={() => onNavigate(view)}
            className={clsx(
              "flex w-full items-center gap-2.5 px-3 py-2 text-sm transition-colors",
              activeView === view
                ? "border-l-2 border-emerald-400 bg-[#2A2A2A]/60 text-white"
                : "border-l-2 border-transparent text-[#A1A1AA] hover:bg-[#2A2A2A]/40 hover:text-white",
            )}
            title={collapsed ? label : undefined}
          >
            <span className="text-base">{icon}</span>
            {!collapsed && <span>{label}</span>}
          </button>
        ))}

        <div className="my-2 mx-3 border-t border-[#2A2A2A]" />

        <button
          onClick={() => onNavigate("settings")}
          className={clsx(
            "flex w-full items-center gap-2.5 px-3 py-2 text-sm transition-colors",
            activeView === "settings"
              ? "border-l-2 border-emerald-400 bg-[#2A2A2A]/60 text-white"
              : "border-l-2 border-transparent text-[#A1A1AA] hover:bg-[#2A2A2A]/40 hover:text-white",
          )}
          title={collapsed ? "Settings" : undefined}
        >
          <span className="text-base">⚙️</span>
          {!collapsed && <span>Settings</span>}
        </button>
      </nav>

      {/* Trust score at bottom */}
      {!collapsed && (
        <div className="border-t border-[#2A2A2A] px-3 py-3">
          <div className="flex items-center gap-2 text-xs text-[#A1A1AA]">
            <div className={clsx("h-2 w-2 rounded-full", trustColor(avgTrust))} />
            <span>Trust: {avgTrust.toFixed(2)}</span>
          </div>
          <div className="mt-1 text-[10px] text-[#A1A1AA]">
            {experimentCount} active experiment{experimentCount !== 1 ? "s" : ""}
          </div>
        </div>
      )}
      {collapsed && (
        <div className="flex justify-center border-t border-[#2A2A2A] py-3">
          <div className={clsx("h-2.5 w-2.5 rounded-full", trustColor(avgTrust))} title={`Trust: ${avgTrust.toFixed(2)}`} />
        </div>
      )}
    </aside>
  );
}
