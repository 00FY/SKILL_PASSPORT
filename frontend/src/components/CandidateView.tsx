import React, { useEffect, useState } from 'react';
import { ArrowRight, Loader2 } from 'lucide-react';
import { PassportDocument } from '../lib/types';
import { postJson } from '../lib/api';

interface SimulationResult {
  new_role_match_pct: number;
  new_score: number;
}

const TOGGLES = [
  { key: 'add_pytest', title: 'Add tests', detail: 'Write tests for the code in your repositories.' },
  { key: 'add_deploy', title: 'Deploy it', detail: 'Add a live URL to the repository homepage, or get a pull request merged.' },
  { key: 'sustained_commits', title: 'Keep committing', detail: 'Build on your projects over at least 3 months.' },
] as const;

interface CandidateViewProps {
  passport: PassportDocument;
  onOpenPytest: () => void;
}

export const CandidateView: React.FC<CandidateViewProps> = ({ passport, onOpenPytest }) => {
  const [toggles, setToggles] = useState<Record<string, boolean>>({});
  const [impacts, setImpacts] = useState<Record<string, number>>({});
  const [simulated, setSimulated] = useState<SimulationResult | null>(null);
  const [busy, setBusy] = useState(false);

  const simulate = (t: Record<string, boolean>) =>
    postJson<SimulationResult>('/api/simulate', { base_passport: passport, toggles: t });

  // Each toggle's impact comes from the same backend formulas that issued the passport
  useEffect(() => {
    setToggles({}); setSimulated(null); setImpacts({});
    let cancelled = false;
    TOGGLES.forEach(({ key }) =>
      simulate({ [key]: true })
        .then(r => { if (!cancelled) setImpacts(prev => ({ ...prev, [key]: r.new_role_match_pct - passport.role_match_pct })); })
        .catch(() => undefined)
    );
    return () => { cancelled = true; };
  }, [passport]);

  const flip = async (key: string) => {
    const next = { ...toggles, [key]: !toggles[key] };
    setToggles(next);
    if (!Object.values(next).some(Boolean)) { setSimulated(null); return; }
    setBusy(true);
    try { setSimulated(await simulate(next)); } catch { setSimulated(null); } finally { setBusy(false); }
  };

  const hasTestingStep = passport.learning_plan.some(lp => /test|pytest/i.test(lp.skill));

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-white/10 bg-[#17181a] p-5">
        <h1 className="font-heading text-2xl font-bold">How {passport.candidate_name} can improve</h1>
        <p className="text-sm text-zinc-400">
          Current role match <strong className="text-zinc-200">{passport.role_match_pct}%</strong> · audit score {passport.overall_score}/100
        </p>
      </div>

      <section className="rounded-xl border border-white/10 bg-[#17181a]">
        <h2 className="border-b border-white/10 px-5 py-3 font-heading font-semibold">Next steps</h2>
        {passport.learning_plan.length === 0 ? (
          <p className="px-5 py-4 text-sm text-zinc-400">Nothing to improve: every claim is already backed by evidence.</p>
        ) : (
          <ol className="divide-y divide-white/5">
            {passport.learning_plan.map((lp, i) => (
              <li key={i} className="flex flex-wrap items-center gap-3 px-5 py-3 text-sm">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white/10 text-xs">{i + 1}</span>
                <span className="min-w-0 flex-1">{lp.action}</span>
                <span className="text-emerald-300">{lp.potential_impact}</span>
              </li>
            ))}
          </ol>
        )}
        {hasTestingStep && (
          <div className="border-t border-white/10 px-5 py-3">
            <button onClick={onOpenPytest} className="text-sm text-indigo-300 hover:underline">
              Get a starter pytest file →
            </button>
          </div>
        )}
      </section>

      <section className="rounded-xl border border-white/10 bg-[#17181a]">
        <h2 className="border-b border-white/10 px-5 py-3 font-heading font-semibold">What if…</h2>
        <div className="grid gap-3 p-5 sm:grid-cols-3">
          {TOGGLES.map(t => (
            <button
              key={t.key}
              onClick={() => flip(t.key)}
              className={`rounded-lg border p-4 text-left text-sm ${toggles[t.key] ? 'border-indigo-400 bg-indigo-500/10' : 'border-white/10 hover:bg-white/5'}`}
            >
              <div className="flex items-center justify-between">
                <span className="font-medium">{t.title}</span>
                <span className="text-emerald-300">{impacts[t.key] === undefined ? '…' : `+${impacts[t.key]}%`}</span>
              </div>
              <p className="mt-1 text-zinc-400">{t.detail}</p>
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 border-t border-white/10 px-5 py-3 text-sm">
          {busy ? <Loader2 className="h-4 w-4 animate-spin text-zinc-400" /> : simulated ? (
            <>
              Role match {passport.role_match_pct}% <ArrowRight className="h-4 w-4" />
              <strong className="text-emerald-300">{simulated.new_role_match_pct}%</strong>
              <span className="text-zinc-400">· audit score {passport.overall_score} → {simulated.new_score}</span>
            </>
          ) : <span className="text-zinc-400">Select changes to see their combined effect.</span>}
        </div>
      </section>
    </div>
  );
};
