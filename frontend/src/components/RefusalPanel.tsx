import React from 'react';
import { AlertOctagon, HelpCircle, ArrowRight, ShieldX, Info } from 'lucide-react';
import { RefusalItem } from '../data/mockData';

interface RefusalPanelProps {
  refusals: RefusalItem[];
}

export const RefusalPanel: React.FC<RefusalPanelProps> = ({ refusals }) => {
  if (!refusals || refusals.length === 0) {
    return (
      <div className="bg-[#101112] rounded border border-[#1B1C1E] p-4 card-inner-glow">
        <div className="flex items-center gap-3 text-[#50d8e9]">
          <div className="w-6 h-6 rounded bg-[#50d8e9]/10 flex items-center justify-center text-xs font-mono">
            ✓
          </div>
          <div>
            <h3 className="text-xs font-mono uppercase tracking-wider text-[#e5e2e3]">Zero Discrepancies Detected</h3>
            <p className="text-[11px] text-[#9A9DA3]">All candidate declarations corroborated against Git blame line authorship and unit tests.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div id="refusals-section" className="bg-[#101112] rounded border border-[#1B1C1E] p-5 card-inner-glow space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-[#1B1C1E]">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded bg-[#93000a]/20 border border-[#ffb4ab]/30 flex items-center justify-center text-[#ffb4ab]">
            <AlertOctagon className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-heading font-bold text-base text-[#e5e2e3] tracking-tight">
                The Refusal Queue: Claims Unsupported
              </h3>
              <span className="px-2 py-0.2 rounded text-[10px] font-mono font-bold bg-[#93000a]/20 text-[#ffb4ab] border border-[#ffb4ab]/30">
                {refusals.length} DISCREPANCIES
              </span>
            </div>
            <p className="text-xs text-[#9A9DA3] font-mono">
              Deterministic rubric rejection log based on code ground-truth audit
            </p>
          </div>
        </div>
        <span className="text-[10px] font-mono text-[#ffb4ab] bg-[#93000a]/10 px-2 py-0.5 rounded border border-[#ffb4ab]/20 hidden sm:block">
          FAIL_SAFE_AUDIT
        </span>
      </div>

      {/* Discrepancies Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
        {refusals.map((item, idx) => {
          const isContradicted = item.verdict === 'CONTRADICTED';
          return (
            <div
              key={idx}
              className={`p-3.5 rounded border transition-all ${
                isContradicted
                  ? 'bg-[#151617] border-[#ffb4ab]/30'
                  : 'bg-[#151617] border-[#1B1C1E]'
              }`}
            >
              <div className="flex items-start justify-between gap-2 mb-2">
                <span className="font-semibold text-xs text-[#e5e2e3] flex items-center gap-1.5">
                  {isContradicted ? (
                    <ShieldX className="w-3.5 h-3.5 text-[#ffb4ab] shrink-0" />
                  ) : (
                    <HelpCircle className="w-3.5 h-3.5 text-[#ffb689] shrink-0" />
                  )}
                  <span>"{item.claim}"</span>
                </span>
                <span
                  className={`text-[9px] font-mono font-bold px-1.5 py-0.2 rounded uppercase shrink-0 ${
                    isContradicted
                      ? 'bg-[#93000a]/30 text-[#ffb4ab] border border-[#ffb4ab]/30'
                      : 'bg-[#ffb689]/20 text-[#ffb689] border border-[#ffb689]/30'
                  }`}
                >
                  {item.verdict.replace('_', ' ')}
                </span>
              </div>

              {/* Finding */}
              <p className="text-xs text-[#c6c5d8] leading-relaxed">
                <strong className="text-[#e5e2e3]">Finding:</strong> {item.reason}
              </p>

              {/* Evidence found */}
              {item.evidence_found && (
                <div className="mt-2 p-2 rounded bg-[#0e0e0f] border border-[#1B1C1E] font-mono text-[10px] text-[#9A9DA3]">
                  <span className="text-[#50d8e9]">AUDIT_LOG:</span> {item.evidence_found}
                </div>
              )}

              {/* Suggested Remedy */}
              {item.suggested_remedy && (
                <div className="mt-2.5 pt-2 border-t border-[#1B1C1E] flex items-center gap-1.5 text-[11px] text-[#50d8e9]">
                  <ArrowRight className="w-3 h-3 text-[#50d8e9] shrink-0" />
                  <span><strong>Actionable Remedy:</strong> {item.suggested_remedy}</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
