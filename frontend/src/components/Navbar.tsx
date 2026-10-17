import React from 'react';
import { ShieldCheck, UserCheck, AlertTriangle, TrendingUp, ShieldAlert, FileText, CheckCircle2 } from 'lucide-react';

interface NavbarProps {
  currentPersona: string;
  onSelectPersona: (personaKey: string) => void;
  activeView: 'recruiter' | 'student';
  onSelectView: (view: 'recruiter' | 'student') => void;
  onOpenUpload: () => void;
  onOpenSecurityModal: () => void;
  tamperProofHash: string;
  hasSecurityAlerts: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentPersona,
  onSelectPersona,
  activeView,
  onSelectView,
  onOpenUpload,
  onOpenSecurityModal,
  tamperProofHash,
  hasSecurityAlerts
}) => {
  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-[#0a0d14]/80 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Golden Rule Tagline */}
          <div className="flex items-center gap-3">
            <div className="relative flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-500 shadow-lg shadow-emerald-500/20">
              <ShieldCheck className="w-6 h-6 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg text-white tracking-tight">Skill Passport</span>
                <span className="text-[10px] uppercase font-semibold tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  Verifiable Ground-Truth
                </span>
              </div>
              <p className="text-xs text-slate-400 hidden sm:block">
                "LLM extracts text, published rules score evidence."
              </p>
            </div>
          </div>

          {/* Persona Switcher Buttons */}
          <div className="hidden lg:flex items-center gap-1.5 p-1 bg-slate-900/80 border border-white/5 rounded-xl">
            <button
              onClick={() => onSelectPersona('priya')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                currentPersona === 'priya'
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-white/5'
              }`}
            >
              <UserCheck className="w-3.5 h-3.5 text-emerald-400" />
              <span>Priya S. (Honest)</span>
            </button>

            <button
              onClick={() => onSelectPersona('alex')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                currentPersona === 'alex'
                  ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-white/5'
              }`}
            >
              <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
              <span>Alex R. (Spammer)</span>
            </button>

            <button
              onClick={() => onSelectPersona('jordan')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                currentPersona === 'jordan'
                  ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-white/5'
              }`}
            >
              <TrendingUp className="w-3.5 h-3.5 text-blue-400" />
              <span>Jordan K. (Learner)</span>
            </button>

            <button
              onClick={() => onSelectPersona('redteam')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                currentPersona === 'redteam'
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-white/5'
              }`}
            >
              <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
              <span>Red-Team Attack</span>
            </button>
          </div>

          {/* Right Action Controls */}
          <div className="flex items-center gap-2.5">
            {/* View Switcher: Recruiter vs Student */}
            <div className="flex items-center bg-slate-900 border border-white/10 rounded-lg p-0.5">
              <button
                onClick={() => onSelectView('recruiter')}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
                  activeView === 'recruiter'
                    ? 'bg-white/15 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Recruiter View
              </button>
              <button
                onClick={() => onSelectView('student')}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
                  activeView === 'student'
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Student Portal
              </button>
            </div>

            {/* Custom Upload Button */}
            <button
              onClick={onOpenUpload}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-all shadow-sm shadow-emerald-600/30"
            >
              <FileText className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Upload Resume</span>
            </button>

            {/* Security Alert Badge */}
            {hasSecurityAlerts && (
              <button
                onClick={onOpenSecurityModal}
                className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-bold rounded-lg bg-rose-500/20 text-rose-300 border border-rose-500/40 animate-pulse"
                title="Security threat quarantined"
              >
                <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
                <span className="hidden md:inline">Injection Blocked</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};
