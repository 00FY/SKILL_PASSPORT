import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { PassportDocument, RefusalItem, SkillPassportItem, Verdict } from '../lib/types';
import { VERDICT_ORDER } from '../lib/verdicts';
import { VerdictBadge } from './VerdictBadge';

export interface ClaimRow {
  name: string;
  verdict: Verdict;
  reason: string;
  points?: number;
  skill?: SkillPassportItem;
  refusal?: RefusalItem;
}

// Scored skills plus skills refused for lack of evidence (e.g. a testing claim with no tests)
export const claimRows = (p: PassportDocument): ClaimRow[] => [
  ...p.skills.map(s => ({
    name: s.name,
    verdict: s.verdict,
    reason: s.verdict === 'CONTRADICTED' ? 'See "Problems found" below' : s.signals[0] ?? '',
    points: s.final_points,
    skill: s,
  })),
  ...p.refusal_panel
    .filter(r => r.verdict === 'CLAIMED_ONLY')
    .map(r => ({ name: r.claim, verdict: r.verdict, reason: r.reason, refusal: r })),
].sort((a, b) => VERDICT_ORDER[a.verdict] - VERDICT_ORDER[b.verdict]);

// Contradictions that aren't a single skill: fake team claims, forks, commit dumps, inflated durations
export const problemRows = (p: PassportDocument): RefusalItem[] =>
  p.refusal_panel.filter(r => r.verdict === 'CONTRADICTED');

interface ClaimListProps {
  passport: PassportDocument;
  onOpenSkill: (skill: SkillPassportItem) => void;
}

export const ClaimList: React.FC<ClaimListProps> = ({ passport, onOpenSkill }) => {
  const rows = claimRows(passport);
  const problems = problemRows(passport);

  return (
    <section className="space-y-6">
      <div className="rounded-xl border border-white/10 bg-[#17181a]">
        <h2 className="border-b border-white/10 px-5 py-3 font-heading font-semibold">Claims from the resume</h2>
        {rows.length === 0 && <p className="px-5 py-4 text-sm text-zinc-400">No technical skills were found in the resume.</p>}
        <ul className="divide-y divide-white/5">
          {rows.map((row, i) => <ClaimRowItem key={`${row.name}-${i}`} row={row} onOpenSkill={onOpenSkill} />)}
        </ul>
      </div>

      {problems.length > 0 && (
        <div className="rounded-xl border border-red-400/30 bg-[#17181a]">
          <h2 className="border-b border-white/10 px-5 py-3 font-heading font-semibold text-red-200">Problems found</h2>
          <ul className="divide-y divide-white/5">
            {problems.map((p, i) => (
              <li key={i} className="space-y-1 px-5 py-4 text-sm">
                <p className="font-medium">"{p.claim}"</p>
                <p className="text-red-200/90">{p.reason}</p>
                {p.evidence_found && <p className="text-zinc-400">{p.evidence_found}</p>}
                {p.suggested_remedy && <p className="text-zinc-400"><span className="text-zinc-300">How to fix:</span> {p.suggested_remedy}</p>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
};

const ClaimRowItem: React.FC<{ row: ClaimRow; onOpenSkill: (s: SkillPassportItem) => void }> = ({ row, onOpenSkill }) => {
  const [open, setOpen] = useState(false);
  const clickable = !!row.skill || !!row.refusal;
  const onClick = () => (row.skill ? onOpenSkill(row.skill) : setOpen(o => !o));

  return (
    <li>
      <button
        onClick={onClick}
        disabled={!clickable}
        className="flex w-full items-center gap-4 px-5 py-3 text-left hover:bg-white/5"
      >
        <div className="min-w-0 flex-1">
          <div className="font-medium">{row.name}</div>
          <div className="truncate text-sm text-zinc-400">{row.reason}</div>
        </div>
        {row.skill?.test_grade && (
          <span className="hidden sm:inline-flex items-center rounded border border-indigo-500/30 bg-indigo-500/10 px-2 py-0.5 text-xs font-mono font-medium text-indigo-300">
            Grade {row.skill.test_grade}
          </span>
        )}
        {row.points !== undefined && <span className="hidden text-sm text-zinc-400 font-medium sm:inline">{row.points} pts</span>}
        <VerdictBadge verdict={row.verdict} />
        {row.skill
          ? <ChevronRight className="h-4 w-4 text-zinc-500" />
          : <ChevronDown className={`h-4 w-4 text-zinc-500 transition-transform ${open ? 'rotate-180' : ''}`} />}
      </button>
      {open && row.refusal && (
        <div className="space-y-1 px-5 pb-4 text-sm text-zinc-400">
          {row.refusal.evidence_found && <p>{row.refusal.evidence_found}</p>}
          {row.refusal.suggested_remedy && <p><span className="text-zinc-300">How to fix:</span> {row.refusal.suggested_remedy}</p>}
        </div>
      )}
    </li>
  );
};
