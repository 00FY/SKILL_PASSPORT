import React, { useEffect, useState } from 'react';
import { Loader2, X } from 'lucide-react';
import { QuizQuestion, QuizResult } from '../lib/types';
import { postJson, request } from '../lib/api';

interface QuizModalProps {
  skillName: string | null;
  onClose: () => void;
}

export const QuizModal: React.FC<QuizModalProps> = ({ skillName, onClose }) => {
  const [questions, setQuestions] = useState<QuizQuestion[] | null>(null);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [result, setResult] = useState<QuizResult | null>(null);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!skillName) return;
    setQuestions(null); setAnswers({}); setResult(null); setError('');
    request<{ questions: QuizQuestion[] }>(`/api/quiz/${encodeURIComponent(skillName)}`)
      .then(d => setQuestions(d.questions))
      .catch(e => setError(e.message));
  }, [skillName]);

  if (!skillName) return null;

  const review = Object.fromEntries((result?.review ?? []).map(r => [r.id, r]));

  const submit = async () => {
    setSubmitting(true);
    try {
      setResult(await postJson<QuizResult>('/api/quiz/submit', { skill: skillName, answers }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-xl border border-white/10 bg-[#141516]">
        <div className="flex items-center justify-between border-b border-white/10 px-6 py-4">
          <h2 className="font-heading text-lg font-bold">{skillName} skill challenge</h2>
          <button onClick={onClose} className="rounded p-1 text-zinc-400 hover:bg-white/10 hover:text-white" aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 space-y-5 overflow-y-auto px-6 py-4 text-sm">
          {error && <p className="rounded-lg bg-red-500/10 p-3 text-red-200">{error}</p>}
          {!error && !questions && <Loader2 className="mx-auto h-6 w-6 animate-spin text-zinc-400" />}

          {result && (
            <div className="rounded-lg border border-emerald-400/30 bg-emerald-500/10 p-4">
              <p className="text-base font-semibold text-emerald-200">
                Grade {result.grade}: {result.correct_count} of {result.total_questions} correct ({result.percentage}%)
              </p>
              <p className="text-zinc-300">
                The grade is shown here only. It isn't added to this signed passport.
              </p>
            </div>
          )}

          {questions?.map((q, i) => (
            <div key={q.id} className="space-y-2">
              <p className="font-medium">{i + 1}. {q.question}</p>
              <div className="grid gap-2">
                {q.options.map((opt, idx) => {
                  const chosen = answers[q.id] === idx;
                  const correctIndex = review[q.id]?.correct_index;
                  const showCorrect = result && idx === correctIndex;
                  const showWrong = result && chosen && idx !== correctIndex;
                  return (
                    <button
                      key={idx}
                      disabled={!!result}
                      onClick={() => setAnswers(a => ({ ...a, [q.id]: idx }))}
                      className={`rounded-lg border px-3 py-2 text-left ${
                        showCorrect ? 'border-emerald-400/50 bg-emerald-500/10'
                        : showWrong ? 'border-red-400/50 bg-red-500/10'
                        : chosen ? 'border-indigo-400 bg-indigo-500/10'
                        : 'border-white/10 hover:bg-white/5'}`}
                    >
                      {opt}
                    </button>
                  );
                })}
              </div>
              {result && <p className="text-xs text-zinc-400">{review[q.id]?.explanation}</p>}
            </div>
          ))}
        </div>

        {questions && !result && (
          <div className="flex items-center justify-between border-t border-white/10 px-6 py-3 text-sm">
            <span className="text-zinc-400">{Object.keys(answers).length} of {questions.length} answered</span>
            <button
              onClick={submit}
              disabled={submitting || Object.keys(answers).length < questions.length}
              className="rounded-lg bg-indigo-500 px-4 py-2 font-semibold text-white hover:bg-indigo-400 disabled:opacity-40"
            >
              Submit answers
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
