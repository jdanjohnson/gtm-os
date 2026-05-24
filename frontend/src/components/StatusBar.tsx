import clsx from "clsx";

interface Props {
  avgTrust: number;
  activeExperimentCount: number;
  memoryCount: number;
  model?: string;
}

function trustColor(score: number): string {
  if (score >= 0.7) return "text-green-400";
  if (score >= 0.5) return "text-yellow-400";
  if (score >= 0.3) return "text-orange-400";
  return "text-red-400";
}

function trustLabel(score: number): string {
  if (score >= 0.7) return "autonomous";
  if (score >= 0.5) return "new segments only";
  if (score >= 0.3) return "approve before execute";
  return "approve everything";
}

export default function StatusBar({ avgTrust, activeExperimentCount, memoryCount, model }: Props) {
  return (
    <footer className="flex items-center justify-between border-t border-[#2A2A2A] bg-[#1A1A1A] px-4 py-1.5 text-[11px] text-[#A1A1AA]">
      <div className="flex items-center gap-4">
        <span className={clsx("font-medium", trustColor(avgTrust))}>
          Trust: {avgTrust.toFixed(2)} — {trustLabel(avgTrust)}
        </span>
        <span>{activeExperimentCount} experiment{activeExperimentCount !== 1 ? "s" : ""} running</span>
        <span>{memoryCount} memories</span>
      </div>
      <div className="flex items-center gap-3">
        {model && <span className="font-mono text-[10px]">{model}</span>}
      </div>
    </footer>
  );
}
