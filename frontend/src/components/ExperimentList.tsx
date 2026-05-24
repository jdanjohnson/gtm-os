import { useEffect, useState } from "react";
import clsx from "clsx";

import {
  Experiment,
  PrimitivesSummary,
  createExperiment,
  listExperiments,
} from "../lib/api";

interface Props {
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  primitives: PrimitivesSummary | null;
}

export default function ExperimentList({ selectedId, onSelect, primitives }: Props) {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [creating, setCreating] = useState(false);

  async function refresh() {
    try {
      const { experiments } = await listExperiments();
      setExperiments(experiments);
    } catch (e) {
      // ignore
    }
  }

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-300">
          Experiments
        </h3>
        <button
          onClick={() => setCreating((v) => !v)}
          className="rounded bg-emerald-600 px-2 py-1 text-xs hover:bg-emerald-500"
        >
          {creating ? "cancel" : "+ new"}
        </button>
      </div>

      {creating && (
        <CreateExperimentForm
          primitives={primitives}
          onCreated={(e) => {
            setCreating(false);
            refresh();
            onSelect(e.id);
          }}
        />
      )}

      <div className="flex-1 overflow-y-auto">
        {experiments.length === 0 && !creating ? (
          <div className="p-4 text-xs text-slate-500">
            No experiments yet. Tell the orchestrator what you want and it will create one.
          </div>
        ) : null}
        {experiments.map((e) => (
          <button
            key={e.id}
            onClick={() => onSelect(e.id)}
            className={clsx(
              "block w-full border-b border-slate-900 px-4 py-3 text-left text-sm hover:bg-slate-800/40",
              selectedId === e.id && "bg-slate-800/60",
            )}
          >
            <div className="font-medium text-slate-100">{e.name}</div>
            <div className="mt-1 flex items-center gap-2 text-[11px] text-slate-400">
              <span className={phaseColor(e.phase)}>{e.phase}</span>
              <span>·</span>
              <span>{e.play_ids.join(", ") || "no play"}</span>
            </div>
            <div className="mt-1 text-[10px] text-slate-500">
              {e.tokens_used.toLocaleString()} / {e.token_budget.toLocaleString()} tokens
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function phaseColor(phase: string) {
  const map: Record<string, string> = {
    design: "text-sky-300",
    build: "text-indigo-300",
    execute: "text-amber-300",
    measure: "text-emerald-300",
    learn: "text-fuchsia-300",
    complete: "text-slate-300",
    paused: "text-rose-300",
  };
  return map[phase] ?? "text-slate-300";
}

function CreateExperimentForm({
  primitives,
  onCreated,
}: {
  primitives: PrimitivesSummary | null;
  onCreated: (e: Experiment) => void;
}) {
  const [name, setName] = useState("");
  const [hypothesis, setHypothesis] = useState("");
  const [play, setPlay] = useState("");
  const [channel, setChannel] = useState("");
  const [busy, setBusy] = useState(false);
  const plays = primitives?.plays ?? [];

  async function submit() {
    if (!name.trim()) return;
    setBusy(true);
    try {
      const { experiment } = await createExperiment({
        name,
        hypothesis: hypothesis || undefined,
        play_ids: play ? [play] : undefined,
        channel: channel || undefined,
      });
      onCreated(experiment);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="border-b border-slate-800 bg-slate-900/40 p-3 text-xs">
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="experiment name"
        className="mb-2 w-full rounded bg-slate-900 px-2 py-1 outline-none focus:ring-1 focus:ring-emerald-500"
      />
      <input
        value={hypothesis}
        onChange={(e) => setHypothesis(e.target.value)}
        placeholder="hypothesis (optional)"
        className="mb-2 w-full rounded bg-slate-900 px-2 py-1 outline-none focus:ring-1 focus:ring-emerald-500"
      />
      <div className="mb-2 grid grid-cols-2 gap-2">
        <select
          value={play}
          onChange={(e) => setPlay(e.target.value)}
          className="rounded bg-slate-900 px-2 py-1"
        >
          <option value="">choose a play…</option>
          {plays.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <input
          value={channel}
          onChange={(e) => setChannel(e.target.value)}
          placeholder="channel (email, linkedin, …)"
          className="rounded bg-slate-900 px-2 py-1"
        />
      </div>
      <button
        onClick={submit}
        disabled={busy || !name.trim()}
        className="w-full rounded bg-emerald-600 px-2 py-1 text-xs disabled:opacity-50"
      >
        {busy ? "creating…" : "create experiment"}
      </button>
    </div>
  );
}
