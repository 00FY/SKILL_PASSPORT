import React, { useState } from 'react';
import {
  TrendingUp, ArrowRight, ShieldCheck, Share2, Eye, EyeOff,
  Sparkles, Check, Copy, Terminal, Zap, Code
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

  const [toggles, setToggles] = useState<Record<string, boolean>>({
    add_pytest: false,
    add_deploy: false,
    sustained_commits: false
  });

  const [simulatedRoleMatch, setSimulatedRoleMatch] = useState<number>(role_match_pct);
  const [simulatedOverall, setSimulatedOverall] = useState<number>(overall_score);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [copiedLink, setCopiedLink] = useState<boolean>(false);

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
        confetti({
          particleCount: 70,
          spread: 60,
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
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-2 pb-2">
        <div>
          <h1 className="font-heading font-extrabold text-2xl sm:text-3xl text-[#e5e2e3] tracking-tighter">
            Student Growth & Simulation Hub
          </h1>
          <p className="font-sans text-xs sm:text-sm text-[#9A9DA3] mt-0.5">
            Real-time what-if simulator and verified learning roadmap for <strong className="text-[#e5e2e3] font-semibold">{candidate_name}</strong>
          </p>
        </div>

        {/* Live Simulation Ticker */}
        <div className="flex items-center gap-4 bg-[#101112] p-3 rounded border border-[#1B1C1E] card-inner-glow">
          <div className="text-right">
            <span className="text-[10px] font-mono uppercase text-[#9A9DA3] block">Current Match</span>
            <span className="font-heading font-bold text-xl text-[#9A9DA3]">{role_match_pct}%</span>
          </div>
          <ArrowRight className="w-4 h-4 text-[#50d8e9]" />
          <div>
            <span className="text-[10px] font-mono uppercase text-[#50d8e9] block">Simulated</span>
            <div className="flex items-baseline gap-1.5">
              <span className="font-heading font-extrabold text-2xl text-[#50d8e9]">{simulatedRoleMatch}%</span>
              {delta > 0 && (
                <span className="text-[10px] font-mono font-bold text-[#50d8e9] bg-[#50d8e9]/10 px-1 py-0.2 rounded border border-[#50d8e9]/20">
                  +{delta}%
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* What-If Simulator Canvas */}
      <div className="bg-[#101112] rounded border border-[#1B1C1E] p-5 card-inner-glow space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-[#1B1C1E]">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-[#5E6BFF]" />
            <h3 className="font-heading font-bold text-base text-[#e5e2e3]">
              What-If Simulation Engine
            </h3>
          </div>
          <span className="text-[10px] font-mono text-[#50d8e9] bg-[#50d8e9]/10 px-2 py-0.5 rounded border border-[#50d8e9]/20">
            LIVE RECALC
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
          {/* Toggle 1 */}
          <div
            onClick={() => handleToggle('add_pytest')}
            className={`p-4 rounded border cursor-pointer transition-all ${
              toggles.add_pytest
                ? 'bg-[#151617] border-[#50d8e9] shadow-md shadow-[#50d8e9]/5'
                : 'bg-[#151617] border-[#1B1C1E] hover:border-[#2a2a2b]'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono font-bold text-[#50d8e9] bg-[#50d8e9]/10 px-1.5 py-0.5 rounded">
                +9% IMPACT
              </span>
              <input
                type="checkbox"
                checked={toggles.add_pytest}
                readOnly
                className="w-4 h-4 rounded text-[#5E6BFF] focus:ring-0 bg-[#0e0e0f] border-[#2a2a2b]"
              />
            </div>
            <h4 className="font-heading font-bold text-sm text-[#e5e2e3] mb-1">Add pytest suite to ShopAPI</h4>
            <p className="text-xs text-[#9A9DA3]">Removes the testing refusal and satisfies test assertion requirements.</p>
          </div>

          {/* Toggle 2 */}
          <div
            onClick={() => handleToggle('add_deploy')}
            className={`p-4 rounded border cursor-pointer transition-all ${
              toggles.add_deploy
                ? 'bg-[#151617] border-[#50d8e9] shadow-md shadow-[#50d8e9]/5'
                : 'bg-[#151617] border-[#1B1C1E] hover:border-[#2a2a2b]'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono font-bold text-[#50d8e9] bg-[#50d8e9]/10 px-1.5 py-0.5 rounded">
                +8% IMPACT
              </span>
              <input
                type="checkbox"
                checked={toggles.add_deploy}
                readOnly
                className="w-4 h-4 rounded text-[#5E6BFF] focus:ring-0 bg-[#0e0e0f] border-[#2a2a2b]"
              />
            </div>
            <h4 className="font-heading font-bold text-sm text-[#e5e2e3] mb-1">Live Production Deployment</h4>
            <p className="text-xs text-[#9A9DA3]">Connect live service to qualify for 10/10 maximum Evidence Weight.</p>
          </div>

          {/* Toggle 3 */}
          <div
            onClick={() => handleToggle('sustained_commits')}
            className={`p-4 rounded border cursor-pointer transition-all ${
              toggles.sustained_commits
                ? 'bg-[#151617] border-[#50d8e9] shadow-md shadow-[#50d8e9]/5'
                : 'bg-[#151617] border-[#1B1C1E] hover:border-[#2a2a2b]'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono font-bold text-[#50d8e9] bg-[#50d8e9]/10 px-1.5 py-0.5 rounded">
                +7% IMPACT
              </span>
              <input
                type="checkbox"
                checked={toggles.sustained_commits}
                readOnly
                className="w-4 h-4 rounded text-[#5E6BFF] focus:ring-0 bg-[#0e0e0f] border-[#2a2a2b]"
              />
            </div>
            <h4 className="font-heading font-bold text-sm text-[#e5e2e3] mb-1">Continuous Commits & PRs</h4>
            <p className="text-xs text-[#9A9DA3]">Demonstrate collaborative pull request workflow across 3+ active months.</p>
          </div>
        </div>
      </div>

      {/* Actionable Learning Plan */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="text-xs font-mono uppercase tracking-widest text-[#9A9DA3]">
            Actionable Engineering Learning Plan
          </div>
          <span className="text-[10px] font-mono text-[#5E6BFF]">
            {learning_plan.length} ACTION ITEMS
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
          {learning_plan.map((plan, idx) => (
            <div
              key={idx}
              className="bg-[#101112] border border-[#1B1C1E] rounded p-4 card-inner-glow flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-mono font-bold text-[#50d8e9] bg-[#50d8e9]/10 px-2 py-0.5 rounded border border-[#50d8e9]/20 uppercase">
                    {plan.skill}
                  </span>
                  <span className="text-[11px] font-mono font-bold text-[#50d8e9]">
                    {plan.potential_impact}
                  </span>
                </div>
                <h3 className="font-heading font-bold text-sm text-[#e5e2e3] mt-2 mb-1">
                  {plan.action}
                </h3>
                {plan.repo_context && (
                  <p className="text-[11px] font-mono text-[#9A9DA3] flex items-center gap-1.5 mt-2">
                    <Terminal className="w-3 h-3 text-[#5E6BFF]" />
                    <span>Target: {plan.repo_context}</span>
                  </p>
                )}
              </div>

              <div className="mt-3 pt-2.5 border-t border-[#1B1C1E] flex items-center justify-between text-[11px] font-mono text-[#9A9DA3]">
                <span>Rubric Corroboration</span>
                <span className="text-[#50d8e9] hover:underline flex items-center gap-1">
                  Execute Action →
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Privacy Controls & 7-Day Signed Token */}
      <div className="bg-[#101112] rounded border border-[#1B1C1E] p-5 card-inner-glow space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-[#1B1C1E]">
          <div>
            <h3 className="font-heading font-bold text-base text-[#e5e2e3]">
              Zero-Trust Privacy & Sharing Token
            </h3>
            <p className="text-xs text-[#9A9DA3]">Choose which code repositories recruiters are granted permission to inspect</p>
          </div>
          <span className="text-[10px] font-mono text-[#50d8e9] bg-[#50d8e9]/10 px-2 py-0.5 rounded border border-[#50d8e9]/20">
            ZERO-TRUST
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="p-3 rounded bg-[#151617] border border-[#1B1C1E] flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-[#e5e2e3]">Public Repositories</p>
              <p className="text-[10px] font-mono text-[#9A9DA3]">api-service, shop-api</p>
            </div>
            <button
              onClick={() => setPrivacyToggles({ ...privacyToggles, show_shopapi: !privacyToggles.show_shopapi })}
              className={`p-1.5 rounded transition-colors ${
                privacyToggles.show_shopapi ? 'text-[#50d8e9] bg-[#50d8e9]/10' : 'text-[#9A9DA3] bg-[#0e0e0f]'
              }`}
            >
              {privacyToggles.show_shopapi ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            </button>
          </div>

          <div className="p-3 rounded bg-[#151617] border border-[#1B1C1E] flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-[#e5e2e3]">Certifications</p>
              <p className="text-[10px] font-mono text-[#9A9DA3]">Coursera, Docker Deep Dive</p>
            </div>
            <button
              onClick={() => setPrivacyToggles({ ...privacyToggles, show_coursera: !privacyToggles.show_coursera })}
              className={`p-1.5 rounded transition-colors ${
                privacyToggles.show_coursera ? 'text-[#50d8e9] bg-[#50d8e9]/10' : 'text-[#9A9DA3] bg-[#0e0e0f]'
              }`}
            >
              {privacyToggles.show_coursera ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            </button>
          </div>

          <div className="p-3 rounded bg-[#151617] border border-[#1B1C1E] flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-[#e5e2e3]">Line-Level Blame Code</p>
              <p className="text-[10px] font-mono text-[#9A9DA3]">Allow code snippet preview</p>
            </div>
            <button
              onClick={() => setPrivacyToggles({ ...privacyToggles, show_blame_metrics: !privacyToggles.show_blame_metrics })}
              className={`p-1.5 rounded transition-colors ${
                privacyToggles.show_blame_metrics ? 'text-[#50d8e9] bg-[#50d8e9]/10' : 'text-[#9A9DA3] bg-[#0e0e0f]'
              }`}
            >
              {privacyToggles.show_blame_metrics ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>

        {/* Generate Signed 7-Day Link */}
        <div className="pt-2 flex flex-col sm:flex-row items-center justify-between gap-3 bg-[#151617] p-3.5 rounded border border-[#1B1C1E]">
          <div>
            <p className="text-xs font-semibold text-[#e5e2e3]">Signed 7-Day Passport Verification Link</p>
            <p className="text-[11px] font-mono text-[#9A9DA3]">Cryptographically verified URL for external recruiters without leaking private keys.</p>
          </div>

          <button
            onClick={handleCopyShareLink}
            className="flex items-center gap-1.5 px-3.5 py-1.5 bg-[#5E6BFF] hover:bg-[#4d5bff] text-white rounded text-xs font-semibold transition-all shrink-0"
          >
            {copiedLink ? <Check className="w-3.5 h-3.5 text-white" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copiedLink ? 'Copied Token!' : 'Copy 7-Day Signed Link'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
