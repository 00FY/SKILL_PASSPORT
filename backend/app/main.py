import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, UploadFile, File, HTTPException, Body, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


def _load_env_if_present() -> None:
    env_paths = [
        os.path.join(os.getcwd(), ".env"),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env")),
    ]
    for p in env_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k, v = k.strip(), v.strip().strip("\"'")
                            if k not in os.environ:
                                os.environ[k] = v
                break
            except Exception:
                pass


_load_env_if_present()

from .schemas import (
    ClaimsDocument, EvidenceDocument, PassportDocument,
    SimulationRequest, SimulationResult, QuizResult, QuizSubmission,
    ApplyQuizRequest, AuditStep, RunAuditLog, StartAssessmentRequest,
    TaskSubmissionRequest, StepEvaluationResult, VerdictEnum,
    CertificateEvidence, PillarScores
)
from .skills import normalize_skill
from .jobs import JobManager, JobFailure, QueueFullError
from .limits import RateLimiter, enforce, require_api_key
from .module1_extractor import LLMClaimExtractor, PDFParser
from .module1_extractor.pdf_parser import ResumeParseError
from .module2_harvester import (
    EvidenceHarvesterService, RepoSourceError, RepoAccessError, parse_repo_source,
    ProfileScanner
)
from .module2_harvester.repo_source import local_repos_allowed
from .module2_harvester.harvester_service import MAX_REPOS
from .module4_certs import CertificateParser
from .module3_rubric import (
    PassportService, QuestionBankEngine, QuizAttemptStore, CryptoSigner, GRADE_WEIGHTS,
    AdaptiveAssessmentEngine, CONTRADICTED_POINTS, DeterministicScoringEngine
)
from .schemas import VerdictEnum
from .data.demo_personas import (
    PRIYA_CLAIMS, PRIYA_EVIDENCE,
    ALEX_CLAIMS, ALEX_EVIDENCE,
    JORDAN_CLAIMS, JORDAN_EVIDENCE,
    RED_TEAM_CLAIMS, RED_TEAM_EVIDENCE
)

app = FastAPI(
    title="Skill Passport API",
    description="LLM extracts text, published rules score evidence. Verifiable ground-truth skill passports.",
    version="1.1.0"
)

# Only the configured frontends may call the API from a browser (comma-separated origins)
CORS_ORIGINS = [
    o.strip() for o in os.getenv(
        "SKILL_PASSPORT_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173"
    ).split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)

extractor = LLMClaimExtractor()
pdf_parser = PDFParser()
harvester = EvidenceHarvesterService()
passport_svc = PassportService()
quiz_engine = QuestionBankEngine()
adaptive_engine = AdaptiveAssessmentEngine(storage_dir=".sessions")
quiz_attempts = QuizAttemptStore()
jobs = JobManager()
# Each analysis clones and blames repositories, so they are limited per client address
analysis_limiter = RateLimiter.from_env("SKILL_PASSPORT_RATE_LIMIT", "20/hour")


def limit_analysis(request: Request) -> None:
    require_api_key(request)
    enforce(analysis_limiter, request)


class HarvestRequest(BaseModel):
    repo_url: str
    candidate_name: Optional[str] = None
    git_identities: List[str] = Field(default_factory=list)


class ExtractTextRequest(BaseModel):
    text: str
    links: Optional[List[str]] = None


class DiscoverReposRequest(BaseModel):
    username: str


class AnalyzeRequest(BaseModel):
    resume_text: Optional[str] = None
    github_username: Optional[str] = None
    repo_url: Optional[str] = None
    repo_urls: List[str] = Field(default_factory=list, description=f"Up to {MAX_REPOS} public repositories")
    candidate_name: Optional[str] = None
    git_identities: List[str] = Field(default_factory=list, description="Git emails / usernames the candidate commits with")
    links: Optional[List[str]] = None
    certificates: List[CertificateEvidence] = Field(default_factory=list, description="Verified certificate credentials uploaded by candidate")


class ParsedResumeResponse(BaseModel):
    filename: str
    text: str
    links: List[str]
    repo_urls: List[str]
    warnings: List[str]


def _repo_links(links: List[str]) -> List[str]:
    repos: List[str] = []
    for link in links:
        try:
            url = parse_repo_source(link).url
        except RepoSourceError:
            continue
        if url not in repos:
            repos.append(url)
    return repos


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Skill Passport Core Engine",
        "golden_rule": "LLM extracts text, published rules score evidence."
    }


# --- Module 1: Ingestion & Extraction ---
@app.post("/api/extract/text", response_model=ClaimsDocument)
def extract_from_text(req: ExtractTextRequest):
    return extractor.extract_from_text(req.text, req.links)


async def _read_resume(file: UploadFile):
    contents = await file.read()
    try:
        return pdf_parser.parse_file(file.filename or "", contents)
    except ResumeParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/api/extract/file", response_model=ClaimsDocument)
async def extract_from_file(file: UploadFile = File(...)):
    parsed = await _read_resume(file)
    return extractor.extract_from_text(parsed.text, parsed.links)


@app.post("/api/parse-resume", response_model=ParsedResumeResponse)
async def parse_resume(file: UploadFile = File(...)):
    """Turn an uploaded PDF / DOCX / TXT resume into text the user can review before analysis."""
    parsed = await _read_resume(file)
    return ParsedResumeResponse(
        filename=file.filename or "resume",
        text=parsed.text,
        links=parsed.links,
        repo_urls=_repo_links(parsed.links)[:MAX_REPOS],
        warnings=parsed.warnings,
    )


# --- Module 2: Code Evidence Harvester ---
@app.post("/api/harvest", response_model=EvidenceDocument, dependencies=[Depends(limit_analysis)])
def harvest_evidence(req: HarvestRequest):
    try:
        return harvester.harvest_repo(req.repo_url, req.candidate_name, req.git_identities)
    except RepoSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RepoAccessError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# --- Profile Discovery & Certificate Upload Endpoints ---
@app.post("/api/discover-repos")
def discover_user_repos(req: DiscoverReposRequest):
    """Auto-discover candidate's public non-fork repositories from GitHub username or profile URL."""
    try:
        scanner = ProfileScanner()
        return scanner.scan_profile(req.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/upload-cert", response_model=CertificateEvidence)
async def upload_certificate(file: UploadFile = File(...), candidate_name: Optional[str] = None):
    """Parse an uploaded certificate PDF or image, extracting issuer, credential ID, skills, and confidence."""
    contents = await file.read()
    parser = CertificateParser()
    return parser.parse_file(file.filename or "certificate", contents, candidate_name)


# --- Unified End-to-End Analysis Pipeline ---
def _run_analysis(req: AnalyzeRequest, progress=None) -> PassportDocument:
    report = progress or (lambda _msg: None)
    repos = [u for u in ([req.repo_url] if req.repo_url else []) + req.repo_urls if u and u.strip()]
    links = list(repos) + list(req.links or [])

    # 0. Profile discovery if username provided and no explicit repos given
    profile_info = None
    if req.github_username and req.github_username.strip():
        try:
            report(f"Scanning GitHub profile @{req.github_username.strip()}")
            scanner = ProfileScanner()
            profile_info = scanner.scan_profile(req.github_username.strip())
            if not repos and profile_info.repo_urls:
                repos = profile_info.repo_urls[:MAX_REPOS]
        except Exception:
            pass

    # 1. Module 1: Extract claims or build from code profile & certs (Optional Resume)
    has_resume = bool(req.resume_text and req.resume_text.strip())
    if has_resume:
        report("Reading the resume")
        claims_doc = extractor.extract_from_text(req.resume_text, links)
    else:
        report("Building skill profile from code repositories and credentials")
        cand_name = (
            req.candidate_name
            or (profile_info.name if profile_info else None)
            or req.github_username
            or "Candidate"
        )
        claims_doc = ClaimsDocument(
            candidate_name=cand_name,
            applied_role="Software Engineer",
            claims=[],
            raw_text_length=0,
            sanitized_text_preview="(Evaluated via Code Profile & Verified Credentials without Resume)"
        )

    if req.candidate_name and req.candidate_name.strip():
        claims_doc.candidate_name = req.candidate_name.strip()

    if profile_info:
        claims_doc.github_profile = profile_info.model_dump()

    # Attach uploaded certificates
    if req.certificates:
        claims_doc.certificates = req.certificates

    # No repositories given: fall back to repository links found in the resume itself
    auto_detected = False
    if not repos and has_resume:
        resume_links = [l for c in claims_doc.claims for l in c.evidence_links] + links
        resume_links += pdf_parser.parse_text_or_markdown(req.resume_text)[1]
        repos = _repo_links(resume_links)[:MAX_REPOS]
        auto_detected = bool(repos)

    # 2. Module 2: Code Evidence Harvester (real git blame, AST parsing, test detection)
    try:
        evidence_doc = harvester.harvest_many(repos, claims_doc.candidate_name, req.git_identities, progress=report)
    except RepoSourceError as exc:
        raise JobFailure(str(exc), 400)
    except RepoAccessError as exc:
        raise JobFailure(str(exc), 422)
    if auto_detected:
        evidence_doc.warnings.insert(0, f"No repository was entered; analysed repositories linked in the resume: {', '.join(repos)}.")

    # 3. Module 3: 4-State Rubric Engine & Cryptographic Signer
    report("Scoring claims and signing the passport")
    gh_user = req.github_username.strip() if req.github_username and req.github_username.strip() else None
    return passport_svc.generate_passport(
        claims_doc, evidence_doc, evidence_source="harvested", github_username=gh_user
    )


@app.post("/api/analyze", response_model=PassportDocument, dependencies=[Depends(limit_analysis)])
def analyze_candidate(req: AnalyzeRequest):
    """Synchronous analysis for scripts. Browsers should use /api/jobs/analyze, since this can take minutes."""
    try:
        return _run_analysis(req)
    except JobFailure as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc))


@app.post("/api/jobs/analyze", status_code=202, dependencies=[Depends(limit_analysis)])
def start_analysis_job(req: AnalyzeRequest):
    # Reject malformed repository links immediately instead of after queueing
    for url in ([req.repo_url] if req.repo_url else []) + req.repo_urls:
        if url and url.strip():
            try:
                parse_repo_source(url, allow_local=local_repos_allowed())
            except RepoSourceError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
    try:
        job = jobs.submit(lambda progress: _run_analysis(req, progress).model_dump(mode="json"))
    except QueueFullError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"job_id": job.id, "status": job.status}


@app.get("/api/jobs/{job_id}")
def get_analysis_job(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown or expired job.")
    return {
        "job_id": job.id,
        "status": job.status,
        "message": job.message,
        "passport": job.result,
        "error": job.error,
        "error_status": job.error_status,
    }


# Note: there is deliberately no endpoint that scores caller-supplied evidence. The server's
# signature vouches for the evidence, so it only signs evidence it harvested itself.


# --- Module 3 & 4: What-If Simulator ---
@app.post("/api/simulate", response_model=SimulationResult)
def simulate_what_if(req: SimulationRequest):
    return passport_svc.simulate_what_if(req)


# --- Outlier-Style Adaptive Technical Assessment Engine ---
@app.post("/api/assessment/start")
def start_assessment(req: StartAssessmentRequest):
    try:
        return adaptive_engine.start_session(
            skill=req.skill,
            passport_hash=req.passport_hash or "",
            initial_verdict=req.initial_verdict,
            candidate_name=req.candidate_name,
            applied_role=req.applied_role,
            repo_context=req.repo_context
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/assessment/start/{skill}")
def start_assessment_get(skill: str, initial_verdict: Optional[str] = None):
    try:
        return adaptive_engine.start_session(skill=skill, initial_verdict=initial_verdict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/assessment/submit-step", response_model=StepEvaluationResult)
def submit_assessment_step(req: TaskSubmissionRequest):
    try:
        session = adaptive_engine.sessions.get(req.session_id)
        skill_name = session["skill"] if session else ""
        res = adaptive_engine.submit_step(req)
        if res.is_complete and res.final_grade:
            attempt_id = quiz_attempts.record(
                normalize_skill(skill_name),
                res.final_grade,
                res.final_weighted_score or 0.0
            )
            res.attempt_id = attempt_id
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Assessment step evaluation failed: {e}")


# --- Challenge Quiz Engine (Backward-Compatible) ---
@app.get("/api/quiz/{skill}")
def get_quiz(skill: str):
    # Answers and explanations stay on the server until the quiz is submitted
    questions = quiz_engine.public_questions(skill)
    if not questions:
        raise HTTPException(status_code=404, detail=f"No Skill Challenge exists for '{skill}' yet.")
    return {"skill": skill, "questions": questions}


@app.post("/api/quiz/submit", response_model=QuizResult)
def submit_quiz(sub: QuizSubmission):
    if not quiz_engine.get_questions_for_skill(sub.skill):
        raise HTTPException(status_code=404, detail=f"No Skill Challenge exists for '{sub.skill}' yet.")
    result = quiz_engine.evaluate_quiz(sub.skill, sub.answers)
    # Remember the graded attempt server-side; the client only gets an id it can redeem once
    result.attempt_id = quiz_attempts.record(normalize_skill(sub.skill), result.grade, result.percentage)
    return result


@app.post("/api/quiz/apply", response_model=PassportDocument)
def apply_quiz_grade(req: ApplyQuizRequest):
    """
    Applies a graded skill challenge (standard or adaptive) to a passport and re-signs it.

    Two checks keep this from becoming a way to get arbitrary passports signed:
    - the passport must carry a valid signature from this server, so it can't have been edited;
    - the grade comes from the server's record of a submitted quiz (single use), not from the client.
    Only the challenged skill's grade and points change: Evidence x Grade Weight + Consistency Bonus (max 100).
    An assessment grade can boost CLAIMED_ONLY or PARTIALLY_SUPPORTED points, but can never override CONTRADICTED.
    """
    passport = req.passport
    signed_payload = passport.model_dump(mode="json")
    if not CryptoSigner.verify_passport_signature(signed_payload, passport.tamper_proof_hash)["valid"]:
        raise HTTPException(status_code=400, detail="This passport's signature is invalid, so a challenge grade can't be applied to it.")

    attempt = quiz_attempts.get(req.attempt_id)
    if attempt is None:
        raise HTTPException(status_code=400, detail="Unknown, expired or already used quiz attempt. Take the challenge again.")

    target_skill = attempt.skill.lower()
    skill_item = next((s for s in passport.skills if normalize_skill(s.name).lower() == target_skill), None)
    if not skill_item:
        raise HTTPException(status_code=404, detail=f"Skill '{attempt.skill}' is not one of this passport's claims.")
    if skill_item.verdict == VerdictEnum.CONTRADICTED:
        raise HTTPException(status_code=409, detail=f"{skill_item.name} is contradicted by repository evidence; a quiz can't override that.")

    quiz_attempts.consume(req.attempt_id)
    grade = attempt.grade
    grade_weight = GRADE_WEIGHTS[grade]
    skill_item.test_grade = grade
    skill_item.final_points = DeterministicScoringEngine.calculate_skill_points(
        skill_item.evidence_score, grade, consistency_bonus=skill_item.consistency_bonus
    )

    # Clean up pending quiz notice
    skill_item.signals = [s for s in skill_item.signals if "Quiz Pending" not in s]
    if skill_item.reasoning:
        skill_item.reasoning = re.sub(r"\s*Mandatory (?:skill )?challenge (?:quiz )?pending.*", "", skill_item.reasoning).strip()
        skill_item.reasoning += f" Completed skill challenge quiz (Grade {grade})."

    # Recalculate pillar scores and balanced overall score
    if passport.pillar_scores:
        tested_skills = [s for s in passport.skills if s.test_grade != "E"]
        if tested_skills:
            quiz_weights = [GRADE_WEIGHTS.get(s.test_grade, 6) * 10 for s in tested_skills]
            passport.pillar_scores.quiz_score = round(sum(quiz_weights) / len(quiz_weights))
        passport.pillar_scores.code_score = round(sum(s.final_points for s in passport.skills) / max(1, len(passport.skills)))
        balanced_overall, weights_used = DeterministicScoringEngine.calculate_pillar_scores(
            code_score=passport.pillar_scores.code_score,
            resume_score=passport.pillar_scores.resume_score,
            cert_score=passport.pillar_scores.cert_score,
            quiz_score=passport.pillar_scores.quiz_score
        )
        passport.pillar_scores.overall_score = balanced_overall
        passport.pillar_scores.weights_used = weights_used
        passport.overall_score = balanced_overall
    else:
        passport.overall_score = DeterministicScoringEngine.overall_score([s.final_points for s in passport.skills])

    if passport.audit_log is None:
        passport.audit_log = RunAuditLog(
            audit_id=f"audit_{uuid.uuid4().hex[:10]}",
            candidate_name=passport.candidate_name,
            traces=[],
            generated_at=datetime.now(timezone.utc).isoformat()
        )

    if req.trajectory:
        passport.audit_log.traces.append(AuditStep(
            step="ADAPTIVE_ASSESSMENT_COMPLETED",
            target=skill_item.name,
            rule_applied=f"Trajectory: {req.trajectory} | Weighted: {attempt.percentage}%",
            verdict_reached=f"Grade {grade} applied; HMAC-SHA256 passport re-signed",
            timestamp=datetime.now(timezone.utc).isoformat()
        ))
    else:
        passport.audit_log.traces.append(AuditStep(
            step="CHALLENGE_TEST_COMPLETED",
            target=skill_item.name,
            rule_applied=(
                f"CHALLENGE_TEST({attempt.percentage}%)_GRADE_{grade}(weight:{grade_weight})_"
                f"FORMULA({skill_item.evidence_score}x{grade_weight}+{skill_item.consistency_bonus})={skill_item.final_points}"
            ),
            verdict_reached=skill_item.verdict.value,
            timestamp=datetime.now(timezone.utc).isoformat()
        ))

    passport.issued_at = datetime.now(timezone.utc).isoformat()
    passport.tamper_proof_hash = CryptoSigner.sign_passport(passport.model_dump(mode="json"))
    return passport


# --- Cryptographic Verification ---
@app.post("/api/verify-signature")
def verify_signature(payload: Dict[str, Any] = Body(...), claimed_hash: Optional[str] = None):
    target_hash = claimed_hash or payload.get("tamper_proof_hash", "")
    result = CryptoSigner.verify_passport_signature(payload, target_hash)
    return {
        "valid": result["valid"],
        "is_valid": result["valid"],
        "reason": result["reason"],
        "claimed_hash": target_hash
    }


# --- Pre-computed Demo Personas (offline demo data, clearly separate from real analysis) ---
@app.get("/api/demo/{persona}", response_model=PassportDocument)
def get_demo_persona(persona: str):
    key = persona.lower()
    if key in ["priya", "honest"]:
        return passport_svc.generate_passport(PRIYA_CLAIMS, PRIYA_EVIDENCE, {"Python": "A", "FastAPI": "B", "Docker": "C"}, evidence_source="demo")
    elif key in ["alex", "inflater", "spammer"]:
        return passport_svc.generate_passport(ALEX_CLAIMS, ALEX_EVIDENCE, {"Python": "D", "Kubernetes": "E"}, evidence_source="demo")
    elif key in ["jordan", "learner"]:
        return passport_svc.generate_passport(JORDAN_CLAIMS, JORDAN_EVIDENCE, {"Python": "B", "Docker": "C"}, evidence_source="demo")
    elif key in ["redteam", "security", "adversary", "cheater"]:
        return passport_svc.generate_passport(RED_TEAM_CLAIMS, RED_TEAM_EVIDENCE, {"Python": "D"}, evidence_source="demo")
    else:
        raise HTTPException(status_code=404, detail="Persona not found. Use 'priya', 'alex', 'jordan', or 'redteam'.")
