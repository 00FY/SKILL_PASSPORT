import React from 'react';
import { Award, FileCode, ShieldCheck, X } from 'lucide-react';
import { RunAuditLog, SkillPassportItem } from '../lib/types';
import { VerdictBadge } from './VerdictBadge';
import { pointsFormula } from '../lib/verdicts';

interface EvidenceDrawerProps {
  skill: SkillPassportItem | null;
  auditLog?: RunAuditLog | null;
  onClose: () => void;
  onOpenQuiz: (skillName: string) => void;
  onOpenDefend: (skillName: string) => void;
}

export const EvidenceDrawer: React.FC<EvidenceDrawerProps> = ({ skill, auditLog, onClose, onOpenQuiz, onOpenDefend }) => {
  if (!skill) return null;
  const traces = auditLog?.traces.filter(t => t.target === skill.name) ?? [];

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/60" onClick={onClose}>
      <aside
        className="h-full w-full max-w-lg overflow-y-auto border-l border-white/10 bg-[#141516] p-6"
        onClick={e => e.stopPropagation()}
      >
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <h2 className="font-heading text-xl font-bold">{skill.name}</h2>
            <p className="text-sm capitalize text-zinc-400">{skill.category.replace('_', ' ')} · {skill.level}</p>
          </div>
          <button onClick={onClose} className="rounded p-1 text-zinc-400 hover:bg-white/10 hover:text-white" aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-6 text-sm">
          <div className="flex items-center gap-3">
            <VerdictBadge verdict={skill.verdict} />
            <span className="text-zinc-300">{skill.final_points} / 100 points</span>
          </div>

          <Section title="What we found">
            <ul className="list-disc space-y-1 pl-5 text-zinc-300">
              {skill.signals.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          </Section>

          <Section title="How the points were calculated">
            <p className="text-zinc-300">{pointsFormula(skill)}</p>
            {skill.reasoning && <p className="text-zinc-400">Evidence level: {skill.reasoning}</p>}
          </Section>

          {(skill.proof_snippet || skill.sample_code) && (
            <Section title="Code written by the candidate">
              {skill.proof_snippet && (
                <p className="flex items-center gap-1.5 text-zinc-400">
                  <FileCode className="h-4 w-4" />{skill.proof_snippet}
                </p>
              )}
              {skill.sample_code && (
                <pre className="mt-2 max-h-80 overflow-auto rounded-lg bg-black/40 p-3 font-mono text-xs leading-relaxed text-zinc-200">
                  {skill.sample_code}
                </pre>
              )}
            </Section>
          )}

          {traces.length > 0 && (
            <Section title="Rules applied">
              <ul className="space-y-1 text-xs text-zinc-400">
                {traces.map((t, i) => <li key={i}><span className="font-mono">{t.rule_applied}</span> → {t.verdict_reached}</li>)}
              </ul>
            </Section>
          )}

          <div className={`rounded-xl border p-4 ${
            skill.signals.some(s => s.toLowerCase().includes('quiz pending'))
              ? 'border-amber-500/40 bg-amber-500/10'
              : 'border-indigo-500/30 bg-indigo-500/10'
          }`}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-semibold text-zinc-100 flex items-center gap-1.5">
                  <Award className="h-4 w-4 text-indigo-400" /> Skill Test Challenge
                  {skill.signals.some(s => s.toLowerCase().includes('quiz pending')) && (
                    <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-bold text-amber-300">
                      MANDATORY PENDING
                    </span>
                  )}
                </p>
                <p className="text-xs text-zinc-400 mt-0.5">
                  {skill.test_grade && !skill.signals.some(s => s.toLowerCase().includes('quiz pending')) ? (
                    <>Verified Grade: <strong className="text-emerald-300">Grade {skill.test_grade}</strong> · Evidence: <strong className="text-zinc-200">{skill.evidence_score}/10</strong></>
                  ) : (
                    <>Complete mandatory challenge to verify this skill and upgrade from <strong className="text-amber-300">Grade E</strong>.</>
                  )}
                </p>
              </div>
              <button
                id="take-test-btn"
                onClick={() => onOpenQuiz(skill.name)}
                className={`flex shrink-0 items-center gap-1.5 rounded-lg px-3.5 py-2 text-xs font-semibold text-white shadow-sm transition-colors ${
                  skill.signals.some(s => s.toLowerCase().includes('quiz pending'))
                    ? 'bg-amber-600 hover:bg-amber-500 shadow-amber-600/20'
                    : 'bg-indigo-600 hover:bg-indigo-500 shadow-indigo-600/20'
                }`}
              >
                <Award className="h-4 w-4" />
                {skill.signals.some(s => s.toLowerCase().includes('quiz pending'))
                  ? `Take ${skill.name} Quiz Now`
                  : `Retake ${skill.name} Test`}
              </button>
            </div>
          </div>

          <DefendCard skill={skill} onOpen={() => onOpenDefend(skill.name)} />
        </div>
      </aside>
    </div>
  );
};

/** Optional "Defend Your Code" test: shown only where the analysis found the candidate's own functions. */
const DefendCard: React.FC<{ skill: SkillPassportItem; onOpen: () => void }> = ({ skill, onOpen }) => {
  const check = skill.authorship_check;
  if (!check) return null;
  const done = check.status === 'confirmed' || check.status === 'inconclusive' || check.status === 'not_explained';
  const tone = check.status === 'confirmed'
    ? 'border-emerald-500/30 bg-emerald-500/10'
    : check.status === 'not_explained' ? 'border-red-500/30 bg-red-500/10' : 'border-white/10 bg-white/[0.03]';

  return (
    <div className={`rounded-xl border p-4 ${tone}`}>
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="flex items-center gap-1.5 font-semibold text-zinc-100">
            <ShieldCheck className="h-4 w-4 text-emerald-400" /> Defend Your Code
            <span className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] font-bold text-zinc-300">OPTIONAL</span>
          </p>
          <p className="mt-0.5 text-xs text-zinc-400">
            {check.status === 'available' && <>{check.question_count} questions about functions <code>git blame</code> says you wrote. One attempt.</>}
            {check.status === 'unavailable' && (check.reason || 'Not enough of your own runnable code was found.')}
            {check.status === 'confirmed' && <>Authorship confirmed: explained {check.correct}/{check.total} of their own functions (+{check.points_effect} points).</>}
            {check.status === 'inconclusive' && <>Explained {check.correct}/{check.total} of their own functions. No change to points.</>}
            {check.status === 'not_explained' && <>Could not explain own code: {check.correct}/{check.total} correct ({check.points_effect} points).</>}
          </p>
          {done && check.commits.length > 0 && (
            <p className="mt-1 font-mono text-[11px] text-zinc-500">{check.commits.join(', ')}</p>
          )}
        </div>
        {check.status === 'available' && (
          <button
            onClick={onOpen}
            className="flex shrink-0 items-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-2 text-xs font-semibold text-white shadow-sm shadow-emerald-600/20 transition-colors hover:bg-emerald-500"
          >
            <ShieldCheck className="h-4 w-4" /> Defend your code
          </button>
        )}
      </div>
    </div>
  );
};

const Section: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div className="space-y-1.5">
    <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{title}</h3>
    {children}
  </div>
);
