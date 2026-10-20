import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Award, ExternalLink, ShieldAlert, ShieldCheck } from 'lucide-react';
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
  const certs = passport.certificates ?? [];

  return (
    <section className="space-y-6">
      <div className="rounded-xl border border-white/10 bg-[#17181a]">
        <h2 className="border-b border-white/10 px-5 py-3 font-heading font-semibold">
          {passport.pillar_scores?.resume_score == null ? 'Evaluated Skills (Code Profile & Credentials)' : 'Claims & Evaluated Skills'}
        </h2>
        {rows.length === 0 && <p className="px-5 py-4 text-sm text-zinc-400">No technical skills detected or claimed.</p>}
        <ul className="divide-y divide-white/5">
          {rows.map((row, i) => <ClaimRowItem key={`${row.name}-${i}`} row={row} onOpenSkill={onOpenSkill} />)}
        </ul>
      </div>

      {certs.length > 0 && (
        <div className="rounded-xl border border-white/10 bg-[#17181a]">
          <h2 className="flex items-center gap-2 border-b border-white/10 px-5 py-3 font-heading font-semibold text-zinc-100">
            <Award className="h-4 w-4 text-amber-400" />
            Verified Issuer Credentials & Certificates ({certs.length})
          </h2>
          <div className="border-b border-white/5 bg-amber-500/[0.04] px-5 py-2.5 text-[11px] text-zinc-300">
            <span className="font-semibold text-amber-300">Evidence Distinction:</span> A verified certificate establishes credible evidence of learning. Practical coding competence is verified separately through GitHub blame and SkillProof challenges.
          </div>
          <ul className="divide-y divide-white/5">
            {certs.map(cert => {
              const s = (cert.issuer_status || '').toLowerCase();
              const isVerified = s === 'verified' || s === 'issuer_verified';
              const isPending = s === 'pending' || s === 'issuer_unparsed' || s === 'issuer_unreachable';
              const isMismatch = (cert.mismatch_reason || '').toLowerCase().includes('recipient') || (cert.mismatch_reason || '').toLowerCase().includes('mismatch');

              return (
                <li key={cert.id} className="p-5 space-y-2.5 text-xs">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2 font-medium text-sm text-zinc-100">
                      <span>{cert.certificate_name}</span>
                      <span className="text-amber-400 font-normal">({cert.issuer})</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {isVerified && (
                        <span className="inline-flex items-center gap-1 rounded bg-emerald-500/15 border border-emerald-500/30 px-2 py-0.5 text-[11px] font-semibold text-emerald-300">
                          <ShieldCheck className="h-3.5 w-3.5" /> Verified
                        </span>
                      )}
                      {isPending && (
                        <span className="inline-flex items-center gap-1 rounded bg-amber-500/15 border border-amber-500/30 px-2 py-0.5 text-[11px] font-semibold text-amber-300" title="Official issuer page recognized; automated parsing pending manual review">
                          ⏳ Pending verification
                        </span>
                      )}
                      {!isVerified && !isPending && (
                        <span className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-semibold border ${
                          isMismatch
                            ? 'bg-rose-500/15 border-rose-500/30 text-rose-300'
                            : 'bg-zinc-500/15 border-zinc-500/30 text-zinc-400'
                        }`}>
                          {isMismatch ? <ShieldAlert className="h-3.5 w-3.5" /> : null}
                          {isMismatch ? 'Needs Review: Recipient Mismatch' : 'Unverified'}
                        </span>
                      )}

                      {isPending && cert.verify_url && (
                        <a
                          href={cert.verify_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 rounded border border-amber-500/40 bg-amber-500/15 px-2 py-0.5 text-[11px] font-semibold text-amber-200 hover:bg-amber-500/25"
                        >
                          Verify manually ↗
                        </a>
                      )}
                    </div>
                  </div>

                  <div className="grid gap-2 sm:grid-cols-2 text-[11px] text-zinc-400">
                    <div>
                      <span className="text-zinc-500">Official Recipient: </span>
                      <span className="text-zinc-200 font-medium">{cert.issuer_record?.recipient_name || cert.candidate_name || 'N/A'}</span>
                    </div>
                    {cert.issue_date && (
                      <div>
                        <span className="text-zinc-500">Issue Date: </span>
                        <span className="text-zinc-200">{cert.issue_date}</span>
                      </div>
                    )}
                    {cert.verify_url && (
                      <div className="sm:col-span-2">
                        <span className="text-zinc-500">Official Issuer URL: </span>
                        <a href={cert.verify_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sky-400 hover:underline break-all">
                          {cert.verify_url} <ExternalLink className="h-3 w-3" />
                        </a>
                      </div>
                    )}
                    {cert.evidence_hash && (
                      <div className="sm:col-span-2 flex flex-wrap items-center gap-1 font-mono text-[10px] text-zinc-500">
                        <span>Record Hash (SHA-256):</span>
                        <span className="text-zinc-400">{cert.evidence_hash}</span>
                        {cert.verification_timestamp && (
                          <span className="text-zinc-500 ml-2">· Checked: {new Date(cert.verification_timestamp).toLocaleTimeString()}</span>
                        )}
                      </div>
                    )}
                  </div>

                  {cert.mismatch_reason && (
                    <p className={`rounded p-2.5 ${
                      isPending
                        ? 'bg-amber-950/30 border border-amber-500/30 text-amber-200'
                        : 'bg-rose-950/40 border border-rose-500/30 text-rose-300'
                    }`}>
                      <strong className={isPending ? 'text-amber-300' : 'text-rose-200'}>Status Note:</strong> {cert.mismatch_reason}
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}

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
  const isQuizPending = row.skill?.signals.some(s => s.toLowerCase().includes('quiz pending'));

  return (
    <li>
      <button
        onClick={onClick}
        disabled={!clickable}
        className="flex w-full items-center gap-4 px-5 py-3 text-left hover:bg-white/5"
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-medium">{row.name}</span>
            {isQuizPending && (
              <span className="rounded bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-300 border border-amber-500/30">
                Quiz Pending
              </span>
            )}
          </div>
          <div className="truncate text-sm text-zinc-400">{row.reason}</div>
        </div>
        {row.skill?.test_grade && (
          <span className={`hidden sm:inline-flex items-center rounded border px-2 py-0.5 text-xs font-mono font-medium ${
            isQuizPending
              ? 'border-amber-500/40 bg-amber-500/10 text-amber-300'
              : 'border-indigo-500/30 bg-indigo-500/10 text-indigo-300'
          }`}>
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
