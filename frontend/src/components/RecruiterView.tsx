import React from 'react';
import {
  CheckCircle2, AlertCircle, FileCode, GitBranch,
  ExternalLink, ShieldCheck, Hash, Eye, Sparkles, Terminal, Activity
} from 'lucide-react';
import { PassportDocument, SkillPassportItem } from '../data/mockData';
import { MetricsRow } from './MetricsRow';
import { TelemetryGraph } from './TelemetryGraph';
import { AuditFeed } from './AuditFeed';
import { RefusalPanel } from './RefusalPanel';

interface RecruiterViewProps {
  passport: PassportDocument;
  onSelectSkill: (skill: SkillPassportItem) => void;
  onVerifySignature: () => void;
  selectedTimeframe: string;
  onSelectRefusalsTab: () => void;
  activeTab?: 'overview' | 'telemetry' | 'refusals' | 'simulator';
  onSelectTab?: (tab: 'overview' | 'telemetry' | 'refusals' | 'simulator') => void;
}

export const RecruiterView: React.FC<RecruiterViewProps> = ({
  passport,
  onSelectSkill,
  onVerifySignature,
  selectedTimeframe,
  onSelectRefusalsTab,
  activeTab = 'overview',
  onSelectTab
}) => {
  const {
    candidate_name,
    applied_role,
    role_match_pct,
    overall_score,
    skills,
    refusal_panel,
    tamper_proof_hash,
    audit_log
  } = passport;

  const getVerdictBadge = (verdict: string) => {
    switch (verdict) {
      case 'VERIFIED':
        return (
          <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-[#50d8e9]/10 text-[#50d8e9] border border-[#50d8e9]/20 uppercase">
            VERIFIED
          </span>
        );
      case 'PARTIALLY_SUPPORTED':
        return (
          <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-[#ffb689]/10 text-[#ffb689] border border-[#ffb689]/20 uppercase">
            PARTIAL
          </span>
        );
      case 'CONTRADICTED':
        return (
          <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-[#93000a]/20 text-[#ffb4ab] border border-[#ffb4ab]/30 uppercase">
            CONTRADICTED
          </span>
        );
      default:
        return (
          <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-[#201f21] text-[#9A9DA3] border border-[#2a2a2b] uppercase">
            CLAIMED ONLY
          </span>
        );
    }
  };

  /* =========================================================================
     VIEW 1: TELEMETRY & BLAME (Dedicated View)
     ========================================================================= */
  if (activeTab === 'telemetry') {
    return (
      <div className="space-y-6 animate-fadeIn">
        {/* View Header */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-2 pb-2 border-b border-[#1B1C1E]">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#50d8e9]/10 text-[#50d8e9] border border-[#50d8e9]/20 uppercase">
                MODULE 2: CODE HARVESTER
              </span>
              <span className="text-[10px] font-mono text-[#9A9DA3]">LIVE TELEMETRY & GIT BLAME</span>
            </div>
            <h1 className="font-heading font-extrabold text-2xl sm:text-3xl text-[#e5e2e3] tracking-tighter">
              Telemetry & Git Blame Inspector
            </h1>
            <p className="font-sans text-xs sm:text-sm text-[#9A9DA3] mt-0.5">
              Ground-truth code telemetry and line-by-line Git author attribution for <strong className="text-[#e5e2e3]">{candidate_name}</strong>
            </p>
          </div>

          <button
            onClick={() => onSelectTab && onSelectTab('overview')}
            className="text-xs font-mono text-[#50d8e9] hover:underline flex items-center gap-1.5 self-start sm:self-auto"
          >
            ← Back to Command Center
          </button>
        </div>

        {/* 4 Stat Telemetry Tiles */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
          <div className="bg-[#101112] border border-[#1B1C1E] rounded p-3.5">
            <span className="text-[10px] font-mono uppercase text-[#9A9DA3]">Author Attribution</span>
            <div className="text-xl font-mono font-bold text-[#50d8e9] mt-0.5">
              {passport.candidate_authorship_pct ?? skills[0]?.authorship_pct ?? 0}%
            </div>
            <span className="text-[10px] font-mono text-[#9A9DA3]">Git blame verified lines</span>
          </div>

          <div className="bg-[#101112] border border-[#1B1C1E] rounded p-3.5">
            <span className="text-[10px] font-mono uppercase text-[#9A9DA3]">Total Analyzed Commits</span>
            <div className="text-xl font-mono font-bold text-[#bec2ff] mt-0.5">
              {passport.total_commits ?? 42}
            </div>
            <span className="text-[10px] font-mono text-[#9A9DA3]">Commit log depth</span>
          </div>

          <div className="bg-[#101112] border border-[#1B1C1E] rounded p-3.5">
            <span className="text-[10px] font-mono uppercase text-[#9A9DA3]">Active Timeline</span>
            <div className="text-xl font-mono font-bold text-[#e5e2e3] mt-0.5">
              {passport.active_months ?? 14} Months
            </div>
            <span className="text-[10px] font-mono text-[#9A9DA3]">Sustained development</span>
          </div>

          <div className="bg-[#101112] border border-[#1B1C1E] rounded p-3.5">
            <span className="text-[10px] font-mono uppercase text-[#9A9DA3]">Repository Status</span>
            <div className={`text-xl font-mono font-bold mt-0.5 ${passport.is_fork ? 'text-[#ffb4ab]' : 'text-[#50d8e9]'}`}>
              {passport.is_fork ? 'FORK DETECTED' : 'ORIGINAL REPO'}
            </div>
            <span className="text-[10px] font-mono text-[#9A9DA3]">Parent lineage check</span>
          </div>
        </div>

        {/* Full-width Telemetry Graph */}
        <div className="bg-[#101112] border border-[#1B1C1E] rounded overflow-hidden">
          <TelemetryGraph
            authorshipPct={passport.candidate_authorship_pct ?? skills[0]?.authorship_pct ?? 0}
            activeMonths={passport.active_months ?? 12}
            hasTests={skills.some(s => s.signals.some(sig => sig.toLowerCase().includes('pytest') || sig.toLowerCase().includes('test')))}
            timeframe={selectedTimeframe}
          />
        </div>

        {/* Interactive Git Blame Proof Cards */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-mono uppercase tracking-widest text-[#9A9DA3] flex items-center gap-2">
              <FileCode className="w-3.5 h-3.5 text-[#50d8e9]" />
              <span>Select Skill to Open Verified Git Blame Proof</span>
            </h2>
            <span className="text-[11px] font-mono text-[#50d8e9]">
              Click any card to open the Evidence Drawer
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
            {skills.map((skill, index) => (
              <div
                key={index}
                onClick={() => onSelectSkill(skill)}
                className="bg-[#101112] border border-[#1B1C1E] hover:border-[#50d8e9] romer-panel-hover rounded p-4 card-inner-glow cursor-pointer transition-all flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div>
                      <h3 className="font-heading font-bold text-base text-[#e5e2e3]">
                        {skill.name}
                      </h3>
                      <p className="text-[11px] font-mono text-[#9A9DA3]">
                        {skill.category.toUpperCase()} • {skill.level.toUpperCase()}
                      </p>
                    </div>
                    {getVerdictBadge(skill.verdict)}
                  </div>

                  <div className="p-2.5 rounded bg-[#151617] border border-[#1B1C1E] font-mono text-xs space-y-1 mb-2">
                    <div className="flex justify-between text-[#9A9DA3] text-[10px]">
                      <span>Git Authorship</span>
                      <strong className="text-[#50d8e9]">{skill.authorship_pct ?? 0}%</strong>
                    </div>
                    <div className="w-full bg-[#1c1b1d] rounded-full h-1 overflow-hidden">
                      <div
                        className="h-1 rounded-full bg-[#50d8e9]"
                        style={{ width: `${Math.min(100, skill.authorship_pct ?? 0)}%` }}
                      />
                    </div>
                  </div>

                  <div className="text-[11px] font-mono text-[#9A9DA3] line-clamp-2">
                    {skill.proof_snippet || "Verified through AST inspection and Git commit history."}
                  </div>
                </div>

                <div className="mt-3 pt-2.5 border-t border-[#1B1C1E] flex items-center justify-between text-[11px] font-mono text-[#50d8e9]">
                  <span>Click to view raw code & blame</span>
                  <Eye className="w-3.5 h-3.5" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  /* =========================================================================
     VIEW 2: REFUSAL QUEUE (Dedicated View)
     ========================================================================= */
  if (activeTab === 'refusals') {
    return (
      <div className="space-y-6 animate-fadeIn">
        {/* View Header */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-2 pb-2 border-b border-[#1B1C1E]">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#ffb4ab]/10 text-[#ffb4ab] border border-[#ffb4ab]/30 uppercase">
                MODULE 3: REFUSAL ENGINE
              </span>
              <span className="text-[10px] font-mono text-[#9A9DA3]">THE GOLDEN RULE IN ENFORCEMENT</span>
            </div>
            <h1 className="font-heading font-extrabold text-2xl sm:text-3xl text-[#e5e2e3] tracking-tighter">
              Refusal & Rejection Queue
            </h1>
            <p className="font-sans text-xs sm:text-sm text-[#9A9DA3] mt-0.5">
              Claims lacking verifiable git blame, failing AST validation, or flagged for prompt injection for <strong className="text-[#e5e2e3]">{candidate_name}</strong>
            </p>
          </div>

          <button
            onClick={() => onSelectTab && onSelectTab('overview')}
            className="text-xs font-mono text-[#50d8e9] hover:underline flex items-center gap-1.5 self-start sm:self-auto"
          >
            ← Back to Command Center
          </button>
        </div>

        {/* Refusal Queue Banner */}
        <div className="bg-[#151617] border border-[#ffb4ab]/20 rounded p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded bg-[#ffb4ab]/10 border border-[#ffb4ab]/30 flex items-center justify-center text-[#ffb4ab] shrink-0">
              <AlertCircle className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-heading font-bold text-sm text-[#e5e2e3]">
                Zero Silent Hallucinations Policy
              </h3>
              <p className="text-xs font-sans text-[#9A9DA3]">
                The LLM never invents grades. If an item cannot be traced to git blame, a passing test suite, or an interactive challenge, it is strictly placed in the Refusal Queue.
              </p>
            </div>
          </div>
          <span className="font-mono text-xs px-3 py-1 rounded bg-[#ffb4ab]/10 text-[#ffb4ab] border border-[#ffb4ab]/30 shrink-0 font-bold">
            {refusal_panel.length} REJECTED CLAIM{refusal_panel.length === 1 ? '' : 'S'}
          </span>
        </div>

        {/* Full-width Refusal Panel */}
        <RefusalPanel refusals={refusal_panel} />
      </div>
    );
  }

  /* =========================================================================
     VIEW 3: COMMAND CENTER (Default Executive Overview)
     ========================================================================= */
  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Page Header (Romer Title & Subtitle) */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-2 pb-2">
        <div>
          <h1 className="font-heading font-extrabold text-2xl sm:text-3xl text-[#e5e2e3] tracking-tighter">
            Executive Command Dashboard
          </h1>
          <p className="font-sans text-xs sm:text-sm text-[#9A9DA3] mt-0.5">
            Real-time code ground-truth audit for <strong className="text-[#e5e2e3] font-semibold">{candidate_name}</strong> ({applied_role})
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#101112] border border-[#1B1C1E] text-xs font-mono text-[#50d8e9]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#50d8e9] beacon-cyan"></span>
            <span>AUDIT SCORE: {overall_score}/100</span>
          </span>
        </div>
      </div>

      {/* Top 3 Metrics Row */}
      <MetricsRow
        roleMatchPct={role_match_pct}
        overallScore={overall_score}
        authorshipPct={passport.candidate_authorship_pct ?? skills[0]?.authorship_pct ?? 0}
        refusalCount={refusal_panel.length}
        activeMonths={passport.active_months ?? 12}
        totalCommits={passport.total_commits}
        isFork={passport.is_fork}
        onSelectRefusals={() => onSelectTab && onSelectTab('refusals')}
      />

      {/* Central Grid Area: Left (2 cols) Telemetry & Skills, Right (1 col) Audit Stream */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (Span 2) */}
        <div className="lg:col-span-2 space-y-6">
          {/* Live Telemetry Graph with header link to full telemetry */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono uppercase tracking-widest text-[#9A9DA3]">
                Telemetry Preview
              </span>
              <button
                onClick={() => onSelectTab && onSelectTab('telemetry')}
                className="text-[11px] font-mono text-[#50d8e9] hover:underline flex items-center gap-1"
              >
                <span>Full Telemetry & Blame</span>
                <span>→</span>
              </button>
            </div>
            <TelemetryGraph
              authorshipPct={passport.candidate_authorship_pct ?? skills[0]?.authorship_pct ?? 0}
              activeMonths={passport.active_months ?? 12}
              hasTests={skills.some(s => s.signals.some(sig => sig.toLowerCase().includes('pytest') || sig.toLowerCase().includes('test')))}
              timeframe={selectedTimeframe}
            />
          </div>

          {/* Competency Ground-Truth Signals */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono uppercase tracking-widest text-[#9A9DA3]">
                  Audited Competency Signals
                </span>
                <span className="text-[10px] font-mono text-[#5E6BFF] bg-[#5E6BFF]/10 px-1.5 py-0.2 rounded border border-[#5E6BFF]/20">
                  {skills.length} DETECTED
                </span>
              </div>
              <span className="text-[11px] font-mono text-[#9A9DA3] hidden sm:block">
                Click card to view Git Blame proof
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
              {skills.map((skill, index) => (
                <div
                  key={index}
                  onClick={() => onSelectSkill(skill)}
                  className="bg-[#101112] border border-[#1B1C1E] hover:border-[#5E6BFF] romer-panel-hover rounded p-4 card-inner-glow cursor-pointer flex flex-col justify-between transition-all"
                >
                  <div>
                    {/* Header */}
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div>
                        <h3 className="font-heading font-bold text-base text-[#e5e2e3]">
                          {skill.name}
                        </h3>
                        <p className="text-[11px] font-mono text-[#9A9DA3]">
                          {skill.category.toUpperCase()} • {skill.level.toUpperCase()}
                        </p>
                      </div>
                      {getVerdictBadge(skill.verdict)}
                    </div>

                    {/* Rubric Points & Grade Formula */}
                    <div className="flex items-center justify-between bg-[#151617] p-2 rounded border border-[#1B1C1E] mb-3 text-xs font-mono">
                      <div>
                        <span className="text-[#9A9DA3]">Points: </span>
                        <strong className="text-[#e5e2e3] font-bold">{skill.final_points}</strong>
                        <span className="text-[10px] text-[#9A9DA3]"> / 100</span>
                      </div>
                      <div className="text-[10px] text-[#50d8e9]">
                        Ev({skill.evidence_score}) × Gr({skill.test_grade})
                      </div>
                    </div>

                    {/* Authorship Bar */}
                    {skill.authorship_pct !== undefined && skill.authorship_pct !== null && (
                      <div className="space-y-1 mb-3">
                        <div className="flex justify-between text-[10px] font-mono">
                          <span className="text-[#9A9DA3]">Git Authorship</span>
                          <span className="font-bold text-[#50d8e9]">{skill.authorship_pct}%</span>
                        </div>
                        <div className="w-full bg-[#1c1b1d] rounded-full h-1 overflow-hidden">
                          <div
                            className={`h-1 rounded-full ${
                              skill.authorship_pct > 70 ? 'bg-[#50d8e9]' : skill.authorship_pct > 30 ? 'bg-[#ffb689]' : 'bg-[#ffb4ab]'
                            }`}
                            style={{ width: `${Math.min(100, skill.authorship_pct)}%` }}
                          />
                        </div>
                      </div>
                    )}

                    {/* Signals preview */}
                    <div className="space-y-1">
                      {skill.signals.slice(0, 2).map((sig, i) => (
                        <div key={i} className="flex items-center gap-1.5 text-[11px] font-mono text-[#c6c5d8] truncate">
                          <CheckCircle2 className="w-3 h-3 text-[#50d8e9] shrink-0" />
                          <span className="truncate">{sig}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Proof snippet tag */}
                  <div className="mt-3 pt-2.5 border-t border-[#1B1C1E] flex items-center justify-between text-[10px] font-mono">
                    <span className="text-[#50d8e9] truncate max-w-[180px]">
                      {skill.proof_snippet || "Repository trace valid"}
                    </span>
                    <span className="text-[#5E6BFF] hover:underline flex items-center gap-0.5">
                      <Eye className="w-3 h-3" />
                      <span>Inspect</span>
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column (Span 1) - Real-time Execution Feed */}
        <div className="lg:col-span-1">
          <AuditFeed auditLog={audit_log} candidateName={candidate_name} />
        </div>
      </div>

      {/* The Refusal Panel Preview */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-mono uppercase tracking-widest text-[#9A9DA3]">
            Refusal Queue Summary
          </span>
          <button
            onClick={() => onSelectTab && onSelectTab('refusals')}
            className="text-[11px] font-mono text-[#ffb4ab] hover:underline flex items-center gap-1"
          >
            <span>Open Dedicated Refusal Queue</span>
            <span>→</span>
          </button>
        </div>
        <RefusalPanel refusals={refusal_panel} />
      </div>
    </div>
  );
};
