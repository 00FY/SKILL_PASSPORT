import React from 'react';
import { X, ShieldAlert, AlertTriangle, ShieldCheck, Bug, Lock } from 'lucide-react';
import { SecurityFlag } from '../data/mockData';

interface SecurityAlertModalProps {
  alerts: SecurityFlag[];
  isOpen: boolean;
  onClose: () => void;
}

export const SecurityAlertModal: React.FC<SecurityAlertModalProps> = ({
  alerts,
  isOpen,
  onClose
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md">
      <div className="w-full max-w-xl bg-[#0e121c] border border-rose-500/30 rounded-3xl shadow-2xl overflow-hidden animate-fadeIn">
        {/* Header */}
        <div className="p-6 border-b border-rose-500/20 bg-rose-950/20 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-rose-500/20 border border-rose-500/30 flex items-center justify-center text-rose-400">
              <ShieldAlert className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-white tracking-tight">
                  Security Defense Protocol Engaged
                </h3>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/30 uppercase">
                  Quarantine Active
                </span>
              </div>
              <p className="text-xs text-rose-300/80">
                Module 1 Prompt-Injection & Steganography Filter Neutralized {alerts.length} Exploit(s)
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-white/5 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Alerts Body */}
        <div className="p-6 space-y-4 max-h-[60vh] overflow-y-auto">
          {alerts.map((flag, idx) => (
            <div
              key={idx}
              className="p-4 rounded-xl bg-slate-900/60 border border-rose-500/20 space-y-2.5"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-rose-400 flex items-center gap-1.5">
                  <Bug className="w-4 h-4 text-rose-400" />
                  <span>{flag.flag_type}</span>
                </span>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">
                  {flag.severity} RISK
                </span>
              </div>

              {/* Raw Payload Snippet */}
              <div className="bg-[#07090f] p-3 rounded-lg border border-white/5 font-mono text-xs text-rose-300/90 break-words">
                <span className="text-slate-500 text-[10px] block mb-1">INTERCEPTED ATTACK PAYLOAD:</span>
                <code>{flag.raw_payload_snippet}</code>
              </div>

              {/* Action Taken */}
              <div className="flex items-center gap-1.5 text-xs text-emerald-400 font-medium">
                <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>{flag.action_taken}</span>
              </div>
            </div>
          ))}

          {/* Defense Explanation */}
          <div className="p-3 rounded-xl bg-slate-900/40 border border-white/5 text-xs text-slate-300 space-y-1">
            <span className="font-semibold text-white flex items-center gap-1">
              <Lock className="w-3.5 h-3.5 text-teal-400" />
              <span>Architectural Protection Guarantee:</span>
            </span>
            <p className="text-slate-400 text-[11px] leading-relaxed">
              Because Skill Passport follows the Golden Rule ("LLM extracts text, published rules score evidence"),
              prompt injections can never forge or boost scores. Every claim must still match verified Git blame line authorship and unit test AST trees.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-white/10 bg-slate-900/80 flex items-center justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold rounded-xl transition-colors"
          >
            Acknowledge & Close
          </button>
        </div>
      </div>
    </div>
  );
};
