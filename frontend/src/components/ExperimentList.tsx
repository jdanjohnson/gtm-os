import { useEffect, useState } from "react";
import clsx from "clsx";
import { Plus, X, FlaskConical } from "lucide-react";

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

const PHASE_CLASS: Record<string, string> = {
  design: "phase-design",
  build: "phase-build",
  execute: "phase-execute",
  measure: "phase-measure",
  learn: "phase-learn",
  complete: "phase-complete",
  paused: "phase-paused",
};

export default function ExperimentList({ selectedId, onSelect, primitives }: Props) {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [creating, setCreating] = useState(false);

  async function refresh() {
    try {
      const { experiments } = await listExperiments();
      setExperiments(experiments);
    } catch {
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
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
        <h3 className="text-xs font-medium uppercase tracking-wider text-slate-400">
          Experiments
        </h3>
        <button
          onClick={() => setCreating((v) => !v)}
          className={clsx(
            "flex items-center gap-1 rounded-lg px-2 py-1 text-xs transition-all",
            creating ? "glass-btn-danger" : "glass-btn"
          )}
        >
          {creating ? <><X size={12} /> cancel</> : <><Plus size={12} /> new</>}
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

      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {experiments.length === 0 && !creating ? (
          <div className="flex flex-col items-center py-8 text-center">
            <FlaskConical size={24} className="text-slate-600 mb-2" />
            <p className="text-xs text-slate-500 px-4">
              No experiments yet. Open the chat and describe what you want to test.
            </p>
          </div>
        ) : null}
        {experiments.map((e) => (
          <button
            key={e.id}
            onClick={() => onSelect(e.id)}
            className={clsx(
              "block w-full rounded-xl px-3 py-3 text-left text-sm transition-all",
              selectedId === e.id
                ? "glass text-slate-100 glow-emerald"
                : "text-slate-300 hover:bg-white/[0.03]",
            )}
          >
            <div className="font-medium text-slate-100 truncate">{e.name}</div>
            <div className="mt-1.5 flex items-center gap-2 text-[11px]">
              <span className={clsx("glass-pill border", PHASE_CLASS[e.phase] ?? "")}>
                {e.phase}
              </span>
              <span className="text-slate-500 truncate">{e.play_ids.join(", ") || "no play"}</span>
            </div>
            <div className="mt-1.5 flex items-center gap-2">
              <div className="flex-1 h-1 overflow-hidden rounded-full bg-slate-800/80">
                <div
                  className="h-full rounded-full bg-emerald-500/50 transition-all"
                  style={{ width: `${e.token_budget > 0 ? Math.min(100, (e.tokens_used / e.token_budget) * 100) : 0}%` }}
                />
              </div>
              <span className="text-[10px] text-slate-500 shrink-0">
                {e.tokens_used.toLocaleString()} tok
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
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
    <div className="border-b border-white/[0.06] p-3 space-y-2 animate-fade-in">
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="experiment name"
        className="glass-input w-full px-3 py-1.5 text-xs text-slate-100"
      />
      <input
        value={hypothesis}
        onChange={(e) => setHypothesis(e.target.value)}
        placeholder="hypothesis (optional)"
        className="glass-input w-full px-3 py-1.5 text-xs text-slate-100"
      />
      <div className="grid grid-cols-2 gap-2">
        <select
          value={play}
          onChange={(e) => setPlay(e.target.value)}
          className="glass-input px-2 py-1.5 text-xs text-slate-100"
        >
          <option value="">play...</option>
          {plays.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
        <input
          value={channel}
          onChange={(e) => setChannel(e.target.value)}
          placeholder="channel"
          className="glass-input px-2 py-1.5 text-xs text-slate-100"
        />
      </div>
      <button
        onClick={submit}
        disabled={!name.trim() || busy}
        className="glass-btn w-full px-3 py-1.5 text-xs disabled:opacity-40"
      >
        {busy ? "creating..." : "Create Experiment"}
      </button>
    </div>
  );
}
