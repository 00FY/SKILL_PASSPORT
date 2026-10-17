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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm overflow-y-auto">
      <div className="w-full max-w-2xl bg-[#101112] border border-[#232426] rounded shadow-2xl overflow-hidden flex flex-col my-8 card-inner-glow">
        {/* Header */}
        <div className="p-4 px-6 border-b border-[#1B1C1E] bg-[#0e0e0f] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded bg-[#1c1b1d] border border-[#2a2a2b] flex items-center justify-center text-[#5E6BFF]">
              <Award className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-heading font-bold text-base text-[#e5e2e3] tracking-tight">
                Skill Challenge Test: {skillName}
              </h3>
              <p className="text-[11px] font-mono text-[#9A9DA3]">
                15-Question Technical Challenge (Basic, Intermediate, Advanced)
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-[#9A9DA3] hover:text-[#e5e2e3] rounded hover:bg-[#1c1b1d] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-5 max-h-[70vh] overflow-y-auto">
          {/* Results Banner if Submitted */}
          {submitted && results && (
            <div className="bg-[#151617] rounded border border-[#50d8e9]/30 p-5 text-center space-y-3 card-inner-glow">
              <span className="text-[10px] font-mono font-bold text-[#50d8e9] bg-[#50d8e9]/10 px-2 py-0.5 rounded border border-[#50d8e9]/20 uppercase">
                Challenge Evaluation Complete
              </span>
              <div className="flex items-center justify-center gap-6">
                <div>
                  <p className="text-[10px] font-mono text-[#9A9DA3] uppercase">Correct</p>
                  <p className="font-heading font-extrabold text-2xl text-[#e5e2e3]">{results.correct} / {results.total}</p>
                </div>
                <div className="h-8 w-px bg-[#1B1C1E]" />
                <div>
                  <p className="text-[10px] font-mono text-[#9A9DA3] uppercase">Grade</p>
                  <p className="font-heading font-extrabold text-2xl text-[#50d8e9]">{results.grade}</p>
                </div>
                <div className="h-8 w-px bg-[#1B1C1E]" />
                <div>
                  <p className="text-[10px] font-mono text-[#9A9DA3] uppercase">Multiplier</p>
                  <p className="font-heading font-extrabold text-2xl text-[#bec2ff]">×{results.gradeWeight}</p>
                </div>
              </div>
              <button
                onClick={handleApplyToPassport}
                className="px-5 py-2 rounded bg-[#5E6BFF] hover:bg-[#4d5bff] text-white font-semibold text-xs transition-all shadow-md shadow-[#5E6BFF]/20"
              >
                Apply Grade to Passport
              </button>
            </div>
          )}

          {/* Question List */}
          <div className="space-y-4">
            {questions.map((q, idx) => (
              <div key={q.id} className="p-4 rounded bg-[#151617] border border-[#1B1C1E] space-y-2.5">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-[#9A9DA3]">QUESTION {idx + 1} OF {questions.length}</span>
                  <span className={`px-1.5 py-0.2 rounded text-[9px] font-bold uppercase ${
                    q.difficulty === 'Basic' ? 'bg-[#50d8e9]/10 text-[#50d8e9] border border-[#50d8e9]/20' :
                    q.difficulty === 'Intermediate' ? 'bg-[#ffb689]/10 text-[#ffb689] border border-[#ffb689]/20' :
                    'bg-[#bec2ff]/10 text-[#bec2ff] border border-[#bec2ff]/20'
                  }`}>
                    {q.difficulty}
                  </span>
                </div>
                <h4 className="text-xs font-semibold text-[#e5e2e3] leading-relaxed">
                  {q.question}
                </h4>

                <div className="space-y-1.5 pt-1">
                  {q.options.map((opt, optIdx) => {
                    const isSelected = selectedAnswers[q.id] === optIdx;
                    const isCorrect = submitted && optIdx === q.correct_index;
                    const isWrong = submitted && isSelected && !isCorrect;

                    return (
                      <button
                        key={optIdx}
                        disabled={submitted}
                        onClick={() => handleSelect(q.id, optIdx)}
                        className={`w-full text-left p-2.5 rounded text-xs font-mono transition-all flex items-center justify-between border ${
                          isCorrect
                            ? 'bg-[#50d8e9]/10 border-[#50d8e9]/40 text-[#50d8e9]'
                            : isWrong
                            ? 'bg-[#93000a]/20 border-[#ffb4ab]/40 text-[#ffb4ab]'
                            : isSelected
                            ? 'bg-[#1c1b1d] border-[#5E6BFF] text-[#e5e2e3]'
                            : 'bg-[#101112] border-[#1B1C1E] text-[#c6c5d8] hover:border-[#2a2a2b]'
                        }`}
                      >
                        <span>{opt}</span>
                        {isCorrect && <CheckCircle2 className="w-3.5 h-3.5 text-[#50d8e9] shrink-0" />}
                      </button>
                    );
                  })}
                </div>

                {submitted && (
                  <p className="text-[10px] font-mono text-[#9A9DA3] pt-2 border-t border-[#1B1C1E]">
                    <strong>Note:</strong> {q.explanation}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="p-3.5 px-6 border-t border-[#1B1C1E] bg-[#0e0e0f] flex items-center justify-between text-xs font-mono text-[#9A9DA3]">
          <span>{Object.keys(selectedAnswers).length} of {questions.length} answered</span>
          {!submitted ? (
            <button
              onClick={handleSubmit}
              disabled={Object.keys(selectedAnswers).length === 0}
              className="px-4 py-1.5 bg-[#5E6BFF] hover:bg-[#4d5bff] disabled:opacity-50 text-white rounded font-semibold transition-all"
            >
              Submit & Grade
            </button>
          ) : (
            <button
              onClick={onClose}
              className="px-4 py-1.5 text-[#9A9DA3] hover:text-white rounded"
            >
              Close
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
