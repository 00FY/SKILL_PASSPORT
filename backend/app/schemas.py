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

class ClaimsDocument(BaseModel):
    candidate_name: str
    applied_role: str
    claims: List[ClaimItem] = Field(default_factory=list)
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
    files_count: int = 0
    sample_snippet: Optional[SampleSnippet] = None
    imports_found: List[str] = Field(default_factory=list)
    route_definitions: int = 0

class QualitySignals(BaseModel):
    has_tests: bool = False
    test_framework: Optional[str] = None
    test_file_count: int = 0
    test_assertion_count: int = 0
    has_error_handling: bool = False
    merged_prs: int = 0
    deployed_url: Optional[str] = None
    single_day_commit_dump: bool = False
    commit_laundering_detected: bool = False
    commit_count: int = 0

class EvidenceDocument(BaseModel):
    repo_url: str
    is_fork: bool = False
    is_cloned_template: bool = False
    candidate_authorship_pct: float = 0.0
    first_commit: Optional[str] = None
    last_commit: Optional[str] = None
    active_months: int = 0
    skills_detected: Dict[str, SkillEvidence] = Field(default_factory=dict)
    signals: QualitySignals = Field(default_factory=QualitySignals)
    raw_audit_notes: List[str] = Field(default_factory=list)

# --- Module 3: Rubric, Verdicts & Passport ---
class SkillPassportItem(BaseModel):
    name: str
    category: str = "language"
    verdict: VerdictEnum
    level: str = "Beginner"  # Beginner, Intermediate, Advanced, Expert
    evidence_score: int = Field(ge=0, le=10, description="0-10 based on evidence hierarchy")
    test_grade: str = Field(description="A (10), B (8), C (6), D (4), E (2)")
    final_points: int = Field(ge=0, le=100, description="evidence_score * grade_weight")
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

class PassportDocument(BaseModel):
    candidate_name: str
    applied_role: str
    role_match_pct: int
    overall_score: int
    candidate_authorship_pct: Optional[float] = 0.0
    active_months: Optional[int] = 1
    total_commits: Optional[int] = 0
    repo_url: Optional[str] = None
    is_fork: Optional[bool] = False
    skills: List[SkillPassportItem] = Field(default_factory=list)
    refusal_panel: List[RefusalItem] = Field(default_factory=list)
    learning_plan: List[LearningPlanItem] = Field(default_factory=list)
    security_alerts: List[SecurityFlag] = Field(default_factory=list)
    tamper_proof_hash: str
    issued_at: str
    audit_log: Optional[RunAuditLog] = None

# --- What-If Simulator Schemas ---
class SimulationRequest(BaseModel):
    base_passport: PassportDocument
    toggles: Dict[str, bool]  # e.g., {"add_pytest_shopapi": True, "sustained_commits_python": True}

class SimulationResult(BaseModel):
    previous_score: int
    new_score: int
    previous_role_match_pct: int
    new_role_match_pct: int
    score_delta: int
    updated_skills: List[SkillPassportItem]
    resolved_refusals: List[str]
