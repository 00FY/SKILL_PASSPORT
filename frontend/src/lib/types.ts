export type Verdict = 'VERIFIED' | 'PARTIALLY_SUPPORTED' | 'CLAIMED_ONLY' | 'CONTRADICTED';

export interface SecurityFlag {
  flag_type: string;
  severity: string;
  raw_payload_snippet: string;
  action_taken: string;
}

export interface SkillPassportItem {
  name: string;
  category: string;
  verdict: Verdict;
  level: string;
  evidence_score: number;
  test_grade: string;
  final_points: number;
  proof_snippet?: string | null;
  sample_code?: string | null;
  authorship_pct?: number | null;
  files_count?: number | null;
  signals: string[];
  reasoning?: string | null;
}

export interface RefusalItem {
  claim: string;
  verdict: Verdict;
  reason: string;
  evidence_found?: string | null;
  suggested_remedy?: string | null;
}

export interface LearningPlanItem {
  action: string;
  skill: string;
  potential_impact: string;
  target_score_delta: number;
  repo_context?: string | null;
}

export interface AuditStep {
  step: string;
  target: string;
  rule_applied: string;
  verdict_reached: string;
  timestamp: string;
}

export interface RunAuditLog {
  audit_id: string;
  candidate_name: string;
  traces: AuditStep[];
  generated_at: string;
}

export interface PassportDocument {
  evidence_source?: 'harvested' | 'demo';
  candidate_name: string;
  applied_role: string;
  role_match_pct: number;
  overall_score: number;
  candidate_authorship_pct?: number | null;
  active_months?: number | null;
  total_commits?: number | null;
  repo_url?: string | null;
  repo_urls?: string[];
  is_fork?: boolean | null;
  skills: SkillPassportItem[];
  refusal_panel: RefusalItem[];
  learning_plan: LearningPlanItem[];
  security_alerts: SecurityFlag[];
  warnings?: string[];
  tamper_proof_hash: string;
  issued_at: string;
  audit_log?: RunAuditLog | null;
}

// Sent without answers; they arrive in QuizResult.review after submission
export interface QuizQuestion {
  id: string;
  skill: string;
  difficulty: string;
  question: string;
  options: string[];
}

export interface QuizReviewItem {
  id: string;
  chosen_index: number | null;
  correct_index: number;
  explanation: string;
}

export interface QuizResult {
  skill: string;
  total_questions: number;
  correct_count: number;
  percentage: number;
  grade: string;
  grade_weight: number;
  review: QuizReviewItem[];
}

export interface AnalysisJob {
  job_id: string;
  status: 'queued' | 'running' | 'done' | 'failed';
  message: string;
  passport: PassportDocument | null;
  error: string | null;
}

// --- Outlier-Style Adaptive Assessment Types ---
export type StageType = 'comprehension' | 'debugging' | 'coding' | 'reasoning';
export type DifficultyTier = 1 | 2 | 3;

export interface PublicTaskItem {
  task_id: string;
  skill: string;
  stage_type: StageType;
  difficulty: DifficultyTier;
  prompt: string;
  starter_code?: string | null;
  options?: string[] | null;
  sample_tests?: string[] | null;
}

export interface TaskSubmissionRequest {
  session_id: string;
  task_id: string;
  selected_option?: number | null;
  submitted_code?: string | null;
  reasoning_text?: string | null;
}

export interface TestCaseResult {
  test_case: number;
  passed: boolean;
  expected?: any;
  actual?: any;
  error?: string;
}

export interface StepEvaluationResult {
  task_id: string;
  passed: boolean;
  step_score: number;
  difficulty_attempted: DifficultyTier;
  next_difficulty?: DifficultyTier | null;
  feedback: string;
  test_results: TestCaseResult[];
  rubric_hits: string[];
  is_complete: boolean;
  next_task?: PublicTaskItem | null;
  final_grade?: string | null;
  final_weighted_score?: number | null;
  trajectory?: string | null;
}

export interface StartAssessmentResponse {
  session_id: string;
  task: PublicTaskItem;
}

