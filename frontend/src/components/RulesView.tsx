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
    <div className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Rules</h1>
      </div>

      {/* Filter tabs */}
      <div className="mb-4 flex gap-1">
        {(["all", "manual", "auto"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded-md px-3 py-1.5 text-xs ${
              filter === f
                ? "bg-[#2A2A2A] text-white"
                : "text-[#A1A1AA] hover:bg-[#2A2A2A]/50"
            }`}
          >
            {f === "auto" ? "Auto-generated" : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <p className="text-sm text-[#A1A1AA]">
          {rules.length === 0
            ? "No rules yet. Rules are auto-generated when learnings reach high confidence, or you can create them manually."
            : "No rules match the current filter."}
        </p>
      ) : (
        <div className="space-y-3">
          {filtered.map((rule) => (
            <div
              key={rule.id}
              className="rounded-xl border border-[#2A2A2A] bg-[#1A1A1A] p-4"
            >
              <div className="mb-1 flex items-center gap-2">
                <span>{rule.source === "manual" ? "🔒" : "🤖"}</span>
                <span className="text-xs text-[#A1A1AA]">
                  {rule.source === "manual" ? "Manual" : "Auto-generated"} · Confidence: {rule.confidence.toFixed(2)}
                </span>
              </div>
              <p className="text-sm">{rule.content}</p>
              {rule.experiment_id && (
                <div className="mt-2 text-[10px] text-[#A1A1AA]">
                  Source: Experiment {rule.experiment_id.slice(0, 8)}
                </div>
              )}
              <div className="mt-2 flex gap-2">
                <button className="rounded bg-[#2A2A2A] px-2.5 py-1 text-xs text-[#A1A1AA] hover:bg-[#3A3A3A]">
                  Edit
                </button>
                {rule.source !== "manual" && (
                  <button className="rounded bg-[#2A2A2A] px-2.5 py-1 text-xs text-[#A1A1AA] hover:bg-[#3A3A3A]">
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
