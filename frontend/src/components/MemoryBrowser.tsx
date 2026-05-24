import { useCallback, useEffect, useState } from "react";

import { MemoryItem, listMemory, searchMemory } from "../lib/api";

const TYPES = ["all", "fact", "learning", "preference", "rule"] as const;

export default function MemoryBrowser() {
  const [items, setItems] = useState<MemoryItem[]>([]);
  const [type, setType] = useState<(typeof TYPES)[number]>("all");
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);

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
        <button
          onClick={load}
          className="rounded bg-emerald-600 px-3 py-1.5 text-sm hover:bg-emerald-500"
        >
          {searching ? "…" : "search"}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4">
        {items.length === 0 && (
          <div className="text-sm text-slate-500">No memories yet.</div>
        )}
        <ul className="space-y-3">
          {items.map((m) => (
            <li
              key={m.id}
              className="rounded-xl border border-slate-800 bg-slate-900/40 p-4"
            >
              <div className="mb-1 flex items-center gap-2 text-xs text-slate-400">
                <span className="rounded bg-slate-800 px-2 py-0.5 uppercase tracking-wider text-slate-300">
                  {m.type}
                </span>
                <span>confidence {m.confidence.toFixed(2)}</span>
                {typeof m.similarity === "number" && (
                  <span>· sim {m.similarity.toFixed(2)}</span>
                )}
                {m.source && <span>· {m.source}</span>}
                {m.experiment_id && (
                  <span>· exp {m.experiment_id.slice(0, 8)}…</span>
                )}
              </div>
              <div className="text-sm text-slate-100">{m.content}</div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
