import { useEffect, useState } from "react";
import type { MemoryItem } from "../lib/api";
import { listMemory } from "../lib/api";

export default function RulesView() {
  const [rules, setRules] = useState<MemoryItem[]>([]);
  const [filter, setFilter] = useState<"all" | "manual" | "auto">("all");

  useEffect(() => {
    listMemory("rule")
      .then(({ memories }) => setRules(memories))
      .catch(() => null);
  }, []);

  const filtered = rules.filter((r) => {
    if (filter === "all") return true;
    if (filter === "auto") return r.source !== "manual";
    return r.source === "manual";
  });

  return (
    <div className="p-7">
      <div className="mb-5 flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">Rules</h1>
      </div>

      {/* Filter tabs */}
      <div className="mb-4 flex gap-1">
        {(["all", "manual", "auto"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded-md px-3 py-1.5 text-xs ${
              filter === f
                ? "glass-heavy text-gray-900 font-semibold"
                : "text-gray-500 hover:bg-black/[0.04]"
            }`}
          >
            {f === "auto" ? "Auto-generated" : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <p className="text-sm text-gray-500">
          {rules.length === 0
            ? "No rules yet. Rules are auto-generated when learnings reach high confidence, or you can create them manually."
            : "No rules match the current filter."}
        </p>
      ) : (
        <div className="space-y-3">
          {filtered.map((rule) => (
            <div
              key={rule.id}
              className="glass-heavy rounded-2xl p-4"
            >
              <div className="mb-1 flex items-center gap-2">
                <span>{rule.source === "manual" ? "🔒" : "🤖"}</span>
                <span className="text-xs text-gray-500">
                  {rule.source === "manual" ? "Manual" : "Auto-generated"} · Confidence: {rule.confidence.toFixed(2)}
                </span>
              </div>
              <p className="text-sm">{rule.content}</p>
              {rule.experiment_id && (
                <div className="mt-2 text-[10px] text-gray-500">
                  Source: Experiment {rule.experiment_id.slice(0, 8)}
                </div>
              )}
              <div className="mt-2 flex gap-2">
                <button className="rounded bg-black/[0.04] px-2.5 py-1 text-xs text-gray-500 hover:bg-black/[0.06]">
                  Edit
                </button>
                {rule.source !== "manual" && (
                  <button className="rounded bg-black/[0.04] px-2.5 py-1 text-xs text-gray-500 hover:bg-black/[0.06]">
                    Demote to learning
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
