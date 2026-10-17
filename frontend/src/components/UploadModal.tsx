import React, { useRef, useState } from 'react';
import { AlertTriangle, FileText, Loader2, X } from 'lucide-react';
import { AnalysisJob, PassportDocument } from '../lib/types';
import { ApiError, postJson, request, waitForJob } from '../lib/api';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCustomVerified: (passport: PassportDocument) => void;
}

interface ParsedResume {
  filename: string;
  text: string;
  repo_urls: string[];
  warnings: string[];
}

const MAX_REPOS = 5;

const splitList = (value: string): string[] =>
  value.split(/[\n,]+/).map(v => v.trim()).filter(Boolean);

export const UploadModal: React.FC<UploadModalProps> = ({ isOpen, onClose, onCustomVerified }) => {
  const [resumeText, setResumeText] = useState('');
  const [repoUrls, setRepoUrls] = useState('');
  const [gitIdentities, setGitIdentities] = useState('');
  const [candidateName, setCandidateName] = useState('');
  const [fileName, setFileName] = useState('');
  const [busyMessage, setBusyMessage] = useState('');
  const [error, setError] = useState('');
  const [notices, setNotices] = useState<string[]>([]);
  const fileInput = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const run = async (message: string, task: () => Promise<void>) => {
    setError('');
    setBusyMessage(message);
    try {
      await task();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong.');
    } finally {
      setBusyMessage('');
    }
  };

  const handleFile = (file: File) => run(`Reading ${file.name}…`, async () => {
    setNotices([]);
    const form = new FormData();
    form.append('file', file);
    const data = await request<ParsedResume>('/api/parse-resume', { method: 'POST', body: form });
    setFileName(data.filename);
    setResumeText(data.text);
    if (!repoUrls.trim() && data.repo_urls.length) setRepoUrls(data.repo_urls.join('\n'));
    setNotices(data.warnings);
  });

  const analyze = () => {
    const repos = splitList(repoUrls);
    if (!resumeText.trim()) { setError('Upload a resume or paste its text first.'); return; }
    if (repos.length > MAX_REPOS) { setError(`At most ${MAX_REPOS} repositories can be analysed at once.`); return; }
    run(
      repos.length ? 'Cloning repositories and checking who wrote the code… (can take a minute)' : 'Looking for repositories linked in the resume…',
      async () => {
        // Analyses run as background jobs on the server; poll until done
        const { job_id } = await postJson<{ job_id: string }>('/api/jobs/analyze', {
          candidate_name: candidateName.trim() || undefined,
          resume_text: resumeText,
          repo_urls: repos,
          git_identities: splitList(gitIdentities),
        });
        const job = await waitForJob<AnalysisJob>(job_id, setBusyMessage);
        const passport = job.passport as PassportDocument;
        onCustomVerified(passport);
        onClose();
      }
    );
  };

  const input = 'w-full rounded-lg border border-white/10 bg-[#1a1b1d] px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:border-indigo-400 focus:outline-none';
  const label = 'mb-1 block text-sm font-medium text-zinc-300';
  const busy = !!busyMessage;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="flex max-h-[90vh] w-full max-w-xl flex-col rounded-xl border border-white/10 bg-[#141516]">
        <div className="flex items-center justify-between border-b border-white/10 px-6 py-4">
          <h2 className="font-heading text-lg font-bold">Analyze a resume</h2>
          <button onClick={onClose} className="rounded p-1 text-zinc-400 hover:bg-white/10 hover:text-white" aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-6 py-5">
          <div>
            <span className={label}>1. Resume</span>
            <input
              ref={fileInput}
              type="file"
              accept=".pdf,.docx,.txt,.md"
              className="hidden"
              onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); e.target.value = ''; }}
            />
            <button
              type="button"
              onClick={() => fileInput.current?.click()}
              disabled={busy}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-white/20 py-3 text-sm text-zinc-300 hover:border-indigo-400 disabled:opacity-50"
            >
              <FileText className="h-4 w-4" />
              {fileName ? `${fileName} - choose another file` : 'Upload PDF, DOCX or TXT (max 5 MB)'}
            </button>
            <textarea
              rows={5}
              value={resumeText}
              onChange={e => setResumeText(e.target.value)}
              className={`${input} mt-2`}
              placeholder="…or paste the resume text here"
            />
          </div>

          <div>
            <label className={label} htmlFor="repos">2. Public repositories <span className="font-normal text-zinc-500">(one per line, up to {MAX_REPOS})</span></label>
            <textarea
              id="repos"
              rows={2}
              value={repoUrls}
              onChange={e => setRepoUrls(e.target.value)}
              className={input}
              placeholder={'https://github.com/user/project\nLeave empty to use links from the resume'}
            />
          </div>

          <div>
            <label className={label} htmlFor="idents">3. Git emails or usernames <span className="font-normal text-zinc-500">(recommended)</span></label>
            <input
              id="idents"
              value={gitIdentities}
              onChange={e => setGitIdentities(e.target.value)}
              className={input}
              placeholder="you@example.com, your-github-username"
            />
            <p className="mt-1 text-xs text-zinc-500">Used to tell the candidate's commits apart from other people's. The repository owner's username is included automatically.</p>
          </div>

          <div>
            <label className={label} htmlFor="name">Candidate name <span className="font-normal text-zinc-500">(optional)</span></label>
            <input id="name" value={candidateName} onChange={e => setCandidateName(e.target.value)} className={input} placeholder="Taken from the resume if empty" />
          </div>

          {notices.length > 0 && (
            <div className="space-y-1 rounded-lg border border-amber-400/40 bg-amber-500/10 p-3 text-sm text-amber-100">
              {notices.map((n, i) => <p key={i}>{n}</p>)}
            </div>
          )}
          {error && (
            <div className="flex gap-2 rounded-lg border border-red-400/40 bg-red-500/10 p-3 text-sm text-red-200">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{error}
            </div>
          )}
          {busy && (
            <div className="flex items-center gap-2 text-sm text-zinc-300">
              <Loader2 className="h-4 w-4 animate-spin" />{busyMessage}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 border-t border-white/10 px-6 py-3">
          <button onClick={onClose} className="rounded-lg px-4 py-2 text-sm text-zinc-300 hover:bg-white/5">Cancel</button>
          <button
            onClick={analyze}
            disabled={busy}
            className="rounded-lg bg-indigo-500 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-400 disabled:opacity-50"
          >
            Analyze
          </button>
        </div>
      </div>
    </div>
  );
};
