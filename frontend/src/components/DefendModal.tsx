import React, { useCallback, useEffect, useRef, useState } from 'react';
import { CheckCircle2, Clock, FileCode, Loader2, ShieldCheck, X, XCircle } from 'lucide-react';
import { postJson } from '../lib/api';
import {
  DefendAnswerResponse, DefendQuestion, DefendResult, DefendStart, PassportDocument,
} from '../lib/types';

interface DefendModalProps {
  skillName: string | null;
  passport: PassportDocument | null;
  onClose: () => void;
  onPassportUpdated: (p: PassportDocument) => void;
}

type Phase = 'intro' | 'question' | 'result';

const STATUS_TEXT: Record<string, string> = {
  confirmed: 'Authorship confirmed',
  inconclusive: 'Inconclusive',
  not_explained: 'Could not explain own code',
};

export const DefendModal: React.FC<DefendModalProps> = ({ skillName, passport, onClose, onPassportUpdated }) => {
  const [phase, setPhase] = useState<Phase>('intro');
  const [extended, setExtended] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [total, setTotal] = useState(0);
  const [limit, setLimit] = useState(90);
  const [question, setQuestion] = useState<DefendQuestion | null>(null);
  const [choice, setChoice] = useState<number | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [result, setResult] = useState<DefendResult | null>(null);
  const [applied, setApplied] = useState<PassportDocument | null>(null);
  // Browser-reported signals, sent with each answer and recorded in the audit trail (never used to fail anyone)
  const pastes = useRef(0);
  const tabSwitches = useRef(0);
  const submitting = useRef(false);

  useEffect(() => {
    if (!skillName) return;
    setPhase('intro'); setExtended(false); setError(''); setResult(null); setApplied(null);
    setQuestion(null); setChoice(null);
  }, [skillName]);

  useEffect(() => {
    if (phase !== 'question') return;
    const onPaste = () => { pastes.current += 1; };
    const onVisibility = () => { if (document.visibilityState === 'hidden') tabSwitches.current += 1; };
    document.addEventListener('paste', onPaste);
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      document.removeEventListener('paste', onPaste);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [phase]);

  const applyResult = useCallback(async (res: DefendResult) => {
    if (!passport) return;
    try {
      const updated = await postJson<PassportDocument>('/api/defend/apply', { passport, attempt_id: res.attempt_id });
      setApplied(updated);
      onPassportUpdated(updated);
    } catch (e) {
      setError(`The result couldn't be added to the passport: ${(e as Error).message}`);
    }
  }, [passport, onPassportUpdated]);

  const submit = useCallback(async (picked: number | null) => {
    if (!question || submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError('');
    try {
      const res = await postJson<DefendAnswerResponse>('/api/defend/answer', {
        session_id: sessionId,
        question_id: question.question_id,
        choice: picked,
        pastes: pastes.current,
        tab_switches: tabSwitches.current,
      });
      pastes.current = 0;
      tabSwitches.current = 0;
      if (res.done && res.result) {
        setResult(res.result);
        setPhase('result');
        await applyResult(res.result);
      } else if (res.question) {
        setQuestion(res.question);
        setChoice(null);
        setSecondsLeft(limit);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }, [question, sessionId, limit, applyResult]);

  // Countdown; when it runs out the current choice (or none) is submitted
  useEffect(() => {
    if (phase !== 'question') return;
    if (secondsLeft <= 0) {
      submit(choice);
      return;
    }
    const t = setTimeout(() => setSecondsLeft(s => s - 1), 1000);
    return () => clearTimeout(t);
  }, [phase, secondsLeft, choice, submit]);

  const start = async () => {
    if (!passport || !skillName) return;
    setBusy(true);
    setError('');
    try {
      const res = await postJson<DefendStart>('/api/defend/start', { passport, skill: skillName, extended_time: extended });
      setSessionId(res.session_id);
      setTotal(res.total);
      setLimit(res.time_limit_s);
      setQuestion(res.question);
      setChoice(null);
      setSecondsLeft(res.time_limit_s);
      pastes.current = 0;
      tabSwitches.current = 0;
      setPhase('question');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (!skillName) return null;
  const check = passport?.skills.find(s => s.name === skillName)?.authorship_check;
  const updatedSkill = applied?.skills.find(s => s.name === skillName);
  const closable = phase !== 'question';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/80 p-4 backdrop-blur-sm">
      <div className="flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#121316] shadow-2xl shadow-black/80">
        <div className="flex items-center justify-between border-b border-white/10 bg-white/[0.02] px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-500 shadow-md shadow-emerald-500/20">
              <ShieldCheck className="h-5 w-5 text-white" />
            </div>
            <div>
              <h2 className="font-heading text-lg font-bold text-white">Defend Your Code · {skillName}</h2>
              <p className="text-xs text-zinc-400">Questions about functions <code>git blame</code> says you wrote</p>
            </div>
          </div>
          {closable && (
            <button onClick={onClose} className="rounded-lg p-1.5 text-zinc-400 transition hover:bg-white/10 hover:text-white" aria-label="Close">
              <X className="h-5 w-5" />
            </button>
          )}
        </div>

        <div className="flex-1 space-y-5 overflow-y-auto p-6 text-sm">
          {error && <div className="rounded-lg border border-red-400/40 bg-red-500/10 p-3 text-red-200">{error}</div>}

          {phase === 'intro' && (
            <>
              <p className="text-zinc-300">
                You'll get {check?.question_count ?? 'a few'} questions about functions from your own repositories, one at a time:
                what a call returns, which line was hidden, or which of your functions a body belongs to. It checks that you
                understand the code credited to you; a general quiz can't do that.
              </p>
              <ul className="space-y-1.5 text-zinc-300">
                <li>• <strong>Optional</strong>: skipping it changes nothing.</li>
                <li>• <strong>One attempt</strong>: once you start, it counts. {extended ? '180' : '90'} seconds per question.</li>
                <li>• <strong className="text-emerald-300">80% or more</strong>: +5 points on {skillName} and an "Authorship confirmed" badge.</li>
                <li>• <strong className="text-red-300">Below 40%</strong>: {skillName}'s points are multiplied by 0.4 and flagged.</li>
                <li>• In between: no change. Pastes and tab switches are noted in the audit trail but never fail you.</li>
              </ul>
              <label className="flex items-center gap-2 text-zinc-300">
                <input type="checkbox" checked={extended} onChange={e => setExtended(e.target.checked)} className="h-4 w-4 accent-emerald-500" />
                I need extended time (180 seconds per question; noted in the audit trail)
              </label>
            </>
          )}

          {phase === 'question' && question && (
            <>
              <div className="flex items-center justify-between text-xs text-zinc-400">
                <span>Question {question.number} of {total}</span>
                <span className={`flex items-center gap-1 font-mono ${secondsLeft <= 15 ? 'text-red-300' : 'text-zinc-300'}`}>
                  <Clock className="h-3.5 w-3.5" /> {secondsLeft}s
                </span>
              </div>
              <div className="h-1 overflow-hidden rounded bg-white/10">
                <div className="h-full bg-emerald-500 transition-all" style={{ width: `${(100 * secondsLeft) / limit}%` }} />
              </div>
              <div>
                <p className="flex items-center gap-1.5 text-xs text-zinc-400">
                  <FileCode className="h-3.5 w-3.5" />
                  <span className="font-mono">{question.path}:{question.line}</span>
                  {question.commit && <span className="font-mono text-zinc-500">@{question.commit.slice(0, 7)}</span>}
                </p>
                <pre className="mt-2 max-h-72 overflow-auto rounded-lg bg-black/40 p-3 font-mono text-xs leading-relaxed text-zinc-200">
                  {question.code.split('\n').map((line, i) => (
                    <div key={i} className={line.includes('??? (hidden line)') ? 'rounded bg-amber-500/20 text-amber-200' : undefined}>
                      {line || ' '}
                    </div>
                  ))}
                </pre>
                {question.context.length > 0 && (
                  <details className="mt-2 text-xs text-zinc-400">
                    <summary className="cursor-pointer">Uses {question.context.length} definition{question.context.length > 1 ? 's' : ''} from the same file</summary>
                    <pre className="mt-1 max-h-40 overflow-auto rounded bg-black/30 p-2 font-mono text-zinc-300">{question.context.join('\n\n')}</pre>
                  </details>
                )}
              </div>
              <p className="text-zinc-200">{question.prompt || 'What does this call return?'}</p>
              {question.call && (
                <pre className="overflow-x-auto rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3 font-mono text-xs text-emerald-200">{question.call}</pre>
              )}
              <div className="grid gap-2">
                {question.options.map((opt, i) => (
                  <button
                    key={i}
                    onClick={() => setChoice(i)}
                    className={`rounded-lg border px-4 py-2.5 text-left font-mono text-xs transition ${
                      choice === i ? 'border-emerald-400 bg-emerald-500/15 text-white' : 'border-white/10 bg-white/[0.02] text-zinc-300 hover:border-white/30'
                    }`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </>
          )}

          {phase === 'result' && result && (
            <>
              <div className={`rounded-xl border p-4 ${
                result.status === 'confirmed' ? 'border-emerald-500/40 bg-emerald-500/10'
                  : result.status === 'not_explained' ? 'border-red-500/40 bg-red-500/10' : 'border-white/10 bg-white/[0.03]'
              }`}>
                <p className="font-heading text-lg font-bold text-white">
                  {STATUS_TEXT[result.status]}: {result.correct}/{result.total} correct
                </p>
                {updatedSkill?.authorship_check && (
                  <p className="mt-1 text-zinc-300">
                    {skillName}: {updatedSkill.final_points - updatedSkill.authorship_check.points_effect} → {updatedSkill.final_points} points.
                    The passport was re-signed.
                  </p>
                )}
                {!applied && !error && <p className="mt-1 flex items-center gap-1.5 text-zinc-400"><Loader2 className="h-4 w-4 animate-spin" /> Updating the passport…</p>}
              </div>
              <ul className="space-y-2">
                {result.review.map((r, i) => (
                  <li key={i} className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
                    <p className="flex items-center gap-1.5 text-xs text-zinc-400">
                      {r.correct ? <CheckCircle2 className="h-4 w-4 text-emerald-400" /> : <XCircle className="h-4 w-4 text-red-400" />}
                      <span className="font-mono">{r.path}</span>
                    </p>
                    <p className="mt-1 text-xs text-zinc-300">
                      {r.call ? <span className="font-mono">{r.call}</span> : r.prompt}
                    </p>
                    <p className="mt-1 text-xs text-zinc-400">
                      {r.kind === 'predict' ? 'Returns' : 'Answer'} <span className="font-mono text-emerald-300">{r.correct_answer}</span>
                      {!r.correct && <> · you answered <span className="font-mono text-red-300">{r.timed_out ? 'nothing in time' : (r.your_answer ?? 'nothing')}</span></>}
                    </p>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>

        <div className="flex items-center justify-end gap-3 border-t border-white/10 px-6 py-4">
          {phase === 'intro' && (
            <>
              <button onClick={onClose} className="rounded-lg px-4 py-2 text-sm text-zinc-300 hover:bg-white/10">Not now</button>
              <button
                onClick={start}
                disabled={busy || !passport}
                className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
              >
                {busy && <Loader2 className="h-4 w-4 animate-spin" />} Start
              </button>
            </>
          )}
          {phase === 'question' && (
            <button
              onClick={() => submit(choice)}
              disabled={busy || choice === null}
              className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
            >
              {busy && <Loader2 className="h-4 w-4 animate-spin" />}
              {question && question.number === total ? 'Finish' : 'Next'}
            </button>
          )}
          {phase === 'result' && (
            <button onClick={onClose} className="rounded-lg bg-white/10 px-4 py-2 text-sm font-semibold text-white hover:bg-white/20">Close</button>
          )}
        </div>
      </div>
    </div>
  );
};
