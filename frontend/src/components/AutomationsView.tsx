import { useEffect, useState } from "react";
import clsx from "clsx";
import {
  Zap,
  Clock,
  Play,
  Pause,
  AlertTriangle,
  CheckCircle2,
  Calendar,
  RefreshCw,
} from "lucide-react";

import { Experiment, listExperiments } from "../lib/api";

export default function AutomationsView() {
  const [experiments, setExperiments] = useState<Experiment[]>([]);

  useEffect(() => {
    listExperiments().then(({ experiments }) => setExperiments(experiments)).catch(() => null);
    const t = setInterval(() => {
      listExperiments().then(({ experiments }) => setExperiments(experiments)).catch(() => null);
    }, 5000);
    return () => clearInterval(t);
  }, []);

  const scheduled = experiments.filter((e) => e.schedule_id);
  const unscheduled = experiments.filter((e) => !e.schedule_id && e.phase !== "complete");

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div>
        <h2 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
          <Zap size={20} className="text-amber-400" />
          Automations
        </h2>
        <p className="text-xs text-slate-500 mt-1">
          Scheduled experiment runs. Set up cron schedules or interval-based triggers.
        </p>
      </div>

      {/* Scheduled */}
      <div>
        <h3 className="text-xs font-medium uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
          <Calendar size={12} className="text-emerald-400" />
          Scheduled ({scheduled.length})
        </h3>

        {scheduled.length === 0 ? (
          <div className="glass-card p-6 text-center">
            <Clock size={28} className="mx-auto mb-2 text-slate-600" />
            <p className="text-sm text-slate-400">No scheduled experiments.</p>
            <p className="text-xs text-slate-500 mt-1">
              Open an experiment and click "Schedule" to set up automated runs.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {scheduled.map((exp) => (
              <ScheduleCard key={exp.id} experiment={exp} />
            ))}
          </div>
        )}
      </div>

      {/* Unscheduled */}
      {unscheduled.length > 0 && (
        <div>
          <h3 className="text-xs font-medium uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
            <RefreshCw size={12} className="text-slate-500" />
            Manual Only ({unscheduled.length})
          </h3>
          <div className="space-y-2">
            {unscheduled.map((exp) => (
              <div key={exp.id} className="glass-card !rounded-xl px-4 py-3 flex items-center justify-between">
                <div>
                  <span className="text-sm text-slate-200">{exp.name}</span>
                  <span className={clsx(
                    "ml-2 glass-pill border text-[10px]",
                    exp.phase === "paused" ? "phase-paused" : "phase-" + exp.phase,
                  )}>
                    {exp.phase}
                  </span>
                </div>
                <span className="text-[11px] text-slate-500">no schedule</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tips */}
      <div className="glass-card p-4">
        <h4 className="text-xs font-medium text-slate-300 mb-2">Scheduling Tips</h4>
        <ul className="space-y-1.5 text-xs text-slate-400">
          <li className="flex items-start gap-2">
            <span className="text-emerald-400 mt-0.5">&#8226;</span>
            Tell the orchestrator in chat: <span className="text-slate-300">"Run experiment X every Monday at 9am"</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-emerald-400 mt-0.5">&#8226;</span>
            Or use cron expressions: <span className="font-mono text-slate-300">0 9 * * 1</span> = every Monday 9am
          </li>
          <li className="flex items-start gap-2">
            <span className="text-emerald-400 mt-0.5">&#8226;</span>
            Experiments auto-pause after 3 consecutive failures
          </li>
        </ul>
      </div>
    </div>
  );
}

function ScheduleCard({ experiment: exp }: { experiment: Experiment }) {
  const isActive = exp.phase !== "paused" && exp.phase !== "complete";

  return (
    <div className={clsx("glass-card p-4", isActive && "glow-emerald")}>
      <div className="flex items-start justify-between mb-2">
        <div>
          <h4 className="text-sm font-medium text-slate-100">{exp.name}</h4>
          <span className={clsx(
            "glass-pill border text-[10px] mt-1 inline-block",
            "phase-" + exp.phase,
          )}>
            {exp.phase}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {isActive ? (
            <div className="flex items-center gap-1 text-[11px] text-emerald-400">
              <Play size={10} /> active
            </div>
          ) : exp.phase === "paused" ? (
            <div className="flex items-center gap-1 text-[11px] text-amber-400">
              <Pause size={10} /> paused
            </div>
          ) : (
            <div className="flex items-center gap-1 text-[11px] text-slate-500">
              <CheckCircle2 size={10} /> done
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-4 text-[11px] text-slate-400">
        <span className="flex items-center gap-1">
          <Clock size={10} />
          schedule: {exp.schedule_id?.slice(0, 8)}...
        </span>
        <span>
          {exp.tokens_used.toLocaleString()} / {exp.token_budget.toLocaleString()} tokens
        </span>
      </div>
    </div>
  );
}
