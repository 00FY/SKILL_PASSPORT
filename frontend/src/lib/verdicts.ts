import { Verdict } from './types';

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
