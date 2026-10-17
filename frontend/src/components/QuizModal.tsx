import React, { useState } from 'react';
import { X, Award, CheckCircle2, AlertCircle, ArrowRight, HelpCircle } from 'lucide-react';
import { QUIZ_QUESTIONS_PYTHON, QuizQuestion } from '../data/mockData';

interface QuizModalProps {
  skillName: string;
  isOpen: boolean;
  onClose: () => void;
  onCompleteQuiz: (skillName: string, grade: string, points: number) => void;
}

export const QuizModal: React.FC<QuizModalProps> = ({
  skillName,
  isOpen,
  onClose,
  onCompleteQuiz
}) => {
  if (!isOpen) return null;

  const questions: QuizQuestion[] = QUIZ_QUESTIONS_PYTHON;
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, number>>({});
  const [submitted, setSubmitted] = useState<boolean>(false);

  const handleSelect = (questionId: string, optionIdx: number) => {
    if (submitted) return;
    setSelectedAnswers(prev => ({ ...prev, [questionId]: optionIdx }));
  };

  const calculateResults = () => {
    let correct = 0;
    questions.forEach(q => {
      if (selectedAnswers[q.id] === q.correct_index) {
        correct++;
      }
    });

    const pct = Math.round((correct / questions.length) * 100);
    let grade = 'C';
    let gradeWeight = 6;

    if (pct >= 85) { grade = 'A'; gradeWeight = 10; }
    else if (pct >= 70) { grade = 'B'; gradeWeight = 8; }
    else if (pct >= 50) { grade = 'C'; gradeWeight = 6; }
    else if (pct >= 35) { grade = 'D'; gradeWeight = 4; }
    else { grade = 'E'; gradeWeight = 2; }

    return { correct, total: questions.length, pct, grade, gradeWeight };
  };

  const results = submitted ? calculateResults() : null;

  const handleSubmit = () => {
    setSubmitted(true);
  };

  const handleApplyToPassport = () => {
    if (results) {
      onCompleteQuiz(skillName, results.grade, 8 * results.gradeWeight);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md overflow-y-auto">
      <div className="w-full max-w-2xl bg-[#0e131f] border border-white/10 rounded-3xl shadow-2xl overflow-hidden flex flex-col my-8">
        {/* Header */}
        <div className="p-6 border-b border-white/10 bg-slate-900/60 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold">
              <Award className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white tracking-tight">
                Skill Challenge Test: {skillName}
              </h3>
              <p className="text-xs text-slate-400">
                15-Question Technical Challenge (Basic, Intermediate, Advanced)
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-white/5 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6 max-h-[70vh] overflow-y-auto">
          {/* Results Banner if Submitted */}
          {submitted && results && (
            <div className="glass-panel rounded-2xl p-6 border border-emerald-500/30 bg-emerald-950/20 text-center space-y-3 animate-fadeIn">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-400 text-xs font-bold border border-emerald-500/30">
                CHALLENGE EVALUATION COMPLETE
              </div>
              <div className="flex items-center justify-center gap-6">
                <div>
                  <p className="text-xs text-slate-400 uppercase font-semibold">Score</p>
                  <p className="text-3xl font-black text-white">{results.correct} / {results.total}</p>
                </div>
                <div className="h-10 w-px bg-white/10" />
                <div>
                  <p className="text-xs text-slate-400 uppercase font-semibold">Awarded Grade</p>
                  <p className="text-3xl font-black text-emerald-400">{results.grade}</p>
                </div>
                <div className="h-10 w-px bg-white/10" />
                <div>
                  <p className="text-xs text-slate-400 uppercase font-semibold">Grade Weight</p>
                  <p className="text-3xl font-black text-teal-400">×{results.gradeWeight}</p>
                </div>
              </div>
              <p className="text-xs text-slate-300">
                Evaluated against published rubric. Click below to apply your new grade to your Skill Passport!
              </p>
              <button
                onClick={handleApplyToPassport}
                className="px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow-lg shadow-emerald-600/30 transition-all"
              >
                Apply Grade to Passport
              </button>
            </div>
          )}

          {/* Question List */}
          <div className="space-y-6">
            {questions.map((q, idx) => (
              <div key={q.id} className="p-4 rounded-xl bg-slate-900/50 border border-white/5 space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-mono text-slate-400">Question {idx + 1} of {questions.length}</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                    q.difficulty === 'Basic' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' :
                    q.difficulty === 'Intermediate' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                    'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                  }`}>
                    {q.difficulty}
                  </span>
                </div>
                <h4 className="text-sm font-semibold text-white leading-relaxed">
                  {q.question}
                </h4>

                <div className="space-y-2 pt-1">
                  {q.options.map((opt, optIdx) => {
                    const isSelected = selectedAnswers[q.id] === optIdx;
                    const isCorrect = submitted && optIdx === q.correct_index;
                    const isWrong = submitted && isSelected && !isCorrect;

                    return (
                      <button
                        key={optIdx}
                        disabled={submitted}
                        onClick={() => handleSelect(q.id, optIdx)}
                        className={`w-full text-left p-3 rounded-xl text-xs font-medium border transition-all flex items-center justify-between ${
                          isCorrect
                            ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300'
                            : isWrong
                            ? 'bg-rose-500/20 border-rose-500/40 text-rose-300'
                            : isSelected
                            ? 'bg-white/10 border-white/30 text-white'
                            : 'bg-slate-900/80 border-white/5 text-slate-300 hover:border-white/15'
                        }`}
                      >
                        <span>{opt}</span>
                        {isCorrect && <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />}
                      </button>
                    );
                  })}
                </div>

                {submitted && (
                  <p className="text-[11px] text-slate-400 pt-2 border-t border-white/5">
                    <strong>Explanation:</strong> {q.explanation}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-white/10 bg-slate-900/80 flex items-center justify-between">
          <span className="text-xs text-slate-400">
            {Object.keys(selectedAnswers).length} of {questions.length} answered
          </span>
          {!submitted ? (
            <button
              onClick={handleSubmit}
              disabled={Object.keys(selectedAnswers).length === 0}
              className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl transition-all shadow-md shadow-emerald-600/20"
            >
              Submit & Grade Challenge
            </button>
          ) : (
            <button
              onClick={onClose}
              className="px-5 py-2 text-slate-400 hover:text-white text-xs font-semibold rounded-xl"
            >
              Close
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
