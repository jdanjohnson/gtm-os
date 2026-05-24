import { useEffect, useState } from "react";
import type { Experiment } from "../lib/api";
import { listExperiments } from "../lib/api";

export default function AutomationsView() {
  const [experiments, setExperiments] = useState<Experiment[]>([]);

  useEffect(() => {
    listExperiments()
      .then(({ experiments }) =>
        setExperiments(experiments.filter((e) => e.schedule_id)),
      )
      .catch(() => null);
  }, []);

  return (
    <div className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Automations</h1>
      </div>

      {/* Filter tabs */}
      <div className="mb-4 flex gap-1">
        {["All", "Active", "Paused"].map((f) => (
          <button
            key={f}
            className="rounded-md px-3 py-1.5 text-xs text-[#A1A1AA] hover:bg-[#2A2A2A]/50 first:bg-[#2A2A2A] first:text-white"
          >
            {f}
          </button>
        ))}
      </div>

      {experiments.length === 0 ? (
        <p className="text-sm text-[#A1A1AA]">
          No scheduled automations yet. Schedule an experiment to create one.
        </p>
      ) : (
        <div className="space-y-3">
          {experiments.map((e) => (
            <div
              key={e.id}
              className="flex items-center justify-between rounded-xl border border-[#2A2A2A] bg-[#1A1A1A] px-4 py-3"
            >
              <div>
                <div className="font-medium text-sm">{e.name}</div>
                <div className="mt-0.5 text-xs text-[#A1A1AA]">
                  Schedule: {e.schedule_id}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="rounded bg-green-900/40 px-2 py-0.5 text-[10px] text-green-300">
                  Active
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
