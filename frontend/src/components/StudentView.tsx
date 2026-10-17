import React, { useState } from 'react';
import {
  TrendingUp, ArrowRight, ShieldCheck, Share2, Eye, EyeOff,
  Sparkles, Check, Copy, Flame, Play, Terminal
} from 'lucide-react';
import confetti from 'canvas-confetti';
import { PassportDocument, LearningPlanItem } from '../data/mockData';

interface StudentViewProps {
  passport: PassportDocument;
  onSimulateScore: (toggles: Record<string, boolean>) => Promise<{ newRoleMatch: number; newOverall: number }>;
}

export const StudentView: React.FC<StudentViewProps> = ({
  passport,
  onSimulateScore
}) => {
  const { candidate_name, role_match_pct, overall_score, learning_plan } = passport;

  // What-If Simulator Toggles
  const [toggles, setToggles] = useState<Record<string, boolean>>({
    add_pytest: false,
    add_deploy: false,
    sustained_commits: false
  });

  const [simulatedRoleMatch, setSimulatedRoleMatch] = useState<number>(role_match_pct);
  const [simulatedOverall, setSimulatedOverall] = useState<number>(overall_score);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [copiedLink, setCopiedLink] = useState<boolean>(false);

  // Privacy toggles
  const [privacyToggles, setPrivacyToggles] = useState<Record<string, boolean>>({
    show_shopapi: true,
    show_coursera: true,
    show_blame_metrics: true
  });

  const handleToggle = async (key: string) => {
    const updated = { ...toggles, [key]: !toggles[key] };
    setToggles(updated);
    setIsSimulating(true);

    try {
      const res = await onSimulateScore(updated);
      setSimulatedRoleMatch(res.newRoleMatch);
      setSimulatedOverall(res.newOverall);

      if (res.newRoleMatch > role_match_pct) {
        // Trigger celebratory confetti
        confetti({
          particleCount: 80,
          spread: 70,
          origin: { y: 0.6 }
        });
      }
    } finally {
      setIsSimulating(false);
    }
  };

  const handleCopyShareLink = () => {
    const shareUrl = `${window.location.origin}?passport=${passport.tamper_proof_hash.replace('sha256:', '')}&expires=7d`;
    navigator.clipboard.writeText(shareUrl);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 3000);
  };

  const delta = simulatedRoleMatch - role_match_pct;

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Student Welcome & Simulator Hero */}
      <div className="glass-panel rounded-3xl p-6 sm:p-8 border border-white/10 relative overflow-hidden bg-gradient-to-r from-slate-900/90 via-slate-900/60 to-emerald-950/30">
        <div className="flex flex-col lg:flex-row items-center justify-between gap-8">
          <div className="space-y-3 text-center lg:text-left flex-1">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold">
              <Flame className="w-4 h-4 text-emerald-400" />
              <span>Student Growth & Skill Level-Up Hub</span>
            </div>
            <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
              Welcome, {candidate_name}
            </h1>
            <p className="text-sm text-slate-300 max-w-xl">
              Skill Passport shows you exactly what recruiters look for in code ground-truth.
              Use the <strong className="text-emerald-400">What-If Simulator</strong> to preview how your score jumps when you add tests or production deployments!
            </p>
          </div>

          {/* Interactive What-If Simulator Scorecard */}
          <div className="bg-[#0b0f19] p-6 rounded-2xl border border-white/10 shadow-2xl flex items-center gap-6 text-center">
            <div>
              <p className="text-xs uppercase tracking-wider text-slate-400 font-semibold mb-1">Current Match</p>
              <span className="text-3xl font-black text-slate-300">{role_match_pct}%</span>
            </div>
            <ArrowRight className="w-5 h-5 text-emerald-400" />
            <div className="relative">
              <p className="text-xs uppercase tracking-wider text-emerald-400 font-bold mb-1 flex items-center gap-1">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Simulated</span>
              </p>
              <div className="flex items-baseline gap-1.5 justify-center">
                <span className="text-4xl font-black text-emerald-400">{simulatedRoleMatch}%</span>
                {delta > 0 && (
                  <span className="text-xs font-bold text-emerald-300 bg-emerald-500/20 px-2 py-0.5 rounded-full border border-emerald-500/30">
                    +{delta}%
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* What-If Simulator Controls */}
      <div className="glass-panel rounded-2xl p-6 border border-emerald-500/20 bg-emerald-950/10 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-emerald-500/10">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center text-emerald-400">
              <TrendingUp className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white tracking-tight">Interactive What-If Simulator</h2>
              <p className="text-xs text-slate-400">Toggle planned engineering improvements to recalculate your passport live</p>
            </div>
          </div>
          <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/20 hidden sm:block">
            REAL-TIME RECALC
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
          {/* Toggle 1: Add pytest */}
          <div
            onClick={() => handleToggle('add_pytest')}
            className={`p-4 rounded-xl border cursor-pointer transition-all ${
              toggles.add_pytest
                ? 'bg-emerald-500/20 border-emerald-500/40 shadow-lg shadow-emerald-500/10'
                : 'bg-slate-900/60 border-white/10 hover:border-white/20'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-emerald-300 bg-emerald-500/20 px-2 py-0.5 rounded">
                +9% IMPACT
              </span>
              <input
                type="checkbox"
                checked={toggles.add_pytest}
                readOnly
                className="w-4 h-4 rounded text-emerald-500 focus:ring-emerald-500"
              />
            </div>
            <h4 className="font-semibold text-sm text-white mb-1">Add pytest test suite to ShopAPI</h4>
            <p className="text-xs text-slate-400">Adds unit tests and active assertions, resolving the Testing refusal.</p>
          </div>

          {/* Toggle 2: Add Live Deployment */}
          <div
            onClick={() => handleToggle('add_deploy')}
            className={`p-4 rounded-xl border cursor-pointer transition-all ${
              toggles.add_deploy
                ? 'bg-emerald-500/20 border-emerald-500/40 shadow-lg shadow-emerald-500/10'
                : 'bg-slate-900/60 border-white/10 hover:border-white/20'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-emerald-300 bg-emerald-500/20 px-2 py-0.5 rounded">
                +8% IMPACT
              </span>
              <input
                type="checkbox"
                checked={toggles.add_deploy}
                readOnly
                className="w-4 h-4 rounded text-emerald-500 focus:ring-emerald-500"
              />
            </div>
            <h4 className="font-semibold text-sm text-white mb-1">Deploy API on Render / Fly.io</h4>
            <p className="text-xs text-slate-400">Connects live deployed endpoint to trigger maximum Evidence Weight (10/10).</p>
          </div>

          {/* Toggle 3: Sustained Commits */}
          <div
            onClick={() => handleToggle('sustained_commits')}
            className={`p-4 rounded-xl border cursor-pointer transition-all ${
              toggles.sustained_commits
                ? 'bg-emerald-500/20 border-emerald-500/40 shadow-lg shadow-emerald-500/10'
                : 'bg-slate-900/60 border-white/10 hover:border-white/20'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-emerald-300 bg-emerald-500/20 px-2 py-0.5 rounded">
                +7% IMPACT
              </span>
              <input
                type="checkbox"
                checked={toggles.sustained_commits}
                readOnly
                className="w-4 h-4 rounded text-emerald-500 focus:ring-emerald-500"
              />
            </div>
            <h4 className="font-semibold text-sm text-white mb-1">Sustained Commit Timeline</h4>
            <p className="text-xs text-slate-400">Maintain continuous commit history across 3+ months with PR reviews.</p>
          </div>
        </div>
      </div>

      {/* Actionable Learning Plan */}
      <div className="space-y-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">Actionable Learning Plan</h2>
          <p className="text-xs text-slate-400">Specific engineering tasks generated directly from your code ground-truth audit</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {learning_plan.map((plan, idx) => (
            <div
              key={idx}
              className="glass-panel rounded-2xl p-5 border border-white/10 flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-teal-400 bg-teal-500/10 px-2.5 py-0.5 rounded border border-teal-500/20">
                    {plan.skill}
                  </span>
                  <span className="text-xs font-bold text-emerald-400 font-mono">
                    {plan.potential_impact}
                  </span>
                </div>
                <h3 className="font-semibold text-base text-white mt-2 mb-1">
                  {plan.action}
                </h3>
                {plan.repo_context && (
                  <p className="text-xs text-slate-400 font-mono flex items-center gap-1 mt-2">
                    <Terminal className="w-3.5 h-3.5 text-slate-500" />
                    <span>Target: {plan.repo_context}</span>
                  </p>
                )}
              </div>

              <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-between text-xs text-slate-400">
                <span>Verified Rubric Improvement</span>
                <span className="text-emerald-400 font-medium flex items-center gap-1">
                  Ready to Implement →
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Privacy Controls & Cryptographic Share Link */}
      <div className="glass-panel rounded-2xl p-6 border border-white/10 space-y-6">
        <div className="flex items-center justify-between pb-3 border-b border-white/10">
          <div>
            <h3 className="text-base font-bold text-white tracking-tight">Privacy & Credential Sharing Controls</h3>
            <p className="text-xs text-slate-400">You control exactly which repositories and certificates recruiters are allowed to inspect</p>
          </div>
          <span className="text-xs font-mono text-emerald-400 flex items-center gap-1">
            <ShieldCheck className="w-4 h-4" />
            <span>Zero-Trust Permissioned</span>
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="p-3 rounded-xl bg-slate-900/60 border border-white/5 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-white">Public Repositories</p>
              <p className="text-[11px] text-slate-400">api-service, shop-api</p>
            </div>
            <button
              onClick={() => setPrivacyToggles({ ...privacyToggles, show_shopapi: !privacyToggles.show_shopapi })}
              className={`p-2 rounded-lg transition-colors ${
                privacyToggles.show_shopapi ? 'text-emerald-400 bg-emerald-500/10' : 'text-slate-500 bg-slate-800'
              }`}
            >
              {privacyToggles.show_shopapi ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
            </button>
          </div>

          <div className="p-3 rounded-xl bg-slate-900/60 border border-white/5 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-white">Certifications</p>
              <p className="text-[11px] text-slate-400">Coursera, Docker Deep Dive</p>
            </div>
            <button
              onClick={() => setPrivacyToggles({ ...privacyToggles, show_coursera: !privacyToggles.show_coursera })}
              className={`p-2 rounded-lg transition-colors ${
                privacyToggles.show_coursera ? 'text-emerald-400 bg-emerald-500/10' : 'text-slate-500 bg-slate-800'
              }`}
            >
              {privacyToggles.show_coursera ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
            </button>
          </div>

          <div className="p-3 rounded-xl bg-slate-900/60 border border-white/5 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-white">Line-Level Blame Code</p>
              <p className="text-[11px] text-slate-400">Allow code snippet preview</p>
            </div>
            <button
              onClick={() => setPrivacyToggles({ ...privacyToggles, show_blame_metrics: !privacyToggles.show_blame_metrics })}
              className={`p-2 rounded-lg transition-colors ${
                privacyToggles.show_blame_metrics ? 'text-emerald-400 bg-emerald-500/10' : 'text-slate-500 bg-slate-800'
              }`}
            >
              {privacyToggles.show_blame_metrics ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Generate Signed 7-Day Share Link */}
        <div className="pt-2 flex flex-col sm:flex-row items-center justify-between gap-4 bg-slate-900/80 p-4 rounded-xl border border-white/5">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-teal-500/10 border border-teal-500/30 flex items-center justify-center text-teal-400">
              <Share2 className="w-4 h-4" />
            </div>
            <div>
              <p className="text-xs font-bold text-white">Signed 7-Day Recruiter Passport Link</p>
              <p className="text-[11px] text-slate-400">Tamper-proof cryptographic link. Recruiter receives verified status without exposing private keys.</p>
            </div>
          </div>

          <button
            onClick={handleCopyShareLink}
            className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold transition-all shadow-md shadow-emerald-600/20 shrink-0"
          >
            {copiedLink ? <Check className="w-3.5 h-3.5 text-white" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copiedLink ? 'Copied to Clipboard!' : 'Copy 7-Day Signed Link'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
