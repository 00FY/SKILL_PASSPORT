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
  // Dynamically map percentage [0..100] to SVG Y coordinate [115..10]
  const pctToY = (pct: number) => {
    const clamped = Math.max(0, Math.min(100, pct));
    return Number((115 - (clamped / 100) * 105).toFixed(1));
  };

  const finalY = pctToY(authorshipPct);
  const mid3Y = pctToY(authorshipPct * 0.85);
  const mid2Y = pctToY(authorshipPct * 0.65);
  const mid1Y = pctToY(authorshipPct * 0.35);
  const startY = pctToY(authorshipPct * 0.15);

  // AST / Tests curve
  const astFinalPct = hasTests ? Math.min(95, authorshipPct * 0.9 + 10) : Math.max(15, authorshipPct * 0.4);
  const astFinalY = pctToY(astFinalPct);
  const astMid2Y = pctToY(astFinalPct * 0.6);
  const astMid1Y = pctToY(astFinalPct * 0.3);
  const astStartY = pctToY(astFinalPct * 0.1);

  // Dynamic timeline labels based on activeMonths
  const m1 = 1;
  const m2 = Math.max(2, Math.round(activeMonths * 0.3));
  const m3 = Math.max(3, Math.round(activeMonths * 0.6));
  const m4 = Math.max(4, Math.round(activeMonths * 0.85));
  const m5 = Math.max(5, activeMonths);

  const candidatePath = `M0,${startY} Q50,${(startY + mid1Y) / 2} 100,${mid1Y} T200,${mid2Y} T320,${mid3Y} T500,${finalY}`;
  const candidateArea = `M0,${startY} Q50,${(startY + mid1Y) / 2} 100,${mid1Y} T200,${mid2Y} T320,${mid3Y} T500,${finalY} L500,120 L0,120 Z`;
  const astPath = `M0,${astStartY} Q60,${(astStartY + astMid1Y) / 2} 120,${astMid1Y} T240,${astMid2Y} T360,${pctToY(astFinalPct * 0.75)} T500,${astFinalY}`;

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
              d={candidatePath}
              fill="none"
              stroke="#50d8e9"
              strokeWidth="2.5"
            />
            {/* Ambient Cyan Area under curve */}
            <path
              d={candidateArea}
              fill="url(#cyanGradient)"
              opacity="0.15"
            />

            {/* Line 2 (Violet): AST Validated Routes & Tests */}
            <path
              d={astPath}
              fill="none"
              stroke="#7a85ff"
              strokeWidth="2"
              strokeDasharray={hasTests ? "none" : "4 2"}
              opacity="0.85"
            />

            {/* Key Milestone Nodes */}
            <circle cx="100" cy={mid1Y} r="3.5" fill="#50d8e9" />
            <circle cx="200" cy={mid2Y} r="3.5" fill="#50d8e9" />
            <circle cx="320" cy={mid3Y} r="3.5" fill="#50d8e9" />
            <circle cx="500" cy={finalY} r="4.5" fill="#50d8e9" className="animate-pulse" />

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
          <span>Month {m1 < 10 ? `0${m1}` : m1} (Setup)</span>
          <span>Month {m2 < 10 ? `0${m2}` : m2} (Alpha)</span>
          <span>Month {m3 < 10 ? `0${m3}` : m3} (Features)</span>
          <span>Month {m4 < 10 ? `0${m4}` : m4} (Tests)</span>
          <span>Month {m5 < 10 ? `0${m5}` : m5} (Active)</span>
        </div>
      </div>
    </div>
  );
};
