import React from 'react';
import {
  X, GitBranch, GitCommit, ShieldCheck, Terminal,
  ExternalLink, FileCode, CheckCircle, Award, HelpCircle
} from 'lucide-react';
import { SkillPassportItem, RunAuditLog } from '../data/mockData';

interface EvidenceDrawerProps {
  skill: SkillPassportItem | null;
  candidateName: string;
  auditLog?: RunAuditLog;
  isOpen: boolean;
  onClose: () => void;
  onOpenQuiz: (skillName: string) => void;
}

export const EvidenceDrawer: React.FC<EvidenceDrawerProps> = ({
  skill,
  candidateName,
  auditLog,
  isOpen,
  onClose,
  onOpenQuiz
}) => {
  if (!isOpen || !skill) return null;

  const getVerdictBadge = (verdict: string) => {
    switch (verdict) {
      case 'VERIFIED':
        return <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">VERIFIED</span>;
      case 'PARTIALLY_SUPPORTED':
        return <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30">PARTIAL EVIDENCE</span>;
      case 'CONTRADICTED':
        return <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/30">CONTRADICTED</span>;
      default:
        return <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-500/10 text-slate-400 border border-slate-500/30">CLAIMED ONLY</span>;
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/60 backdrop-blur-sm transition-opacity">
      <div className="absolute inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-xl bg-[#0d111a] border-l border-white/10 shadow-2xl flex flex-col">
          {/* Header */}
          <div className="p-6 border-b border-white/10 flex items-center justify-between bg-slate-900/60">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold text-lg">
                {skill.name.charAt(0)}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-xl font-bold text-white tracking-tight">{skill.name}</h2>
                  {getVerdictBadge(skill.verdict)}
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Audited Ground-Truth Evidence for {candidateName}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-white/5 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Drawer Body */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* Rubric Points Breakdown */}
            <div className="glass-panel rounded-xl p-4 border border-white/10">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Published Rubric Formula
                </span>
                <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                  Score = Evidence (0–10) × Grade (2–10)
                </span>
              </div>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="bg-slate-900/80 p-2.5 rounded-lg border border-white/5">
                  <p className="text-xs text-slate-400">Evidence Weight</p>
                  <p className="text-xl font-bold text-white mt-1">{skill.evidence_score} <span className="text-xs text-slate-500">/ 10</span></p>
                </div>
                <div className="bg-slate-900/80 p-2.5 rounded-lg border border-white/5">
                  <p className="text-xs text-slate-400">Quiz Grade</p>
                  <p className="text-xl font-bold text-emerald-400 mt-1">{skill.test_grade}</p>
                </div>
                <div className="bg-slate-900/80 p-2.5 rounded-lg border border-emerald-500/20 bg-emerald-950/20">
                  <p className="text-xs text-emerald-300 font-medium">Final Points</p>
                  <p className="text-xl font-bold text-emerald-400 mt-1">{skill.final_points} <span className="text-xs text-emerald-500">/ 100</span></p>
                </div>
              </div>
              {skill.reasoning && (
                <p className="text-xs text-slate-300 mt-3 pt-3 border-t border-white/5 flex items-start gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  <span>{skill.reasoning}</span>
                </p>
              )}
            </div>

            {/* Git Blame Authorship Card */}
            {skill.authorship_pct !== undefined && skill.authorship_pct !== null && (
              <div className="glass-panel rounded-xl p-4 border border-white/10 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <GitBranch className="w-4 h-4 text-emerald-400" />
                    <span className="text-sm font-semibold text-white">Git Blame Authorship</span>
                  </div>
                  <span className="text-sm font-bold text-emerald-400 font-mono">
                    {skill.authorship_pct}% Authored
                  </span>
                </div>
                <div className="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden">
                  <div
                    className={`h-2.5 rounded-full transition-all duration-500 ${
                      skill.authorship_pct > 70 ? 'bg-emerald-500' : skill.authorship_pct > 40 ? 'bg-amber-500' : 'bg-rose-500'
                    }`}
                    style={{ width: `${Math.min(100, skill.authorship_pct)}%` }}
                  />
                </div>
                <p className="text-xs text-slate-400">
                  Verified by inspecting line-by-line commit authorship metadata, excluding vendor libraries and lockfiles.
                </p>
              </div>
            )}

            {/* File & Line Proof Snippet */}
            {skill.proof_snippet && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs font-semibold text-slate-300 uppercase tracking-wider">
                    <FileCode className="w-4 h-4 text-teal-400" />
                    <span>Verifiable Proof Snippet</span>
                  </div>
                  <span className="text-xs font-mono text-teal-300 bg-teal-500/10 px-2 py-0.5 rounded border border-teal-500/20">
                    {skill.proof_snippet}
                  </span>
                </div>
                {skill.sample_code ? (
                  <div className="bg-[#07090e] border border-white/10 rounded-xl p-3 font-mono text-xs overflow-x-auto text-emerald-300/90 leading-relaxed">
                    <pre>{skill.sample_code}</pre>
                  </div>
                ) : (
                  <div className="bg-[#07090e] border border-white/10 rounded-xl p-3 text-xs text-slate-400">
                    File reference verified in candidate repository: <code className="text-teal-400">{skill.proof_snippet}</code>
                  </div>
                )}
              </div>
            )}

            {/* Quality Signals */}
            <div className="space-y-2">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                AST & Verification Signals
              </span>
              <div className="space-y-2">
                {skill.signals.map((sig, idx) => (
                  <div key={idx} className="flex items-start gap-2.5 p-2.5 rounded-lg bg-slate-900/50 border border-white/5 text-xs text-slate-200">
                    <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                    <span>{sig}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* run.json Micro-Trace Audit Log */}
            {auditLog && auditLog.traces.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    <Terminal className="w-4 h-4 text-slate-400" />
                    <span>Execution Trace (run.json)</span>
                  </div>
                  <span className="text-[11px] font-mono text-slate-500">{auditLog.audit_id}</span>
                </div>
                <div className="bg-[#06080e] border border-white/10 rounded-xl p-3 font-mono text-[11px] space-y-1.5 max-h-48 overflow-y-auto">
                  {auditLog.traces.map((trace, i) => (
                    <div key={i} className="flex items-center justify-between text-slate-400 hover:text-slate-200 py-0.5 border-b border-white/5 last:border-0">
                      <span className="text-emerald-400 font-semibold">{trace.step}</span>
                      <span className="text-slate-300 truncate max-w-[140px]">{trace.rule_applied}</span>
                      <span className="text-teal-400 font-bold">{trace.verdict_reached}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Footer Action */}
          <div className="p-4 border-t border-white/10 bg-slate-900/80 flex items-center justify-between">
            <button
              onClick={() => onOpenQuiz(skill.name)}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium rounded-lg transition-colors shadow-lg shadow-emerald-600/20"
            >
              <Award className="w-4 h-4" />
              <span>Launch 15-Q Challenge Test</span>
            </button>
            <button
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-white rounded-lg hover:bg-white/5 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
