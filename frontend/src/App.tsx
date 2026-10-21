import React, { useEffect, useState } from 'react';
import { AlertTriangle, Loader2 } from 'lucide-react';
import { TopBar, View } from './components/TopBar';
import { RecruiterView } from './components/RecruiterView';
import { CandidateView } from './components/CandidateView';
import { EvidenceDrawer } from './components/EvidenceDrawer';
import { QuizModal } from './components/QuizModal';
import { DefendModal } from './components/DefendModal';
import { UploadModal } from './components/UploadModal';
import { PytestGeneratorModal } from './components/PytestGeneratorModal';
import { AnalysisAlert, AnalysisNotice } from './components/AnalysisAlert';
import { PassportDocument, SkillPassportItem } from './lib/types';
import { request } from './lib/api';

export const App: React.FC = () => {
  const [passport, setPassport] = useState<PassportDocument | null>(null);
  const [loadError, setLoadError] = useState('');
  const [demoKey, setDemoKey] = useState('priya');
  const [view, setView] = useState<View>('recruiter');

  const [selectedSkill, setSelectedSkill] = useState<SkillPassportItem | null>(null);
  const [quizSkill, setQuizSkill] = useState<string | null>(null);
  const [defendSkill, setDefendSkill] = useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [pytestOpen, setPytestOpen] = useState(false);
  const [analysisNotice, setAnalysisNotice] = useState<AnalysisNotice | null>(null);

  const loadDemo = async (key: string) => {
    setDemoKey(key);
    setLoadError('');
    setPassport(null);
    try {
      setPassport(await request<PassportDocument>(`/api/demo/${key}`));
    } catch (e) {
      setLoadError((e as Error).message);
    }
  };

  useEffect(() => { loadDemo('priya'); }, []);

  return (
    <div className="min-h-screen bg-[#121314] text-zinc-100">
      <TopBar
        view={view}
        onChangeView={setView}
        demoKey={demoKey}
        onSelectDemo={loadDemo}
        onAnalyze={() => setUploadOpen(true)}
      />

      <main className="mx-auto max-w-5xl px-4 py-6">
        {loadError && (
          <div className="flex items-center gap-3 rounded-lg border border-red-400/40 bg-red-500/10 p-4 text-sm text-red-200">
            <AlertTriangle className="h-4 w-4 shrink-0" />{loadError}
          </div>
        )}
        {!passport && !loadError && <Loader2 className="mx-auto mt-16 h-6 w-6 animate-spin text-zinc-500" />}
        {passport && (view === 'recruiter'
          ? <RecruiterView passport={passport} onOpenSkill={setSelectedSkill} />
          : <CandidateView passport={passport} onOpenPytest={() => setPytestOpen(true)} />)}
      </main>

      <footer className="pb-8 text-center text-xs text-zinc-500">
        Skills are scored from the candidate's code by fixed rules. An AI model only reads the resume text.
      </footer>

      <EvidenceDrawer
        skill={selectedSkill}
        auditLog={passport?.audit_log}
        onClose={() => setSelectedSkill(null)}
        onOpenQuiz={name => { setSelectedSkill(null); setQuizSkill(name); }}
        onOpenDefend={name => { setSelectedSkill(null); setDefendSkill(name); }}
      />
      <QuizModal
        skillName={quizSkill}
        passport={passport}
        onClose={() => setQuizSkill(null)}
        onPassportUpdated={p => setPassport(p)}
      />
      <DefendModal
        skillName={defendSkill}
        passport={passport}
        onClose={() => setDefendSkill(null)}
        onPassportUpdated={p => setPassport(p)}
      />
      <UploadModal
        isOpen={uploadOpen}
        onAlert={setAnalysisNotice}
        onClose={() => setUploadOpen(false)}
        onCustomVerified={p => {
          setPassport(p); setDemoKey('custom'); setView('recruiter');
          const problems = (p.warnings || []).filter(w => /github|could not clone|cloning .*timed out/i.test(w));
          if (problems.length) setAnalysisNotice({
            title: 'Analysis completed with GitHub warnings',
            messages: [...new Set(problems)],
          });
        }}
      />
      <PytestGeneratorModal isOpen={pytestOpen} onClose={() => setPytestOpen(false)} />
      <AnalysisAlert notice={analysisNotice} onClose={() => setAnalysisNotice(null)} />
    </div>
  );
};

export default App;
