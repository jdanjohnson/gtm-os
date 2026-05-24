import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";

import { MemoryItem, listMemory, searchMemory } from "../lib/api";

const TYPES = ["all", "fact", "learning", "preference", "rule"] as const;

function ConfidenceBar({ confidence }: { confidence: number }) {
  const pct = Math.min(100, confidence * 100);
  const color =
    confidence >= 0.8
      ? "bg-emerald-500"
      : confidence >= 0.5
        ? "bg-amber-500"
        : "bg-rose-500";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-800">
        <div className={clsx("h-full rounded-full", color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] text-slate-400">{confidence.toFixed(2)}</span>
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
    <div className="flex h-full w-full flex-col overflow-hidden">
      <div className="flex items-center gap-2 border-b border-slate-800 px-6 py-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="search memory…"
          onKeyDown={(e) => e.key === "Enter" && load()}
          className="flex-1 rounded bg-slate-900 px-3 py-1.5 text-sm outline-none focus:ring-1 focus:ring-emerald-500"
        />
        <select
          value={type}
          onChange={(e) => setType(e.target.value as any)}
          className="rounded bg-slate-900 px-2 py-1.5 text-sm"
        >
          {TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as any)}
          className="rounded bg-slate-900 px-2 py-1.5 text-sm"
        >
          <option value="confidence">by confidence</option>
          <option value="date">by date</option>
        </select>
        <button
          onClick={load}
          className="rounded bg-emerald-600 px-3 py-1.5 text-sm hover:bg-emerald-500"
        >
          {searching ? "…" : "search"}
        </button>
      </div>

      <div className="border-b border-slate-800 px-6 py-2 text-xs text-slate-500">
        {items.length} {items.length === 1 ? "memory" : "memories"}
        {query.trim() ? ` matching "${query}"` : ""}
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4">
        {items.length === 0 && (
          <div className="text-sm text-slate-500">No memories yet.</div>
        )}
        <ul className="space-y-3">
          {sorted.map((m) => (
            <li
              key={m.id}
              className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 transition-colors hover:border-slate-700"
            >
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs text-slate-400">
                  <span
                    className={clsx(
                      "rounded px-2 py-0.5 uppercase tracking-wider text-xs font-medium",
                      m.type === "fact" && "bg-blue-900/50 text-blue-300",
                      m.type === "learning" && "bg-purple-900/50 text-purple-300",
                      m.type === "preference" && "bg-amber-900/50 text-amber-300",
                      m.type === "rule" && "bg-emerald-900/50 text-emerald-300",
                    )}
                  >
                    {m.type}
                  </span>
                  {typeof m.similarity === "number" && m.similarity > 0 && (
                    <span className="text-slate-500">sim {m.similarity.toFixed(2)}</span>
                  )}
                  {m.source && <span className="text-slate-500">· {m.source}</span>}
                </div>
                <ConfidenceBar confidence={m.confidence} />
              </div>
              <div className="text-sm text-slate-100">{m.content}</div>
              <div className="mt-2 flex items-center gap-3 text-[10px] text-slate-500">
                {m.experiment_id && <span>exp: {m.experiment_id.slice(0, 8)}…</span>}
                {m.reinforced_by && m.reinforced_by.length > 0 && (
                  <span>reinforced ×{m.reinforced_by.length}</span>
                )}
                {m.created_at && <span>{m.created_at}</span>}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
