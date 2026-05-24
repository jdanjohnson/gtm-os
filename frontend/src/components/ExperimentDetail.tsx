import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import {
  X,
  Play,
  Pause,
  RotateCw,
  Clock,
  Calendar,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Wrench,
} from "lucide-react";

import {
  Experiment,
  Run,
  getExperiment,
  pauseExperiment,
  resumeExperiment,
  runTick,
  scheduleExperiment,
} from "../lib/api";

interface Props {
  experimentId: string | null;
  onClear: () => void;
}

const PHASES = ["design", "build", "execute", "measure", "learn", "complete"];

const PHASE_CONFIG: Record<string, { class: string }> = {
  design: { class: "phase-design" },
  build: { class: "phase-build" },
  execute: { class: "phase-execute" },
  measure: { class: "phase-measure" },
  learn: { class: "phase-learn" },
  complete: { class: "phase-complete" },
  paused: { class: "phase-paused" },
};

function PhasePipeline({ currentPhase }: { currentPhase: string }) {
  const activeIdx = PHASES.indexOf(currentPhase);
  return (
    <div className="mb-6 flex items-center gap-1.5">
      {PHASES.map((phase, i) => {
        const isActive = phase === currentPhase;
        const isComplete = activeIdx > i;
        const isPaused = currentPhase === "paused";
        return (
          <div key={phase} className="flex items-center gap-1.5">
            <div
              className={clsx(
                "glass-pill border text-[11px] transition-all",
                isActive && !isPaused && PHASE_CONFIG[phase]?.class,
                isActive && !isPaused && "ring-1 ring-white/10",
                isComplete && "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
                !isActive && !isComplete && "text-slate-600 border-transparent",
                isPaused && isActive && "phase-paused ring-1 ring-white/10",
              )}
            >
              {isComplete && <span className="mr-1">&#10003;</span>}
              {phase}
            </div>
            {i < PHASES.length - 1 && (
              <div
                className={clsx(
                  "h-px w-3 transition-all",
                  isComplete ? "bg-emerald-500/40" : "bg-slate-800",
                )}
              />
            )}
          </div>
        );
      })}
      {currentPhase === "paused" && (
        <div className="ml-2 glass-pill border phase-paused text-[10px]">
          PAUSED
        </div>
      )}
    </div>
  );
}

function TokenUsageBar({ used, budget }: { used: number; budget: number }) {
  const pct = Math.min(100, (used / budget) * 100);
  const isHigh = pct > 80;
  return (
    <div className="mb-6">
      <div className="mb-1.5 flex justify-between text-[11px] text-slate-400">
        <span>Token Usage</span>
        <span>
          {used.toLocaleString()} / {budget.toLocaleString()} ({pct.toFixed(1)}%)
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800/80">
        <div
          className={clsx(
            "h-full rounded-full transition-all",
            isHigh
              ? "bg-gradient-to-r from-rose-500 to-rose-400"
              : "bg-gradient-to-r from-emerald-500 to-emerald-400",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function ExperimentDetail({ experimentId, onClear }: Props) {
  const [experiment, setExperiment] = useState<Experiment | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [busy, setBusy] = useState(false);
  const [ticking, setTicking] = useState(false);
  const [showSchedule, setShowSchedule] = useState(false);
  const [expandedRun, setExpandedRun] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!experimentId) {
      setExperiment(null);
      setRuns([]);
      return;
    }
    try {
      const { experiment, runs } = await getExperiment(experimentId);
      setExperiment(experiment);
      setRuns(runs);
    } catch {
      setExperiment(null);
    }
  }, [experimentId]);

  useEffect(() => {
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [load]);

  if (!experimentId || !experiment) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center text-center">
        <div className="glass-card p-8">
          <div className="text-slate-600 mb-2">
            <ChevronRight size={32} className="mx-auto" />
          </div>
          <p className="text-sm text-slate-400">Select an experiment from the sidebar.</p>
        </div>
      </div>
    );
  }

  async function withBusy<T>(fn: () => Promise<T>): Promise<T | undefined> {
    setBusy(true);
    try {
      return await fn();
    } catch (e) {
      console.error(e);
    } finally {
      setBusy(false);
      load();
    }
  }

  return (
    <div className="flex h-full w-full flex-col overflow-y-auto p-6 animate-fade-in">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h2 className="text-xl font-semibold text-slate-100">{experiment.name}</h2>
          {experiment.hypothesis && (
            <p className="mt-1 text-sm text-slate-400">{experiment.hypothesis}</p>
          )}
          <div className="mt-1 text-[10px] text-slate-600 font-mono">id: {experiment.id}</div>
        </div>
        <button
          onClick={onClear}
          className="glass-pill flex items-center gap-1 text-slate-400 hover:text-slate-200 transition-colors"
        >
          <X size={12} /> close
        </button>
      </div>

      <PhasePipeline currentPhase={experiment.phase} />
      <TokenUsageBar used={experiment.tokens_used} budget={experiment.token_budget} />

      {/* Info grid */}
      <div className="glass-card mb-6 grid grid-cols-2 gap-4 p-4 text-sm">
        <Field label="Phase" value={experiment.phase} />
        <Field label="Play(s)" value={experiment.play_ids.join(", ") || "none"} />
        <Field label="Agent" value={experiment.current_agent || "orchestrator"} />
        <Field label="Created" value={experiment.created_at ? new Date(experiment.created_at).toLocaleDateString() : "unknown"} />
        {experiment.description && (
          <div className="col-span-2">
            <Field label="Description" value={experiment.description} />
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="mb-6 flex flex-wrap gap-2">
        {experiment.phase !== "paused" && experiment.phase !== "complete" && (
          <button
            disabled={busy}
            onClick={() => withBusy(() => pauseExperiment(experiment.id))}
            className="glass-btn-danger flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs disabled:opacity-40"
          >
            <Pause size={12} /> Pause
          </button>
        )}
        {experiment.phase === "paused" && (
          <button
            disabled={busy}
            onClick={() => withBusy(() => resumeExperiment(experiment.id))}
            className="glass-btn flex items-center gap-1.5 px-3 py-1.5 text-xs disabled:opacity-40"
          >
            <Play size={12} /> Resume
          </button>
        )}
        <button
          disabled={ticking || busy}
          onClick={async () => {
            setTicking(true);
            try { await runTick(experiment.id); } catch (e) { console.error(e); }
            setTicking(false);
            load();
          }}
          className="glass-btn flex items-center gap-1.5 px-3 py-1.5 text-xs disabled:opacity-40"
        >
          {ticking ? <Loader2 size={12} className="animate-spin" /> : <RotateCw size={12} />}
          {ticking ? "Running..." : "Run Tick"}
        </button>
        <button
          onClick={() => setShowSchedule((v) => !v)}
          className="glass-pill flex items-center gap-1.5 text-slate-400 hover:text-slate-200 transition-colors"
        >
          <Calendar size={12} />
          {showSchedule ? "hide schedule" : "schedule"}
        </button>
      </div>

      {showSchedule && (
        <ScheduleForm
          experimentId={experiment.id}
          onScheduled={() => { setShowSchedule(false); load(); }}
        />
      )}

      {/* Runs */}
      <div className="space-y-2">
        <h3 className="text-xs font-medium uppercase tracking-wider text-slate-400 mb-3">
          Run History ({runs.length})
        </h3>
        {runs.length === 0 && (
          <p className="text-xs text-slate-500">No runs yet. Click "Run Tick" to start.</p>
        )}
        {runs.map((r) => (
          <div key={r.id} className="glass-card !rounded-xl overflow-hidden">
            <button
              onClick={() => setExpandedRun(expandedRun === r.id ? null : r.id)}
              className="flex w-full items-center justify-between px-4 py-3 text-left"
            >
              <div className="flex items-center gap-2">
                {r.status === "completed" && <CheckCircle2 size={14} className="text-emerald-400" />}
                {r.status === "failed" && <AlertTriangle size={14} className="text-rose-400" />}
                {r.status === "running" && <Loader2 size={14} className="text-sky-400 animate-spin" />}
                <span className="text-sm text-slate-200">{r.phase}</span>
                <span className={clsx("glass-pill border text-[10px]", PHASE_CONFIG[r.phase]?.class)}>
                  {r.status}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-[10px] text-slate-500">
                  {r.tokens_used.toLocaleString()} tok
                </span>
                <span className="text-[10px] text-slate-600 font-mono">
                  {r.started_at ? new Date(r.started_at).toLocaleTimeString() : ""}
                </span>
                {expandedRun === r.id ? <ChevronDown size={12} className="text-slate-500" /> : <ChevronRight size={12} className="text-slate-500" />}
              </div>
            </button>
            {expandedRun === r.id && (
              <div className="border-t border-white/[0.06] px-4 py-3 text-xs animate-fade-in">
                {r.error && (
                  <div className="mb-2 rounded-lg bg-rose-500/10 border border-rose-500/20 p-2 text-rose-300">
                    {r.error}
                  </div>
                )}
                {r.tools_used && r.tools_used.length > 0 && (
                  <div>
                    <span className="text-slate-400 flex items-center gap-1 mb-1">
                      <Wrench size={10} /> Tools used:
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {r.tools_used.map((t, i) => (
                        <span key={i} className="glass-pill text-slate-400">{t.name}</span>
                      ))}
                    </div>
                  </div>
                )}
                <div className="mt-2 text-slate-500 font-mono">
                  id: {r.id}
                  {r.completed_at && ` | completed: ${new Date(r.completed_at).toLocaleString()}`}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-0.5">{label}</div>
      <div className="text-sm text-slate-200">{value}</div>
    </div>
  );
}

function ScheduleForm({
  experimentId,
  onScheduled,
}: {
  experimentId: string;
  onScheduled: () => void;
}) {
  const [cron, setCron] = useState("*/30 * * * *");
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    try {
      await scheduleExperiment(experimentId, { cron_expr: cron });
      onScheduled();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="glass-card mb-6 p-4 animate-fade-in">
      <div className="flex items-center gap-2 mb-2 text-xs text-slate-400">
        <Clock size={12} />
        Schedule this experiment
      </div>
      <div className="flex gap-2">
        <input
          value={cron}
          onChange={(e) => setCron(e.target.value)}
          placeholder="cron expression"
          className="glass-input flex-1 px-3 py-1.5 text-xs text-slate-100"
        />
        <button
          onClick={submit}
          disabled={busy || !cron.trim()}
          className="glass-btn px-3 py-1.5 text-xs disabled:opacity-40"
        >
          {busy ? "saving..." : "Save Schedule"}
        </button>
      </div>
    </div>
  );
}
