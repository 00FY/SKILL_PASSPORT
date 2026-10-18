from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

class VerdictEnum(str, Enum):
    VERIFIED = "VERIFIED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    CLAIMED_ONLY = "CLAIMED_ONLY"
    CONTRADICTED = "CONTRADICTED"

class SecurityFlag(BaseModel):
    flag_type: str = Field(description="Type of threat, e.g. PROMPT_INJECTION, ZERO_WIDTH_CHARS, WHITE_TEXT")
    severity: str = Field(default="HIGH", description="LOW, MEDIUM, HIGH, CRITICAL")
    raw_payload_snippet: str
    action_taken: str = "Stripped from text and quarantined"

# --- Module 1: Ingestion & Claims ---
class ClaimItem(BaseModel):
    id: str
    skill: str
    category: str = "language"  # language, framework, devops, soft_skill, database, etc.
    claimed_duration_months: Optional[int] = 0
    claimed_detail: Optional[str] = None
    evidence_links: List[str] = Field(default_factory=list)

class CertificateEvidence(BaseModel):
    id: str
    filename: str
    certificate_name: str
    issuer: str
    candidate_name: Optional[str] = None
    issue_date: Optional[str] = None
    credential_id: Optional[str] = None
    verify_url: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    confidence_score: float = 0.8
    raw_text_snippet: Optional[str] = None

class ClaimsDocument(BaseModel):
    candidate_name: str
    applied_role: str
    claims: List[ClaimItem] = Field(default_factory=list)
    certificates: List[CertificateEvidence] = Field(default_factory=list)
    github_profile: Optional[Dict[str, Any]] = None
    security_flags: List[SecurityFlag] = Field(default_factory=list)
    raw_text_length: int = 0
    sanitized_text_preview: Optional[str] = None

# --- Module 2: Code Evidence ---
class SampleSnippet(BaseModel):
    file: str
    lines: str
    blame_match: float = 1.0
    code_preview: Optional[str] = None

class SkillEvidence(BaseModel):
    lines_authored: int = 0
    total_lines: int = 0
    authorship_pct: Optional[float] = Field(default=None, description="Candidate share of lines in the files backing this skill")
    files_count: int = 0
    sample_snippet: Optional[SampleSnippet] = None
    imports_found: List[str] = Field(default_factory=list)
    route_definitions: int = 0
    repo_count: int = Field(default=1, description="Number of distinct repositories evidencing this skill")
    active_months: int = Field(default=0, description="Distinct calendar months of commits touching this skill's files")
    distinct_months: List[str] = Field(default_factory=list, description="Sorted list of distinct YYYY-MM commit months")

class QualitySignals(BaseModel):
    has_tests: bool = False
    test_framework: Optional[str] = None
    test_frameworks: List[str] = Field(default_factory=list)
    test_file_count: int = 0
    test_assertion_count: int = 0
    has_error_handling: bool = False
    merged_prs: int = 0
    deployed_url: Optional[str] = None
    single_day_commit_dump: bool = False
    commit_laundering_detected: bool = False
    commit_count: int = 0
    candidate_commit_count: int = 0

class ExcludedRepo(BaseModel):
    repo_url: str
    reason: str

class EvidenceDocument(BaseModel):
    repo_url: str
    repo_urls: List[str] = Field(default_factory=list)
    is_fork: bool = False
    is_cloned_template: bool = False
    candidate_authorship_pct: float = 0.0
    first_commit: Optional[str] = None
    last_commit: Optional[str] = None
    active_months: int = 0
    unique_contributors: Optional[int] = None
    total_code_lines: int = 0
    candidate_code_lines: int = 0
    authors_found: List[str] = Field(default_factory=list, description="Top commit identities seen in the repo (helps fix identity mismatches)")
    identities_used: List[str] = Field(default_factory=list)
    skills_detected: Dict[str, SkillEvidence] = Field(default_factory=dict)
    signals: QualitySignals = Field(default_factory=QualitySignals)
    excluded_repos: List[ExcludedRepo] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    raw_audit_notes: List[str] = Field(default_factory=list)

# --- Module 3: Rubric, Verdicts & Passport ---
class SkillPassportItem(BaseModel):
    name: str
    category: str = "language"
    verdict: VerdictEnum
    level: str = "Beginner"  # Beginner, Intermediate, Advanced, Expert
    evidence_score: int = Field(ge=0, le=10, description="0-10 based on evidence hierarchy")
    test_grade: str = Field(description="A (10), B (8), C (6), D (4), E (2)")
    final_points: int = Field(ge=0, le=100, description="evidence_score * grade_weight + consistency_bonus, capped at 100")
    consistency_bonus: int = Field(default=0, ge=0, description="Points added for evidence across repos / months (included in final_points)")
    proof_snippet: Optional[str] = None
    sample_code: Optional[str] = None
    authorship_pct: Optional[float] = None
    files_count: Optional[int] = None
    signals: List[str] = Field(default_factory=list)
    reasoning: Optional[str] = None

class RefusalItem(BaseModel):
    claim: str
    verdict: VerdictEnum
    reason: str
    evidence_found: Optional[str] = None
    suggested_remedy: Optional[str] = None

class LearningPlanItem(BaseModel):
    action: str
    skill: str
    potential_impact: str
    target_score_delta: int = 5
    repo_context: Optional[str] = None

class QuizQuestion(BaseModel):
    id: str
    skill: str
    difficulty: str  # Basic, Intermediate, Advanced
    question: str
    options: List[str]
    correct_index: int
    explanation: str

class PublicQuizQuestion(BaseModel):
    """A quiz question as sent to the browser: no answer, no explanation."""
    id: str
    skill: str
    difficulty: str
    question: str
    options: List[str]

class QuizReviewItem(BaseModel):
    id: str
    chosen_index: Optional[int] = None
    correct_index: int
    explanation: str

class QuizSubmission(BaseModel):
    skill: str
    answers: Dict[str, int]  # question_id -> selected_index

class QuizResult(BaseModel):
    skill: str
    total_questions: int
    correct_count: int
    percentage: float
    grade: str  # A, B, C, D, E
    grade_weight: int
    review: List[QuizReviewItem] = Field(default_factory=list, description="Answers revealed only after submission")
    attempt_id: Optional[str] = Field(default=None, description="Server-side record of this graded attempt; pass to /api/quiz/apply")

class AuditStep(BaseModel):
    step: str
    target: str
    rule_applied: str
    verdict_reached: str
    timestamp: str

class RunAuditLog(BaseModel):
    audit_id: str
    candidate_name: str
    traces: List[AuditStep] = Field(default_factory=list)
    generated_at: str

class PillarScores(BaseModel):
    code_score: Optional[int] = Field(default=None, description="Score based on git blame, tests, authorship, commits (0-100)")
    resume_score: Optional[int] = Field(default=None, description="Score based on resume claims verification (0-100)")
    cert_score: Optional[int] = Field(default=None, description="Score based on verified certificates (0-100)")
    quiz_score: Optional[int] = Field(default=None, description="Score based on mandatory skill challenge quizzes (0-100)")
    overall_score: int = Field(description="Final balanced score across active pillars")
    weights_used: Dict[str, float] = Field(default_factory=dict, description="Active pillar weights, e.g. code: 0.40, quiz: 0.25")

class PassportDocument(BaseModel):
    evidence_source: str = Field(
        default="harvested",
        description="'harvested' = evidence collected by this server from real repositories; 'demo' = fictional sample data"
    )
    candidate_name: str
    applied_role: str
    role_match_pct: int
    overall_score: int
    candidate_authorship_pct: Optional[float] = 0.0
    active_months: Optional[int] = 1
    total_commits: Optional[int] = 0
    repo_url: Optional[str] = None
    repo_urls: List[str] = Field(default_factory=list)
    github_username: Optional[str] = None
    is_fork: Optional[bool] = False
    skills: List[SkillPassportItem] = Field(default_factory=list)
    refusal_panel: List[RefusalItem] = Field(default_factory=list)
    learning_plan: List[LearningPlanItem] = Field(default_factory=list)
    security_alerts: List[SecurityFlag] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    pillar_scores: Optional[PillarScores] = None
    certificates: List[CertificateEvidence] = Field(default_factory=list)
    tamper_proof_hash: str
    issued_at: str
    audit_log: Optional[RunAuditLog] = None

# --- What-If Simulator Schemas ---
class SimulationRequest(BaseModel):
    base_passport: PassportDocument
    toggles: Dict[str, bool]  # add_pytest / add_tests, add_deploy / deployed_url, sustained_commits / author_more

class SimulationResult(BaseModel):
    previous_score: int
    new_score: int
    previous_role_match_pct: int
    new_role_match_pct: int
    score_delta: int
    updated_skills: List[SkillPassportItem]
    resolved_refusals: List[str]

class ApplyQuizRequest(BaseModel):
    """The grade comes from the server's record of the attempt, never from the client."""
    passport: PassportDocument
    attempt_id: str

