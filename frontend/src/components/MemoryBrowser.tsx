import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import {
  Brain,
  Search,
  Filter,
  ArrowUpDown,
  Sparkles,
  BookMarked,
  Lightbulb,
  Settings2,
  Scale,
  ArrowUpRight,
} from "lucide-react";

import { MemoryItem, listMemory, searchMemory } from "../lib/api";

const TYPES = ["all", "fact", "learning", "preference", "rule"] as const;

const TYPE_CONFIG: Record<string, { icon: typeof Brain; class: string }> = {
  fact: { icon: BookMarked, class: "text-sky-300 bg-sky-500/10 border-sky-500/20" },
  learning: { icon: Lightbulb, class: "text-purple-300 bg-purple-500/10 border-purple-500/20" },
  preference: { icon: Settings2, class: "text-amber-300 bg-amber-500/10 border-amber-500/20" },
  rule: { icon: Scale, class: "text-emerald-300 bg-emerald-500/10 border-emerald-500/20" },
};

function ConfidenceBar({ confidence }: { confidence: number }) {
  const pct = Math.min(100, confidence * 100);
  const color =
    confidence >= 0.8 ? "from-emerald-500 to-emerald-400" :
    confidence >= 0.5 ? "from-amber-500 to-amber-400" :
    "from-rose-500 to-rose-400";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-800/80">
        <div
          className={clsx("h-full rounded-full bg-gradient-to-r", color)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[10px] text-slate-500">{confidence.toFixed(2)}</span>
    </div>
  );
}

export default function MemoryBrowser() {
  const [items, setItems] = useState<MemoryItem[]>([]);
  const [type, setType] = useState<(typeof TYPES)[number]>("all");
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [sortBy, setSortBy] = useState<"confidence" | "date">("confidence");

  const load = useCallback(async () => {
    const tf = type === "all" ? undefined : type;
    if (query.trim()) {
      setSearching(true);
      try {
        const { results } = await searchMemory(query, tf);
        setItems(results);
      } finally {
        setSearching(false);
      }
    } else {
      const { memories } = await listMemory(tf);
      setItems(memories);
    }
  }, [type, query]);

  useEffect(() => {
    load();
  }, [load]);

  const sorted = [...items].sort((a, b) => {
    if (sortBy === "confidence") return b.confidence - a.confidence;
    return (b.created_at || "").localeCompare(a.created_at || "");
  });

  return (
    <div className="flex h-full w-full flex-col overflow-hidden animate-fade-in">
      {/* Search bar */}
      <div className="flex items-center gap-3 px-6 py-4 border-b border-white/[0.06]">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="search memory..."
            onKeyDown={(e) => e.key === "Enter" && load()}
            className="glass-input w-full pl-8 pr-3 py-2 text-sm text-slate-100"
          />
        </div>

        {/* Type filter */}
        <div className="flex gap-1">
          {TYPES.map((t) => (
            <button
              key={t}
              onClick={() => setType(t)}
              className={clsx(
                "glass-pill border transition-all text-[11px]",
                type === t
                  ? "text-emerald-300 border-emerald-500/30 bg-emerald-500/10"
                  : "text-slate-400 hover:text-slate-200",
              )}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Sort */}
        <button
          onClick={() => setSortBy(sortBy === "confidence" ? "date" : "confidence")}
          className="glass-pill border flex items-center gap-1 text-slate-400 hover:text-slate-200 transition-colors"
        >
          <ArrowUpDown size={10} />
          {sortBy === "confidence" ? "confidence" : "date"}
        </button>

        <button
          onClick={load}
          className="glass-btn px-3 py-1.5 text-xs"
        >
          {searching ? "..." : "Search"}
        </button>
      </div>

      {/* Stats bar */}
      <div className="flex items-center gap-4 px-6 py-2 border-b border-white/[0.06] text-[11px] text-slate-500">
        <span className="flex items-center gap-1">
          <Brain size={11} />
          {items.length} {items.length === 1 ? "memory" : "memories"}
          {query.trim() ? ` matching "${query}"` : ""}
        </span>
        <span className="flex items-center gap-1">
          <Sparkles size={11} />
          {items.filter((m) => m.confidence >= 0.8).length} high confidence
        </span>
      </div>

      {/* Memory list */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {items.length === 0 && (
          <div className="glass-card p-8 text-center">
            <Brain size={32} className="mx-auto mb-3 text-slate-600" />
            <p className="text-sm text-slate-400">No memories yet.</p>
            <p className="text-xs text-slate-500 mt-1">
              Run experiments to generate facts, learnings, and preferences.
            </p>
          </div>
        )}

        <div className="space-y-3">
          {sorted.map((m) => {
            const typeInfo = TYPE_CONFIG[m.type];
            const TypeIcon = typeInfo?.icon ?? Brain;
            return (
              <div
                key={m.id}
                className="glass-card p-4 group"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <div className={clsx(
                      "flex h-6 w-6 items-center justify-center rounded-lg border",
                      typeInfo?.class ?? "text-slate-400 bg-slate-500/10 border-slate-500/20",
                    )}>
                      <TypeIcon size={12} />
                    </div>
                    <span className={clsx(
                      "glass-pill border text-[10px] uppercase tracking-wider font-medium",
                      typeInfo?.class ?? "text-slate-400",
                    )}>
                      {m.type}
                    </span>
                    {typeof m.similarity === "number" && m.similarity > 0 && (
                      <span className="text-[10px] text-slate-500">
                        sim {m.similarity.toFixed(2)}
                      </span>
                    )}
                    {m.source && (
                      <span className="text-[10px] text-slate-600">{m.source}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <ConfidenceBar confidence={m.confidence} />
                    {m.confidence >= 0.8 && m.type === "learning" && (
                      <button className="glass-pill border text-[10px] text-emerald-300 border-emerald-500/20 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
                        <ArrowUpRight size={9} /> promote to rule
                      </button>
                    )}
                  </div>
                </div>

                <p className="text-sm text-slate-200">{m.content}</p>

                <div className="mt-2 flex items-center gap-3 text-[10px] text-slate-600">
                  {m.experiment_id && <span>exp: {m.experiment_id.slice(0, 8)}...</span>}
                  {m.reinforced_by && m.reinforced_by.length > 0 && (
                    <span>reinforced {m.reinforced_by.length}x</span>
                  )}
                  {m.created_at && <span>{new Date(m.created_at).toLocaleDateString()}</span>}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
