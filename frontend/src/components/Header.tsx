import React from 'react';
import { ShieldCheck, Hash, Terminal, Sparkles, Activity } from 'lucide-react';

interface HeaderProps {
  candidateName: string;
  appliedRole: string;
  tamperProofHash: string;
  onVerifySignature: () => void;
  selectedTimeframe: string;
  onSelectTimeframe: (tf: string) => void;
  activeView: 'recruiter' | 'student';
}

export const Header: React.FC<HeaderProps> = ({
  candidateName,
  appliedRole,
  tamperProofHash,
  onVerifySignature,
  selectedTimeframe,
  onSelectTimeframe,
  activeView
}) => {
  return (
    <header className="border-b border-[#1B1C1E] bg-[#101112] px-6 py-3.5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 sticky top-0 z-30">
      {/* Breadcrumbs & Candidate Target */}
      <div className="flex items-center gap-2 text-xs font-mono">
        <span className="text-[#9A9DA3]">OPERATIONS</span>
        <span className="text-[#454655]">/</span>
        <span className="text-[#9A9DA3] uppercase tracking-wider">{activeView === 'recruiter' ? 'EXECUTIVE AUDIT' : 'STUDENT HUB'}</span>
        <span className="text-[#454655]">/</span>
        <span className="text-[#e5e2e3] font-bold tracking-tight">{candidateName.toUpperCase()}</span>
        <span className="hidden lg:inline-flex items-center gap-1 ml-2 text-[10px] font-mono text-[#50d8e9] bg-[#50d8e9]/10 px-2 py-0.5 rounded border border-[#50d8e9]/20">
          <Activity className="w-3 h-3 text-[#50d8e9]" />
          <span>ROLE: {appliedRole.toUpperCase()}</span>
        </span>
      </div>

      {/* Right Controls: Cryptographic SHA-256 seal & Time range filter */}
      <div className="flex items-center gap-3 w-full sm:w-auto justify-between sm:justify-end">
        {/* SHA-256 Seal Button */}
        <button
          onClick={onVerifySignature}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#0e0e0f] border border-[#232426] hover:border-[#5E6BFF] text-[11px] font-mono text-[#c6c5d8] hover:text-white transition-all shadow-inner"
          title="Inspect cryptographic proof"
        >
          <Hash className="w-3 h-3 text-[#50d8e9]" />
          <span className="truncate max-w-[120px] sm:max-w-[160px]">{tamperProofHash}</span>
          <span className="text-[9px] font-bold text-[#50d8e9] bg-[#50d8e9]/10 px-1 py-0.2 rounded">
            SEALED
          </span>
        </button>

        {/* Time Filters */}
        <div className="flex bg-[#070708] rounded p-[2px] border border-[#1B1C1E]">
          {['1H', '24H', '7D', 'ALL'].map((tf) => (
            <button
              key={tf}
              onClick={() => onSelectTimeframe(tf)}
              className={`px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider transition-all rounded ${
                selectedTimeframe === tf
                  ? 'bg-[#191A1C] text-[#e5e2e3] shadow-sm font-semibold'
                  : 'text-[#9A9DA3] hover:text-[#e5e2e3]'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>
    </header>
  );
};
