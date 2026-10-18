import React, { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Loader2, ShieldAlert, XCircle } from 'lucide-react';
import { PassportDocument } from '../lib/types';
import { postJson } from '../lib/api';
import { claimRows, problemRows } from './ClaimList';
import { PillarScoreBar } from './PillarScoreBar';

type SignatureState = 'checking' | 'valid' | 'invalid' | 'error';

export const PassportSummary: React.FC<{ passport: PassportDocument }> = ({ passport }) => {
  const [signature, setSignature] = useState<SignatureState>('checking');

  // Ask the backend to verify the HMAC signature of exactly what is displayed
  useEffect(() => {
    let cancelled = false;
    setSignature('checking');
    postJson<{ valid: boolean }>('/api/verify-signature', passport)
      .then(r => !cancelled && setSignature(r.valid ? 'valid' : 'invalid'))
      .catch(() => !cancelled && setSignature('error'));
    return () => { cancelled = true; };
  }, [passport]);

  const rows = claimRows(passport);
  const problems = problemRows(passport);
  const count = (v: string) => rows.filter(r => r.verdict === v).length;
  const verified = count('VERIFIED');

  const breakdown = [
    count('PARTIALLY_SUPPORTED') && `${count('PARTIALLY_SUPPORTED')} partly supported`,
    count('CLAIMED_ONLY') && `${count('CLAIMED_ONLY')} with no evidence`,
    count('CONTRADICTED') && `${count('CONTRADICTED')} contradicted`,
    problems.length && `${problems.length} problem${problems.length === 1 ? '' : 's'} found`,
  ].filter(Boolean).join(' · ');

  return (
    <section className="space-y-4">
      {passport.security_alerts.length > 0 && (
        <div className="rounded-lg border border-red-400/40 bg-red-500/10 p-4 text-sm text-red-200">
          <div className="mb-2 flex items-center gap-2 font-semibold">
            <ShieldAlert className="h-4 w-4" />
            Hidden instructions found in the resume ({passport.security_alerts.length})
          </div>
          <p className="mb-2 text-red-200/80">They were removed before any analysis. What was found:</p>
          <ul className="list-disc space-y-1 pl-5 text-red-100/90">
            {passport.security_alerts.map((a, i) => <li key={i} className="break-words">{a.raw_payload_snippet}</li>)}
          </ul>
        </div>
      )}

      {passport.warnings && passport.warnings.length > 0 && (
        <div className="flex gap-3 rounded-lg border border-amber-400/40 bg-amber-500/10 p-4 text-sm text-amber-100">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
          <div className="space-y-1">{passport.warnings.map((w, i) => <p key={i}>{w}</p>)}</div>
        </div>
      )}

      <div className="rounded-xl border border-white/10 bg-[#17181a] p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="font-heading text-2xl font-bold">{passport.candidate_name}</h1>
            <p className="text-sm text-zinc-400">{passport.applied_role}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {passport.evidence_source === 'demo' && (
              <span
                className="rounded-full border border-sky-400/40 bg-sky-500/10 px-3 py-1 text-sm text-sky-200"
                title="Fictional sample data. The signature confirms it wasn't altered, not that it describes a real person."
              >
                Demo data
              </span>
            )}
            <SignatureBadge state={signature} />
          </div>
        </div>

        <p className="mt-4 text-lg">
          <strong className={verified > 0 ? 'text-emerald-300' : 'text-zinc-200'}>{verified} of {rows.length}</strong> claims verified by code
        </p>
        {breakdown && <p className="text-sm text-zinc-400">{breakdown}</p>}

        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <Stat label="Balanced score" value={`${passport.overall_score}/100`} hint="Score balanced across active pillars (code, quiz, resume, certs)" />
          <Stat label="Role match" value={`${passport.role_match_pct}%`} hint="Share of claims backed by evidence, minus 7 per problem" />
          <Stat
            label="Code written by candidate"
            value={passport.candidate_authorship_pct != null && passport.total_commits ? `${passport.candidate_authorship_pct}%` : '-'}
            hint={passport.total_commits
              ? `Across ${passport.total_commits} commits over ${passport.active_months} month${passport.active_months === 1 ? '' : 's'}`
              : 'No repository analysed'}
          />
        </div>

        {passport.pillar_scores && (
          <div className="mt-5">
            <PillarScoreBar pillarScores={passport.pillar_scores} overallScore={passport.overall_score} />
          </div>
        )}
      </div>
    </section>
  );
};

const Stat: React.FC<{ label: string; value: string; hint: string }> = ({ label, value, hint }) => (
  <div className="rounded-lg bg-white/5 p-3">
    <div className="text-xs text-zinc-400">{label}</div>
    <div className="text-2xl font-semibold">{value}</div>
    <div className="text-xs text-zinc-500">{hint}</div>
  </div>
);

const SignatureBadge: React.FC<{ state: SignatureState }> = ({ state }) => {
  const styles: Record<SignatureState, [string, React.ReactNode, string]> = {
    checking: ['text-zinc-400 border-white/10', <Loader2 className="h-4 w-4 animate-spin" />, 'Checking signature'],
    valid: ['text-emerald-300 border-emerald-400/30', <CheckCircle2 className="h-4 w-4" />, 'Signature valid'],
    invalid: ['text-red-300 border-red-400/40', <XCircle className="h-4 w-4" />, 'Signature invalid - passport was altered'],
    error: ['text-zinc-400 border-white/10', <AlertTriangle className="h-4 w-4" />, 'Signature not checked'],
  };
  const [cls, icon, text] = styles[state];
  return (
    <span
      className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm ${cls}`}
      title="The backend recomputes the HMAC-SHA256 signature over this passport"
    >
      {icon}{text}
    </span>
  );
};
