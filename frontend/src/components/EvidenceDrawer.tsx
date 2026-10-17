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
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#50d8e9]/10 text-[#50d8e9] border border-[#50d8e9]/20 uppercase">VERIFIED</span>;
      case 'PARTIALLY_SUPPORTED':
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#ffb689]/10 text-[#ffb689] border border-[#ffb689]/20 uppercase">PARTIAL</span>;
      case 'CONTRADICTED':
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#93000a]/20 text-[#ffb4ab] border border-[#ffb4ab]/30 uppercase">CONTRADICTED</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#201f21] text-[#9A9DA3] border border-[#2a2a2b] uppercase">CLAIMED ONLY</span>;
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/75 backdrop-blur-sm transition-opacity">
      <div className="absolute inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-xl bg-[#101112] border-l border-[#1B1C1E] shadow-2xl flex flex-col h-full">
          {/* Header */}
          <div className="p-4 px-6 border-b border-[#1B1C1E] flex items-center justify-between bg-[#0e0e0f]">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded bg-[#1c1b1d] border border-[#2a2a2b] flex items-center justify-center text-[#50d8e9] font-mono font-bold text-sm">
                {skill.name.charAt(0)}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="font-heading font-bold text-lg text-[#e5e2e3] tracking-tight">{skill.name}</h2>
                  {getVerdictBadge(skill.verdict)}
                </div>
                <p className="text-[11px] font-mono text-[#9A9DA3]">
                  Ground-Truth Audit Node • {candidateName}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 text-[#9A9DA3] hover:text-[#e5e2e3] rounded hover:bg-[#1c1b1d] transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Drawer Body */}
          <div className="flex-1 overflow-y-auto p-5 space-y-5">
            {/* Rubric Points Breakdown */}
            <div className="bg-[#151617] rounded border border-[#1B1C1E] p-4 card-inner-glow">
              <div className="flex items-center justify-between mb-2.5">
                <span className="text-[10px] font-mono uppercase tracking-widest text-[#9A9DA3]">
                  Published Rubric Formula
                </span>
                <span className="text-[10px] font-mono text-[#50d8e9] bg-[#50d8e9]/10 px-2 py-0.5 rounded border border-[#50d8e9]/20">
                  Score = Ev (0–10) × Gr (2–10)
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2.5 text-center">
                <div className="bg-[#101112] p-2.5 rounded border border-[#1B1C1E]">
                  <p className="text-[10px] font-mono text-[#9A9DA3]">Evidence Weight</p>
                  <p className="font-heading font-extrabold text-xl text-[#e5e2e3] mt-0.5">{skill.evidence_score} <span className="text-[10px] text-[#9A9DA3]">/ 10</span></p>
                </div>
                <div className="bg-[#101112] p-2.5 rounded border border-[#1B1C1E]">
                  <p className="text-[10px] font-mono text-[#9A9DA3]">Quiz Grade</p>
                  <p className="font-heading font-extrabold text-xl text-[#50d8e9] mt-0.5">{skill.test_grade}</p>
                </div>
                <div className="bg-[#101112] p-2.5 rounded border border-[#5E6BFF]/30 bg-[#5E6BFF]/10">
                  <p className="text-[10px] font-mono text-[#bec2ff]">Final Points</p>
                  <p className="font-heading font-extrabold text-xl text-[#5E6BFF] mt-0.5">{skill.final_points} <span className="text-[10px] text-[#bec2ff]">/ 100</span></p>
                </div>
              </div>
              {skill.reasoning && (
                <p className="text-xs text-[#c6c5d8] mt-3 pt-2.5 border-t border-[#1B1C1E] flex items-start gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-[#50d8e9] shrink-0 mt-0.5" />
                  <span>{skill.reasoning}</span>
                </p>
              )}
            </div>

            {/* Git Blame Authorship Card */}
            {skill.authorship_pct !== undefined && skill.authorship_pct !== null && (
              <div className="bg-[#151617] rounded border border-[#1B1C1E] p-4 card-inner-glow space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <GitBranch className="w-3.5 h-3.5 text-[#50d8e9]" />
                    <span className="text-xs font-mono uppercase tracking-wider text-[#e5e2e3]">Git Blame Authorship</span>
                  </div>
                  <span className="text-xs font-mono font-bold text-[#50d8e9]">
                    {skill.authorship_pct}% Authored
                  </span>
                </div>
                <div className="w-full bg-[#101112] rounded-full h-1.5 overflow-hidden">
                  <div
                    className={`h-1.5 rounded-full ${
                      skill.authorship_pct > 70 ? 'bg-[#50d8e9]' : skill.authorship_pct > 30 ? 'bg-[#ffb689]' : 'bg-[#ffb4ab]'
                    }`}
                    style={{ width: `${Math.min(100, skill.authorship_pct)}%` }}
                  />
                </div>
                <p className="text-[11px] text-[#9A9DA3]">
                  Line-by-line commit authorship attribution calculated, excluding third-party vendors and locks.
                </p>
              </div>
            )}

            {/* File & Line Proof Snippet */}
            {skill.proof_snippet && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-[#9A9DA3]">
                    <FileCode className="w-3.5 h-3.5 text-[#50d8e9]" />
                    <span>Verifiable Proof Snippet</span>
                  </div>
                  <span className="text-[10px] font-mono text-[#50d8e9] bg-[#50d8e9]/10 px-2 py-0.5 rounded border border-[#50d8e9]/20">
                    {skill.proof_snippet}
                  </span>
                </div>
                {skill.sample_code ? (
                  <div className="bg-[#070708] border border-[#1B1C1E] rounded p-3 font-mono text-[11px] overflow-x-auto text-[#50d8e9]/90 leading-relaxed">
                    <pre>{skill.sample_code}</pre>
                  </div>
                ) : (
                  <div className="bg-[#070708] border border-[#1B1C1E] rounded p-3 text-xs text-[#9A9DA3]">
                    File reference verified in candidate repository: <code className="text-[#50d8e9]">{skill.proof_snippet}</code>
                  </div>
                )}
              </div>
            )}

            {/* Quality Signals */}
            <div className="space-y-2">
              <span className="text-[10px] font-mono uppercase tracking-widest text-[#9A9DA3]">
                AST & Verification Signals
              </span>
              <div className="space-y-1.5">
                {skill.signals.map((sig, idx) => (
                  <div key={idx} className="flex items-start gap-2 p-2 rounded bg-[#151617] border border-[#1B1C1E] text-xs text-[#c6c5d8]">
                    <CheckCircle className="w-3.5 h-3.5 text-[#50d8e9] shrink-0 mt-0.5" />
                    <span>{sig}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Micro-Trace Audit Log */}
            {auditLog && auditLog.traces.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-[#9A9DA3]">
                    <Terminal className="w-3.5 h-3.5 text-[#bec2ff]" />
                    <span>Execution Trace (run.json)</span>
                  </div>
                  <span className="text-[10px] font-mono text-[#9A9DA3]">{auditLog.audit_id}</span>
                </div>
                <div className="bg-[#070708] border border-[#1B1C1E] rounded p-3 font-mono text-[10px] space-y-1 max-h-40 overflow-y-auto">
                  {auditLog.traces.map((trace, i) => (
                    <div key={i} className="flex items-center justify-between text-[#9A9DA3] py-0.5 border-b border-[#1B1C1E] last:border-0">
                      <span className="text-[#50d8e9] font-bold">{trace.step}</span>
                      <span className="text-[#e5e2e3] truncate max-w-[150px]">{trace.rule_applied}</span>
                      <span className="text-[#bec2ff]">{trace.verdict_reached}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Footer Action */}
          <div className="p-3.5 px-5 border-t border-[#1B1C1E] bg-[#0e0e0f] flex items-center justify-between">
            <button
              onClick={() => onOpenQuiz(skill.name)}
              className="flex items-center gap-1.5 px-3.5 py-1.5 bg-[#5E6BFF] hover:bg-[#4d5bff] text-white text-xs font-semibold rounded transition-colors shadow-sm"
            >
              <Award className="w-3.5 h-3.5" />
              <span>Launch 15-Q Challenge</span>
            </button>
            <button
              onClick={onClose}
              className="px-3 py-1.5 text-xs font-mono text-[#9A9DA3] hover:text-white rounded hover:bg-[#1c1b1d] transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
