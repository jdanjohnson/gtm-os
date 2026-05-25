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
];

const SECONDARY_ITEMS: { view: SidebarView; icon: string; label: string }[] = [
  { view: "automations", icon: "⏰", label: "Automations" },
  { view: "rules", icon: "📏", label: "Rules" },
  { view: "integrations", icon: "🔌", label: "Integrations" },
];

function trustColor(score: number): string {
  if (score >= 0.7) return "#10B981";
  if (score >= 0.5) return "#F59E0B";
  if (score >= 0.3) return "#F97316";
  return "#EF4444";
}

export default function Sidebar({
  activeView,
  collapsed,
  onToggleCollapse,
  onNavigate,
  avgTrust,
  experimentCount,
}: Props) {
  const trustPct = Math.min(avgTrust, 1);
  const radius = 15;
  const circumference = 2 * Math.PI * radius;
  const strokeOffset = circumference * (1 - trustPct);

  return (
    <aside
      className={clsx(
        "flex shrink-0 flex-col bg-[rgba(24,26,42,0.85)] backdrop-blur-[40px] transition-all duration-200",
        "border-r border-white/[0.04]",
        collapsed ? "w-[56px]" : "w-[220px]",
      )}
    >
      {/* Brand */}
      <div
        className="flex cursor-pointer items-center gap-3 border-b border-white/[0.05] px-4 py-[14px]"
        onClick={onToggleCollapse}
      >
        <div className="flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-[10px] bg-gradient-to-br from-coral to-[#FF8A65] text-[15px] font-extrabold text-white shadow-[0_2px_8px_rgba(239,99,68,0.3)]">
          G
        </div>
        {!collapsed && (
          <span className="text-[15px] font-bold tracking-tight text-white">
            GTM-OS
          </span>
        )}
      </div>

      {/* Nav items */}
      <nav className="flex-1 px-[10px] py-3">
        <div className="flex flex-col gap-0.5">
          {NAV_ITEMS.map(({ view, icon, label }) => (
            <button
              key={view}
              onClick={() => onNavigate(view)}
              className={clsx(
                "relative flex w-full items-center gap-[11px] rounded-xl px-3 py-[9px] text-[13px] font-medium transition-colors",
                activeView === view
                  ? "bg-white/10 text-white"
                  : "text-white/50 hover:bg-white/[0.06] hover:text-white/70",
              )}
              title={collapsed ? label : undefined}
            >
              {activeView === view && (
                <span className="absolute left-0 top-1/2 h-[18px] w-[3px] -translate-y-1/2 rounded-r-sm bg-coral" />
              )}
              <span className="w-[18px] text-center text-[15px]">{icon}</span>
              {!collapsed && <span>{label}</span>}
              {!collapsed && view === "experiments" && experimentCount > 0 && (
                <span className="ml-auto min-w-[18px] rounded-full bg-coral px-[6px] py-[1px] text-center text-[10px] font-bold text-white">
                  {experimentCount}
                </span>
              )}
            </button>
          ))}
        </div>

        <div className="mx-3 my-2 h-px bg-white/[0.05]" />

        <div className="flex flex-col gap-0.5">
          {SECONDARY_ITEMS.map(({ view, icon, label }) => (
            <button
              key={view}
              onClick={() => onNavigate(view)}
              className={clsx(
                "relative flex w-full items-center gap-[11px] rounded-xl px-3 py-[9px] text-[13px] font-medium transition-colors",
                activeView === view
                  ? "bg-white/10 text-white"
                  : "text-white/50 hover:bg-white/[0.06] hover:text-white/70",
              )}
              title={collapsed ? label : undefined}
            >
              {activeView === view && (
                <span className="absolute left-0 top-1/2 h-[18px] w-[3px] -translate-y-1/2 rounded-r-sm bg-coral" />
              )}
              <span className="w-[18px] text-center text-[15px]">{icon}</span>
              {!collapsed && <span>{label}</span>}
            </button>
          ))}
        </div>

        <div className="mx-3 my-2 h-px bg-white/[0.05]" />

        <button
          onClick={() => onNavigate("settings")}
          className={clsx(
            "relative flex w-full items-center gap-[11px] rounded-xl px-3 py-[9px] text-[13px] font-medium transition-colors",
            activeView === "settings"
              ? "bg-white/10 text-white"
              : "text-white/50 hover:bg-white/[0.06] hover:text-white/70",
          )}
          title={collapsed ? "Settings" : undefined}
        >
          {activeView === "settings" && (
            <span className="absolute left-0 top-1/2 h-[18px] w-[3px] -translate-y-1/2 rounded-r-sm bg-coral" />
          )}
          <span className="w-[18px] text-center text-[15px]">⚙️</span>
          {!collapsed && <span>Settings</span>}
        </button>
      </nav>

      {/* Trust ring footer */}
      <div className="border-t border-white/[0.05] px-4 py-3">
        {!collapsed ? (
          <div className="flex items-center gap-3 rounded-2xl border border-white/[0.06] bg-white/[0.04] px-3 py-[10px]">
            <div className="relative h-[38px] w-[38px] shrink-0">
              <svg viewBox="0 0 38 38" className="h-[38px] w-[38px] -rotate-90">
                <circle
                  cx="19" cy="19" r={radius}
                  fill="none"
                  stroke="rgba(255,255,255,0.08)"
                  strokeWidth="3"
                />
                <circle
                  cx="19" cy="19" r={radius}
                  fill="none"
                  stroke={trustColor(avgTrust)}
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeDasharray={circumference}
                  strokeDashoffset={strokeOffset}
                  className="transition-all duration-700"
                />
              </svg>
              <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white">
                {Math.round(avgTrust * 100)}
              </span>
            </div>
            <div>
              <div className="text-[10px] text-white/50">Avg Trust</div>
              <div className="text-[13px] font-semibold text-white">
                {avgTrust.toFixed(2)}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex justify-center">
            <div className="relative h-[28px] w-[28px]">
              <svg viewBox="0 0 38 38" className="h-[28px] w-[28px] -rotate-90">
                <circle cx="19" cy="19" r={radius} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="3" />
                <circle cx="19" cy="19" r={radius} fill="none" stroke={trustColor(avgTrust)} strokeWidth="3" strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={strokeOffset} />
              </svg>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
