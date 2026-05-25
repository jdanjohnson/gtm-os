import { useEffect, useState } from "react";
import { listMemory, searchMemory, type MemoryItem } from "../lib/api";

export default function MemoryBrowser() {
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<string | undefined>();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    listMemory(typeFilter)
      .then(({ memories: m }) => setMemories(m))
      .catch(() => null);
  }, [typeFilter]);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const { results } = await searchMemory(query, typeFilter);
      setMemories(results);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setQuery("");
    listMemory(typeFilter)
      .then(({ memories: m }) => setMemories(m))
      .catch(() => null);
  };

  return (
    <div className="p-7">
      <h1 className="mb-5 text-xl font-bold text-gray-900">Memory</h1>

      {/* Search bar */}
      <div className="mb-4 flex gap-2">
        <input
          type="text"
          placeholder="Search memories..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          className="flex-1 rounded-lg border border-black/[0.06] glass-heavy px-3 py-2 text-sm placeholder-gray-400 focus:border-coral/40 focus:outline-none"
        />
        <button
          onClick={handleSearch}
          disabled={loading}
          className="rounded-lg bg-coral px-4 py-2 text-sm hover:bg-coral-hover disabled:opacity-50"
        >
          {loading ? "..." : "Search"}
        </button>
        {query && (
          <button
            onClick={handleClear}
            className="rounded-lg bg-black/[0.04] px-3 py-2 text-sm text-gray-500 hover:bg-black/[0.06]"
          >
            Clear
          </button>
        )}
      </div>

      {/* Type filter */}
      <div className="mb-4 flex gap-1">
        {[undefined, "learning", "rule", "correction", "context"].map((t) => (
          <button
            key={t ?? "all"}
            onClick={() => setTypeFilter(t)}
            className={`rounded-md px-3 py-1.5 text-xs ${
              typeFilter === t
                ? "glass-heavy text-gray-900 font-semibold"
                : "text-gray-500 hover:bg-black/[0.04]"
            }`}
          >
            {t ? t.charAt(0).toUpperCase() + t.slice(1) : "All"}
          </button>
        ))}
      </div>

      {/* Results */}
      {memories.length === 0 ? (
        <p className="text-sm text-gray-500">
          No memories found. Memories are created automatically as agents run experiments.
        </p>
      ) : (
        <div className="space-y-3">
          {memories.map((m) => (
            <div
              key={m.id}
              className="glass-heavy rounded-2xl p-4"
            >
              <div className="mb-1.5 flex items-center gap-2">
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                    m.type === "rule"
                      ? "bg-blue-500/10 text-blue-600"
                      : m.type === "learning"
                        ? "bg-emerald-500/10 text-emerald-600"
                        : m.type === "correction"
                          ? "bg-orange-500/10 text-orange-600"
                          : "bg-gray-100 text-gray-500"
                  }`}
                >
                  {m.type}
                </span>
                <span className="text-[11px] text-gray-500">
                  Confidence: {m.confidence.toFixed(2)}
                </span>
                {m.similarity != null && (
                  <span className="text-[11px] text-gray-500">
                    · Similarity: {m.similarity.toFixed(3)}
                  </span>
                )}
              </div>
              <p className="text-sm">{m.content}</p>
              {m.experiment_id && (
                <div className="mt-2 text-[10px] text-gray-500">
                  Experiment: {m.experiment_id.slice(0, 8)}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
