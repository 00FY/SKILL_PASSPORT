import React, { useEffect, useState } from 'react';
import {
  Loader2, X, CheckCircle2, XCircle, AlertCircle, ArrowRight,
  Terminal, Code, Bug, BookOpen, Brain, Sparkles, RefreshCw, Zap
} from 'lucide-react';
import {
  PassportDocument, PublicTaskItem, StepEvaluationResult,
  DifficultyTier, StageType
} from '../lib/types';
import { postJson } from '../lib/api';

interface QuizModalProps {
  skillName: string | null;
  passport: PassportDocument | null;
  onClose: () => void;
  onPassportUpdated?: (updated: PassportDocument) => void;
}

const STAGES: { type: StageType; label: string; icon: React.FC<{ className?: string }> }[] = [
  { type: 'comprehension', label: 'Comprehension', icon: BookOpen },
  { type: 'debugging', label: 'Debugging', icon: Bug },
  { type: 'coding', label: 'Coding', icon: Code },
  { type: 'reasoning', label: 'Reasoning', icon: Brain },
];

export const QuizModal: React.FC<QuizModalProps> = ({ skillName, passport, onClose, onPassportUpdated }) => {
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  // Assessment Session State
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentTask, setCurrentTask] = useState<PublicTaskItem | null>(null);
  const [stageIdx, setStageIdx] = useState(0);
  const [currentDifficulty, setCurrentDifficulty] = useState<DifficultyTier>(2);

  // User input per step
  const [selectedOption, setSelectedOption] = useState<number | null>(null);
  const [codeText, setCodeText] = useState('');
  const [reasoningText, setReasoningText] = useState('');

  // Evaluation results
  const [stepResult, setStepResult] = useState<StepEvaluationResult | null>(null);
  const [finalResult, setFinalResult] = useState<StepEvaluationResult | null>(null);
  const [appliedPassport, setAppliedPassport] = useState<PassportDocument | null>(null);

  // Initialize assessment session
  useEffect(() => {
    if (!skillName) return;

    setLoading(true);
    setError('');
    setSessionId(null);
    setCurrentTask(null);
    setStageIdx(0);
    setCurrentDifficulty(2);
    setSelectedOption(null);
    setCodeText('');
    setReasoningText('');
    setStepResult(null);
    setFinalResult(null);
    setAppliedPassport(null);

    // Look up skill verdict in passport for repo-seeded difficulty
    const skillItem = passport?.skills.find(
      s => s.name.toLowerCase() === skillName.toLowerCase()
    );

    postJson<{ session_id: string; task: PublicTaskItem }>('/api/assessment/start', {
      skill: skillName,
      initial_verdict: skillItem?.verdict,
      passport_hash: passport?.tamper_proof_hash || ''
    })
      .then(res => {
        setSessionId(res.session_id);
        setCurrentTask(res.task);
        setCurrentDifficulty(res.task.difficulty);
        setCodeText(res.task.starter_code || '');
      })
      .catch(err => {
        setError(err.message || 'Failed to initialize technical assessment.');
      })
      .finally(() => {
        setLoading(false);
      });
  }, [skillName]);

  if (!skillName) return null;

  // Handle Tab key in code textarea for comfortable editing
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const target = e.currentTarget;
      const start = target.selectionStart;
      const end = target.selectionEnd;
      const value = target.value;
      const newValue = value.substring(0, start) + '    ' + value.substring(end);
      setCodeText(newValue);
      setTimeout(() => {
        target.selectionStart = target.selectionEnd = start + 4;
      }, 0);
    }
  };

  const handleStepSubmit = async () => {
    if (!sessionId || !currentTask) return;
    setSubmitting(true);
    setError('');

    try {
      const res = await postJson<StepEvaluationResult>('/api/assessment/submit-step', {
        session_id: sessionId,
        task_id: currentTask.task_id,
        selected_option: currentTask.stage_type === 'comprehension' ? selectedOption : null,
        submitted_code: currentTask.stage_type === 'debugging' || currentTask.stage_type === 'coding' ? codeText : null,
        reasoning_text: currentTask.stage_type === 'reasoning' ? reasoningText : null
      });

      setStepResult(res);

      if (res.is_complete) {
        setFinalResult(res);
        // Automatically apply the final grade and audit trace to passport
        if (passport && res.final_grade) {
          try {
            const updated = await postJson<PassportDocument>('/api/quiz/apply', {
              passport,
              skill: skillName,
              grade: res.final_grade,
              percentage: res.final_weighted_score,
              trajectory: res.trajectory
            });
            setAppliedPassport(updated);
            onPassportUpdated?.(updated);
          } catch (applyErr) {
            console.error('Failed to apply assessment score to passport:', applyErr);
          }
        }
      }
    } catch (e) {
      setError((e as Error).message || 'Failed to evaluate step.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleNextStage = () => {
    if (!stepResult?.next_task) return;
    const nextTask = stepResult.next_task;
    setCurrentTask(nextTask);
    setStageIdx(prev => prev + 1);
    if (stepResult.next_difficulty) {
      setCurrentDifficulty(stepResult.next_difficulty);
    }
    setSelectedOption(null);
    setCodeText(nextTask.starter_code || '');
    setReasoningText('');
    setStepResult(null);
  };

  const wordCount = reasoningText.trim().split(/\s+/).filter(Boolean).length;
  const updatedSkill = appliedPassport?.skills.find(
    s => s.name.toLowerCase() === skillName.toLowerCase()
  );

  const getTierColor = (tier: DifficultyTier) => {
    switch (tier) {
      case 1:
        return {
          badge: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
          dot: 'bg-emerald-400',
          label: 'Tier 1 · Foundational (1.0x)'
        };
      case 2:
        return {
          badge: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30',
          dot: 'bg-indigo-400',
          label: 'Tier 2 · Intermediate (1.5x)'
        };
      case 3:
        return {
          badge: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
          dot: 'bg-amber-400',
          label: 'Tier 3 · Advanced (2.2x)'
        };
    }
  };

  const tierInfo = getTierColor(currentDifficulty);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="flex max-h-[92vh] w-full max-w-3xl flex-col rounded-2xl border border-white/10 bg-[#121316] shadow-2xl shadow-black/80 overflow-hidden">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-white/10 bg-white/[0.02] px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 shadow-md shadow-indigo-500/20">
              <Zap className="h-5 w-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-heading text-lg font-bold text-white">{skillName} Technical Assessment</h2>
                <span className="rounded-full bg-indigo-500/10 px-2.5 py-0.5 text-[11px] font-medium text-indigo-300 border border-indigo-500/20">
                  Adaptive Engine
                </span>
              </div>
              <p className="text-xs text-zinc-400">
                Outlier-style staircase evaluation · AST-sandboxed verification
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-zinc-400 transition hover:bg-white/10 hover:text-white"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Stage Stepper & Live Difficulty Indicator */}
        <div className="border-b border-white/10 bg-black/40 px-6 py-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            {/* Stepper Steps */}
            <div className="flex items-center gap-2 sm:gap-3">
              {STAGES.map((s, idx) => {
                const Icon = s.icon;
                const isCurrent = idx === stageIdx && !finalResult;
                const isPassed = idx < stageIdx || (finalResult && idx <= stageIdx);
                return (
                  <div key={s.type} className="flex items-center gap-1.5">
                    <div
                      className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium transition ${
                        isCurrent
                          ? 'border border-indigo-400/40 bg-indigo-500/20 text-indigo-200 shadow-sm shadow-indigo-500/20'
                          : isPassed
                          ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20'
                          : 'bg-white/5 text-zinc-500 border border-transparent'
                      }`}
                    >
                      {isPassed ? (
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                      ) : (
                        <Icon className={`h-3.5 w-3.5 ${isCurrent ? 'text-indigo-400' : 'text-zinc-500'}`} />
                      )}
                      <span>{s.label}</span>
                    </div>
                    {idx < STAGES.length - 1 && <span className="text-xs text-zinc-600">→</span>}
                  </div>
                );
              })}
            </div>

            {/* Dynamic Difficulty Badge */}
            <div className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold ${tierInfo.badge}`}>
              <span className={`h-2 w-2 rounded-full animate-pulse ${tierInfo.dot}`} />
              <span>{tierInfo.label}</span>
            </div>
          </div>
        </div>

        {/* Main Content Area */}
        <div className="flex-1 space-y-5 overflow-y-auto p-6 text-sm">
          {error && (
            <div className="flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-200">
              <AlertCircle className="h-5 w-5 shrink-0 text-red-400" />
              <div>
                <p className="font-semibold text-red-300">Evaluation Notice</p>
                <p className="text-xs text-red-200/90 mt-0.5">{error}</p>
              </div>
            </div>
          )}

          {loading && (
            <div className="flex flex-col items-center justify-center py-16 space-y-3">
              <Loader2 className="h-8 w-8 animate-spin text-indigo-400" />
              <p className="text-sm text-zinc-400">Initializing adaptive test harness for {skillName}...</p>
            </div>
          )}

          {/* FINAL COMPLETION WORKBENCH */}
          {finalResult && (
            <div className="space-y-5">
              <div className="rounded-2xl border border-emerald-400/30 bg-gradient-to-b from-emerald-500/15 to-emerald-950/20 p-6 space-y-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-2xl font-bold font-mono">
                      {finalResult.final_grade}
                    </div>
                    <div>
                      <h3 className="font-heading text-lg font-bold text-white flex items-center gap-2">
                        <span>Assessment Complete</span>
                        <Sparkles className="h-4 w-4 text-emerald-400" />
                      </h3>
                      <p className="text-xs text-emerald-300/90">
                        Weighted Mastery: {finalResult.final_weighted_score}% · Grade {finalResult.final_grade} Awarded
                      </p>
                    </div>
                  </div>
                  <span className="rounded-lg bg-emerald-500/20 px-3 py-1 font-mono text-xs font-bold text-emerald-300 border border-emerald-500/30">
                    Grade {finalResult.final_grade}
                  </span>
                </div>

                {/* Trajectory Breakdown */}
                {finalResult.trajectory && (
                  <div className="rounded-xl border border-white/10 bg-black/40 p-3 space-y-1">
                    <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                      Staircase Adaptive Trajectory
                    </p>
                    <p className="font-mono text-xs text-emerald-300 font-medium">
                      {finalResult.trajectory}
                    </p>
                  </div>
                )}

                {/* Updated Points Display */}
                {updatedSkill ? (
                  <div className="rounded-xl bg-white/5 p-3.5 text-xs text-zinc-300 space-y-1 border border-white/5">
                    <p className="font-medium text-white">
                      Skill Points Updated: Evidence {updatedSkill.evidence_score}/10 × Grade {finalResult.final_grade} = <strong className="text-emerald-300 text-sm font-mono">{updatedSkill.final_points} / 100 points</strong>
                    </p>
                    <p className="text-zinc-400">
                      Overall Audit Score and tamper-proof HMAC-SHA256 signature re-signed deterministically.
                    </p>
                  </div>
                ) : (
                  <p className="text-xs text-zinc-400">
                    Skill points computed: Evidence Score × Grade Weight = Real-time points update applied.
                  </p>
                )}
              </div>

              <div className="flex justify-end pt-2">
                <button
                  onClick={onClose}
                  className="rounded-xl bg-indigo-500 px-6 py-2.5 font-semibold text-white shadow-lg shadow-indigo-500/20 hover:bg-indigo-400 transition"
                >
                  Done & Return to Passport
                </button>
              </div>
            </div>
          )}

          {/* ACTIVE STEP WORKBENCH */}
          {!loading && !finalResult && currentTask && (
            <div className="space-y-5">
              {/* Task Header & Prompt */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-indigo-400">
                    Stage {stageIdx + 1} of 4 · {currentTask.stage_type.toUpperCase()}
                  </span>
                  <span className="text-xs text-zinc-400 font-mono">
                    ID: {currentTask.task_id}
                  </span>
                </div>
                <h3 className="text-base font-semibold text-white leading-relaxed">
                  {currentTask.prompt}
                </h3>
              </div>

              {/* 1. COMPREHENSION WORKBENCH */}
              {currentTask.stage_type === 'comprehension' && (
                <div className="space-y-4">
                  {currentTask.starter_code && (
                    <div className="overflow-hidden rounded-xl border border-white/10 bg-[#0d0e11]">
                      <div className="flex items-center gap-1.5 border-b border-white/10 bg-white/[0.03] px-3.5 py-2 text-xs text-zinc-400 font-mono">
                        <Terminal className="h-3.5 w-3.5 text-zinc-500" />
                        <span>code snippet</span>
                      </div>
                      <pre className="p-4 font-mono text-xs text-zinc-200 overflow-x-auto leading-relaxed">
                        {currentTask.starter_code}
                      </pre>
                    </div>
                  )}

                  <div className="grid gap-2.5 pt-1">
                    {currentTask.options?.map((opt, idx) => {
                      const isChosen = selectedOption === idx;
                      return (
                        <button
                          key={idx}
                          id={`comprehension-option-${idx}`}
                          disabled={submitting || !!stepResult}
                          onClick={() => setSelectedOption(idx)}
                          className={`flex items-start gap-3 rounded-xl border p-3.5 text-left text-sm transition ${
                            isChosen
                              ? 'border-indigo-400 bg-indigo-500/15 text-white shadow-sm shadow-indigo-500/20'
                              : 'border-white/10 bg-white/[0.02] text-zinc-300 hover:border-white/20 hover:bg-white/[0.05]'
                          } ${stepResult ? 'opacity-80' : ''}`}
                        >
                          <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-xs font-mono font-medium ${
                            isChosen
                              ? 'border-indigo-400 bg-indigo-500 text-white'
                              : 'border-white/20 text-zinc-400'
                          }`}>
                            {String.fromCharCode(65 + idx)}
                          </span>
                          <span className="leading-snug">{opt}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* 2 & 3. DEBUGGING & CODING WORKBENCH */}
              {(currentTask.stage_type === 'debugging' || currentTask.stage_type === 'coding') && (
                <div className="space-y-4">
                  <div className="overflow-hidden rounded-xl border border-white/10 bg-[#0a0b0d] shadow-inner">
                    <div className="flex items-center justify-between border-b border-white/10 bg-white/[0.03] px-4 py-2.5">
                      <div className="flex items-center gap-2 text-xs font-mono text-zinc-400">
                        <Terminal className="h-3.5 w-3.5 text-indigo-400" />
                        <span>solution.py</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setCodeText(currentTask.starter_code || '')}
                        disabled={submitting || !!stepResult}
                        className="flex items-center gap-1 text-xs text-zinc-400 hover:text-white transition"
                      >
                        <RefreshCw className="h-3 w-3" />
                        <span>Reset code</span>
                      </button>
                    </div>

                    <textarea
                      id="code-editor-textarea"
                      value={codeText}
                      onChange={e => setCodeText(e.target.value)}
                      onKeyDown={handleKeyDown}
                      disabled={submitting || !!stepResult}
                      rows={11}
                      spellCheck={false}
                      className="w-full bg-transparent p-4 font-mono text-xs text-zinc-100 placeholder-zinc-600 focus:outline-none resize-y leading-relaxed"
                      placeholder="# Write your implementation here..."
                    />
                  </div>

                  {/* Visible Sample Tests */}
                  {currentTask.sample_tests && currentTask.sample_tests.length > 0 && (
                    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3.5 space-y-1.5">
                      <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                        Sample Verification Assertions
                      </p>
                      <div className="space-y-1">
                        {currentTask.sample_tests.map((st, i) => (
                          <p key={i} className="font-mono text-xs text-zinc-300 bg-black/40 px-2.5 py-1.5 rounded-lg border border-white/5">
                            {st}
                          </p>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* 4. REASONING WORKBENCH */}
              {currentTask.stage_type === 'reasoning' && (
                <div className="space-y-4">
                  <div className="rounded-xl border border-white/10 bg-[#0a0b0d] p-3 space-y-2">
                    <div className="flex items-center justify-between text-xs text-zinc-400">
                      <span className="font-medium">Technical Reasoning & Architecture Rationale</span>
                      <span className={`font-mono text-xs font-semibold ${wordCount >= 12 ? 'text-emerald-400' : 'text-amber-400'}`}>
                        {wordCount} words {wordCount < 12 ? '(Min: 12)' : '✓'}
                      </span>
                    </div>

                    <textarea
                      id="reasoning-textarea"
                      value={reasoningText}
                      onChange={e => setReasoningText(e.target.value)}
                      disabled={submitting || !!stepResult}
                      rows={7}
                      className="w-full rounded-lg border border-white/5 bg-black/40 p-3.5 text-xs text-zinc-100 placeholder-zinc-500 focus:border-indigo-500/50 focus:outline-none"
                      placeholder="Explain root cause, execution flow, thread/process boundaries, and architectural trade-offs..."
                    />
                  </div>

                  <p className="text-xs text-zinc-400 italic">
                    Note: Graded against deterministic rubric concept clusters and prompt injection defenses.
                  </p>
                </div>
              )}

              {/* STEP FEEDBACK & TEST CASES CONSOLE */}
              {stepResult && (
                <div className={`rounded-xl border p-4 space-y-3 ${
                  stepResult.passed
                    ? 'border-emerald-500/30 bg-emerald-500/10'
                    : 'border-amber-500/30 bg-amber-500/10'
                }`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {stepResult.passed ? (
                        <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                      ) : (
                        <XCircle className="h-5 w-5 text-amber-400" />
                      )}
                      <p className="font-semibold text-white">
                        {stepResult.passed ? 'Step Passed Successfully' : 'Step Incomplete / Low Score'}
                      </p>
                    </div>
                    <span className="text-xs font-mono font-bold px-2.5 py-0.5 rounded bg-black/40 text-zinc-300">
                      Score: {Math.round(stepResult.step_score * 100)}%
                    </span>
                  </div>

                  <p className="text-xs text-zinc-300">{stepResult.feedback}</p>

                  {/* Test Cases Results */}
                  {stepResult.test_results && stepResult.test_results.length > 0 && (
                    <div className="space-y-1.5 pt-1">
                      <p className="text-xs font-semibold text-zinc-400">Automated Hidden Test Assertions:</p>
                      <div className="grid gap-1.5 max-h-40 overflow-y-auto">
                        {stepResult.test_results.map((tr, i) => (
                          <div
                            key={i}
                            className={`flex items-center justify-between rounded-lg px-3 py-1.5 text-xs font-mono border ${
                              tr.passed
                                ? 'border-emerald-500/20 bg-emerald-500/5 text-emerald-300'
                                : 'border-red-500/20 bg-red-500/5 text-red-300'
                            }`}
                          >
                            <span>Test Case #{tr.test_case}</span>
                            <span>{tr.passed ? 'PASSED ✓' : tr.error || 'FAILED ✗'}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Rubric Hits Badges */}
                  {stepResult.rubric_hits && stepResult.rubric_hits.length > 0 && (
                    <div className="space-y-1.5 pt-1">
                      <p className="text-xs font-semibold text-zinc-400">Verified Concept Clusters:</p>
                      <div className="flex flex-wrap gap-2">
                        {stepResult.rubric_hits.map((hit, i) => (
                          <span
                            key={i}
                            className="inline-flex items-center gap-1 rounded-full bg-emerald-500/20 border border-emerald-500/30 px-3 py-0.5 text-xs font-medium text-emerald-300"
                          >
                            <CheckCircle2 className="h-3 w-3" />
                            {hit}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Difficulty Transition Notice */}
                  {stepResult.next_difficulty && (
                    <div className="flex items-center gap-2 pt-1 text-xs text-zinc-400 border-t border-white/5">
                      <span>Next Difficulty Shift:</span>
                      <span className="font-semibold text-white">
                        {stepResult.next_difficulty > currentDifficulty
                          ? 'Elevating to Tier 3 (Advanced) ↗'
                          : stepResult.next_difficulty < currentDifficulty
                          ? 'Adjusting to Tier 1 (Foundational) ↘'
                          : 'Maintaining current Tier'}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer Controls */}
        {!loading && !finalResult && currentTask && (
          <div className="flex items-center justify-between border-t border-white/10 bg-white/[0.02] px-6 py-4">
            <span className="text-xs text-zinc-400">
              {currentTask.stage_type === 'comprehension'
                ? selectedOption !== null ? 'Answer selected' : 'Select an option'
                : currentTask.stage_type === 'reasoning'
                ? `${wordCount} words drafted`
                : 'Sandboxed code runner active'}
            </span>

            <div className="flex items-center gap-3">
              {stepResult && !stepResult.is_complete ? (
                <button
                  id="next-stage-btn"
                  onClick={handleNextStage}
                  className="flex items-center gap-2 rounded-xl bg-indigo-500 px-5 py-2.5 font-semibold text-white shadow-lg shadow-indigo-500/20 hover:bg-indigo-400 transition"
                >
                  <span>Proceed to Stage {stageIdx + 2}</span>
                  <ArrowRight className="h-4 w-4" />
                </button>
              ) : (
                <button
                  id="submit-step-btn"
                  onClick={handleStepSubmit}
                  disabled={
                    submitting ||
                    !!stepResult ||
                    (currentTask.stage_type === 'comprehension' && selectedOption === null) ||
                    ((currentTask.stage_type === 'debugging' || currentTask.stage_type === 'coding') && !codeText.trim()) ||
                    (currentTask.stage_type === 'reasoning' && !reasoningText.trim())
                  }
                  className="flex items-center gap-2 rounded-xl bg-indigo-500 px-5 py-2.5 font-semibold text-white shadow-lg shadow-indigo-500/20 hover:bg-indigo-400 disabled:opacity-40 transition"
                >
                  {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
                  <span>
                    {submitting
                      ? 'Verifying against Sandbox...'
                      : currentTask.stage_type === 'comprehension'
                      ? 'Submit Choice'
                      : currentTask.stage_type === 'reasoning'
                      ? 'Grade Reasoning'
                      : 'Run & Verify Tests'}
                  </span>
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
