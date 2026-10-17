import React from 'react';
import { AlertOctagon, HelpCircle, ArrowRight, ShieldX, Info } from 'lucide-react';
import { RefusalItem } from '../data/mockData';

interface RefusalPanelProps {
  refusals: RefusalItem[];
}

export const RefusalPanel: React.FC<RefusalPanelProps> = ({ refusals }) => {
  if (!refusals || refusals.length === 0) {
    return (
      <div className="glass-panel rounded-2xl p-6 border border-emerald-500/20 bg-emerald-950/10">
        <div className="flex items-center gap-3 text-emerald-400">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center">
            ✓
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">All Claims Verifiable</h3>
            <p className="text-xs text-emerald-300/80">No contradictory or unsupported claims found in candidate submission.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="glass-panel rounded-2xl p-6 border border-rose-500/20 bg-rose-950/10 space-y-4">
      {/* Panel Header */}
      <div className="flex items-center justify-between pb-3 border-b border-rose-500/10">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-rose-500/20 flex items-center justify-center text-rose-400">
            <AlertOctagon className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-white tracking-tight">The Refusal Panel</h3>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">
                {refusals.length} Unsupported
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Claims we couldn't support against published verifiable ground truth
            </p>
          </div>
        </div>
        <span className="text-[11px] font-mono text-rose-400/80 bg-rose-500/10 px-2 py-1 rounded border border-rose-500/20 hidden sm:block">
          AUDIT_FAIL_SAFE
        </span>
      </div>

      {/* Refusal Items Grid */}
      <div className="space-y-3">
        {refusals.map((item, idx) => {
          const isContradicted = item.verdict === 'CONTRADICTED';
          return (
            <div
              key={idx}
              className={`p-4 rounded-xl border transition-all ${
                isContradicted
                  ? 'bg-rose-900/10 border-rose-500/20 hover:border-rose-500/40'
                  : 'bg-slate-900/40 border-slate-700/40 hover:border-slate-600'
              }`}
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
                <span className="font-semibold text-sm text-slate-200 flex items-center gap-2">
                  {isContradicted ? (
                    <ShieldX className="w-4 h-4 text-rose-400 shrink-0" />
                  ) : (
                    <HelpCircle className="w-4 h-4 text-slate-400 shrink-0" />
                  )}
                  <span>"{item.claim}"</span>
                </span>
                <span
                  className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider self-start sm:self-auto ${
                    isContradicted
                      ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                      : 'bg-slate-700/40 text-slate-300 border border-slate-600'
                  }`}
                >
                  {item.verdict.replace('_', ' ')}
                </span>
              </div>

              {/* Reason Explanation */}
              <p className="text-xs text-slate-300 leading-relaxed pl-6">
                <strong className="text-rose-300">Auditor Finding:</strong> {item.reason}
              </p>

              {/* Evidence Found details if any */}
              {item.evidence_found && (
                <p className="text-[11px] text-slate-400 pl-6 mt-1.5 font-mono">
                  Ground Truth: {item.evidence_found}
                </p>
              )}

              {/* Suggested Remedy */}
              {item.suggested_remedy && (
                <div className="mt-2.5 pt-2 pl-6 border-t border-white/5 flex items-center gap-1.5 text-xs text-teal-300/90">
                  <ArrowRight className="w-3.5 h-3.5 text-teal-400 shrink-0" />
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
