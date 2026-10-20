import { SkillPassportItem, Verdict } from './types';

export const VERDICT_LABEL: Record<Verdict, string> = {
  VERIFIED: 'Verified by code',
  PARTIALLY_SUPPORTED: 'Partly supported',
  CLAIMED_ONLY: 'No evidence',
  CONTRADICTED: 'Contradicted',
};

export const VERDICT_STYLE: Record<Verdict, string> = {
  VERIFIED: 'bg-emerald-400/10 text-emerald-300 border-emerald-400/30',
  PARTIALLY_SUPPORTED: 'bg-amber-400/10 text-amber-300 border-amber-400/30',
  CLAIMED_ONLY: 'bg-zinc-400/10 text-zinc-300 border-zinc-400/30',
  CONTRADICTED: 'bg-red-400/10 text-red-300 border-red-400/30',
};

export const VERDICT_ORDER: Record<Verdict, number> = {
  VERIFIED: 0,
  PARTIALLY_SUPPORTED: 1,
  CLAIMED_ONLY: 2,
  CONTRADICTED: 3,
};

export const GRADE_WEIGHT: Record<string, number> = { A: 10, B: 8, C: 6, D: 4, E: 2 };

/** The points formula exactly as the backend applies it, so the numbers on screen add up. */
export const pointsFormula = (skill: SkillPassportItem): string => {
  if (skill.verdict === 'CONTRADICTED') {
    return `Contradicted by repository evidence: fixed ${skill.final_points} points`;
  }
  const weight = GRADE_WEIGHT[skill.test_grade] ?? 6;
  const bonus = skill.consistency_bonus ?? 0;
  const raw = skill.evidence_score * weight + bonus;
  const effect = skill.authorship_check?.points_effect ?? 0;
  const base = skill.final_points - effect;
  const bonusPart = bonus > 0 ? ` + ${bonus} consistency bonus` : '';
  const capPart = raw > 100 ? ` = ${raw}, capped at ${base}` : ` = ${base}`;
  const formula = `Evidence ${skill.evidence_score}/10 × grade ${skill.test_grade} (${weight})${bonusPart}${capPart} points`;
  const status = skill.authorship_check?.status;
  if (status === 'confirmed') return `${formula}, + ${effect} for explaining their own code = ${skill.final_points} points`;
  if (status === 'not_explained') return `${formula}, × 0.4 for not explaining their own code = ${skill.final_points} points`;
  return formula;
};
