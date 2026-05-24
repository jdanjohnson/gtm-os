import { useEffect, useState } from "react";
import clsx from "clsx";
import type { Experiment } from "../lib/api";

interface Props {
  experiments: Experiment[];
  activeExperiments: Experiment[];
  trustScores: Record<string, number>;
  avgTrust: number;
  memoryCount: number;
  onOpenExperiment: (id: string) => void;
}

interface ProposedExperiment {
  id: string;
  name: string;
  hypothesis?: string;
  rationale?: string;
  status: string;
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

export default function Dashboard({
  experiments,
  activeExperiments,
  trustScores,
  avgTrust,
  memoryCount,
  onOpenExperiment,
}: Props) {
  const [proposals, setProposals] = useState<ProposedExperiment[]>([]);

  useEffect(() => {
    fetch("/api/proposed-experiments?status=pending")
      .then((r) => r.json())
      .then((d) => setProposals(d.proposals || []))
      .catch(() => null);
  }, []);

  const handleApprove = async (id: string) => {
    await fetch(`/api/proposed-experiments/${id}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "approve" }),
    });
    setProposals((p) => p.filter((x) => x.id !== id));
  };

  const handleDismiss = async (id: string) => {
    await fetch(`/api/proposed-experiments/${id}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "reject" }),
    });
    setProposals((p) => p.filter((x) => x.id !== id));
  };

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold">Good morning</h1>
        <p className="mt-1 text-sm text-[#A1A1AA]">
          {activeExperiments.length} experiment{activeExperiments.length !== 1 ? "s" : ""} running
          {avgTrust > 0 ? ` · Trust trending ${avgTrust >= 0.5 ? "up" : "steady"}` : ""}
        </p>
      </div>

      {/* Active Experiments */}
      <section className="mb-6">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[#A1A1AA]">
          Active Experiments
        </h2>
        {activeExperiments.length === 0 ? (
          <p className="text-sm text-[#A1A1AA]">No active experiments. Start one from the chat.</p>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {activeExperiments.map((e) => {
              const trust = trustScores[e.config?.channel as string] ?? 0;
              return (
                <button
                  key={e.id}
                  onClick={() => onOpenExperiment(e.id)}
                  className="rounded-xl border border-[#2A2A2A] bg-[#1A1A1A] p-4 text-left hover:border-[#3A3A3A] transition-colors"
                >
                  <div className="mb-2 flex items-center justify-between">
                    <span className="font-medium text-sm">{e.name}</span>
                    <span className={clsx("h-2.5 w-2.5 rounded-full", PHASE_DOTS[e.phase])} />
                  </div>
                  {e.hypothesis && (
                    <p className="mb-2 text-xs text-[#A1A1AA] line-clamp-2">{e.hypothesis}</p>
                  )}
                  <div className="flex items-center justify-between text-[11px] text-[#A1A1AA]">
                    <span className={phaseTextColor(e.phase)}>{e.phase}</span>
                    <span>Trust {trust.toFixed(2)}</span>
                  </div>
                  <div className="mt-2 text-[10px] text-[#A1A1AA]">
                    {e.tokens_used.toLocaleString()} / {e.token_budget.toLocaleString()} tokens
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </section>

      {/* Two-column: Learnings + Proposed */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Recent completed experiments (stand-in for learnings) */}
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[#A1A1AA]">
            Recent Experiments
          </h2>
          <div className="rounded-xl border border-[#2A2A2A] bg-[#1A1A1A] p-4">
            {experiments.filter((e) => e.phase === "complete").length === 0 ? (
              <p className="text-xs text-[#A1A1AA]">No completed experiments yet.</p>
            ) : (
              <div className="space-y-3">
                {experiments
                  .filter((e) => e.phase === "complete")
                  .slice(0, 5)
                  .map((e) => (
                    <button
                      key={e.id}
                      onClick={() => onOpenExperiment(e.id)}
                      className="block w-full text-left"
                    >
                      <div className="text-sm">{e.name}</div>
                      <div className="text-[11px] text-[#A1A1AA]">Completed</div>
                    </button>
                  ))}
              </div>
            )}
          </div>
        </section>

        {/* Proposed Experiments */}
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[#A1A1AA]">
            Proposed Experiments
          </h2>
          <div className="rounded-xl border border-[#2A2A2A] bg-[#1A1A1A] p-4">
            {proposals.length === 0 ? (
              <p className="text-xs text-[#A1A1AA]">No pending proposals.</p>
            ) : (
              <div className="space-y-3">
                {proposals.map((p) => (
                  <div key={p.id} className="rounded-lg border border-[#2A2A2A] p-3">
                    <div className="mb-1 text-sm font-medium">{p.name}</div>
                    {p.hypothesis && (
                      <p className="mb-2 text-xs text-[#A1A1AA]">{p.hypothesis}</p>
                    )}
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleApprove(p.id)}
                        className="rounded bg-emerald-600 px-2.5 py-1 text-xs hover:bg-emerald-500"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => handleDismiss(p.id)}
                        className="rounded bg-[#2A2A2A] px-2.5 py-1 text-xs text-[#A1A1AA] hover:bg-[#3A3A3A]"
                      >
                        Dismiss
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Trust + Stats row */}
      <section className="mt-6">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[#A1A1AA]">
          System Overview
        </h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label="Avg Trust" value={avgTrust.toFixed(2)} sub={avgTrust >= 0.7 ? "Autonomous" : avgTrust >= 0.3 ? "Semi-auto" : "Manual"} />
          <StatCard label="Experiments" value={String(experiments.length)} sub={`${activeExperiments.length} active`} />
          <StatCard label="Memories" value={String(memoryCount)} sub="knowledge items" />
          <StatCard
            label="Trust Scores"
            value={String(Object.keys(trustScores).length)}
            sub="experiment types tracked"
          />
        </div>
      </section>
    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-xl border border-[#2A2A2A] bg-[#1A1A1A] p-4">
      <div className="text-xs text-[#A1A1AA]">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      <div className="mt-0.5 text-[11px] text-[#A1A1AA]">{sub}</div>
    </div>
  );
}

function phaseTextColor(phase: string): string {
  const map: Record<string, string> = {
    design: "text-yellow-400",
    build: "text-blue-400",
    execute: "text-green-400",
    measure: "text-orange-400",
    learn: "text-purple-400",
    complete: "text-gray-400",
    paused: "text-red-400",
  };
  return map[phase] ?? "text-gray-400";
}
