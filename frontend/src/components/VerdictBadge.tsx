import React from 'react';
import { Verdict } from '../lib/types';
import { VERDICT_LABEL, VERDICT_STYLE } from '../lib/verdicts';

export const VerdictBadge: React.FC<{ verdict: Verdict }> = ({ verdict }) => (
  <span className={`inline-flex items-center whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium ${VERDICT_STYLE[verdict]}`}>
    {VERDICT_LABEL[verdict]}
  </span>
);
