import clsx from "clsx";
import {
  Users,
  Bot,
  Search,
  PenTool,
  BarChart3,
  Cog,
  Crown,
  MessageSquare,
  TrendingUp,
  Target,
  Star,
} from "lucide-react";

import { PrimitivesSummary } from "../lib/api";

interface Props {
  primitives: PrimitivesSummary | null;
  onSwitchToChat: (agent: string) => void;
}

interface AgentInfo {
  id: string;
  name: string;
  role: string;
  description: string;
  icon: typeof Bot;
  accent: string;
  glowClass: string;
  stats: {
    qualityScore: number;
    tasksCompleted: number;
    avgTokens: number;
  };
}

function getAgentInfo(agentId: string): AgentInfo {
  const agents: Record<string, Omit<AgentInfo, "id">> = {
    orchestrator: {
      name: "Orchestrator",
      role: "Team Lead",
      description: "Coordinates all agents, delegates tasks, manages experiment lifecycle. The primary interface between you and the GTM team.",
      icon: Crown,
      accent: "emerald",
      glowClass: "glow-emerald",
      stats: { qualityScore: 0.85, tasksCompleted: 0, avgTokens: 2400 },
    },
    researcher: {
      name: "Researcher",
      role: "Discovery & Intel",
      description: "Finds prospects, researches companies, gathers competitive intelligence. Uses Apollo, LinkedIn, and web scraping tools.",
      icon: Search,
      accent: "sky",
      glowClass: "glow-indigo",
      stats: { qualityScore: 0.78, tasksCompleted: 0, avgTokens: 3200 },
    },
    copywriter: {
      name: "Copywriter",
      role: "Content & Messaging",
      description: "Drafts emails, sequences, call scripts, and marketing copy. Follows brand voice, tone guidelines, and channel-specific rules.",
      icon: PenTool,
      accent: "purple",
      glowClass: "glow-purple",
      stats: { qualityScore: 0.82, tasksCompleted: 0, avgTokens: 1800 },
    },
    analyst: {
      name: "Analyst",
      role: "Metrics & Learning",
      description: "Analyzes experiment results, compares hypotheses, identifies patterns. Generates learnings and proposes follow-up experiments.",
      icon: BarChart3,
      accent: "amber",
      glowClass: "glow-amber",
      stats: { qualityScore: 0.88, tasksCompleted: 0, avgTokens: 2100 },
    },
    operator: {
      name: "Operator",
      role: "Execution & Tools",
      description: "Executes outbound actions: sends emails, updates CRMs, triggers webhooks. Interfaces with Composio integrations.",
      icon: Cog,
      accent: "rose",
      glowClass: "",
      stats: { qualityScore: 0.91, tasksCompleted: 0, avgTokens: 1500 },
    },
  };

  return {
    id: agentId,
    ...(agents[agentId] ?? {
      name: agentId.replace(/\b\w/g, (c) => c.toUpperCase()),
      role: "Specialist",
      description: `Custom agent: ${agentId}`,
      icon: Bot,
      accent: "slate",
      glowClass: "",
      stats: { qualityScore: 0.7, tasksCompleted: 0, avgTokens: 2000 },
    }),
  };
}

const ACCENT_MAP: Record<string, { bg: string; text: string; border: string }> = {
  emerald: { bg: "bg-emerald-500/10", text: "text-emerald-400", border: "border-emerald-500/20" },
  sky: { bg: "bg-sky-500/10", text: "text-sky-400", border: "border-sky-500/20" },
  purple: { bg: "bg-purple-500/10", text: "text-purple-400", border: "border-purple-500/20" },
  amber: { bg: "bg-amber-500/10", text: "text-amber-400", border: "border-amber-500/20" },
  rose: { bg: "bg-rose-500/10", text: "text-rose-400", border: "border-rose-500/20" },
  slate: { bg: "bg-slate-500/10", text: "text-slate-400", border: "border-slate-500/20" },
};

export default function AgentsView({ primitives, onSwitchToChat }: Props) {
  const agentIds = primitives?.agents ?? ["orchestrator", "researcher", "copywriter", "analyst", "operator"];
  const agents = agentIds.map(getAgentInfo);

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div>
        <h2 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
          <Users size={20} className="text-emerald-400" />
          Your GTM Team
        </h2>
        <p className="text-xs text-slate-500 mt-1">
          {agents.length} specialist agents. Click "Talk to" to switch the chat to any agent.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {agents.map((agent) => {
          const Icon = agent.icon;
          const colors = ACCENT_MAP[agent.accent] ?? ACCENT_MAP.slate;
          return (
            <div key={agent.id} className={clsx("glass-card p-5", agent.glowClass && agent.glowClass)}>
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className={clsx(
                    "flex h-11 w-11 items-center justify-center rounded-xl border",
                    colors.bg, colors.text, colors.border,
                  )}>
                    <Icon size={22} />
                  </div>
                  <div>
                    <h3 className="text-sm font-medium text-slate-100">{agent.name}</h3>
                    <span className="text-[11px] text-slate-500">{agent.role}</span>
                  </div>
                </div>
                <button
                  onClick={() => onSwitchToChat(agent.id)}
                  className="glass-btn flex items-center gap-1.5 px-3 py-1.5 text-xs"
                >
                  <MessageSquare size={12} />
                  Talk to
                </button>
              </div>

              <p className="text-xs text-slate-400 mb-4">{agent.description}</p>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-3">
                <div className="glass !rounded-xl p-2.5 text-center">
                  <div className={clsx("text-lg font-semibold", colors.text)}>
                    {(agent.stats.qualityScore * 100).toFixed(0)}
                  </div>
                  <div className="text-[10px] text-slate-500 flex items-center justify-center gap-1">
                    <Star size={8} /> Quality
                  </div>
                </div>
                <div className="glass !rounded-xl p-2.5 text-center">
                  <div className="text-lg font-semibold text-slate-200">
                    {agent.stats.tasksCompleted}
                  </div>
                  <div className="text-[10px] text-slate-500 flex items-center justify-center gap-1">
                    <Target size={8} /> Tasks
                  </div>
                </div>
                <div className="glass !rounded-xl p-2.5 text-center">
                  <div className="text-lg font-semibold text-slate-200">
                    {agent.stats.avgTokens > 1000 ? `${(agent.stats.avgTokens / 1000).toFixed(1)}k` : agent.stats.avgTokens}
                  </div>
                  <div className="text-[10px] text-slate-500 flex items-center justify-center gap-1">
                    <TrendingUp size={8} /> Avg tok
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
