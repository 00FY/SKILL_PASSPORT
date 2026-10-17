import React from 'react';
import {
  ShieldCheck, Terminal, UserCheck, AlertTriangle, TrendingUp,
  ShieldAlert, Upload, FileText, CheckCircle2, Lock, Cpu, Activity, HelpCircle
} from 'lucide-react';

interface SidebarProps {
  currentPersona: string;
  onSelectPersona: (personaKey: string) => void;
  activeView: 'recruiter' | 'student';
  onSelectView: (view: 'recruiter' | 'student') => void;
  onOpenUpload: () => void;
  onOpenSecurityModal: () => void;
  hasSecurityAlerts: boolean;
  activeTab: 'overview' | 'telemetry' | 'refusals' | 'simulator';
  onSelectTab: (tab: 'overview' | 'telemetry' | 'refusals' | 'simulator') => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentPersona,
  onSelectPersona,
  activeView,
  onSelectView,
  onOpenUpload,
  onOpenSecurityModal,
  hasSecurityAlerts,
  activeTab,
  onSelectTab
}) => {
  return (
    <aside className="w-64 h-screen fixed left-0 top-0 z-40 bg-[#0e0e0f] border-r border-[#1B1C1E] flex flex-col justify-between hidden md:flex">
      {/* Brand & Subtitle */}
      <div>
        <div className="p-4 border-b border-[#1B1C1E] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded bg-[#1c1b1d] border border-[#2a2a2b] flex items-center justify-center text-[#50d8e9]">
              <Terminal className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-heading font-extrabold text-sm tracking-tight text-[#e5e2e3]">ROMER</span>
                <span className="text-[10px] font-mono text-[#50d8e9] bg-[#50d8e9]/10 px-1 py-0.2 rounded border border-[#50d8e9]/20">
                  AUDIT
                </span>
              </div>
              <p className="font-mono text-[11px] text-[#9A9DA3]">v2.4.0-groundtruth</p>
            </div>
          </div>
          <div className="w-2 h-2 rounded-full bg-[#50d8e9] beacon-cyan animate-beacon" title="System Live" />
        </div>

        {/* View Switcher: Recruiter vs Student */}
        <div className="p-3 border-b border-[#1B1C1E] bg-[#101112]">
          <div className="grid grid-cols-2 gap-1 p-0.5 bg-[#0e0e0f] rounded border border-[#1B1C1E]">
            <button
              onClick={() => onSelectView('recruiter')}
              className={`py-1.5 px-2 text-[11px] font-semibold uppercase tracking-wider rounded transition-all text-center ${
                activeView === 'recruiter'
                  ? 'bg-[#1c1b1d] text-[#e5e2e3] border border-[#2a2a2b] shadow-sm'
                  : 'text-[#9A9DA3] hover:text-[#e5e2e3]'
              }`}
            >
              Recruiter
            </button>
            <button
              onClick={() => onSelectView('student')}
              className={`py-1.5 px-2 text-[11px] font-semibold uppercase tracking-wider rounded transition-all text-center ${
                activeView === 'student'
                  ? 'bg-[#5E6BFF] text-white shadow-sm'
                  : 'text-[#9A9DA3] hover:text-[#e5e2e3]'
              }`}
            >
              Student
            </button>
          </div>
        </div>

        {/* Main Navigation Links */}
        <div className="py-3 space-y-0.5">
          <div className="px-4 py-1 text-[10px] font-mono uppercase tracking-widest text-[#9A9DA3]">
            Operations
          </div>

          <button
            onClick={() => {
              onSelectView('recruiter');
              onSelectTab('overview');
            }}
            className={`w-full flex items-center gap-2.5 px-4 py-2 text-xs font-semibold tracking-wider uppercase transition-all text-left ${
              activeTab === 'overview' && activeView === 'recruiter'
                ? 'bg-[#151617] text-[#50d8e9] border-r-2 border-[#50d8e9]'
                : 'text-[#c6c5d8] hover:text-[#e5e2e3] hover:bg-[#151617]/50'
            }`}
          >
            <Activity className="w-3.5 h-3.5 text-[#50d8e9]" />
            <span>Command Center</span>
          </button>

          <button
            onClick={() => {
              onSelectView('recruiter');
              onSelectTab('telemetry');
            }}
            className={`w-full flex items-center gap-2.5 px-4 py-2 text-xs font-semibold tracking-wider uppercase transition-all text-left ${
              activeTab === 'telemetry' && activeView === 'recruiter'
                ? 'bg-[#151617] text-[#50d8e9] border-r-2 border-[#50d8e9]'
                : 'text-[#c6c5d8] hover:text-[#e5e2e3] hover:bg-[#151617]/50'
            }`}
          >
            <Cpu className="w-3.5 h-3.5 text-[#bec2ff]" />
            <span>Telemetry & Blame</span>
          </button>

          <button
            onClick={() => {
              onSelectView('recruiter');
              onSelectTab('refusals');
            }}
            className={`w-full flex items-center gap-2.5 px-4 py-2 text-xs font-semibold tracking-wider uppercase transition-all text-left ${
              activeTab === 'refusals' && activeView === 'recruiter'
                ? 'bg-[#151617] text-[#ffb4ab] border-r-2 border-[#ffb4ab]'
                : 'text-[#c6c5d8] hover:text-[#e5e2e3] hover:bg-[#151617]/50'
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5 text-[#ffb4ab]" />
            <span>Refusal Queue</span>
          </button>

          <button
            onClick={() => {
              onSelectView('student');
              onSelectTab('simulator');
            }}
            className={`w-full flex items-center gap-2.5 px-4 py-2 text-xs font-semibold tracking-wider uppercase transition-all text-left ${
              activeView === 'student' || activeTab === 'simulator'
                ? 'bg-[#151617] text-[#ffb689] border-r-2 border-[#ffb689]'
                : 'text-[#c6c5d8] hover:text-[#e5e2e3] hover:bg-[#151617]/50'
            }`}
          >
            <TrendingUp className="w-3.5 h-3.5 text-[#ffb689]" />
            <span>What-If Simulator</span>
          </button>
        </div>

        {/* Candidate Switcher (Demo Personas) */}
        <div className="py-2 border-t border-[#1B1C1E] space-y-1">
          <div className="px-4 py-1 text-[10px] font-mono uppercase tracking-widest text-[#9A9DA3]">
            Audit Profiles
          </div>

          <button
            onClick={() => onSelectPersona('priya')}
            className={`w-full flex items-center justify-between px-4 py-1.5 text-xs font-medium transition-all ${
              currentPersona === 'priya'
                ? 'bg-[#1c1b1d] text-[#e5e2e3] font-semibold border-l-2 border-[#50d8e9]'
                : 'text-[#9A9DA3] hover:text-[#e5e2e3]'
            }`}
          >
            <span className="flex items-center gap-2">
              <UserCheck className="w-3.5 h-3.5 text-[#50d8e9]" />
              <span>Priya S.</span>
            </span>
            <span className="text-[10px] font-mono text-[#50d8e9]">72% / 91%</span>
          </button>

          <button
            onClick={() => onSelectPersona('alex')}
            className={`w-full flex items-center justify-between px-4 py-1.5 text-xs font-medium transition-all ${
              currentPersona === 'alex'
                ? 'bg-[#1c1b1d] text-[#e5e2e3] font-semibold border-l-2 border-[#ffb4ab]'
                : 'text-[#9A9DA3] hover:text-[#e5e2e3]'
            }`}
          >
            <span className="flex items-center gap-2">
              <AlertTriangle className="w-3.5 h-3.5 text-[#ffb4ab]" />
              <span>Alex R.</span>
            </span>
            <span className="text-[10px] font-mono text-[#ffb4ab]">FORK / 4%</span>
          </button>

          <button
            onClick={() => onSelectPersona('jordan')}
            className={`w-full flex items-center justify-between px-4 py-1.5 text-xs font-medium transition-all ${
              currentPersona === 'jordan'
                ? 'bg-[#1c1b1d] text-[#e5e2e3] font-semibold border-l-2 border-[#bec2ff]'
                : 'text-[#9A9DA3] hover:text-[#e5e2e3]'
            }`}
          >
            <span className="flex items-center gap-2">
              <TrendingUp className="w-3.5 h-3.5 text-[#bec2ff]" />
              <span>Jordan K.</span>
            </span>
            <span className="text-[10px] font-mono text-[#bec2ff]">54%</span>
          </button>

          <button
            onClick={() => onSelectPersona('redteam')}
            className={`w-full flex items-center justify-between px-4 py-1.5 text-xs font-medium transition-all ${
              currentPersona === 'redteam'
                ? 'bg-[#93000a]/20 text-[#ffb4ab] font-semibold border-l-2 border-[#ffb4ab]'
                : 'text-[#9A9DA3] hover:text-[#e5e2e3]'
            }`}
          >
            <span className="flex items-center gap-2">
              <ShieldAlert className="w-3.5 h-3.5 text-[#ffb4ab]" />
              <span>Red-Team Attack</span>
            </span>
            <span className="text-[9px] font-mono text-[#ffb4ab] bg-[#93000a]/40 px-1 py-0.5 rounded">BLOCKED</span>
          </button>
        </div>
      </div>

      {/* Bottom Dock */}
      <div className="p-4 border-t border-[#1B1C1E] bg-[#0e0e0f] space-y-3">
        {/* Launch Audit Action Button */}
        <button
          onClick={onOpenUpload}
          className="w-full bg-[#5E6BFF] hover:bg-[#4d5bff] text-white rounded py-2 px-3 text-xs font-semibold flex items-center justify-center gap-2 transition-all shadow-md shadow-[#5E6BFF]/20"
        >
          <Upload className="w-3.5 h-3.5" />
          <span>Launch Audit Terminal</span>
        </button>

        {/* Security Quarantine Alert trigger if active */}
        {hasSecurityAlerts && (
          <button
            onClick={onOpenSecurityModal}
            className="w-full bg-[#93000a]/20 hover:bg-[#93000a]/40 border border-[#ffb4ab]/30 text-[#ffb4ab] rounded py-1.5 px-2 text-[11px] font-semibold flex items-center justify-center gap-1.5 transition-all"
          >
            <ShieldAlert className="w-3 h-3 text-[#ffb4ab]" />
            <span>1 Threat Quarantined</span>
          </button>
        )}

        {/* User / Terminal Status */}
        <div className="pt-2 border-t border-[#1B1C1E] flex items-center justify-between text-[11px] font-mono text-[#9A9DA3]">
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-[#50d8e9]"></span>
            <span>AUDIT_NODE_01</span>
          </span>
          <span className="text-[#50d8e9]">ONLINE</span>
        </div>
      </div>
    </aside>
  );
};
