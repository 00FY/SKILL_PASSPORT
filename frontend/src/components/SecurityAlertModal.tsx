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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
      <div className="w-full max-w-xl bg-[#101112] border border-[#ffb4ab]/30 rounded shadow-2xl overflow-hidden card-inner-glow animate-fadeIn">
        {/* Header */}
        <div className="p-4 px-6 border-b border-[#1B1C1E] bg-[#93000a]/15 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded bg-[#93000a]/30 border border-[#ffb4ab]/40 flex items-center justify-center text-[#ffb4ab]">
              <ShieldAlert className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-heading font-bold text-base text-[#e5e2e3] tracking-tight">
                  Security Defense Protocol Engaged
                </h3>
                <span className="text-[9px] font-mono font-bold px-1.5 py-0.2 rounded bg-[#ffb4ab]/20 text-[#ffb4ab] border border-[#ffb4ab]/30 uppercase">
                  Quarantine Active
                </span>
              </div>
              <p className="text-[11px] font-mono text-[#ffb4ab]/80">
                Module 1 Prompt-Injection Defense Neutralized {alerts.length} Exploit(s)
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-[#9A9DA3] hover:text-[#e5e2e3] rounded hover:bg-[#1c1b1d] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Alerts Body */}
        <div className="p-6 space-y-4 max-h-[60vh] overflow-y-auto">
          {alerts.map((flag, idx) => (
            <div
              key={idx}
              className="p-3.5 rounded bg-[#151617] border border-[#ffb4ab]/30 space-y-2"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-[#ffb4ab] flex items-center gap-1.5">
                  <Bug className="w-3.5 h-3.5 text-[#ffb4ab]" />
                  <span>{flag.flag_type}</span>
                </span>
                <span className="text-[9px] font-mono font-bold px-1.5 py-0.2 rounded bg-[#93000a]/30 text-[#ffb4ab] border border-[#ffb4ab]/30">
                  {flag.severity} RISK
                </span>
              </div>

              {/* Raw Payload Snippet */}
              <div className="bg-[#0e0e0f] p-2.5 rounded border border-[#1B1C1E] font-mono text-[11px] text-[#ffb4ab]/90 break-words">
                <span className="text-[#9A9DA3] text-[9px] block mb-1">INTERCEPTED ATTACK PAYLOAD:</span>
                <code>{flag.raw_payload_snippet}</code>
              </div>

              {/* Action Taken */}
              <div className="flex items-center gap-1.5 text-xs font-mono text-[#50d8e9]">
                <ShieldCheck className="w-3.5 h-3.5 text-[#50d8e9] shrink-0" />
                <span>{flag.action_taken}</span>
              </div>
            </div>
          ))}

          {/* Defense Explanation */}
          <div className="p-3 rounded bg-[#0e0e0f] border border-[#1B1C1E] text-xs space-y-1">
            <span className="font-mono font-semibold text-[#e5e2e3] flex items-center gap-1">
              <Lock className="w-3 h-3 text-[#50d8e9]" />
              <span>Architectural Protection Guarantee:</span>
            </span>
            <p className="text-[#9A9DA3] text-[11px] leading-relaxed">
              Because Skill Passport follows the Golden Rule ("LLM extracts text, published rules score evidence"),
              prompt injections can never forge or boost scores. Every claim must still match verified Git blame line authorship and unit test AST trees.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="p-3.5 px-6 border-t border-[#1B1C1E] bg-[#0e0e0f] flex items-center justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-[#1c1b1d] hover:bg-[#2a2a2b] text-[#e5e2e3] text-xs font-mono rounded transition-colors"
          >
            Acknowledge & Close
          </button>
        </div>
      </div>
    </div>
  );
};
