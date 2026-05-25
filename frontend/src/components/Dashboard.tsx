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

const PHASE_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
  design: { bg: "bg-amber-500/10", text: "text-amber-500", dot: "bg-amber-500" },
  build: { bg: "bg-blue-500/10", text: "text-blue-500", dot: "bg-blue-500" },
  execute: { bg: "bg-emerald-500/10", text: "text-emerald-500", dot: "bg-emerald-500" },
  measure: { bg: "bg-orange-500/10", text: "text-orange-500", dot: "bg-orange-500" },
  learn: { bg: "bg-purple-500/10", text: "text-purple-500", dot: "bg-purple-500" },
  complete: { bg: "bg-gray-400/10", text: "text-gray-400", dot: "bg-gray-400" },
  paused: { bg: "bg-red-400/10", text: "text-red-400", dot: "bg-red-400" },
};

function trustRingColor(score: number): string {
  if (score >= 0.7) return "#10B981";
  if (score >= 0.5) return "#F59E0B";
  if (score >= 0.3) return "#F97316";
  return "#EF4444";
}

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

  const totalTokens = experiments.reduce((s, e) => s + e.token_budget, 0);
  const usedTokens = experiments.reduce((s, e) => s + e.tokens_used, 0);
  const tokenPct = totalTokens > 0 ? Math.round((usedTokens / totalTokens) * 100) : 0;

  const trustEntries = Object.entries(trustScores);
  const ringRadius = 27;
  const ringCircumference = 2 * Math.PI * ringRadius;

  return (
    <div className="p-7">
      {/* Greeting */}
      <div className="mb-7 flex items-start justify-between">
        <div>
          <h1 className="text-[28px] font-bold tracking-tight text-gray-900">
            Good morning
          </h1>
          <p className="mt-1 text-[13px] text-gray-500">
            {activeExperiments.length} experiment{activeExperiments.length !== 1 ? "s" : ""} running
            {avgTrust > 0 ? ` · Trust trending ${avgTrust >= 0.5 ? "up" : "steady"}` : ""}
            {proposals.length > 0 ? ` · ${proposals.length} proposal${proposals.length !== 1 ? "s" : ""} waiting` : ""}
          </p>
        </div>
      </div>

      {/* Proposal banners */}
      {proposals.length > 0 && (
        <div className="mb-7 space-y-3">
          {proposals.map((p) => (
            <div
              key={p.id}
              className="flex items-center gap-4 rounded-2xl border border-coral/15 bg-gradient-to-r from-coral/[0.08] to-purple-500/[0.06] p-[18px] backdrop-blur-sm"
            >
              <div className="flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-xl bg-coral-light text-xl">
                💡
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[13px] font-semibold text-gray-900">{p.name}</div>
                {p.hypothesis && (
                  <div className="mt-0.5 text-[12px] text-gray-500 truncate">{p.hypothesis}</div>
                )}
              </div>
              <div className="flex gap-2 shrink-0">
                <button
                  onClick={() => handleApprove(p.id)}
                  className="rounded-full bg-coral px-4 py-[6px] text-[11px] font-semibold text-white shadow-[0_2px_8px_rgba(239,99,68,0.25)] transition hover:bg-coral-hover"
                >
                  Approve
                </button>
                <button
                  onClick={() => handleDismiss(p.id)}
                  className="glass-subtle rounded-full px-4 py-[6px] text-[11px] font-semibold text-gray-500 transition hover:text-gray-700"
                >
                  Dismiss
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Stats Row */}
      <div className="mb-7 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          icon="🧪"
          iconBg="bg-coral-light"
          label="Active Experiments"
          value={String(activeExperiments.length)}
          sub={`${experiments.length} total`}
          accent="text-gray-900"
        />
        <StatCard
          icon="✅"
          iconBg="bg-emerald-500/10"
          label="Avg Trust Score"
          value={avgTrust.toFixed(2)}
          sub={avgTrust >= 0.7 ? "Autonomous" : avgTrust >= 0.5 ? "Semi-auto" : "Manual"}
          accent="text-emerald-600"
        />
        <StatCard
          icon="🧠"
          iconBg="bg-purple-500/10"
          label="Memory Entries"
          value={String(memoryCount)}
          bar={{ pct: Math.min(memoryCount / 1000, 1) * 100, color: "bg-purple-500" }}
          accent="text-gray-900"
        />
        <StatCard
          icon="⚡"
          iconBg="bg-amber-500/10"
          label="Token Usage"
          value={usedTokens > 1000 ? `${(usedTokens / 1000).toFixed(1)}k` : String(usedTokens)}
          sub={`${tokenPct}% of ${totalTokens > 1000 ? `${(totalTokens / 1000).toFixed(0)}k` : totalTokens} budget`}
          bar={{ pct: tokenPct, color: "bg-coral" }}
          accent="text-gray-900"
        />
      </div>

      {/* Active Experiments */}
      <section className="mb-7">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-[13px] font-bold text-gray-900">Active Experiments</h2>
        </div>
        {activeExperiments.length === 0 ? (
          <div className="glass-heavy flex flex-col items-center rounded-2xl p-10 text-center">
            <div className="mb-3 flex h-16 w-16 items-center justify-center rounded-full text-3xl glass">
              🧪
            </div>
            <div className="text-[15px] font-semibold text-gray-900">No experiments yet</div>
            <div className="mt-1 text-[12px] text-gray-500">Start your first experiment from the chat.</div>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {activeExperiments.map((e) => {
              const trust = trustScores[e.config?.channel as string] ?? 0;
              const phase = PHASE_COLORS[e.phase] ?? PHASE_COLORS.design;
              const tokenPctExp = e.token_budget > 0 ? (e.tokens_used / e.token_budget) * 100 : 0;
              return (
                <button
                  key={e.id}
                  onClick={() => onOpenExperiment(e.id)}
                  className="glass-heavy rounded-2xl p-[18px] text-left transition-all hover:-translate-y-0.5 hover:shadow-[0_8px_40px_rgba(0,0,0,0.08)]"
                >
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-[14px] font-semibold text-gray-900">{e.name}</span>
                    <span className={clsx("rounded-full px-3 py-[3px] text-[11px] font-semibold", phase.bg, phase.text)}>
                      {e.phase}
                    </span>
                  </div>
                  {e.hypothesis && (
                    <p className="mb-3 text-[12px] leading-relaxed text-gray-500 line-clamp-2">
                      {e.hypothesis}
                    </p>
                  )}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-[6px] text-[11px] font-medium text-gray-400">
                      <span className={clsx("h-[7px] w-[7px] rounded-full", phase.dot)} />
                      {trust.toFixed(2)}
                    </div>
                    <div className="h-1 w-20 overflow-hidden rounded-full bg-black/5">
                      <div
                        className="h-full rounded-full bg-coral transition-all"
                        style={{ width: `${Math.min(tokenPctExp, 100)}%` }}
                      />
                    </div>
                  </div>
                  <div className="mt-2 text-[10px] text-gray-400">
                    {e.tokens_used.toLocaleString()} / {e.token_budget.toLocaleString()} tokens
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </section>

      {/* Two columns: Trust + Proposals/Recent */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* Trust by Channel */}
        <div className="glass-heavy rounded-2xl p-[22px]">
          <h3 className="mb-4 text-[13px] font-bold text-gray-900">Trust by Channel</h3>
          {trustEntries.length === 0 ? (
            <p className="text-[12px] text-gray-400">No trust scores yet.</p>
          ) : (
            <div className="flex flex-wrap justify-center gap-5 py-2">
              {trustEntries.map(([channel, score]) => {
                const offset = ringCircumference * (1 - Math.min(score, 1));
                return (
                  <div key={channel} className="flex flex-col items-center gap-2">
                    <div className="relative h-16 w-16">
                      <svg viewBox="0 0 64 64" className="h-16 w-16 -rotate-90">
                        <circle cx="32" cy="32" r={ringRadius} fill="none" stroke="rgba(0,0,0,0.05)" strokeWidth="4.5" />
                        <circle
                          cx="32" cy="32" r={ringRadius}
                          fill="none"
                          stroke={trustRingColor(score)}
                          strokeWidth="4.5"
                          strokeLinecap="round"
                          strokeDasharray={ringCircumference}
                          strokeDashoffset={offset}
                          className="transition-all duration-700"
                        />
                      </svg>
                      <span
                        className="absolute inset-0 flex items-center justify-center text-[13px] font-bold"
                        style={{ color: trustRingColor(score) }}
                      >
                        {Math.round(score * 100)}
                      </span>
                    </div>
                    <span className="text-[10px] font-medium capitalize text-gray-500">{channel}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Recent completed + system overview */}
        <div className="glass-heavy rounded-2xl p-[22px]">
          <h3 className="mb-4 text-[13px] font-bold text-gray-900">Recent Experiments</h3>
          {experiments.filter((e) => e.phase === "complete").length === 0 ? (
            <p className="text-[12px] text-gray-400">No completed experiments yet.</p>
          ) : (
            <div className="space-y-2">
              {experiments
                .filter((e) => e.phase === "complete")
                .slice(0, 5)
                .map((e) => (
                  <button
                    key={e.id}
                    onClick={() => onOpenExperiment(e.id)}
                    className="flex w-full items-center gap-3 rounded-xl p-3 text-left transition glass-subtle hover:bg-white/40"
                  >
                    <div className="flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-lg bg-gray-400/10 text-[15px]">
                      ✓
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-[12px] font-semibold text-gray-900">{e.name}</div>
                      <div className="text-[11px] text-gray-400">Completed</div>
                    </div>
                  </button>
                ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({
  icon,
  iconBg,
  label,
  value,
  sub,
  bar,
  accent,
}: {
  icon: string;
  iconBg: string;
  label: string;
  value: string;
  sub?: string;
  bar?: { pct: number; color: string };
  accent: string;
}) {
  return (
    <div className="glass-heavy rounded-2xl p-5 transition-all hover:-translate-y-0.5 hover:shadow-[0_8px_40px_rgba(0,0,0,0.08)]">
      <div className="mb-[10px] flex items-center justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-[0.5px] text-gray-400">
          {label}
        </span>
        <div className={clsx("flex h-9 w-9 items-center justify-center rounded-xl text-[16px]", iconBg)}>
          {icon}
        </div>
      </div>
      <div className={clsx("text-[26px] font-bold tracking-tight", accent)}>{value}</div>
      {bar && (
        <div className="mt-[10px] h-[5px] overflow-hidden rounded-full bg-black/[0.04]">
          <div
            className={clsx("h-full rounded-full transition-all", bar.color)}
            style={{ width: `${Math.min(bar.pct, 100)}%` }}
          />
        </div>
      )}
      {sub && <div className="mt-1 text-[11px] text-gray-500">{sub}</div>}
    </div>
  );
}
