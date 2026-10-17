import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
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
import { ShieldCheck, CheckCircle2, Lock, GitFork, BookOpen, ExternalLink } from 'lucide-react';

export const App: React.FC = () => {
  const [currentPersonaKey, setCurrentPersonaKey] = useState<string>('priya');
  const [passport, setPassport] = useState<PassportDocument>(MOCK_PRIYA);
  const [activeView, setActiveView] = useState<'recruiter' | 'student'>('recruiter');

  // Modals state
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
      // Fallback to embedded mock data for 100% offline reliability
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

    // Client-side simulation fallback
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

  return (
    <div className="min-h-screen bg-[#0a0d14] text-slate-100 flex flex-col font-sans">
      {/* Top Navigation */}
      <Navbar
        currentPersona={currentPersonaKey}
        onSelectPersona={handleSelectPersona}
        activeView={activeView}
        onSelectView={setActiveView}
        onOpenUpload={() => setIsUploadModalOpen(true)}
        onOpenSecurityModal={() => setIsSecurityModalOpen(true)}
        tamperProofHash={passport.tamper_proof_hash}
        hasSecurityAlerts={passport.security_alerts && passport.security_alerts.length > 0}
      />

      {/* Cryptographic Signature Toast */}
      {signatureVerifiedNotice && (
        <div className="fixed top-20 right-6 z-50 p-4 rounded-2xl bg-[#0e1626] border border-emerald-500/40 shadow-2xl flex items-center gap-3 animate-fadeIn text-xs">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center text-emerald-400">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <p className="font-bold text-white">Cryptographic Fingerprint Verified</p>
            <p className="text-slate-400 font-mono text-[11px] truncate max-w-xs">{passport.tamper_proof_hash}</p>
          </div>
        </div>
      )}

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeView === 'recruiter' ? (
          <RecruiterView
            passport={passport}
            onSelectSkill={setSelectedSkill}
            onVerifySignature={handleVerifySignature}
          />
        ) : (
          <StudentView
            passport={passport}
            onSimulateScore={handleSimulateScore}
          />
        )}
      </main>

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

      {/* Footer / Architectural Golden Rule Banner */}
      <footer className="border-t border-white/5 bg-[#07090f] py-6 text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-center sm:text-left">
          <div className="flex items-center gap-2">
            <Lock className="w-4 h-4 text-emerald-500" />
            <span className="text-slate-400 font-medium">
              Skill Passport: <span className="text-emerald-400">"LLM extracts text, published rules score evidence."</span>
            </span>
          </div>
          <div className="flex items-center gap-4 text-[11px] font-mono text-slate-500">
            <span>Deterministic 4-State Engine</span>
            <span>•</span>
            <span>Git Blame Authorship</span>
            <span>•</span>
            <span>SHA-256 Tamper-Proof</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;
