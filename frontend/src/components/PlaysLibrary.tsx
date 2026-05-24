import { useCallback, useMemo, useState } from "react";
import type { PlayMeta, PrimitivesSummary } from "../lib/api";

interface Props {
  primitives: PrimitivesSummary | null;
  onUsePlay?: (play: PlayMeta, mode: "use" | "fork") => void;
}

interface SavedPlay {
  id: string;
  playId: string;
  name: string;
  mode: "use" | "fork";
  usedAt: string;
}

const KIND_TABS = ["all", "playbook", "workflow", "skill", "tool"] as const;
type KindFilter = (typeof KIND_TABS)[number];
type ViewTab = "library" | "my-plays";

const KIND_ICONS: Record<string, string> = {
  playbook: "🎯",
  workflow: "🔄",
  skill: "⚡",
  tool: "🔧",
  play: "📋",
};

const KIND_COLORS: Record<string, string> = {
  playbook: "border-emerald-500/30 bg-emerald-500/5",
  workflow: "border-blue-500/30 bg-blue-500/5",
  skill: "border-purple-500/30 bg-purple-500/5",
  tool: "border-orange-500/30 bg-orange-500/5",
  play: "border-[#2A2A2A] bg-[#1A1A1A]",
};

const KIND_BADGE: Record<string, string> = {
  playbook: "bg-emerald-500/15 text-emerald-400",
  workflow: "bg-blue-500/15 text-blue-400",
  skill: "bg-purple-500/15 text-purple-400",
  tool: "bg-orange-500/15 text-orange-400",
  play: "bg-[#2A2A2A] text-[#A1A1AA]",
};

const STORAGE_KEY = "gtm-os-my-plays";

function loadSavedPlays(): SavedPlay[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function persistSavedPlays(plays: SavedPlay[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(plays));
}

export default function PlaysLibrary({ primitives, onUsePlay }: Props) {
  const plays: PlayMeta[] = primitives?.plays_meta ?? [];
  const [kindFilter, setKindFilter] = useState<KindFilter>("all");
  const [search, setSearch] = useState("");
  const [viewTab, setViewTab] = useState<ViewTab>("library");
  const [savedPlays, setSavedPlays] = useState<SavedPlay[]>(loadSavedPlays);
  const [namingPlay, setNamingPlay] = useState<{ play: PlayMeta; mode: "use" | "fork" } | null>(null);
  const [playName, setPlayName] = useState("");

  const filtered = useMemo(() => {
    let result = plays;
    if (kindFilter !== "all") {
      result = result.filter((p) => p.kind === kindFilter);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.description.toLowerCase().includes(q) ||
          p.tags.some((t) => t.toLowerCase().includes(q)) ||
          p.category.toLowerCase().includes(q),
      );
    }
    return result;
  }, [plays, kindFilter, search]);

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: plays.length };
    for (const p of plays) {
      c[p.kind] = (c[p.kind] || 0) + 1;
    }
    return c;
  }, [plays]);

  const handleUsePlay = useCallback(
    (play: PlayMeta, mode: "use" | "fork") => {
      setNamingPlay({ play, mode });
      setPlayName(play.name);
    },
    [],
  );

  const confirmUsePlay = useCallback(() => {
    if (!namingPlay) return;
    const newSaved: SavedPlay = {
      id: `sp-${Date.now()}`,
      playId: namingPlay.play.id,
      name: playName.trim() || namingPlay.play.name,
      mode: namingPlay.mode,
      usedAt: new Date().toISOString(),
    };
    const updated = [newSaved, ...savedPlays];
    setSavedPlays(updated);
    persistSavedPlays(updated);
    onUsePlay?.(namingPlay.play, namingPlay.mode);
    setNamingPlay(null);
    setPlayName("");
  }, [namingPlay, playName, savedPlays, onUsePlay]);

  const removeSavedPlay = useCallback(
    (id: string) => {
      const updated = savedPlays.filter((sp) => sp.id !== id);
      setSavedPlays(updated);
      persistSavedPlays(updated);
    },
    [savedPlays],
  );

  return (
    <div className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Plays</h1>
        <span className="text-xs text-[#A1A1AA]">
          {viewTab === "library"
            ? `${filtered.length} of ${plays.length} items`
            : `${savedPlays.length} saved`}
        </span>
      </div>

      {/* View tabs: Library / My Plays */}
      <div className="mb-4 flex gap-1 border-b border-[#2A2A2A]">
        <button
          onClick={() => setViewTab("library")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            viewTab === "library"
              ? "border-emerald-400 text-white"
              : "border-transparent text-[#A1A1AA] hover:text-white"
          }`}
        >
          Library
          <span className="ml-1.5 text-xs text-[#777]">({plays.length})</span>
        </button>
        <button
          onClick={() => setViewTab("my-plays")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            viewTab === "my-plays"
              ? "border-emerald-400 text-white"
              : "border-transparent text-[#A1A1AA] hover:text-white"
          }`}
        >
          My Plays
          <span className="ml-1.5 text-xs text-[#777]">({savedPlays.length})</span>
        </button>
      </div>

      {/* Naming modal */}
      {namingPlay && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="w-full max-w-md rounded-xl border border-[#2A2A2A] bg-[#1A1A1A] p-6 space-y-4">
            <h3 className="text-sm font-semibold">
              {namingPlay.mode === "use" ? "Use" : "Fork"}: {namingPlay.play.name}
            </h3>
            <p className="text-xs text-[#A1A1AA]">
              Give this play a name for your reference. It will appear in My Plays and start a chat to configure it.
            </p>
            <input
              type="text"
              value={playName}
              onChange={(e) => setPlayName(e.target.value)}
              placeholder="Name your play…"
              className="w-full rounded-lg border border-[#2A2A2A] bg-[#0F0F0F] px-3 py-2 text-sm text-white placeholder-[#555] focus:border-emerald-600 focus:outline-none"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === "Enter") confirmUsePlay();
              }}
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => { setNamingPlay(null); setPlayName(""); }}
                className="rounded-md px-3 py-1.5 text-xs text-[#A1A1AA] hover:bg-[#2A2A2A]"
              >
                Cancel
              </button>
              <button
                onClick={confirmUsePlay}
                className="rounded-md bg-emerald-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-emerald-500"
              >
                {namingPlay.mode === "use" ? "Start Play" : "Fork & Start"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Library tab */}
      {viewTab === "library" && (
        <>
          {/* Kind tabs */}
          <div className="mb-4 flex gap-1">
            {KIND_TABS.map((tab) => (
              <button
                key={tab}
                onClick={() => setKindFilter(tab)}
                className={`rounded-md px-3 py-1.5 text-xs transition-colors ${
                  kindFilter === tab
                    ? "bg-[#2A2A2A] text-white"
                    : "text-[#A1A1AA] hover:bg-[#2A2A2A]/50"
                }`}
              >
                {tab === "all" ? "All" : `${tab.charAt(0).toUpperCase() + tab.slice(1)}s`}
                <span className="ml-1.5 text-[10px] opacity-60">
                  {counts[tab] || 0}
                </span>
              </button>
            ))}
          </div>

          {/* Search */}
          <div className="mb-4">
            <input
              type="text"
              placeholder="Search plays..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-lg border border-[#2A2A2A] bg-[#1A1A1A] px-3 py-2 text-sm text-white placeholder-[#555] focus:border-[#3A3A3A] focus:outline-none"
            />
          </div>

          {filtered.length === 0 ? (
            <p className="text-sm text-[#A1A1AA]">
              {plays.length === 0
                ? "No plays found. Add PLAY.md files to your primitives/plays/ directory."
                : "No plays match your filter."}
            </p>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {filtered.map((play) => (
                <div
                  key={play.id}
                  className={`rounded-xl border p-4 transition-colors hover:border-[#3A3A3A] ${KIND_COLORS[play.kind] || KIND_COLORS.play}`}
                >
                  <div className="mb-2 flex items-center gap-2">
                    <span>{KIND_ICONS[play.kind] || "📋"}</span>
                    <span className="font-medium text-sm truncate flex-1">
                      {play.name}
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${KIND_BADGE[play.kind] || KIND_BADGE.play}`}
                    >
                      {play.kind}
                    </span>
                  </div>
                  <p className="mb-3 text-xs text-[#A1A1AA] line-clamp-2">
                    {play.description || `${play.kind} for ${play.id}`}
                  </p>
                  {play.tags.length > 0 && (
                    <div className="mb-3 flex flex-wrap gap-1">
                      {play.tags.slice(0, 4).map((tag) => (
                        <span
                          key={tag}
                          className="rounded bg-[#2A2A2A] px-1.5 py-0.5 text-[10px] text-[#A1A1AA]"
                        >
                          {tag}
                        </span>
                      ))}
                      {play.tags.length > 4 && (
                        <span className="text-[10px] text-[#555]">
                          +{play.tags.length - 4}
                        </span>
                      )}
                    </div>
                  )}
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleUsePlay(play, "use")}
                      className="rounded bg-emerald-600 px-2.5 py-1 text-xs hover:bg-emerald-500"
                    >
                      Use Play
                    </button>
                    <button
                      onClick={() => handleUsePlay(play, "fork")}
                      className="rounded bg-[#2A2A2A] px-2.5 py-1 text-xs text-[#A1A1AA] hover:bg-[#3A3A3A]"
                    >
                      Fork
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* My Plays tab */}
      {viewTab === "my-plays" && (
        <div>
          {savedPlays.length === 0 ? (
            <div className="rounded-lg border border-[#2A2A2A] bg-[#1A1A1A] p-8 text-center">
              <p className="text-sm text-[#A1A1AA]">
                No plays used yet. Browse the{" "}
                <button
                  onClick={() => setViewTab("library")}
                  className="text-emerald-400 hover:underline"
                >
                  Library
                </button>{" "}
                to use or fork a play.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {savedPlays.map((sp) => {
                const original = plays.find((p) => p.id === sp.playId);
                return (
                  <div
                    key={sp.id}
                    className="flex items-center justify-between rounded-lg border border-[#2A2A2A] bg-[#1A1A1A] px-4 py-3"
                  >
                    <div className="flex items-center gap-3">
                      <span>{original ? (KIND_ICONS[original.kind] || "📋") : "📋"}</span>
                      <div>
                        <div className="text-sm font-medium">{sp.name}</div>
                        <div className="text-[10px] text-[#777]">
                          {sp.mode === "fork" ? "Forked" : "Used"} from {sp.playId}
                          {" · "}
                          {new Date(sp.usedAt).toLocaleDateString()}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => {
                          if (original) onUsePlay?.(original, sp.mode);
                        }}
                        disabled={!original}
                        className="rounded px-2.5 py-1 text-xs bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-40"
                      >
                        Re-run
                      </button>
                      <button
                        onClick={() => removeSavedPlay(sp.id)}
                        className="rounded px-2 py-1 text-xs text-red-400 hover:bg-red-900/20 transition-colors"
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
