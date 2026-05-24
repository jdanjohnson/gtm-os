import { useEffect, useState } from "react";
import type { PrimitivesSummary } from "../lib/api";

interface Props {
  primitives: PrimitivesSummary | null;
}

export default function PlaysLibrary({ primitives }: Props) {
  const plays = primitives?.plays ?? [];
  const [filter, setFilter] = useState("all");

  return (
    <div className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Play Library</h1>
      </div>

      {/* Filter tabs */}
      <div className="mb-4 flex gap-1">
        {["all", "email", "social", "seo"].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded-md px-3 py-1.5 text-xs ${
              filter === f
                ? "bg-[#2A2A2A] text-white"
                : "text-[#A1A1AA] hover:bg-[#2A2A2A]/50"
            }`}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {plays.length === 0 ? (
        <p className="text-sm text-[#A1A1AA]">
          No plays found. Add PLAY.md files to your primitives/plays/ directory.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {plays.map((play) => (
            <div
              key={play}
              className="rounded-xl border border-[#2A2A2A] bg-[#1A1A1A] p-4"
            >
              <div className="mb-2 flex items-center gap-2">
                <span>📋</span>
                <span className="font-medium text-sm">{play}</span>
              </div>
              <p className="mb-3 text-xs text-[#A1A1AA]">
                Playbook for {play} campaigns
              </p>
              <div className="flex gap-2">
                <button className="rounded bg-emerald-600 px-2.5 py-1 text-xs hover:bg-emerald-500">
                  Use Play
                </button>
                <button className="rounded bg-[#2A2A2A] px-2.5 py-1 text-xs text-[#A1A1AA] hover:bg-[#3A3A3A]">
                  Fork
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
