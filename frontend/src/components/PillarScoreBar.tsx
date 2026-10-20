import React from 'react';
import { Award, Code2, FileText, CheckCircle2, AlertCircle } from 'lucide-react';
import { PillarScores } from '../lib/types';

interface PillarScoreBarProps {
  pillarScores?: PillarScores | null;
  overallScore: number;
}

export const PillarScoreBar: React.FC<PillarScoreBarProps> = ({ pillarScores, overallScore }) => {
  if (!pillarScores) return null;

  const weights = pillarScores.weights_used || {};
  const codeWeight = Math.round((weights.code || 0) * 100);
  const resumeWeight = Math.round((weights.resume || 0) * 100);
  const certWeight = Math.round((weights.certs || 0) * 100);
  const quizWeight = Math.round((weights.quiz || 0) * 100);

  return (
    <div className="rounded-xl border border-white/10 bg-[#161719] p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-3">
        <div>
          <h3 className="font-heading text-sm font-semibold uppercase tracking-wider text-zinc-300">
            Multi-Signal Rubric · Balanced Pillar Scoring
          </h3>
          <p className="text-xs text-zinc-400">
            Scores are balanced across authentic code ground-truth, resume claims, verified certificates, and mandatory skill challenge tests.
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-indigo-400/30 bg-indigo-500/10 px-3 py-1 text-xs font-semibold text-indigo-300">
          <span>Overall: {pillarScores.overall_score || overallScore}/100</span>
        </div>
      </div>

      {/* Visual Pillar Cards */}
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {/* Pillar 1: Code Profile */}
        <div className="rounded-lg border border-white/5 bg-white/[0.03] p-3">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-medium text-emerald-400">
              <Code2 className="h-3.5 w-3.5" /> Code Profile
            </span>
            <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-[10px] font-bold text-emerald-300">
              {codeWeight}% wt
            </span>
          </div>
          <div className="mt-2 flex items-baseline gap-1">
            <span className="text-xl font-bold text-zinc-100">
              {pillarScores.code_score != null ? `${pillarScores.code_score}` : '—'}
            </span>
            <span className="text-xs text-zinc-500">/100</span>
          </div>
          <div className="mt-1 text-[11px] text-zinc-400">
            Git blame & tests
          </div>
        </div>

        {/* Pillar 2: Resume / Bio */}
        <div className="rounded-lg border border-white/5 bg-white/[0.03] p-3">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-medium text-sky-400">
              <FileText className="h-3.5 w-3.5" /> Resume / Bio
            </span>
            <span className="rounded bg-sky-500/20 px-1.5 py-0.5 text-[10px] font-bold text-sky-300">
              {resumeWeight ? `${resumeWeight}% wt` : 'Omitted'}
            </span>
          </div>
          <div className="mt-2 flex items-baseline gap-1">
            <span className="text-xl font-bold text-zinc-100">
              {pillarScores.resume_score != null ? `${pillarScores.resume_score}` : '—'}
            </span>
            <span className="text-xs text-zinc-500">{pillarScores.resume_score != null ? '/100' : 'None'}</span>
          </div>
          <div className="mt-1 text-[11px] text-zinc-400">
            {pillarScores.resume_score != null ? 'Claims alignment' : 'Weight shifted to code'}
          </div>
        </div>

        {/* Pillar 3: Certificates */}
        <div className="rounded-lg border border-white/5 bg-white/[0.03] p-3">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-medium text-amber-400">
              <Award className="h-3.5 w-3.5" /> Certificates
            </span>
            <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-bold text-amber-300">
              {certWeight ? `${certWeight}% wt` : 'None'}
            </span>
          </div>
          <div className="mt-2 flex items-baseline gap-1">
            <span className="text-xl font-bold text-zinc-100">
              {pillarScores.cert_score != null ? `${pillarScores.cert_score}` : '—'}
            </span>
            <span className="text-xs text-zinc-500">{pillarScores.cert_score != null ? '/100' : 'None'}</span>
          </div>
          <div className="mt-1 text-[11px] text-zinc-400">
            {pillarScores.cert_score != null ? 'Verified credentials' : 'Optional bonus'}
          </div>
        </div>

        {/* Pillar 4: Skill Challenge Quiz */}
        <div className="rounded-lg border border-white/5 bg-white/[0.03] p-3">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-medium text-purple-400">
              <CheckCircle2 className="h-3.5 w-3.5" /> Skill Quizzes
            </span>
            <span className="rounded bg-purple-500/20 px-1.5 py-0.5 text-[10px] font-bold text-purple-300">
              {quizWeight}% wt
            </span>
          </div>
          <div className="mt-2 flex items-baseline gap-1">
            <span className="text-xl font-bold text-zinc-100">
              {pillarScores.quiz_score != null ? `${pillarScores.quiz_score}` : '—'}
            </span>
            <span className="text-xs text-zinc-500">/100</span>
          </div>
          <div className="mt-1 text-[11px] text-zinc-400">
            Mandatory test challenge
          </div>
        </div>
      </div>

      {/* Proportional Contribution Bar */}
      <div className="mt-4">
        <div className="flex h-2 w-full overflow-hidden rounded-full bg-white/10">
          {codeWeight > 0 && (
            <div
              style={{ width: `${codeWeight}%` }}
              className="bg-emerald-500 transition-all duration-300"
              title={`Code profile contribution (${codeWeight}%)`}
            />
          )}
          {resumeWeight > 0 && (
            <div
              style={{ width: `${resumeWeight}%` }}
              className="bg-sky-500 transition-all duration-300"
              title={`Resume claims contribution (${resumeWeight}%)`}
            />
          )}
          {certWeight > 0 && (
            <div
              style={{ width: `${certWeight}%` }}
              className="bg-amber-500 transition-all duration-300"
              title={`Certificates contribution (${certWeight}%)`}
            />
          )}
          {quizWeight > 0 && (
            <div
              style={{ width: `${quizWeight}%` }}
              className="bg-purple-500 transition-all duration-300"
              title={`Mandatory quiz contribution (${quizWeight}%)`}
            />
          )}
        </div>
        <div className="mt-2 flex items-center justify-between text-[11px] text-zinc-500">
          <span>Active weights: Code {codeWeight}% · Quiz {quizWeight}% {resumeWeight > 0 ? `· Resume ${resumeWeight}%` : ''} {certWeight > 0 ? `· Certs ${certWeight}%` : ''}</span>
          <span>Adaptive balancing active</span>
        </div>
      </div>
    </div>
  );
};
