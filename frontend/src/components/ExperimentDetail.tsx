import { useCallback, useEffect, useState } from "react";

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

export default function ExperimentDetail({ experimentId, onClear }: Props) {
  const [experiment, setExperiment] = useState<Experiment | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [busy, setBusy] = useState(false);
  const [ticking, setTicking] = useState(false);
  const [showSchedule, setShowSchedule] = useState(false);

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
      <div className="flex h-full w-full items-center justify-center text-sm text-slate-500">
        Select an experiment from the sidebar.
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
    <div className="flex h-full w-full flex-col overflow-y-auto px-6 py-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">{experiment.name}</h2>
          <div className="mt-1 text-xs text-slate-400">id: {experiment.id}</div>
        </div>
        <button
          onClick={onClear}
          className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-400 hover:bg-slate-800"
        >
          close
        </button>
      </div>

      <section className="mb-4 grid grid-cols-2 gap-4 rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-sm">
        <Field label="phase" value={experiment.phase} />
        <Field label="play(s)" value={experiment.play_ids.join(", ") || "—"} />
        <Field label="channel" value={(experiment.config?.channel as string) ?? "—"} />
        <Field label="agent" value={experiment.current_agent ?? "—"} />
        <Field
          label="tokens"
          value={`${experiment.tokens_used.toLocaleString()} / ${experiment.token_budget.toLocaleString()}`}
        />
        <Field
          label="schedule"
          value={experiment.schedule_id ? experiment.schedule_id.slice(0, 8) + "…" : "—"}
        />
      </section>

      {experiment.hypothesis && (
        <section className="mb-4 rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-sm">
          <div className="mb-1 text-xs uppercase tracking-wide text-slate-400">Hypothesis</div>
          <div className="whitespace-pre-wrap">{experiment.hypothesis}</div>
        </section>
      )}
      {experiment.description && (
        <section className="mb-4 rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-sm">
          <div className="mb-1 text-xs uppercase tracking-wide text-slate-400">Description</div>
          <div className="whitespace-pre-wrap">{experiment.description}</div>
        </section>
      )}

      <section className="mb-4 flex flex-wrap gap-2">
        <button
          disabled={busy || ticking}
          onClick={async () => {
            setTicking(true);
            try {
              await runTick(experiment.id);
            } finally {
              setTicking(false);
              load();
            }
          }}
          className="rounded bg-emerald-600 px-3 py-1.5 text-xs hover:bg-emerald-500 disabled:opacity-40"
        >
          {ticking ? "running tick…" : "run tick"}
        </button>
        <button
          disabled={busy || experiment.phase === "paused"}
          onClick={() => withBusy(() => pauseExperiment(experiment.id))}
          className="rounded bg-rose-700/80 px-3 py-1.5 text-xs hover:bg-rose-600 disabled:opacity-40"
        >
          pause
        </button>
        <button
          disabled={busy || experiment.phase !== "paused"}
          onClick={() => withBusy(() => resumeExperiment(experiment.id))}
          className="rounded bg-indigo-700 px-3 py-1.5 text-xs hover:bg-indigo-600 disabled:opacity-40"
        >
          resume
        </button>
        <button
          onClick={() => setShowSchedule((v) => !v)}
          className="rounded border border-slate-700 px-3 py-1.5 text-xs hover:bg-slate-800"
        >
          {showSchedule ? "hide schedule" : "schedule"}
        </button>
      </section>

      {showSchedule && (
        <ScheduleForm
          experimentId={experiment.id}
          onDone={() => {
            setShowSchedule(false);
            load();
          }}
        />
      )}

      <section className="mt-2">
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Runs
        </h3>
        {runs.length === 0 ? (
          <div className="text-xs text-slate-500">No runs yet — kick one off with “run tick”.</div>
        ) : (
          <div className="space-y-2">
            {runs.map((r) => (
              <div
                key={r.id}
                className="rounded border border-slate-800 bg-slate-900/40 p-3 text-xs"
              >
                <div className="flex items-center justify-between text-slate-300">
                  <span>
                    [{r.phase}] {r.status}
                    {r.error ? <span className="ml-2 text-rose-400">{r.error}</span> : null}
                  </span>
                  <span className="text-slate-500">
                    {r.tokens_used} tokens · {r.started_at}
                  </span>
                </div>
                {r.tools_used && r.tools_used.length > 0 && (
                  <ul className="mt-2 space-y-1 text-slate-400">
                    {r.tools_used.map((t, i) => (
                      <li key={i} className="font-mono text-[11px]">
                        → {t.name}({JSON.stringify(t.arguments).slice(0, 120)}…)
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className="text-slate-100">{value}</div>
    </div>
  );
}

function ScheduleForm({
  experimentId,
  onDone,
}: {
  experimentId: string;
  onDone: () => void;
}) {
  const [cron, setCron] = useState("");
  const [interval, setInterval] = useState("");
  const [maxCost, setMaxCost] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    try {
      await scheduleExperiment(experimentId, {
        cron_expr: cron || undefined,
        interval_seconds: interval ? Number(interval) : undefined,
        max_cost: maxCost ? Number(maxCost) : undefined,
      });
      onDone();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mb-4 rounded-xl border border-slate-800 bg-slate-900/30 p-4 text-xs">
      <div className="mb-2 grid grid-cols-2 gap-2">
        <input
          value={cron}
          onChange={(e) => setCron(e.target.value)}
          placeholder="cron expr (e.g. 0 9 * * 1-5)"
          className="rounded bg-slate-900 px-2 py-1"
        />
        <input
          value={interval}
          onChange={(e) => setInterval(e.target.value)}
          placeholder="interval seconds"
          type="number"
          className="rounded bg-slate-900 px-2 py-1"
        />
        <input
          value={maxCost}
          onChange={(e) => setMaxCost(e.target.value)}
          placeholder="max cost ($)"
          type="number"
          step="0.01"
          className="rounded bg-slate-900 px-2 py-1"
        />
      </div>
      <button
        onClick={submit}
        disabled={busy || (!cron && !interval)}
        className="rounded bg-emerald-600 px-3 py-1.5 disabled:opacity-50"
      >
        {busy ? "scheduling…" : "set schedule"}
      </button>
    </div>
  );
}
