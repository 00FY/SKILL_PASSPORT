import React from 'react';
import { ShieldCheck, GitBranch, AlertTriangle, TrendingUp } from 'lucide-react';

interface MetricsRowProps {
  roleMatchPct: number;
  overallScore: number;
  authorshipPct?: number;
  refusalCount: number;
  activeMonths?: number;
  onSelectRefusals: () => void;
}

export const MetricsRow: React.FC<MetricsRowProps> = ({
  roleMatchPct,
  overallScore,
  authorshipPct = 91.2,
  refusalCount,
  activeMonths = 14,
  onSelectRefusals
}) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {/* Metric 1: Role Match Telemetry */}
      <div className="bg-[#101112] border border-[#1B1C1E] rounded p-4 card-inner-glow relative overflow-hidden flex flex-col justify-between">
        <div className="absolute top-4 right-4 w-2 h-2 rounded-full bg-[#50d8e9] beacon-cyan animate-beacon" />
        <div>
          <div className="text-[11px] font-mono uppercase tracking-widest text-[#9A9DA3] mb-1">
            Role Alignment Index
          </div>
          <div className="font-heading font-extrabold text-3xl sm:text-4xl text-[#e5e2e3] tracking-tighter">
            {roleMatchPct.toFixed(1)}%
          </div>
        </div>
        <div className="flex items-center justify-between text-xs font-mono text-[#9A9DA3] mt-3 pt-2.5 border-t border-[#1B1C1E]">
          <span className="text-[#50d8e9] flex items-center gap-1">
            <TrendingUp className="w-3.5 h-3.5" />
            <span>+9.0% potential via pytest</span>
          </span>
          <span>Score: {overallScore}/100</span>
        </div>
      </div>

      {/* Metric 2: Ground-Truth Line Authorship */}
      <div className="bg-[#101112] border border-[#1B1C1E] rounded p-4 card-inner-glow relative overflow-hidden flex flex-col justify-between">
        <div className="absolute top-4 right-4 w-2 h-2 rounded-full bg-[#50d8e9] beacon-cyan animate-beacon" />
        <div>
          <div className="text-[11px] font-mono uppercase tracking-widest text-[#9A9DA3] mb-1">
            Git Blame Authorship
          </div>
          <div className="font-heading font-extrabold text-3xl sm:text-4xl text-[#e5e2e3] tracking-tighter">
            {authorshipPct ? authorshipPct.toFixed(1) : '91.2'}%
          </div>
        </div>
        <div className="flex items-center justify-between text-xs font-mono text-[#9A9DA3] mt-3 pt-2.5 border-t border-[#1B1C1E]">
          <span className="text-[#bec2ff]">
            {activeMonths} months sustained history
          </span>
          <span className="text-[#9A9DA3]">0 template forks</span>
        </div>
      </div>

      {/* Metric 3: Refusal & Discrepancy Queue */}
      <div
        onClick={onSelectRefusals}
        className="bg-[#101112] border border-[#1B1C1E] hover:border-[#ffb4ab]/40 cursor-pointer rounded p-4 card-inner-glow relative overflow-hidden flex flex-col justify-between transition-all"
      >
        <div className={`absolute top-4 right-4 w-2 h-2 rounded-full ${
          refusalCount > 0 ? 'bg-[#ffb4ab] beacon-error animate-beacon' : 'bg-[#50d8e9] beacon-cyan'
        }`} />
        <div>
          <div className="text-[11px] font-mono uppercase tracking-widest text-[#9A9DA3] mb-1">
            Refusal & Incident Queue
          </div>
          <div className="font-heading font-extrabold text-3xl sm:text-4xl text-[#e5e2e3] tracking-tighter">
            {refusalCount} <span className="text-base font-normal text-[#9A9DA3]">Item{refusalCount === 1 ? '' : 's'}</span>
          </div>
        </div>
        <div className="flex items-center justify-between text-xs font-mono mt-3 pt-2.5 border-t border-[#1B1C1E]">
          <span className={refusalCount > 0 ? 'text-[#ffb4ab]' : 'text-[#50d8e9]'}>
            {refusalCount > 0 ? '1 Contradicted • 1 Claimed-Only' : '0 Anomalies Detected'}
          </span>
          <span className="text-[#c6c5d8] underline text-[11px]">Inspect →</span>
        </div>
      </div>
    </div>
  );
};
