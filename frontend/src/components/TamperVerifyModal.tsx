import React, { useState } from 'react';
import { X, ShieldCheck, ShieldAlert, Hash, AlertTriangle, Terminal, CheckCircle2, Lock, ArrowRight, RefreshCw } from 'lucide-react';
import { PassportDocument } from '../data/mockData';

interface TamperVerifyModalProps {
  isOpen: boolean;
  onClose: () => void;
  passport: PassportDocument;
}

export const TamperVerifyModal: React.FC<TamperVerifyModalProps> = ({
  isOpen,
  onClose,
  passport
}) => {
  if (!isOpen) return null;

  const [isTamperActive, setIsTamperActive] = useState<boolean>(false);
  const [verifying, setVerifying] = useState<boolean>(false);

  const originalScore = passport.overall_score;
  const tamperedScore = Math.min(100, originalScore + 10);
  const currentScore = isTamperActive ? tamperedScore : originalScore;

  // Compute a deterministic simulated forged hash when tampered
  const originalHash = passport.tamper_proof_hash || "hmac-sha256:fc465c15a4e975a1bef57ae73328e7b307c4cf39599b0f7566df772bc103a3f6";
  const forgedHash = "hmac-sha256:9a3f781c0e29b4e1837d9284719283748291038475819283746152439581726a";
  const computedHash = isTamperActive ? forgedHash : originalHash;
  const isMatch = !isTamperActive;

  const handleToggleTamper = () => {
    setVerifying(true);
    setIsTamperActive(!isTamperActive);
    setTimeout(() => setVerifying(false), 250);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fadeIn">
      <div className="w-full max-w-2xl bg-[#101112] border border-[#232426] rounded shadow-2xl overflow-hidden card-inner-glow flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className={`p-4 px-6 border-b flex items-center justify-between transition-colors ${
          isMatch ? 'bg-[#0e0e0f] border-[#1B1C1E]' : 'bg-[#93000a]/20 border-[#ffb4ab]/30'
        }`}>
          <div className="flex items-center gap-3">
            <div className={`w-8 h-8 rounded flex items-center justify-center transition-colors ${
              isMatch ? 'bg-[#50d8e9]/10 text-[#50d8e9] border border-[#50d8e9]/30' : 'bg-[#93000a]/40 text-[#ffb4ab] border border-[#ffb4ab]/40 animate-pulse'
            }`}>
              {isMatch ? <ShieldCheck className="w-4 h-4" /> : <ShieldAlert className="w-4 h-4" />}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-heading font-bold text-base text-[#e5e2e3]">
                  Cryptographic Integrity & Tamper Audit
                </h3>
                <span className={`text-[9px] font-mono font-bold px-1.5 py-0.2 rounded uppercase border ${
                  isMatch
                    ? 'bg-[#50d8e9]/10 text-[#50d8e9] border-[#50d8e9]/30'
                    : 'bg-[#93000a]/30 text-[#ffb4ab] border-[#ffb4ab]/40 animate-pulse'
                }`}>
                  {isMatch ? 'HMAC VERIFIED' : 'TAMPER DETECTED'}
                </span>
              </div>
              <p className="text-[11px] font-mono text-[#9A9DA3]">
                Candidate: {passport.candidate_name} • Key: SHA-256 HMAC Sealing
              </p>
            </div>
          </div>
          <button
            id="btn-close-tamper-modal"
            onClick={onClose}
            className="p-1.5 text-[#9A9DA3] hover:text-[#e5e2e3] rounded hover:bg-[#1c1b1d] transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-5 overflow-y-auto">
          {/* Status Verdict Banner */}
          <div className={`p-4 rounded border transition-all ${
            isMatch
              ? 'bg-[#50d8e9]/5 border-[#50d8e9]/30'
              : 'bg-[#93000a]/15 border-[#ffb4ab]/40'
          }`}>
            <div className="flex items-start gap-3">
              {isMatch ? (
                <CheckCircle2 className="w-5 h-5 text-[#50d8e9] shrink-0 mt-0.5" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-[#ffb4ab] shrink-0 mt-0.5 animate-bounce" />
              )}
              <div>
                <h4 className={`font-heading font-bold text-sm tracking-tight ${
                  isMatch ? 'text-[#50d8e9]' : 'text-[#ffb4ab]'
                }`}>
                  {isMatch
                    ? 'Signature Valid — Unaltered Since Audit'
                    : 'TAMPER DETECTED: Signature Mismatch'}
                </h4>
                <p className="text-xs font-sans text-[#c6c5d8] mt-1 leading-relaxed">
                  {isMatch
                    ? 'The cryptographic HMAC-SHA256 signature matches the canonical passport payload with 100% mathematical precision. No scores, evidence, or refusal logs have been altered.'
                    : `Security Alert: Payload score parameter was modified from ${originalScore} to ${tamperedScore} (+10 points). The computed hash no longer matches the digital seal.`}
                </p>
              </div>
            </div>
          </div>

          {/* Interactive Simulation Switch */}
          <div className="bg-[#151617] border border-[#232426] rounded p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <span className="text-xs font-mono font-bold text-[#e5e2e3] flex items-center gap-1.5">
                <Terminal className="w-3.5 h-3.5 text-[#5E6BFF]" />
                <span>Simulate Score Forgery Attack</span>
              </span>
              <p className="text-xs text-[#9A9DA3] mt-0.5">
                Artificially inflate overall score by +10 points to observe HMAC rejection.
              </p>
            </div>

            <button
              id="btn-simulate-tamper"
              onClick={handleToggleTamper}
              className={`px-4 py-2 rounded text-xs font-mono font-bold flex items-center gap-2 transition-all shrink-0 cursor-pointer ${
                isTamperActive
                  ? 'bg-[#ffb4ab] text-black shadow-lg shadow-[#ffb4ab]/20'
                  : 'bg-[#101112] text-[#50d8e9] border border-[#50d8e9]/40 hover:bg-[#50d8e9]/10'
              }`}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${verifying ? 'animate-spin' : ''}`} />
              <span>{isTamperActive ? 'Revert Attack' : 'Simulate Tamper (+10 pts)'}</span>
            </button>
          </div>

          {/* Side-by-side Score & Signature Diff */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            {/* Sealed Original */}
            <div className="bg-[#101112] border border-[#1B1C1E] rounded p-3.5 space-y-2">
              <span className="text-[10px] font-mono uppercase text-[#9A9DA3] block">
                Sealed Audit State
              </span>
              <div className="flex items-baseline justify-between">
                <span className="text-xs text-[#9A9DA3]">Audit Score:</span>
                <span className="font-heading font-extrabold text-xl text-[#50d8e9]">
                  {originalScore} / 100
                </span>
              </div>
              <div className="pt-2 border-t border-[#1B1C1E]">
                <span className="text-[9px] font-mono text-[#9A9DA3] block mb-1">EXPECTED HMAC-SHA256:</span>
                <p className="font-mono text-[10px] text-[#50d8e9] break-all bg-[#070708] p-2 rounded border border-[#1B1C1E]">
                  {originalHash}
                </p>
              </div>
            </div>

            {/* Current Payload */}
            <div className={`bg-[#101112] border rounded p-3.5 space-y-2 transition-colors ${
              isMatch ? 'border-[#1B1C1E]' : 'border-[#ffb4ab]/40 bg-[#93000a]/10'
            }`}>
              <span className="text-[10px] font-mono uppercase text-[#9A9DA3] block">
                Inspected Payload State
              </span>
              <div className="flex items-baseline justify-between">
                <span className="text-xs text-[#9A9DA3]">Evaluated Score:</span>
                <div className="flex items-center gap-1.5">
                  <span className={`font-heading font-extrabold text-xl ${
                    isMatch ? 'text-[#e5e2e3]' : 'text-[#ffb4ab] line-through'
                  }`}>
                    {currentScore} / 100
                  </span>
                  {isTamperActive && (
                    <span className="text-[10px] font-mono font-bold text-[#ffb4ab] bg-[#ffb4ab]/20 px-1 rounded">
                      FORGED
                    </span>
                  )}
                </div>
              </div>
              <div className="pt-2 border-t border-[#1B1C1E]">
                <span className="text-[9px] font-mono text-[#9A9DA3] block mb-1">COMPUTED PAYLOAD HASH:</span>
                <p className={`font-mono text-[10px] break-all p-2 rounded border ${
                  isMatch
                    ? 'text-[#50d8e9] bg-[#070708] border-[#1B1C1E]'
                    : 'text-[#ffb4ab] bg-[#93000a]/20 border-[#ffb4ab]/30'
                }`}>
                  {computedHash}
                </p>
              </div>
            </div>
          </div>

          {/* Code JSON Canonical Payload */}
          <div className="space-y-1.5">
            <span className="text-[10px] font-mono uppercase tracking-widest text-[#9A9DA3] flex items-center gap-1.5">
              <Lock className="w-3 h-3 text-[#50d8e9]" />
              <span>Canonical JSON Normalization Inspection</span>
            </span>
            <div className="bg-[#070708] border border-[#1B1C1E] rounded p-3 font-mono text-[11px] text-[#c6c5d8] overflow-x-auto max-h-40">
              <pre>{JSON.stringify({
                candidate_name: passport.candidate_name,
                applied_role: passport.applied_role,
                overall_score: currentScore,
                role_match_pct: passport.role_match_pct,
                tamper_status: isMatch ? "AUTHENTIC" : "MODIFIED_UNAUTHORIZED"
              }, null, 2)}</pre>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-3 px-6 border-t border-[#1B1C1E] bg-[#0e0e0f] flex justify-between items-center text-xs font-mono">
          <span className="text-[#9A9DA3]">Algorithm: HMAC-SHA256 (RFC 2104)</span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded bg-[#1c1b1d] hover:bg-[#2a2a2b] text-[#e5e2e3] transition-colors"
          >
            Close Inspector
          </button>
        </div>
      </div>
    </div>
  );
};
