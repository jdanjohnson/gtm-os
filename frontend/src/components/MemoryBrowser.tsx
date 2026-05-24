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
    <div className="p-6">
      <h1 className="mb-4 text-xl font-semibold">Memory</h1>

      {/* Search bar */}
      <div className="mb-4 flex gap-2">
        <input
          type="text"
          placeholder="Search memories..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          className="flex-1 rounded-lg border border-[#2A2A2A] bg-[#1A1A1A] px-3 py-2 text-sm placeholder-[#A1A1AA] focus:border-emerald-500 focus:outline-none"
        />
        <button
          onClick={handleSearch}
          disabled={loading}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm hover:bg-emerald-500 disabled:opacity-50"
        >
          {loading ? "..." : "Search"}
        </button>
        {query && (
          <button
            onClick={handleClear}
            className="rounded-lg bg-[#2A2A2A] px-3 py-2 text-sm text-[#A1A1AA] hover:bg-[#3A3A3A]"
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
                ? "bg-[#2A2A2A] text-white"
                : "text-[#A1A1AA] hover:bg-[#2A2A2A]/50"
            }`}
          >
            {t ? t.charAt(0).toUpperCase() + t.slice(1) : "All"}
          </button>
        ))}
      </div>

      {/* Results */}
      {memories.length === 0 ? (
        <p className="text-sm text-[#A1A1AA]">
          No memories found. Memories are created automatically as agents run experiments.
        </p>
      ) : (
        <div className="space-y-3">
          {memories.map((m) => (
            <div
              key={m.id}
              className="rounded-xl border border-[#2A2A2A] bg-[#1A1A1A] p-4"
            >
              <div className="mb-1.5 flex items-center gap-2">
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                    m.type === "rule"
                      ? "bg-blue-900/40 text-blue-300"
                      : m.type === "learning"
                        ? "bg-green-900/40 text-green-300"
                        : m.type === "correction"
                          ? "bg-orange-900/40 text-orange-300"
                          : "bg-gray-800 text-gray-300"
                  }`}
                >
                  {m.type}
                </span>
                <span className="text-[11px] text-[#A1A1AA]">
                  Confidence: {m.confidence.toFixed(2)}
                </span>
                {m.similarity != null && (
                  <span className="text-[11px] text-[#A1A1AA]">
                    · Similarity: {m.similarity.toFixed(3)}
                  </span>
                )}
              </div>
              <p className="text-sm">{m.content}</p>
              {m.experiment_id && (
                <div className="mt-2 text-[10px] text-[#A1A1AA]">
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
