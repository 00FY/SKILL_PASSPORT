import os
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, UploadFile, File, HTTPException, Body, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .schemas import (
    ClaimsDocument, EvidenceDocument, PassportDocument,
    SimulationRequest, SimulationResult, QuizResult, QuizSubmission,
    ApplyQuizRequest, AuditStep
)
from .skills import normalize_skill
from .jobs import JobManager, JobFailure, QueueFullError
from .limits import RateLimiter, enforce, require_api_key
from .module1_extractor import LLMClaimExtractor, PDFParser
from .module1_extractor.pdf_parser import ResumeParseError
from .module2_harvester import EvidenceHarvesterService, RepoSourceError, RepoAccessError, parse_repo_source
from .module2_harvester.repo_source import local_repos_allowed
from .module2_harvester.harvester_service import MAX_REPOS
from .module3_rubric import (
    PassportService, QuestionBankEngine, CryptoSigner, GRADE_WEIGHTS
)
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


class AnalyzeRequest(BaseModel):
    resume_text: str
    repo_url: Optional[str] = None
    repo_urls: List[str] = Field(default_factory=list, description=f"Up to {MAX_REPOS} public repositories")
    candidate_name: Optional[str] = None
    git_identities: List[str] = Field(default_factory=list, description="Git emails / usernames the candidate commits with")
    links: Optional[List[str]] = None


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


# --- Unified End-to-End Analysis Pipeline ---
def _run_analysis(req: AnalyzeRequest, progress=None) -> PassportDocument:
    report = progress or (lambda _msg: None)
    repos = [u for u in ([req.repo_url] if req.repo_url else []) + req.repo_urls if u and u.strip()]
    links = list(repos) + list(req.links or [])

    # 1. Module 1: Extract claims and guard against prompt injection
    report("Reading the resume")
    claims_doc = extractor.extract_from_text(req.resume_text, links)
    if req.candidate_name and req.candidate_name.strip():
        claims_doc.candidate_name = req.candidate_name.strip()

    # No repositories given: fall back to repository links found in the resume itself
    auto_detected = False
    if not repos:
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

    # 3. Module 3: 4-State Rubric Engine & Cryptographic Signer (evidence was harvested by this server)
    report("Scoring claims and signing the passport")
    return passport_svc.generate_passport(claims_doc, evidence_doc, evidence_source="harvested")


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


# --- Challenge Quiz Engine ---
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
    return quiz_engine.evaluate_quiz(sub.skill, sub.answers)


@app.post("/api/quiz/apply", response_model=PassportDocument)
def apply_quiz_grade(req: ApplyQuizRequest):
    """
    Applies the completed skill challenge test grade to a passport, recalculating
    the skill points via: Final Points = min(100, max(0, Evidence Score * Grade Weight + Consistency Bonus))
    recalculating the overall audit score, appending the audit trace, and re-signing the passport.
    """
    passport = req.passport
    target_skill = normalize_skill(req.skill).lower()
    skill_item = next((s for s in passport.skills if normalize_skill(s.name).lower() == target_skill), None)
    if not skill_item:
        raise HTTPException(status_code=404, detail=f"Skill '{req.skill}' not found in passport claims.")

    grade = req.grade.upper()
    grade_weight = GRADE_WEIGHTS.get(grade, 6)
    skill_item.test_grade = grade

    # Extract consistency bonus if present in reasoning
    consistency_bonus = 0
    if skill_item.reasoning and "Includes +" in skill_item.reasoning:
        matches = re.findall(r"\+(\d+)\s*pts", skill_item.reasoning)
        consistency_bonus = sum(int(m) for m in matches)

    skill_item.final_points = min(100, max(0, skill_item.evidence_score * grade_weight + consistency_bonus))

    # Recalculate overall audit score
    passport.overall_score = round(sum(s.final_points for s in passport.skills) / max(1, len(passport.skills)))

    # Record in audit log
    if passport.audit_log:
        pct_text = f" ({req.percentage}%)" if req.percentage is not None else ""
        passport.audit_log.traces.append(AuditStep(
            step="CHALLENGE_TEST_COMPLETED",
            target=skill_item.name,
            rule_applied=f"CHALLENGE_TEST{pct_text}_GRADE_{grade}(weight:{grade_weight})_FORMULA({skill_item.evidence_score}x{grade_weight}+{consistency_bonus})={skill_item.final_points}",
            verdict_reached=skill_item.verdict.value,
            timestamp=datetime.now(timezone.utc).isoformat()
        ))

    # Re-sign the passport with HMAC-SHA256
    raw_dict = passport.model_dump()
    raw_dict.pop("tamper_proof_hash", None)
    raw_dict["issued_at"] = datetime.now(timezone.utc).isoformat()
    passport.issued_at = raw_dict["issued_at"]
    passport.tamper_proof_hash = CryptoSigner.sign_passport(raw_dict)

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
