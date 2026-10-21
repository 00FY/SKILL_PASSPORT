import React, { useRef, useState } from 'react';
import { AlertTriangle, Award, Check, Code2, FileText, Github, Loader2, Sparkles, Trash2, X } from 'lucide-react';
import { AnalysisJob, CertificateEvidence, PassportDocument } from '../lib/types';
import { ApiError, discoverRepos, postJson, request, uploadCert, waitForJob } from '../lib/api';
import { AnalysisNotice } from './AnalysisAlert';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCustomVerified: (passport: PassportDocument) => void;
  onAlert: (notice: AnalysisNotice) => void;
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

const nameTokens = (name: string) =>
  name.toLowerCase().normalize('NFKD').replace(/[^a-z\s]/g, ' ').split(/\s+/).filter(Boolean);

/** Same idea as the server's check: every part of the shorter name appears in the longer one (initials allowed). */
const namesMatch = (a: string, b: string) => {
  const [short, long] = [nameTokens(a), nameTokens(b)].sort((x, y) => x.length - y.length);
  if (!short.length) return false;
  return short.every(t => long.some(u => u === t || (t.length === 1 && u.startsWith(t)) || (u.length === 1 && t.startsWith(u))));
};

export const UploadModal: React.FC<UploadModalProps> = ({ isOpen, onClose, onCustomVerified, onAlert }) => {
  const [githubUsername, setGithubUsername] = useState('');
  const [resumeText, setResumeText] = useState('');
  const [repoUrls, setRepoUrls] = useState('');
  const [gitIdentities, setGitIdentities] = useState('');
  const [candidateName, setCandidateName] = useState('');
  const [fileName, setFileName] = useState('');
  const [certificates, setCertificates] = useState<CertificateEvidence[]>([]);
  const [busyMessage, setBusyMessage] = useState('');
  const [discovering, setDiscovering] = useState(false);
  const [error, setError] = useState('');
  const [notices, setNotices] = useState<string[]>([]);

  const fileInput = useRef<HTMLInputElement>(null);
  const certFileInput = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const run = async (message: string, task: () => Promise<void>) => {
    setError('');
    setBusyMessage(message);
    try {
      await task();
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Something went wrong. Please try again.';
      setError(message);
      onAlert({ title: 'Analysis could not finish', messages: [message] });
    } finally {
      setBusyMessage('');
    }
  };

  const handleResumeFile = (file: File) => run(`Reading ${file.name}…`, async () => {
    setNotices([]);
    const form = new FormData();
    form.append('file', file);
    const data = await request<ParsedResume>('/api/parse-resume', { method: 'POST', body: form });
    setFileName(data.filename);
    setResumeText(data.text);
    if (!repoUrls.trim() && data.repo_urls.length) setRepoUrls(data.repo_urls.join('\n'));
    setNotices(data.warnings);
  });

  const handleCertUpload = async (file: File) => {
    setError('');
    setBusyMessage(`Parsing ${file.name}…`);
    try {
      const cert = await uploadCert(file, candidateName.trim() || undefined);
      // The candidate's name is never taken from a certificate: the certificate has to match the candidate
      setCertificates(prev => [...prev, cert]);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Failed to parse certificate.');
    } finally {
      setBusyMessage('');
    }
  };

  const removeCert = (id: string) => {
    setCertificates(prev => prev.filter(c => c.id !== id));
  };

  const handleDiscoverProfile = async () => {
    if (!githubUsername.trim()) {
      setError('Enter a GitHub username or profile URL first.');
      return;
    }
    setError('');
    setNotices([]);
    setDiscovering(true);
    try {
      const data = await discoverRepos(githubUsername.trim());
      if (data.name && !candidateName.trim()) {
        setCandidateName(data.name);
      }
      if (data.repo_urls.length > 0) {
        setRepoUrls(data.repo_urls.join('\n'));
      }
      if (data.warnings && data.warnings.length > 0) {
        setNotices(data.repo_urls.length > 0 ? data.warnings : [
          ...data.warnings,
          'Paste your repository URLs into "Repositories to analyze" instead: the analysis clones them directly and does not need the GitHub API.',
        ]);
        onAlert({ title: 'GitHub repository discovery needs attention', messages: data.warnings });
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to discover GitHub profile. Please try again.';
      setError(message);
      onAlert({ title: 'GitHub repository discovery failed', messages: [message] });
    } finally {
      setDiscovering(false);
    }
  };

  const analyze = () => {
    const repos = splitList(repoUrls);
    const hasResume = !!resumeText.trim();
    const hasCode = repos.length > 0 || !!githubUsername.trim();
    const hasCerts = certificates.length > 0;

    if (!candidateName.trim()) {
      setError("Enter the candidate's full name: certificates and the passport are checked against it.");
      return;
    }

    if (!hasResume && !hasCode && !hasCerts) {
      setError('Please provide at least a GitHub username, repository, resume, or certificate.');
      return;
    }

    if (repos.length > MAX_REPOS) {
      setError(`At most ${MAX_REPOS} repositories can be analysed at once.`);
      return;
    }

    run(
      repos.length || githubUsername
        ? 'Scanning repositories, checking git blame & tests… (can take a minute)'
        : 'Evaluating claims and credentials…',
      async () => {
        const { job_id } = await postJson<{ job_id: string }>('/api/jobs/analyze', {
          candidate_name: candidateName.trim(),
          github_username: githubUsername.trim() || undefined,
          resume_text: resumeText.trim() || undefined,
          repo_urls: repos,
          git_identities: splitList(gitIdentities),
          certificates: certificates,
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
  const busy = !!busyMessage || discovering;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="flex max-h-[92vh] w-full max-w-2xl flex-col rounded-xl border border-white/10 bg-[#141516] shadow-2xl">
        <div className="flex items-center justify-between border-b border-white/10 px-6 py-4">
          <div>
            <h2 className="font-heading text-lg font-bold">Multi-Signal Candidate Analysis</h2>
            <p className="text-xs text-zinc-400">Score candidate across 4 pillars: Code Profile, Resume, Certificates & Quizzes</p>
          </div>
          <button onClick={onClose} className="rounded p-1 text-zinc-400 hover:bg-white/10 hover:text-white" aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-6 py-5">
          {/* Pillar 1: GitHub Profile Scan */}
          <div className="rounded-lg border border-white/10 bg-[#18191c] p-4">
            <div className="flex items-center justify-between">
              <label className={label} htmlFor="gh_user">
                <span className="flex items-center gap-1.5 font-semibold text-emerald-400">
                  <Github className="h-4 w-4" /> 1. GitHub Profile (Code Pillar)
                </span>
              </label>
              <span className="text-[11px] text-zinc-400">Scans all public repos</span>
            </div>
            <div className="mt-1 flex gap-2">
              <input
                id="gh_user"
                value={githubUsername}
                onChange={e => setGithubUsername(e.target.value)}
                className={input}
                placeholder="e.g. torvalds or https://github.com/username"
                disabled={busy}
              />
              <button
                type="button"
                onClick={handleDiscoverProfile}
                disabled={busy || !githubUsername.trim()}
                className="flex shrink-0 items-center gap-1.5 rounded-lg border border-indigo-400/30 bg-indigo-500/20 px-3 py-2 text-xs font-semibold text-indigo-300 hover:bg-indigo-500/30 disabled:opacity-40"
              >
                {discovering ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                Discover Repos
              </button>
            </div>

            <div className="mt-3">
              <label className="text-xs text-zinc-400" htmlFor="repos">
                Repositories to analyze <span className="text-zinc-500">(auto-populated from profile, up to {MAX_REPOS}):</span>
              </label>
              <textarea
                id="repos"
                rows={2}
                value={repoUrls}
                onChange={e => setRepoUrls(e.target.value)}
                className={`${input} mt-1`}
                placeholder={'https://github.com/user/project\nOne repository per line'}
              />
            </div>
          </div>

          {/* Pillar 2: Resume / Bio (Optional) */}
          <div className="rounded-lg border border-white/10 bg-[#18191c] p-4">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-sm font-semibold text-sky-400">
                <FileText className="h-4 w-4" /> 2. Resume / Bio <span className="text-xs font-normal text-zinc-400">(Optional)</span>
              </span>
              <span className="text-[11px] text-zinc-400">Claims cross-checked against code</span>
            </div>
            <p className="mt-0.5 text-xs text-zinc-400">
              Not required. If omitted, skills are derived directly from public code and credentials.
            </p>
            <input
              ref={fileInput}
              type="file"
              accept=".pdf,.docx,.txt,.md"
              className="hidden"
              onChange={e => { const f = e.target.files?.[0]; if (f) handleResumeFile(f); e.target.value = ''; }}
            />
            <button
              type="button"
              onClick={() => fileInput.current?.click()}
              disabled={busy}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-white/20 py-2.5 text-xs text-zinc-300 hover:border-sky-400 disabled:opacity-50"
            >
              <FileText className="h-4 w-4" />
              {fileName ? `${fileName} - choose another file` : 'Upload PDF, DOCX or TXT (max 5 MB)'}
            </button>
            <textarea
              rows={3}
              value={resumeText}
              onChange={e => setResumeText(e.target.value)}
              className={`${input} mt-2`}
              placeholder="…or paste resume text (optional)"
            />
          </div>

          {/* Pillar 3: Certificates (Upload) */}
          <div className="rounded-lg border border-white/10 bg-[#18191c] p-4">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-sm font-semibold text-amber-400">
                <Award className="h-4 w-4" /> 3. Certificates <span className="text-xs font-normal text-zinc-400">(Upload PDF or Images)</span>
              </span>
              <span className="text-[11px] text-zinc-400">Coursera, AWS, Udemy, etc.</span>
            </div>
            <p className="mt-1 text-[11px] text-zinc-400">
              <span className="text-amber-400 font-medium">Credibility distinction:</span> Certificate provides evidence of learning. GitHub code analysis & SkillProof assessment verify practical demonstration.
            </p>
            <input
              ref={certFileInput}
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.webp"
              className="hidden"
              onChange={e => { const f = e.target.files?.[0]; if (f) handleCertUpload(f); e.target.value = ''; }}
            />
            <button
              type="button"
              onClick={() => certFileInput.current?.click()}
              disabled={busy}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-amber-500/30 py-2.5 text-xs text-amber-200 hover:border-amber-400 hover:bg-amber-500/5 disabled:opacity-50"
            >
              <Award className="h-4 w-4" />
              + Upload Certificate File (PDF, PNG, JPG)
            </button>

            {certificates.length > 0 && (
              <div className="mt-3 space-y-2">
                {certificates.map(c => {
                  const s = (c.issuer_status || '').toLowerCase();
                  const isVerified = s === 'verified' || s === 'issuer_verified';
                  const isPending = s === 'pending' || s === 'issuer_unparsed' || s === 'issuer_unreachable';
                  const isMismatch = (c.mismatch_reason || '').toLowerCase().includes('recipient') || (c.mismatch_reason || '').toLowerCase().includes('mismatch');
                  // The issuer confirmed it for this recipient; it only counts for the candidate if the names match
                  const recipient = c.issuer_record?.recipient_name || '';
                  const holder = candidateName.trim();
                  const otherPerson = isVerified && !!recipient && !!holder && !namesMatch(recipient, holder);
                  const holderUnknown = isVerified && !!recipient && !holder;

                  return (
                    <div key={c.id} className="flex items-start justify-between rounded-md border border-white/10 bg-white/[0.02] p-2.5 text-xs">
                      <div className="space-y-1.5 pr-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold text-zinc-200">{c.certificate_name}</span>
                          <span className="text-amber-400 font-normal">({c.issuer})</span>
                          {isVerified && !otherPerson && (
                            <span className="inline-flex items-center gap-1 rounded bg-emerald-500/15 border border-emerald-500/30 px-2 py-0.5 text-[10px] font-semibold text-emerald-300">
                              ✓ Verified{holderUnknown ? ` for ${recipient}` : ''}
                            </span>
                          )}
                          {otherPerson && (
                            <span className="inline-flex items-center gap-1 rounded bg-rose-500/15 border border-rose-500/30 px-2 py-0.5 text-[10px] font-semibold text-rose-300">
                              ⚠ Issued to {recipient}, not {holder}: won't count
                            </span>
                          )}
                          {isPending && (
                            <span className="inline-flex items-center gap-1 rounded bg-amber-500/15 border border-amber-500/30 px-2 py-0.5 text-[10px] font-semibold text-amber-300" title="Official issuer page recognized; automated parsing pending manual review">
                              ⏳ Pending verification
                            </span>
                          )}
                          {!isVerified && !isPending && (
                            <span className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-semibold border ${
                              isMismatch
                                ? 'bg-rose-500/15 border-rose-500/30 text-rose-300'
                                : 'bg-zinc-500/15 border-zinc-500/30 text-zinc-400'
                            }`}>
                              {isMismatch ? '⚠ Needs Review: Recipient Mismatch' : 'Unverified'}
                            </span>
                          )}
                        </div>

                        <div className="flex flex-wrap items-center gap-2 text-[11px] text-zinc-400">
                          {c.issuer_record?.recipient_name ? (
                            <span className="text-zinc-300">Official Recipient: <span className="text-white font-medium">{c.issuer_record.recipient_name}</span></span>
                          ) : c.candidate_name ? (
                            <span>File Holder: {c.candidate_name}</span>
                          ) : null}

                          {c.verify_url && (
                            <a
                              href={c.verify_url}
                              target="_blank"
                              rel="noreferrer"
                              className={`inline-flex items-center gap-1 font-medium hover:underline ${
                                isPending
                                  ? 'rounded bg-amber-500/20 border border-amber-500/40 px-2 py-0.5 text-amber-200 hover:bg-amber-500/30'
                                  : 'text-sky-400'
                              }`}
                            >
                              {isPending ? 'Verify manually ↗' : 'Issuer URL ↗'}
                            </a>
                          )}

                          {c.evidence_hash && (
                            <span className="font-mono text-[10px] text-zinc-500" title={`Evidence SHA-256: ${c.evidence_hash}`}>
                              SHA: {c.evidence_hash.slice(0, 8)}...
                            </span>
                          )}
                        </div>

                        {c.mismatch_reason && (
                          <p className={`text-[11px] ${isPending ? 'text-amber-300/90' : 'text-rose-400/90'}`}>
                            {c.mismatch_reason}
                          </p>
                        )}
                      </div>
                      <button
                        type="button"
                        onClick={() => removeCert(c.id)}
                        className="rounded p-1 text-zinc-400 hover:bg-white/10 hover:text-red-400"
                        title="Remove certificate"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Candidate Name & Git Identities */}
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className={label} htmlFor="name">Candidate name <span className="font-normal text-red-300">(required)</span></label>
              <input
                id="name"
                required
                value={candidateName}
                onChange={e => setCandidateName(e.target.value)}
                className={input}
                placeholder="Full name, as on certificates"
              />
            </div>
            <div>
              <label className={label} htmlFor="idents">Git email or username <span className="font-normal text-zinc-500">(recommended)</span></label>
              <input
                id="idents"
                value={gitIdentities}
                onChange={e => setGitIdentities(e.target.value)}
                className={input}
                placeholder="you@example.com, your-username"
              />
            </div>
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
              <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />{busyMessage}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 border-t border-white/10 px-6 py-3">
          <button onClick={onClose} className="rounded-lg px-4 py-2 text-sm text-zinc-300 hover:bg-white/5">Cancel</button>
          <button
            onClick={analyze}
            disabled={busy || !candidateName.trim()}
            title={candidateName.trim() ? undefined : "Enter the candidate's name first"}
            className="flex items-center gap-2 rounded-lg bg-indigo-500 px-5 py-2 text-sm font-semibold text-white hover:bg-indigo-400 disabled:opacity-50 shadow-md shadow-indigo-500/20"
          >
            Run Multi-Signal Analysis
          </button>
        </div>
      </div>
    </div>
  );
};
