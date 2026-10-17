import React from 'react';
import { Award, FileCode, X } from 'lucide-react';
import { RunAuditLog, SkillPassportItem } from '../lib/types';
import { VerdictBadge } from './VerdictBadge';

interface EvidenceDrawerProps {
  skill: SkillPassportItem | null;
  auditLog?: RunAuditLog | null;
  onClose: () => void;
  onOpenQuiz: (skillName: string) => void;
}

export const EvidenceDrawer: React.FC<EvidenceDrawerProps> = ({ skill, auditLog, onClose, onOpenQuiz }) => {
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
            <p className="text-zinc-300">
              Evidence {skill.evidence_score}/10 × grade {skill.test_grade} = {skill.final_points} points
            </p>
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

          {skill.verdict !== 'VERIFIED' && (
            <button
              onClick={() => onOpenQuiz(skill.name)}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-white/15 py-2.5 text-zinc-200 hover:bg-white/5"
            >
              <Award className="h-4 w-4" />
              Take the {skill.name} skill challenge
            </button>
          )}
        </div>
      </aside>
    </div>
  );
};

const Section: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div className="space-y-1.5">
    <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{title}</h3>
    {children}
  </div>
);
