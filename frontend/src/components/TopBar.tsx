import React from 'react';
import { ShieldCheck, Upload } from 'lucide-react';

export type View = 'recruiter' | 'candidate';

export const DEMOS = [
  { key: 'priya', label: 'Priya - honest engineer' },
  { key: 'alex', label: 'Alex - forked repository' },
  { key: 'jordan', label: 'Jordan - early learner' },
  { key: 'redteam', label: 'Red team - injection attack' },
];

interface TopBarProps {
  view: View;
  onChangeView: (view: View) => void;
  demoKey: string;
  onSelectDemo: (key: string) => void;
  onAnalyze: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({ view, onChangeView, demoKey, onSelectDemo, onAnalyze }) => (
  <header className="sticky top-0 z-30 border-b border-white/10 bg-[#121314]/95 backdrop-blur">
    <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-3 px-4 py-3">
      <div className="flex items-center gap-2 mr-auto">
        <ShieldCheck className="h-5 w-5 text-emerald-300" />
        <span className="font-heading text-lg font-bold">Skill Passport</span>
      </div>

      <div className="flex rounded-lg border border-white/10 p-0.5 text-sm">
        {(['recruiter', 'candidate'] as View[]).map(v => (
          <button
            key={v}
            onClick={() => onChangeView(v)}
            className={`rounded-md px-3 py-1.5 ${view === v ? 'bg-white/10 text-white' : 'text-zinc-400 hover:text-white'}`}
          >
            {v === 'recruiter' ? 'Recruiter view' : 'Candidate view'}
          </button>
        ))}
      </div>

      <select
        value={demoKey}
        onChange={e => onSelectDemo(e.target.value)}
        className="rounded-lg border border-white/10 bg-[#1a1b1d] px-3 py-2 text-sm text-zinc-200"
        aria-label="Load a demo passport"
      >
        {demoKey === 'custom' && <option value="custom">Your analysis</option>}
        {DEMOS.map(d => <option key={d.key} value={d.key}>Demo: {d.label}</option>)}
      </select>

      <button
        onClick={onAnalyze}
        className="flex items-center gap-2 rounded-lg bg-indigo-500 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-400"
      >
        <Upload className="h-4 w-4" />
        Analyze a resume
      </button>
    </div>
  </header>
);
