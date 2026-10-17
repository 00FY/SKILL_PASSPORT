import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { RecruiterView } from './components/RecruiterView';
import { StudentView } from './components/StudentView';
import { EvidenceDrawer } from './components/EvidenceDrawer';
import { QuizModal } from './components/QuizModal';
import { SecurityAlertModal } from './components/SecurityAlertModal';
import { UploadModal } from './components/UploadModal';
import {
  MOCK_PRIYA, MOCK_ALEX, MOCK_JORDAN, MOCK_REDTEAM,
  PassportDocument, SkillPassportItem
} from './data/mockData';
import { ShieldCheck, Lock, Activity } from 'lucide-react';

export const App: React.FC = () => {
  const [currentPersonaKey, setCurrentPersonaKey] = useState<string>('priya');
  const [passport, setPassport] = useState<PassportDocument>(MOCK_PRIYA);
  const [activeView, setActiveView] = useState<'recruiter' | 'student'>('recruiter');
  const [activeTab, setActiveTab] = useState<'overview' | 'telemetry' | 'refusals' | 'simulator'>('overview');
  const [selectedTimeframe, setSelectedTimeframe] = useState<string>('ALL');

  // Modals
  const [selectedSkill, setSelectedSkill] = useState<SkillPassportItem | null>(null);
  const [quizSkillName, setQuizSkillName] = useState<string | null>(null);
  const [isSecurityModalOpen, setIsSecurityModalOpen] = useState<boolean>(false);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState<boolean>(false);
  const [signatureVerifiedNotice, setSignatureVerifiedNotice] = useState<boolean>(false);

  // Load persona from API with fallback
  const handleSelectPersona = async (key: string) => {
    setCurrentPersonaKey(key);

    try {
      const res = await fetch(`/api/demo/${key}`);
      if (res.ok) {
        const data = await res.json();
        setPassport(data);
        if (key === 'redteam') {
          setIsSecurityModalOpen(true);
        }
        return;
      }
    } catch {
      // Fallback
    }

    if (key === 'priya') setPassport(MOCK_PRIYA);
    else if (key === 'alex') setPassport(MOCK_ALEX);
    else if (key === 'jordan') setPassport(MOCK_JORDAN);
    else if (key === 'redteam') {
      setPassport(MOCK_REDTEAM);
      setIsSecurityModalOpen(true);
    }
  };

  const handleSimulateScore = async (toggles: Record<string, boolean>) => {
    try {
      const res = await fetch('/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_passport: passport,
          toggles
        })
      });

      if (res.ok) {
        const data = await res.json();
        return {
          newRoleMatch: data.new_role_match_pct,
          newOverall: data.new_score
        };
      }
    } catch {
      // Offline fallback
    }

    let boost = 0;
    if (toggles.add_pytest) boost += 9;
    if (toggles.add_deploy) boost += 8;
    if (toggles.sustained_commits) boost += 7;

    return {
      newRoleMatch: Math.min(98, passport.role_match_pct + boost),
      newOverall: Math.min(100, passport.overall_score + Math.round(boost * 0.7))
    };
  };

  const handleCustomVerified = (customPassport: PassportDocument) => {
    setCurrentPersonaKey('custom');
    setPassport(customPassport);
    if (customPassport.security_alerts && customPassport.security_alerts.length > 0) {
      setIsSecurityModalOpen(true);
    }
  };

  const handleCompleteQuiz = (skillName: string, grade: string, points: number) => {
    setPassport(prev => {
      const updatedSkills = prev.skills.map(s => {
        if (s.name.toLowerCase() === skillName.toLowerCase()) {
          return {
            ...s,
            test_grade: grade,
            final_points: points,
            signals: [...s.signals, `Challenge test passed with grade ${grade}`]
          };
        }
        return s;
      });

      const totalPts = updatedSkills.reduce((acc, s) => acc + s.final_points, 0);
      const newOverall = Math.round(totalPts / Math.max(1, updatedSkills.length));

      return {
        ...prev,
        overall_score: newOverall,
        skills: updatedSkills
      };
    });
  };

  const handleVerifySignature = () => {
    setSignatureVerifiedNotice(true);
    setTimeout(() => setSignatureVerifiedNotice(false), 4000);
  };

  const handleSelectRefusalsTab = () => {
    setActiveTab('refusals');
    const el = document.getElementById('refusals-section');
    if (el) el.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div className="min-h-screen bg-[#131314] text-[#e5e2e3] flex flex-row font-sans selection:bg-[#5E6BFF] selection:text-white">
      {/* Romer Left Sidebar Dock */}
      <Sidebar
        currentPersona={currentPersonaKey}
        onSelectPersona={handleSelectPersona}
        activeView={activeView}
        onSelectView={setActiveView}
        onOpenUpload={() => setIsUploadModalOpen(true)}
        onOpenSecurityModal={() => setIsSecurityModalOpen(true)}
        hasSecurityAlerts={passport.security_alerts && passport.security_alerts.length > 0}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
      />

      {/* Main Command View Area */}
      <div className="flex-1 md:ml-64 flex flex-col min-h-screen overflow-x-hidden">
        {/* Top Header */}
        <Header
          candidateName={passport.candidate_name}
          appliedRole={passport.applied_role}
          tamperProofHash={passport.tamper_proof_hash}
          onVerifySignature={handleVerifySignature}
          selectedTimeframe={selectedTimeframe}
          onSelectTimeframe={setSelectedTimeframe}
          activeView={activeView}
        />

        {/* Cryptographic Toast Notice */}
        {signatureVerifiedNotice && (
          <div className="fixed top-16 right-6 z-50 p-3 rounded bg-[#101112] border border-[#50d8e9]/40 shadow-2xl flex items-center gap-3 animate-fadeIn text-xs font-mono">
            <div className="w-7 h-7 rounded bg-[#50d8e9]/10 flex items-center justify-center text-[#50d8e9]">
              <ShieldCheck className="w-4 h-4" />
            </div>
            <div>
              <p className="font-bold text-[#e5e2e3]">Cryptographic Seal Verified</p>
              <p className="text-[#9A9DA3] text-[10px] truncate max-w-xs">{passport.tamper_proof_hash}</p>
            </div>
          </div>
        )}

        {/* Content Body */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto space-y-6">
          {activeView === 'recruiter' ? (
            <RecruiterView
              passport={passport}
              onSelectSkill={setSelectedSkill}
              onVerifySignature={handleVerifySignature}
              selectedTimeframe={selectedTimeframe}
              onSelectRefusalsTab={handleSelectRefusalsTab}
            />
          ) : (
            <StudentView
              passport={passport}
              onSimulateScore={handleSimulateScore}
            />
          )}
        </main>

        {/* Romer Terminal Footer */}
        <footer className="border-t border-[#1B1C1E] bg-[#0e0e0f] py-3 px-6 text-xs font-mono text-[#9A9DA3] flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Lock className="w-3.5 h-3.5 text-[#50d8e9]" />
            <span>THE GOLDEN RULE: <strong className="text-[#e5e2e3]">"LLM extracts text, published rules score evidence."</strong></span>
          </div>
          <div className="flex items-center gap-3 text-[10px] text-[#454655]">
            <span>ENGINE: DETERMINISTIC 4-STATE</span>
            <span>•</span>
            <span>BLAME: GIT AUTHORSHIP %</span>
            <span>•</span>
            <span>CRYPTO: SHA-256</span>
          </div>
        </footer>
      </div>

      {/* Slide-over Evidence Drawer */}
      <EvidenceDrawer
        skill={selectedSkill}
        candidateName={passport.candidate_name}
        auditLog={passport.audit_log}
        isOpen={!!selectedSkill}
        onClose={() => setSelectedSkill(null)}
        onOpenQuiz={(skillName) => {
          setSelectedSkill(null);
          setQuizSkillName(skillName);
        }}
      />

      {/* 15-Question Challenge Test Modal */}
      <QuizModal
        skillName={quizSkillName || 'Python'}
        isOpen={!!quizSkillName}
        onClose={() => setQuizSkillName(null)}
        onCompleteQuiz={handleCompleteQuiz}
      />

      {/* Prompt Injection Security Defense Modal */}
      <SecurityAlertModal
        alerts={passport.security_alerts || []}
        isOpen={isSecurityModalOpen}
        onClose={() => setIsSecurityModalOpen(false)}
      />

      {/* Custom Upload & GitHub Analyzer Modal */}
      <UploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onCustomVerified={handleCustomVerified}
      />
    </div>
  );
};

export default App;
