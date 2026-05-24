import type { PrimitivesSummary } from "../lib/api";

interface Props {
  primitives: PrimitivesSummary | null;
}

const AGENT_INFO: Record<string, { icon: string; role: string }> = {
  orchestrator: { icon: "🎯", role: "Coordinates experiment phases and delegates to specialists" },
  researcher: { icon: "🔍", role: "Finds prospects, researches markets, gathers intelligence" },
  copywriter: { icon: "✍️", role: "Drafts outbound sequences, email copy, LinkedIn messages" },
  analyst: { icon: "📊", role: "Measures results, compares hypotheses, synthesizes learnings" },
  operator: { icon: "⚡", role: "Executes sends via Composio integrations" },
};

export default function AgentsView({ primitives }: Props) {
  const agents = primitives?.agents ?? Object.keys(AGENT_INFO);

  return (
    <div className="p-6">
      <h1 className="mb-4 text-xl font-semibold">Agents</h1>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {agents.map((agent) => {
          const info = AGENT_INFO[agent] ?? { icon: "🤖", role: "Custom agent" };
          return (
            <div
              key={agent}
              className="rounded-xl border border-[#2A2A2A] bg-[#1A1A1A] p-4"
            >
              <div className="mb-2 flex items-center gap-2">
                <span className="text-lg">{info.icon}</span>
                <span className="font-medium capitalize">{agent}</span>
              </div>
              <p className="mb-3 text-xs text-[#A1A1AA]">{info.role}</p>
              <div className="flex gap-2">
                <button className="rounded bg-emerald-600 px-2.5 py-1 text-xs hover:bg-emerald-500">
                  Chat
                </button>
                <button className="rounded bg-[#2A2A2A] px-2.5 py-1 text-xs text-[#A1A1AA] hover:bg-[#3A3A3A]">
                  Edit persona
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
