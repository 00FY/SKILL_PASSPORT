import React from 'react';
import {
  CheckCircle2, AlertCircle, FileCode, GitCommit,
  ExternalLink, ShieldCheck, Hash, Eye, Sparkles
} from 'lucide-react';
import { PassportDocument, SkillPassportItem } from '../data/mockData';
import { RefusalPanel } from './RefusalPanel';

interface RecruiterViewProps {
  passport: PassportDocument;
  onSelectSkill: (skill: SkillPassportItem) => void;
  onVerifySignature: () => void;
}

export const RecruiterView: React.FC<RecruiterViewProps> = ({
  passport,
  onSelectSkill,
  onVerifySignature
}) => {
  const { candidate_name, applied_role, role_match_pct, overall_score, skills, refusal_panel, tamper_proof_hash } = passport;

  // Circular gauge calculations
  const radius = 64;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (role_match_pct / 100) * circumference;

  const getVerdictStyle = (verdict: string) => {
    switch (verdict) {
      case 'VERIFIED':
        return {
          bg: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
          badgeText: 'VERIFIED',
          glow: 'hover:border-emerald-500/40'
        };
      case 'PARTIALLY_SUPPORTED':
        return {
          bg: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
          badgeText: 'PARTIAL EVIDENCE',
          glow: 'hover:border-amber-500/40'
        };
      case 'CONTRADICTED':
        return {
          bg: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
          badgeText: 'CONTRADICTED',
          glow: 'hover:border-rose-500/40'
        };
      default:
        return {
          bg: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
          badgeText: 'CLAIMED ONLY',
          glow: 'hover:border-slate-500/40'
        };
    }
  };

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Top Banner: Candidate Overview & Verification Metrics */}
      <div className="glass-panel rounded-3xl p-6 sm:p-8 border border-white/10 relative overflow-hidden">
        {/* Subtle background ambient glow */}
        <div className="absolute top-0 right-0 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-80 h-80 bg-teal-500/5 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col lg:flex-row items-center justify-between gap-8">
          {/* Candidate Info */}
          <div className="space-y-3 text-center lg:text-left flex-1">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold">
              <ShieldCheck className="w-4 h-4" />
              <span>Published Audit Rubric v2.1</span>
            </div>
            <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
              {candidate_name}
            </h1>
            <p className="text-base text-slate-300 font-medium">
              Applied Role: <span className="text-emerald-400 font-semibold">{applied_role}</span>
            </p>

            {/* Cryptographic SHA-256 Fingerprint */}
            <div className="pt-2 flex flex-wrap items-center justify-center lg:justify-start gap-2">
              <button
                onClick={onVerifySignature}
                className="group flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/90 border border-white/10 hover:border-emerald-500/40 transition-all text-xs font-mono text-slate-400 hover:text-slate-200"
                title="Click to verify cryptographic SHA-256 seal"
              >
                <Hash className="w-3.5 h-3.5 text-emerald-400 group-hover:rotate-12 transition-transform" />
                <span className="truncate max-w-[200px] sm:max-w-xs">{tamper_proof_hash}</span>
                <span className="text-[10px] text-emerald-400 font-sans font-bold bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">
                  VERIFIED SEAL
                </span>
              </button>
            </div>
          </div>

          {/* Verification Gauges */}
          <div className="flex items-center gap-8 bg-slate-900/60 p-5 rounded-2xl border border-white/5 shadow-inner">
            {/* Radial Role Match Gauge */}
            <div className="flex flex-col items-center">
              <div className="relative w-36 h-36 flex items-center justify-center">
                <svg className="w-full h-full transform -rotate-90">
                  <circle
                    cx="72"
                    cy="72"
                    r={radius}
                    stroke="currentColor"
                    strokeWidth="12"
                    className="text-slate-800"
                    fill="transparent"
                  />
                  <circle
                    cx="72"
                    cy="72"
                    r={radius}
                    stroke="currentColor"
                    strokeWidth="12"
                    className={`transition-all duration-1000 ease-out ${
                      role_match_pct >= 70 ? 'text-emerald-400' : role_match_pct >= 40 ? 'text-amber-400' : 'text-rose-400'
                    }`}
                    fill="transparent"
                    strokeDasharray={circumference}
                    strokeDashoffset={strokeDashoffset}
                    strokeLinecap="round"
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                  <span className="text-3xl font-black text-white tracking-tight">{role_match_pct}%</span>
                  <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Role Match</span>
                </div>
              </div>
            </div>

            {/* Overall Score Dial */}
            <div className="flex flex-col items-center text-center pl-6 border-l border-white/10">
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-tr from-slate-900 to-slate-800 border border-white/10 flex flex-col items-center justify-center shadow-lg">
                <span className="text-2xl font-black text-emerald-400">{overall_score}</span>
                <span className="text-[9px] uppercase font-bold text-slate-400">Points</span>
              </div>
              <span className="text-xs font-semibold text-slate-300 mt-2">Overall Score</span>
              <span className="text-[10px] text-slate-500">Max: 100</span>
            </div>
          </div>
        </div>
      </div>

      {/* Verified Skills Grid */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-white tracking-tight">Top Competencies & Evidence</h2>
            <p className="text-xs text-slate-400">Click any skill to launch the interactive Git Blame & AST Evidence Drawer</p>
          </div>
          <span className="text-xs text-emerald-400 font-medium hidden sm:flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Interactive Drawer Enabled</span>
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {skills.map((skill, index) => {
            const style = getVerdictStyle(skill.verdict);
            return (
              <div
                key={index}
                onClick={() => onSelectSkill(skill)}
                className={`glass-panel glass-panel-hover rounded-2xl p-5 border border-white/10 cursor-pointer flex flex-col justify-between ${style.glow}`}
              >
                <div>
                  {/* Skill Card Header */}
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <div>
                      <h3 className="font-bold text-base text-white group-hover:text-emerald-400 transition-colors">
                        {skill.name}
                      </h3>
                      <span className="text-[11px] text-slate-400 capitalize">
                        {skill.category} • {skill.level}
                      </span>
                    </div>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${style.bg}`}>
                      {style.badgeText}
                    </span>
                  </div>

                  {/* Rubric Points & Grade Formula */}
                  <div className="flex items-center justify-between bg-slate-900/60 p-2.5 rounded-xl border border-white/5 mb-3 text-xs">
                    <div>
                      <span className="text-slate-400">Score: </span>
                      <strong className="text-white">{skill.final_points} pts</strong>
                    </div>
                    <div className="text-[11px] font-mono text-emerald-400">
                      Ev: {skill.evidence_score} × Gr: {skill.test_grade}
                    </div>
                  </div>

                  {/* Authorship Bar if available */}
                  {skill.authorship_pct !== undefined && skill.authorship_pct !== null && (
                    <div className="space-y-1 mb-3">
                      <div className="flex justify-between text-[11px]">
                        <span className="text-slate-400">Git Authorship</span>
                        <span className="font-bold text-emerald-400 font-mono">{skill.authorship_pct}%</span>
                      </div>
                      <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="bg-emerald-500 h-1.5 rounded-full"
                          style={{ width: `${Math.min(100, skill.authorship_pct)}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Signals List Preview */}
                  <div className="space-y-1 text-xs text-slate-300">
                    {skill.signals.slice(0, 2).map((sig, i) => (
                      <div key={i} className="flex items-center gap-1.5 text-[11px] text-slate-300 truncate">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                        <span className="truncate">{sig}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Card Action Hint */}
                <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-between text-xs text-slate-400 group-hover:text-emerald-400">
                  <span className="font-mono text-[10px] text-teal-400 truncate max-w-[170px]">
                    {skill.proof_snippet || "Ground truth audit ready"}
                  </span>
                  <div className="flex items-center gap-1 text-emerald-400 font-medium">
                    <Eye className="w-3.5 h-3.5" />
                    <span>Inspect</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* The Refusal Panel */}
      <RefusalPanel refusals={refusal_panel} />
    </div>
  );
};
