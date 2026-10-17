import React from 'react';
import { Download } from 'lucide-react';
import { PassportDocument } from '../lib/types';

export const AuditDetails: React.FC<{ passport: PassportDocument }> = ({ passport }) => {
  const repos = passport.repo_urls?.length ? passport.repo_urls : passport.repo_url ? [passport.repo_url] : [];

  // The signed JSON is the shareable artifact: anyone can POST it to /api/verify-signature
  const download = () => {
    const blob = new Blob([JSON.stringify(passport, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `skill-passport-${passport.candidate_name.replace(/\W+/g, '-').toLowerCase()}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <details className="group rounded-xl border border-white/10 bg-[#17181a]">
      <summary className="cursor-pointer select-none px-5 py-3 font-heading font-semibold text-zinc-300 hover:text-white">
        Audit details
      </summary>
      <div className="space-y-5 border-t border-white/10 px-5 py-4 text-sm">
        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
          <Item label="Repositories analysed" value={repos.length ? repos.map(r => <a key={r} href={r} target="_blank" rel="noreferrer" className="block text-indigo-300 hover:underline">{r}</a>) : 'None'} />
          <Item label="Commits / active months" value={`${passport.total_commits ?? 0} / ${passport.active_months ?? 0}`} />
          <Item label="Issued" value={new Date(passport.issued_at).toLocaleString()} />
          <Item label="Signature" value={<code className="break-all text-xs text-zinc-400">{passport.tamper_proof_hash}</code>} />
        </dl>

        <div className="space-y-1 text-zinc-400">
          <p className="text-zinc-300">How the numbers are calculated</p>
          <p>Each skill earns <em>evidence tier × grade</em> points (max 100). Evidence tiers: deployed or merged PR 10, own tests 8, own code 7, certificate 4, resume only 2. Grades: A 10, B 8, C 6, D 4, E 2.</p>
          <p>Role match = (100 × verified + 55 × partly supported) / skills - 7 per problem, kept between 10% and 95%.</p>
        </div>

        {passport.audit_log && passport.audit_log.traces.length > 0 && (
          <div>
            <p className="mb-2 text-zinc-300">Rule trace</p>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="text-zinc-500">
                  <tr><th className="py-1 pr-4 font-normal">Check</th><th className="py-1 pr-4 font-normal">Target</th><th className="py-1 pr-4 font-normal">Rule</th><th className="py-1 font-normal">Result</th></tr>
                </thead>
                <tbody className="text-zinc-300">
                  {passport.audit_log.traces.map((t, i) => (
                    <tr key={i} className="border-t border-white/5">
                      <td className="py-1 pr-4">{t.step}</td><td className="py-1 pr-4">{t.target}</td>
                      <td className="py-1 pr-4 font-mono">{t.rule_applied}</td><td className="py-1">{t.verdict_reached}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <button onClick={download} className="flex items-center gap-2 rounded-lg border border-white/15 px-3 py-2 text-zinc-200 hover:bg-white/5">
          <Download className="h-4 w-4" />
          Download signed passport (JSON)
        </button>
      </div>
    </details>
  );
};

const Item: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div>
    <dt className="text-zinc-500">{label}</dt>
    <dd className="text-zinc-200">{value}</dd>
  </div>
);
