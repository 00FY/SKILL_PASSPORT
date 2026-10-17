import React, { useState } from 'react';
import { Terminal, ShieldCheck, CheckCircle2, AlertOctagon, HelpCircle, ArrowUpRight } from 'lucide-react';
import { RunAuditLog, AuditStep } from '../data/mockData';

interface AuditFeedProps {
  auditLog?: RunAuditLog;
  candidateName: string;
}

export const AuditFeed: React.FC<AuditFeedProps> = ({ auditLog, candidateName }) => {
  const [filter, setFilter] = useState<'all' | 'alerts'>('all');

  const traces: AuditStep[] = auditLog?.traces || [
    { step: "INGEST", target: "resume.pdf", rule_applied: "PDF_PARSER_EXTRACT", verdict_reached: "SUCCESS", timestamp: "12:00:00.100" },
    { step: "SECURITY", target: "raw_text", rule_applied: "INJECTION_GUARD", verdict_reached: "PASSED", timestamp: "12:00:00.120" },
    { step: "BLAME", target: "api-service", rule_applied: "GIT_BLAME_AUTHORSHIP", verdict_reached: "91.2% AUTHORED", timestamp: "12:00:00.250" },
    { step: "AST_SCAN", target: "app/routes.py", rule_applied: "FASTAPI_ROUTE_DETECT", verdict_reached: "12 ROUTES FOUND", timestamp: "12:00:00.310" },
    { step: "TEST_CRAWL", target: "api-service", rule_applied: "PYTEST_DISCOVERY", verdict_reached: "4 FILES / 26 ASSERTS", timestamp: "12:00:00.380" },
    { step: "CONTRADICTION", target: "ShopAPI", rule_applied: "SOLE_COMMITTER_CHECK", verdict_reached: "CONTRADICTED", timestamp: "12:00:00.410" },
    { step: "TEST_CRAWL", target: "ShopAPI", rule_applied: "ZERO_TEST_ASSERTIONS", verdict_reached: "CLAIMED_ONLY", timestamp: "12:00:00.430" },
    { step: "RUBRIC", target: "Python", rule_applied: "EVIDENCE(8) * GRADE_A(10)", verdict_reached: "80 POINTS", timestamp: "12:00:00.450" },
    { step: "CRYPTO_SIGN", target: "passport.json", rule_applied: "SHA256_SEAL", verdict_reached: "SEALED", timestamp: "12:00:00.500" }
  ];

  const filtered = filter === 'alerts'
    ? traces.filter(t => t.verdict_reached.includes('CONTRADICTED') || t.verdict_reached.includes('CLAIMED_ONLY') || t.verdict_reached.includes('RISK'))
    : traces;

  return (
    <div className="bg-[#101112] border border-[#232426] rounded flex flex-col overflow-hidden h-full">
      {/* Header */}
      <div className="p-3 px-4 border-b border-[#1B1C1E] flex justify-between items-center bg-[#0e0e0f]">
        <div className="text-xs font-mono uppercase tracking-widest text-[#9A9DA3] flex items-center gap-2">
          <Terminal className="w-3.5 h-3.5 text-[#bec2ff]" />
          <span>Execution Feed (run.json)</span>
        </div>
        <div className="flex bg-[#070708] rounded p-[2px] border border-[#1B1C1E]">
          <button
            onClick={() => setFilter('all')}
            className={`px-2 py-0.5 text-[10px] font-mono uppercase ${
              filter === 'all' ? 'bg-[#1c1b1d] text-[#e5e2e3]' : 'text-[#9A9DA3]'
            }`}
          >
            All ({traces.length})
          </button>
          <button
            onClick={() => setFilter('alerts')}
            className={`px-2 py-0.5 text-[10px] font-mono uppercase ${
              filter === 'alerts' ? 'bg-[#1c1b1d] text-[#ffb4ab]' : 'text-[#9A9DA3]'
            }`}
          >
            Anomalies
          </button>
        </div>
      </div>

      {/* Ticker List */}
      <div className="p-3 space-y-2 overflow-y-auto max-h-[380px] font-mono text-[11px]">
        {filtered.map((item, idx) => {
          const isError = item.verdict_reached.includes('CONTRADICTED') || item.verdict_reached.includes('RISK');
          const isWarning = item.verdict_reached.includes('CLAIMED_ONLY');
          const isSuccess = !isError && !isWarning;

          return (
            <div
              key={idx}
              className={`p-2.5 rounded border transition-all ${
                isError
                  ? 'bg-[#93000a]/10 border-[#ffb4ab]/30'
                  : isWarning
                  ? 'bg-[#ffb689]/10 border-[#ffb689]/20'
                  : 'bg-[#151617] border-[#1B1C1E] hover:border-[#2a2a2b]'
              }`}
            >
              <div className="flex items-center justify-between text-[10px] text-[#9A9DA3] mb-1">
                <span className="font-bold text-[#bec2ff] uppercase">{item.step}</span>
                <span>{item.timestamp.split('T')[1]?.replace('Z', '') || item.timestamp}</span>
              </div>

              <div className="text-[#e5e2e3] font-medium truncate mb-1">
                {item.rule_applied}
              </div>

              <div className="flex items-center justify-between">
                <span className="text-[10px] text-[#9A9DA3] truncate max-w-[140px]">
                  Target: {item.target}
                </span>
                <span
                  className={`text-[9px] font-bold px-1.5 py-0.2 rounded uppercase ${
                    isError
                      ? 'bg-[#ffb4ab]/20 text-[#ffb4ab] border border-[#ffb4ab]/30'
                      : isWarning
                      ? 'bg-[#ffb689]/20 text-[#ffb689] border border-[#ffb689]/30'
                      : 'bg-[#50d8e9]/10 text-[#50d8e9] border border-[#50d8e9]/20'
                  }`}
                >
                  {item.verdict_reached}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer Info */}
      <div className="p-2.5 px-3 border-t border-[#1B1C1E] bg-[#0e0e0f] text-[10px] font-mono text-[#9A9DA3] flex items-center justify-between">
        <span>Deterministic Rule Trace</span>
        <span className="text-[#50d8e9]">ZERO LLM BIAS</span>
      </div>
    </div>
  );
};
