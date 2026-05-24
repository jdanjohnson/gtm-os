import { useEffect, useState } from "react";
import clsx from "clsx";
import {
  FlaskConical,
  Brain,
  BookOpen,
  TrendingUp,
  TrendingDown,
  ArrowRight,
  Clock,
  Pause,
  Play,
  Zap,
  Lightbulb,
  Target,
  BarChart3,
} from "lucide-react";

import {
  Experiment,
  MemoryItem,
  PrimitivesSummary,
  listExperiments,
  listMemory,
} from "../lib/api";

interface Props {
  onSelectExperiment: (id: string) => void;
  primitives: PrimitivesSummary | null;
  health: { ok: boolean; version: string; model: string; scheduler_running: boolean; composio_configured: boolean; primitives_dir: string } | null;
}

const PHASE_CONFIG: Record<string, { label: string; class: string }> = {
  design: { label: "Design", class: "phase-design" },
  build: { label: "Build", class: "phase-build" },
  execute: { label: "Execute", class: "phase-execute" },
  measure: { label: "Measure", class: "phase-measure" },
  learn: { label: "Learn", class: "phase-learn" },
  complete: { label: "Complete", class: "phase-complete" },
  paused: { label: "Paused", class: "phase-paused" },
};

export default function Dashboard({ onSelectExperiment, primitives, health }: Props) {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [memories, setMemories] = useState<MemoryItem[]>([]);

  useEffect(() => {
    listExperiments().then(({ experiments }) => setExperiments(experiments)).catch(() => null);
    listMemory().then(({ memories }) => setMemories(memories)).catch(() => null);
    const t = setInterval(() => {
      listExperiments().then(({ experiments }) => setExperiments(experiments)).catch(() => null);
    }, 5000);
    return () => clearInterval(t);
  }, []);

  const active = experiments.filter((e) => e.phase !== "complete" && e.phase !== "paused");
  const completed = experiments.filter((e) => e.phase === "complete");
  const paused = experiments.filter((e) => e.phase === "paused");
  const learnings = memories.filter((m) => m.type === "learning");
  const recentLearnings = learnings.slice(0, 5);
  const totalTokens = experiments.reduce((s, e) => s + e.tokens_used, 0);

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      {/* Stats Row */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          icon={<FlaskConical size={18} />}
          label="Active Experiments"
          value={active.length}
          accent="emerald"
        />
        <StatCard
          icon={<Lightbulb size={18} />}
          label="Learnings"
          value={learnings.length}
          accent="purple"
        />
        <StatCard
          icon={<Brain size={18} />}
          label="Memories"
          value={memories.length}
          accent="indigo"
        />
        <StatCard
          icon={<BarChart3 size={18} />}
          label="Tokens Used"
          value={totalTokens > 1000 ? `${(totalTokens / 1000).toFixed(1)}k` : totalTokens}
          accent="amber"
        />
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Active Experiments */}
        <div className="col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-slate-300 flex items-center gap-2">
              <Target size={16} className="text-emerald-400" />
              Active Experiments
            </h2>
            <span className="text-xs text-slate-500">{active.length} running</span>
          </div>

          {active.length === 0 && (
            <div className="glass-card p-8 text-center">
              <FlaskConical size={32} className="mx-auto mb-3 text-slate-600" />
              <p className="text-sm text-slate-400">No active experiments yet.</p>
              <p className="text-xs text-slate-500 mt-1">
                Open the chat and describe what you want to test.
              </p>
            </div>
          )}

          <div className="space-y-3">
            {active.map((exp) => (
              <ExperimentCard
                key={exp.id}
                experiment={exp}
                onClick={() => onSelectExperiment(exp.id)}
              />
            ))}
          </div>

          {paused.length > 0 && (
            <>
              <h3 className="text-xs font-medium text-slate-500 flex items-center gap-2 mt-6">
                <Pause size={12} /> Paused ({paused.length})
              </h3>
              <div className="space-y-3">
                {paused.map((exp) => (
                  <ExperimentCard
                    key={exp.id}
                    experiment={exp}
                    onClick={() => onSelectExperiment(exp.id)}
                  />
                ))}
              </div>
            </>
          )}

          {completed.length > 0 && (
            <>
              <h3 className="text-xs font-medium text-slate-500 flex items-center gap-2 mt-6">
                <Play size={12} /> Completed ({completed.length})
              </h3>
              <div className="space-y-3">
                {completed.slice(0, 3).map((exp) => (
                  <ExperimentCard
                    key={exp.id}
                    experiment={exp}
                    onClick={() => onSelectExperiment(exp.id)}
                  />
                ))}
              </div>
            </>
          )}
        </div>

        {/* Right column */}
        <div className="space-y-6">
          {/* System Health */}
          <div className="glass-card p-4 space-y-3">
            <h3 className="text-xs font-medium text-slate-400 uppercase tracking-wider flex items-center gap-2">
              <Zap size={12} className="text-amber-400" />
              System Health
            </h3>
            <div className="space-y-2">
              <HealthRow
                label="Scheduler"
                ok={health?.scheduler_running ?? false}
              />
              <HealthRow
                label="Composio"
                ok={health?.composio_configured ?? false}
              />
              <HealthRow
                label="LLM"
                ok={!!health?.model}
                value={health?.model}
              />
            </div>
            <div className="flex flex-wrap gap-1.5 pt-1">
              <span className="glass-pill text-slate-400">
                {primitives?.plays.length ?? 0} plays
              </span>
              <span className="glass-pill text-slate-400">
                {primitives?.agents.length ?? 0} agents
              </span>
              <span className="glass-pill text-slate-400">
                {memories.length} memories
              </span>
            </div>
          </div>

          {/* Recent Learnings */}
          <div className="glass-card p-4 space-y-3">
            <h3 className="text-xs font-medium text-slate-400 uppercase tracking-wider flex items-center gap-2">
              <Lightbulb size={12} className="text-purple-400" />
              Recent Learnings
            </h3>
            {recentLearnings.length === 0 ? (
              <p className="text-xs text-slate-500">
                No learnings yet. Run experiments to generate insights.
              </p>
            ) : (
              <ul className="space-y-2">
                {recentLearnings.map((l) => (
                  <li key={l.id} className="text-xs text-slate-300 border-l-2 border-purple-500/30 pl-3 py-1">
                    {l.content.length > 120 ? l.content.slice(0, 120) + "..." : l.content}
                    <div className="text-[10px] text-slate-500 mt-0.5">
                      confidence: {l.confidence.toFixed(2)}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Quick Actions */}
          <div className="glass-card p-4 space-y-3">
            <h3 className="text-xs font-medium text-slate-400 uppercase tracking-wider flex items-center gap-2">
              <BookOpen size={12} className="text-sky-400" />
              Available Plays
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {(primitives?.plays ?? []).slice(0, 8).map((p) => (
                <span key={p} className="glass-pill text-sky-300">{p}</span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ icon, label, value, accent }: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  accent: "emerald" | "purple" | "indigo" | "amber";
}) {
  const accentColors = {
    emerald: "text-emerald-400 glow-emerald",
    purple: "text-purple-400 glow-purple",
    indigo: "text-indigo-400 glow-indigo",
    amber: "text-amber-400 glow-amber",
  };
  return (
    <div className="glass-card p-4">
      <div className={clsx("mb-2", accentColors[accent])}>
        {icon}
      </div>
      <div className="text-2xl font-semibold text-slate-100">{value}</div>
      <div className="text-[11px] text-slate-500 mt-0.5">{label}</div>
    </div>
  );
}

function ExperimentCard({ experiment: exp, onClick }: { experiment: Experiment; onClick: () => void }) {
  const phase = PHASE_CONFIG[exp.phase] ?? PHASE_CONFIG.design;
  const pct = exp.token_budget > 0 ? Math.min(100, (exp.tokens_used / exp.token_budget) * 100) : 0;

  return (
    <button
      onClick={onClick}
      className="glass-card w-full p-4 text-left group"
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-medium text-slate-100 truncate">{exp.name}</h3>
            <span className={clsx("glass-pill border", phase.class)}>
              {phase.label}
            </span>
          </div>
          {exp.hypothesis && (
            <p className="text-xs text-slate-400 mt-1.5 line-clamp-2">{exp.hypothesis}</p>
          )}
        </div>
        <ArrowRight size={16} className="text-slate-600 group-hover:text-emerald-400 transition-colors shrink-0 ml-3 mt-1" />
      </div>

      <div className="flex items-center gap-4 mt-3">
        <div className="flex items-center gap-2 text-[11px] text-slate-500">
          <BookOpen size={12} />
          {exp.play_ids.join(", ") || "no play"}
        </div>
        <div className="flex-1">
          <div className="h-1 w-full overflow-hidden rounded-full bg-slate-800/80">
            <div
              className={clsx(
                "h-full rounded-full transition-all",
                pct > 80 ? "bg-rose-500" : "bg-emerald-500/60",
              )}
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
        <span className="text-[10px] text-slate-500 shrink-0">
          {exp.tokens_used.toLocaleString()} tok
        </span>
      </div>
    </button>
  );
}

function HealthRow({ label, ok, value }: { label: string; ok: boolean; value?: string }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-slate-400">{label}</span>
      <div className="flex items-center gap-2">
        {value && <span className="text-slate-500 truncate max-w-[120px]">{value}</span>}
        <span className={clsx(
          "h-2 w-2 rounded-full",
          ok ? "bg-emerald-400" : "bg-slate-600"
        )} />
      </div>
    </div>
  );
}
