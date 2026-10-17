import React from 'react';
import { Activity, ShieldCheck, Terminal, Layers } from 'lucide-react';

interface TelemetryGraphProps {
  authorshipPct: number;
  activeMonths: number;
  hasTests: boolean;
  timeframe: string;
}

export const TelemetryGraph: React.FC<TelemetryGraphProps> = ({
  authorshipPct,
  activeMonths,
  hasTests,
  timeframe
}) => {
  return (
    <div className="bg-[#151617] border border-[#232426] rounded flex flex-col overflow-hidden relative">
      {/* Telemetry Header */}
      <div className="p-3 px-4 border-b border-[#1B1C1E] flex justify-between items-center bg-[#101112]">
        <div className="text-xs font-mono uppercase tracking-widest text-[#9A9DA3] flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 text-[#50d8e9]" />
          <span>Live Telemetry: Commit History & AST Syntactic Signals</span>
        </div>
        <div className="flex items-center gap-3 text-[11px] font-mono">
          <span className="flex items-center gap-1.5 text-[#50d8e9]">
            <span className="w-2 h-0.5 bg-[#50d8e9] inline-block"></span>
            <span>Candidate Lines ({authorshipPct}%)</span>
          </span>
          <span className="flex items-center gap-1.5 text-[#bec2ff]">
            <span className="w-2 h-0.5 bg-[#7a85ff] inline-block"></span>
            <span>AST Routes & Asserts</span>
          </span>
        </div>
      </div>

      {/* Grid Canvas */}
      <div className="flex-1 grid-bg p-5 relative min-h-[220px] flex flex-col justify-end">
        {/* Subtle radial glow */}
        <div
          className="absolute inset-0 opacity-25 pointer-events-none"
          style={{ background: 'radial-gradient(circle at 60% 40%, rgba(94, 107, 255, 0.25) 0%, transparent 70%)' }}
        />

        {/* Y Axis Labels */}
        <div className="absolute left-4 top-4 bottom-8 flex flex-col justify-between font-mono text-[10px] text-[#454655]">
          <span>100%</span>
          <span>75%</span>
          <span>50%</span>
          <span>25%</span>
          <span>0%</span>
        </div>

        {/* SVG Curves */}
        <div className="w-full h-36 relative ml-8 mr-2">
          <svg className="w-full h-full overflow-visible" preserveAspectRatio="none" viewBox="0 0 500 120">
            {/* Grid horizontal guidelines */}
            <line x1="0" y1="0" x2="500" y2="0" stroke="#1B1C1E" strokeWidth="1" strokeDasharray="4 4" />
            <line x1="0" y1="30" x2="500" y2="30" stroke="#1B1C1E" strokeWidth="1" strokeDasharray="4 4" />
            <line x1="0" y1="60" x2="500" y2="60" stroke="#1B1C1E" strokeWidth="1" strokeDasharray="4 4" />
            <line x1="0" y1="90" x2="500" y2="90" stroke="#1B1C1E" strokeWidth="1" strokeDasharray="4 4" />
            <line x1="0" y1="120" x2="500" y2="120" stroke="#1B1C1E" strokeWidth="1" />

            {/* Line 1 (Cyan): Candidate Code Authorship & Commits */}
            <path
              d="M0,95 Q50,85 100,75 T200,45 T320,30 T420,18 T500,12"
              fill="none"
              stroke="#50d8e9"
              strokeWidth="2.5"
            />
            {/* Ambient Cyan Area under curve */}
            <path
              d="M0,95 Q50,85 100,75 T200,45 T320,30 T420,18 T500,12 L500,120 L0,120 Z"
              fill="url(#cyanGradient)"
              opacity="0.15"
            />

            {/* Line 2 (Violet): AST Validated Routes & Tests */}
            <path
              d="M0,110 Q60,105 120,90 T240,65 T360,40 T440,32 T500,24"
              fill="none"
              stroke="#7a85ff"
              strokeWidth="2"
              strokeDasharray={hasTests ? "none" : "4 2"}
              opacity="0.85"
            />

            {/* Key Milestone Nodes */}
            <circle cx="100" cy="75" r="3.5" fill="#50d8e9" />
            <circle cx="200" cy="45" r="3.5" fill="#50d8e9" />
            <circle cx="320" cy="30" r="3.5" fill="#50d8e9" />
            <circle cx="500" cy="12" r="4.5" fill="#50d8e9" className="animate-pulse" />

            <defs>
              <linearGradient id="cyanGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#50d8e9" stopOpacity="0.8" />
                <stop offset="100%" stopColor="#50d8e9" stopOpacity="0" />
              </linearGradient>
            </defs>
          </svg>
        </div>

        {/* X Axis Timeline Labels */}
        <div className="w-full border-t border-[#1B1C1E] mt-2 pt-1.5 flex justify-between font-mono text-[10px] text-[#454655] pl-8 pr-2">
          <span>Month 01 (Initial Setup)</span>
          <span>Month 04 (Core API)</span>
          <span>Month 08 (Microservices)</span>
          <span>Month 12 (Pytest Suite)</span>
          <span>Month 14 (Deploy on Render)</span>
        </div>
      </div>
    </div>
  );
};
