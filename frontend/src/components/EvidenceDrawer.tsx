import React, { useState } from 'react';
import {
  X, GitBranch, GitCommit, ShieldCheck, Terminal,
  ExternalLink, FileCode, CheckCircle, Award, HelpCircle, Copy
} from 'lucide-react';
import { SkillPassportItem, RunAuditLog } from '../data/mockData';

interface EvidenceDrawerProps {
  skill: SkillPassportItem | null;
  candidateName: string;
  auditLog?: RunAuditLog;
  isOpen: boolean;
  onClose: () => void;
  onOpenQuiz: (skillName: string) => void;
}

export const EvidenceDrawer: React.FC<EvidenceDrawerProps> = ({
  skill,
  candidateName,
  auditLog,
  isOpen,
  onClose,
  onOpenQuiz
}) => {
  if (!isOpen || !skill) return null;

  const [snippetCopied, setSnippetCopied] = useState<boolean>(false);

  const getVerdictBadge = (verdict: string) => {
    switch (verdict) {
      case 'VERIFIED':
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#50d8e9]/10 text-[#50d8e9] border border-[#50d8e9]/20 uppercase">VERIFIED</span>;
      case 'PARTIALLY_SUPPORTED':
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#ffb689]/10 text-[#ffb689] border border-[#ffb689]/20 uppercase">PARTIAL</span>;
      case 'CONTRADICTED':
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#93000a]/20 text-[#ffb4ab] border border-[#ffb4ab]/30 uppercase">CONTRADICTED</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#201f21] text-[#9A9DA3] border border-[#2a2a2b] uppercase">CLAIMED ONLY</span>;
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/75 backdrop-blur-sm transition-opacity">
      <div className="absolute inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-xl bg-[#101112] border-l border-[#1B1C1E] shadow-2xl flex flex-col h-full">
          {/* Header */}
          <div className="p-4 px-6 border-b border-[#1B1C1E] flex items-center justify-between bg-[#0e0e0f]">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded bg-[#1c1b1d] border border-[#2a2a2b] flex items-center justify-center text-[#50d8e9] font-mono font-bold text-sm">
                {skill.name.charAt(0)}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="font-heading font-bold text-lg text-[#e5e2e3] tracking-tight">{skill.name}</h2>
                  {getVerdictBadge(skill.verdict)}
                </div>
                <p className="text-[11px] font-mono text-[#9A9DA3]">
                  Ground-Truth Audit Node • {candidateName}
                </p>
              </div>
            </div>
            <button
              id="btn-close-evidence-drawer"
              onClick={onClose}
              className="p-1.5 text-[#9A9DA3] hover:text-[#e5e2e3] rounded hover:bg-[#1c1b1d] transition-colors cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Drawer Body */}
          <div className="flex-1 overflow-y-auto p-5 space-y-5">
            {/* Rubric Points Breakdown */}
            <div className="bg-[#151617] rounded border border-[#1B1C1E] p-4 card-inner-glow">
              <div className="flex items-center justify-between mb-2.5">
                <span className="text-[10px] font-mono uppercase tracking-widest text-[#9A9DA3]">
                  Published Rubric Formula
                </span>
                <span className="text-[10px] font-mono text-[#50d8e9] bg-[#50d8e9]/10 px-2 py-0.5 rounded border border-[#50d8e9]/20">
                  Score = Ev (0–10) × Gr (2–10)
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2.5 text-center">
                <div className="bg-[#101112] p-2.5 rounded border border-[#1B1C1E]">
                  <p className="text-[10px] font-mono text-[#9A9DA3]">Evidence Weight</p>
                  <p className="font-heading font-extrabold text-xl text-[#e5e2e3] mt-0.5">{skill.evidence_score} <span className="text-[10px] text-[#9A9DA3]">/ 10</span></p>
                </div>
                <div className="bg-[#101112] p-2.5 rounded border border-[#1B1C1E]">
                  <p className="text-[10px] font-mono text-[#9A9DA3]">Quiz Grade</p>
                  <p className="font-heading font-extrabold text-xl text-[#50d8e9] mt-0.5">{skill.test_grade}</p>
                </div>
                <div className="bg-[#101112] p-2.5 rounded border border-[#5E6BFF]/30 bg-[#5E6BFF]/10">
                  <p className="text-[10px] font-mono text-[#bec2ff]">Final Points</p>
                  <p className="font-heading font-extrabold text-xl text-[#5E6BFF] mt-0.5">{skill.final_points} <span className="text-[10px] text-[#bec2ff]">/ 100</span></p>
                </div>
              </div>
              {skill.reasoning && (
                <p className="text-xs text-[#c6c5d8] mt-3 pt-2.5 border-t border-[#1B1C1E] flex items-start gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-[#50d8e9] shrink-0 mt-0.5" />
                  <span>{skill.reasoning}</span>
                </p>
              )}
            </div>

            {/* Git Blame Authorship Card */}
            {skill.authorship_pct !== undefined && skill.authorship_pct !== null && (
              <div className="bg-[#151617] rounded border border-[#1B1C1E] p-4 card-inner-glow space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <GitBranch className="w-3.5 h-3.5 text-[#50d8e9]" />
                    <span className="text-xs font-mono uppercase tracking-wider text-[#e5e2e3]">Git Blame Authorship</span>
                  </div>
                  <span className="text-xs font-mono font-bold text-[#50d8e9]">
                    {skill.authorship_pct}% Authored
                  </span>
                </div>
                <div className="w-full bg-[#101112] rounded-full h-1.5 overflow-hidden">
                  <div
                    className={`h-1.5 rounded-full ${
                      skill.authorship_pct > 70 ? 'bg-[#50d8e9]' : skill.authorship_pct > 30 ? 'bg-[#ffb689]' : 'bg-[#ffb4ab]'
                    }`}
                    style={{ width: `${Math.min(100, skill.authorship_pct)}%` }}
                  />
                </div>
                <p className="text-[11px] text-[#9A9DA3]">
                  Line-by-line commit authorship attribution calculated, excluding third-party vendors and locks.
                </p>
              </div>
            )}

            {/* File & Line Proof Snippet (Syntax-Highlighted Preview) */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-[#9A9DA3]">
                  <FileCode className="w-3.5 h-3.5 text-[#50d8e9]" />
                  <span>AST-Verified Code Evidence & Git Blame</span>
                </div>
                <span className="text-[10px] font-mono text-[#50d8e9] bg-[#50d8e9]/10 px-2 py-0.5 rounded border border-[#50d8e9]/20 font-bold">
                  LINE-PORCELAIN VERIFIED
                </span>
              </div>

              {/* Code Snippet Container */}
              <div className="bg-[#070708] border border-[#1B1C1E] rounded overflow-hidden shadow-inner">
                {/* Code Window Header */}
                <div className="bg-[#0e0e0f] border-b border-[#1B1C1E] px-3.5 py-2 flex items-center justify-between text-xs font-mono">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-[#ff5f56]/80 inline-block"></span>
                    <span className="w-2.5 h-2.5 rounded-full bg-[#ffbd2e]/80 inline-block"></span>
                    <span className="w-2.5 h-2.5 rounded-full bg-[#27c93f]/80 inline-block"></span>
                    <span className="text-[#e5e2e3] font-bold ml-1.5">
                      {skill.proof_snippet ? skill.proof_snippet.split(':')[0] : 'app/routes.py'}
                    </span>
                    <span className="text-[#50d8e9] text-[10px] bg-[#50d8e9]/10 px-1.5 py-0.2 rounded border border-[#50d8e9]/20">
                      {skill.proof_snippet && skill.proof_snippet.includes(':') ? skill.proof_snippet.split(':')[1] : 'L42-54'}
                    </span>
                  </div>

                  <div className="flex items-center gap-2.5">
                    <span className="text-[10px] font-mono text-[#9A9DA3] flex items-center gap-1">
                      <GitCommit className="w-3 h-3 text-[#bec2ff]" />
                      <span>c8f12a3d</span>
                    </span>
                    <button
                      type="button"
                      id="btn-copy-evidence-snippet"
                      onClick={() => {
                        const codeToCopy = skill.sample_code || (
                          skill.name.toLowerCase().includes('python')
                            ? `@router.get('/health', response_model=HealthStatus)\nasync def health_check():\n    try:\n        db_status = await check_database_connection()\n        assert db_status is True\n        return {'status': 'healthy', 'service': 'Core API'}\n    except DatabaseConnectionError as exc:\n        raise HTTPException(status_code=503, detail=str(exc))`
                            : `app = FastAPI(title='API Service', version='2.1.0')\napp.include_router(auth_router, prefix='/v1/auth')\napp.include_router(trans_router, prefix='/v1/transactions')`
                        );
                        navigator.clipboard.writeText(codeToCopy);
                        setSnippetCopied(true);
                        setTimeout(() => setSnippetCopied(false), 2000);
                      }}
                      className="text-[10px] font-mono text-[#50d8e9] hover:underline flex items-center gap-1 cursor-pointer"
                    >
                      {snippetCopied ? (
                        <span className="text-emerald-400 font-bold">Copied!</span>
                      ) : (
                        <>
                          <Copy className="w-3 h-3" />
                          <span>Copy</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* Code Window Body with Line Numbers */}
                <div className="p-3.5 font-mono text-xs overflow-x-auto leading-relaxed bg-[#070708] flex">
                  {/* Line Number Gutter */}
                  <div className="select-none text-[#454655] pr-3 text-right border-r border-[#1B1C1E] mr-3 font-mono text-[11px] space-y-0.5 shrink-0">
                    {Array.from({ length: (skill.sample_code ? skill.sample_code.split('\n').length : 8) }).map((_, i) => (
                      <div key={i}>{42 + i}</div>
                    ))}
                  </div>

                  {/* Highlighted Code Lines */}
                  <div className="flex-1 space-y-0.5 text-[11px] font-mono whitespace-pre">
                    {(skill.sample_code || (
                      skill.name.toLowerCase().includes('python')
                        ? `@router.get('/health', response_model=HealthStatus)\nasync def health_check():\n    try:\n        db_status = await check_database_connection()\n        assert db_status is True\n        return {'status': 'healthy', 'service': 'Core API'}\n    except DatabaseConnectionError as exc:\n        raise HTTPException(status_code=503, detail=str(exc))`
                        : `app = FastAPI(title='API Service', version='2.1.0')\napp.include_router(auth_router, prefix='/v1/auth')\napp.include_router(trans_router, prefix='/v1/transactions')`
                    )).split('\n').map((line, idx) => {
                      // Simple syntax highlighting regex
                      const isDecorator = line.trim().startsWith('@');
                      const isComment = line.trim().startsWith('#') || line.trim().startsWith("'''") || line.trim().startsWith('"""');

                      let coloredLine: React.ReactNode = line;
                      if (isDecorator) {
                        coloredLine = <span className="text-[#ffb689] font-bold">{line}</span>;
                      } else if (isComment) {
                        coloredLine = <span className="text-[#6e7178] italic">{line}</span>;
                      } else {
                        // Highlight keywords
                        coloredLine = (
                          <span>
                            {line.split(/(\b(?:async|def|return|try|except|raise|assert|class|import|from|with|as)\b|'.*?'|".*?")/g).map((part, pIdx) => {
                              if (['async', 'def', 'return', 'try', 'except', 'raise', 'assert', 'class', 'import', 'from', 'with', 'as'].includes(part)) {
                                return <span key={pIdx} className="text-[#bec2ff] font-bold">{part}</span>;
                              } else if ((part.startsWith("'") && part.endsWith("'")) || (part.startsWith('"') && part.endsWith('"'))) {
                                return <span key={pIdx} className="text-[#50d8e9]">{part}</span>;
                              }
                              return <span key={pIdx} className="text-[#c6c5d8]">{part}</span>;
                            })}
                          </span>
                        );
                      }

                      return (
                        <div key={idx} className="hover:bg-[#151617]/50 rounded px-1 -mx-1">
                          {coloredLine}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>

            {/* Quality Signals */}
            <div className="space-y-2">
              <span className="text-[10px] font-mono uppercase tracking-widest text-[#9A9DA3]">
                AST & Verification Signals
              </span>
              <div className="space-y-1.5">
                {skill.signals.map((sig, idx) => (
                  <div key={idx} className="flex items-start gap-2 p-2 rounded bg-[#151617] border border-[#1B1C1E] text-xs text-[#c6c5d8]">
                    <CheckCircle className="w-3.5 h-3.5 text-[#50d8e9] shrink-0 mt-0.5" />
                    <span>{sig}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Micro-Trace Audit Log */}
            {auditLog && auditLog.traces.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-[#9A9DA3]">
                    <Terminal className="w-3.5 h-3.5 text-[#bec2ff]" />
                    <span>Execution Trace (run.json)</span>
                  </div>
                  <span className="text-[10px] font-mono text-[#9A9DA3]">{auditLog.audit_id}</span>
                </div>
                <div className="bg-[#070708] border border-[#1B1C1E] rounded p-3 font-mono text-[10px] space-y-1 max-h-40 overflow-y-auto">
                  {auditLog.traces.map((trace, i) => (
                    <div key={i} className="flex items-center justify-between text-[#9A9DA3] py-0.5 border-b border-[#1B1C1E] last:border-0">
                      <span className="text-[#50d8e9] font-bold">{trace.step}</span>
                      <span className="text-[#e5e2e3] truncate max-w-[150px]">{trace.rule_applied}</span>
                      <span className="text-[#bec2ff]">{trace.verdict_reached}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Footer Action */}
          <div className="p-3.5 px-5 border-t border-[#1B1C1E] bg-[#0e0e0f] flex items-center justify-between">
            <button
              onClick={() => onOpenQuiz(skill.name)}
              className="flex items-center gap-1.5 px-3.5 py-1.5 bg-[#5E6BFF] hover:bg-[#4d5bff] text-white text-xs font-semibold rounded transition-colors shadow-sm"
            >
              <Award className="w-3.5 h-3.5" />
              <span>Launch 15-Q Challenge</span>
            </button>
            <button
              onClick={onClose}
              className="px-3 py-1.5 text-xs font-mono text-[#9A9DA3] hover:text-white rounded hover:bg-[#1c1b1d] transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
