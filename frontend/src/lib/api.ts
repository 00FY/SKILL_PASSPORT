export class ApiError extends Error {}

const describe = async (res: Response): Promise<string> => {
  try {
    const body = await res.json();
    if (typeof body.detail === 'string') return body.detail;
    if (Array.isArray(body.detail)) return body.detail.map((d: { msg?: string }) => d.msg).join('; ');
  } catch {
    // fall through
  }
  return `Request failed with status ${res.status}.`;
};

// Only for private deployments: a key built into the frontend is visible to anyone who loads it
const API_KEY: string | undefined = import.meta.env.VITE_SKILL_PASSPORT_API_KEY;

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  const headers = new Headers(init?.headers);
  if (API_KEY) headers.set('X-API-Key', API_KEY);
  try {
    res = await fetch(path, { ...init, headers });
  } catch {
    throw new ApiError('Could not reach the backend. Is the API running on port 8000?');
  }
  if (!res.ok) throw new ApiError(await describe(res));
  return res.json() as Promise<T>;
}

export const postJson = <T,>(path: string, body: unknown) =>
  request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

/** Poll a background job until it finishes, reporting its progress messages. */
export async function waitForJob<T extends { status: string; message: string; error: string | null }>(
  jobId: string,
  onProgress: (message: string) => void,
  intervalMs = 1500,
): Promise<T> {
  for (;;) {
    const job = await request<T>(`/api/jobs/${jobId}`);
    if (job.status === 'done') return job;
    if (job.status === 'failed') throw new ApiError(job.error || 'Analysis failed.');
    onProgress(job.message);
  }
}

export interface DiscoveredProfile {
  username: string;
  name?: string | null;
  bio?: string | null;
  avatar_url?: string | null;
  public_repos_count: number;
  repo_urls: string[];
  detected_languages: string[];
  topics: string[];
  warnings: string[];
}

export interface CertificateEvidence {
  id: string;
  filename: string;
  certificate_name: string;
  issuer: string;
  candidate_name?: string | null;
  issue_date?: string | null;
  credential_id?: string | null;
  verify_url?: string | null;
  skills: string[];
  confidence_score: number;
  raw_text_snippet?: string | null;
}

export const discoverRepos = (username: string) =>
  postJson<DiscoveredProfile>('/api/discover-repos', { username });

export const uploadCert = async (file: File, candidateName?: string): Promise<CertificateEvidence> => {
  const form = new FormData();
  form.append('file', file);
  if (candidateName) form.append('candidate_name', candidateName);
  return request<CertificateEvidence>('/api/upload-cert', { method: 'POST', body: form });
};
