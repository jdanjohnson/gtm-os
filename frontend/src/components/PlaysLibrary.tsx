import { useState } from "react";
import clsx from "clsx";
import {
  BookOpen,
  Mail,
  Link,
  Phone,
  Search,
  Globe,
  Users,
  ArrowRight,
  Tag,
  Layers,
} from "lucide-react";

import { PrimitivesSummary } from "../lib/api";

interface Props {
  primitives: PrimitivesSummary | null;
}

interface PlayInfo {
  id: string;
  name: string;
  description: string;
  channel: string;
  category: "b2b" | "local" | "other";
  tools: string[];
}

function inferPlayInfo(playId: string): PlayInfo {
  const name = playId.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  const channelMap: Record<string, string> = {
    "emailing": "email",
    "cold-calling": "cold-call",
    "prospecting": "search",
    "enriching": "enrichment",
    "seo": "seo",
    "kol-crm": "crm",
  };

  let channel = "general";
  for (const [key, val] of Object.entries(channelMap)) {
    if (playId.includes(key)) { channel = val; break; }
  }

  const category = playId.startsWith("b2b") ? "b2b" : playId.startsWith("local") ? "local" : "other";

  const descriptions: Record<string, string> = {
    "b2b-prospecting": "Discover and qualify B2B prospects using Apollo, LinkedIn, and web research",
    "b2b-emailing": "Multi-touch email sequences targeting B2B decision-makers with personalized messaging",
    "b2b-enriching": "Enrich prospect data with firmographics, technographics, and intent signals",
    "b2b-cold-calling": "Structured cold-call scripts with objection handling for B2B outreach",
    "local-prospecting": "Find local business opportunities through directories and review platforms",
    "local-emailing": "Personalized email outreach for local business partnerships",
    "local-enriching": "Enrich local business data with reviews, hours, and owner information",
    "local-cold-calling": "Local business cold-call scripts adapted for service-area targeting",
    "seo": "Content optimization and keyword targeting for organic search growth",
    "kol-crm": "Key Opinion Leader relationship management and influencer outreach",
  };

  const tools: string[] = [];
  if (channel === "email") tools.push("Gmail", "Mailgun");
  if (channel === "search" || channel === "enrichment") tools.push("Apollo", "Clearbit");
  if (playId.includes("linkedin") || playId.includes("prospecting")) tools.push("LinkedIn");
  if (channel === "seo") tools.push("Google Search Console", "Ahrefs");
  if (channel === "crm") tools.push("HubSpot", "Notion");
  if (tools.length === 0) tools.push("Composio");

  return {
    id: playId,
    name,
    description: descriptions[playId] ?? `GTM play: ${name}`,
    channel,
    category,
    tools,
  };
}

const CHANNEL_ICONS: Record<string, typeof Mail> = {
  email: Mail,
  "cold-call": Phone,
  search: Search,
  enrichment: Layers,
  seo: Globe,
  crm: Users,
  general: BookOpen,
};

export default function PlaysLibrary({ primitives }: Props) {
  const [filter, setFilter] = useState<"all" | "b2b" | "local" | "other">("all");
  const [searchQuery, setSearchQuery] = useState("");

  const plays = (primitives?.plays ?? []).map(inferPlayInfo);
  const filtered = plays.filter((p) => {
    if (filter !== "all" && p.category !== filter) return false;
    if (searchQuery.trim() && !p.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
            <BookOpen size={20} className="text-sky-400" />
            Play Library
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            {plays.length} plays available. Select one to use in an experiment.
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="search plays..."
            className="glass-input w-full pl-8 pr-3 py-2 text-sm text-slate-100"
          />
        </div>
        <div className="flex gap-1">
          {(["all", "b2b", "local", "other"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={clsx(
                "glass-pill border transition-all",
                filter === f
                  ? "text-emerald-300 border-emerald-500/30 bg-emerald-500/10"
                  : "text-slate-400 hover:text-slate-200",
              )}
            >
              {f === "all" ? "All" : f.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Card Grid */}
      <div className="grid grid-cols-2 gap-4">
        {filtered.map((play) => {
          const ChannelIcon = CHANNEL_ICONS[play.channel] ?? BookOpen;
          return (
            <div key={play.id} className="glass-card p-5 group">
              <div className="flex items-start justify-between mb-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-500/10 text-sky-400">
                  <ChannelIcon size={20} />
                </div>
                <span className={clsx(
                  "glass-pill border text-[10px]",
                  play.category === "b2b" ? "text-indigo-300 border-indigo-500/30" :
                  play.category === "local" ? "text-amber-300 border-amber-500/30" :
                  "text-slate-400"
                )}>
                  {play.category}
                </span>
              </div>

              <h3 className="text-sm font-medium text-slate-100 mb-1">{play.name}</h3>
              <p className="text-xs text-slate-400 mb-3 line-clamp-2">{play.description}</p>

              <div className="flex items-center gap-2 mb-3">
                <Tag size={10} className="text-slate-500" />
                <span className="glass-pill text-slate-500">{play.channel}</span>
              </div>

              <div className="flex flex-wrap gap-1 mb-4">
                {play.tools.map((t) => (
                  <span key={t} className="glass-pill text-slate-500 text-[10px]">{t}</span>
                ))}
              </div>

              <div className="flex gap-2">
                <button className="glass-btn flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs">
                  Use Play <ArrowRight size={12} />
                </button>
                <button className="glass-pill border text-slate-400 hover:text-slate-200 px-3 py-1.5 text-xs transition-colors">
                  Fork
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <div className="glass-card p-8 text-center">
          <BookOpen size={32} className="mx-auto mb-3 text-slate-600" />
          <p className="text-sm text-slate-400">No plays match your filter.</p>
        </div>
      )}
    </div>
  );
}
