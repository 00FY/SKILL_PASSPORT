import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, UploadFile, File, HTTPException, Body, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .schemas import (
    ClaimsDocument, EvidenceDocument, PassportDocument,
    SimulationRequest, SimulationResult, QuizResult, QuizSubmission,
    ApplyQuizRequest, AuditStep, RunAuditLog, StartAssessmentRequest,
    TaskSubmissionRequest, StepEvaluationResult, VerdictEnum,
    AuthorshipCheck, DefendStartRequest, DefendAnswerRequest, DefendApplyRequest,
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
from .module3_rubric.sandbox import SandboxUnavailable
from .module3_rubric import (
    PassportService, QuestionBankEngine, QuizAttemptStore, CryptoSigner, GRADE_WEIGHTS,
    AdaptiveAssessmentEngine, CONTRADICTED_POINTS, DeterministicScoringEngine
)
from .module3_rubric.adaptive_engine import AttemptLimitReached
from .module3_rubric.defend_your_code import (
    DefendYourCode, adjust_points, STATUS_AVAILABLE, STATUS_UNAVAILABLE, STATUS_CONFIRMED, STATUS_NOT_EXPLAINED,
    BONUS_POINTS, FAIL_FACTOR,
)
from .module2_harvester.function_picker import functions_from_source
from .data.demo_defend import DEMO_DEFEND_FILES
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
defend = DefendYourCode(sandbox=adaptive_engine.sandbox)
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
    profile_problem = None
    if req.github_username and req.github_username.strip():
        try:
            report(f"Scanning GitHub profile @{req.github_username.strip()}")
            scanner = ProfileScanner()
            profile_info = scanner.scan_profile(req.github_username.strip())
            if not repos and profile_info.repo_urls:
                repos = profile_info.repo_urls[:MAX_REPOS]
            if not profile_info.repo_urls and profile_info.warnings:
                profile_problem = profile_info.warnings[0]
        except ValueError as exc:
            profile_problem = str(exc)
        except Exception as exc:
            profile_problem = f"GitHub profile lookup failed: {exc}"

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

    if not repos and profile_problem:
        # The repositories were meant to come from the GitHub profile; don't issue a passport without them
        raise JobFailure(
            f"Couldn't list @{req.github_username.strip()}'s repositories: {profile_problem} "
            "Paste the repository URLs into 'Repositories to analyze' instead (cloning doesn't use the GitHub API), "
            "or set GITHUB_TOKEN on the server and try again.",
            503,
        )

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
    passport = passport_svc.generate_passport(
        claims_doc, evidence_doc, evidence_source="harvested", github_username=gh_user
    )
    report("Preparing Defend Your Code questions from the candidate's own functions")
    return _attach_defend(passport, functions=evidence_doc.authored_functions)


# --- Defend Your Code: optional questions about the candidate's own functions ---
DEFEND_SKILL = "Python"
_demo_defend_questions: Dict[str, list] = {}


def _attach_defend(passport: PassportDocument, functions: Optional[list] = None,
                   prebuilt: Optional[list] = None) -> PassportDocument:
    """Marks whether Defend Your Code is available for the passport's Python claim, and re-signs it."""
    item = next((s for s in passport.skills if normalize_skill(s.name) == DEFEND_SKILL), None)
    if not item or item.verdict not in (VerdictEnum.VERIFIED, VerdictEnum.PARTIALLY_SUPPORTED):
        return passport
    reason = ""
    if prebuilt is not None:
        questions = prebuilt
    else:
        try:
            questions, reason = defend.build_questions(functions or [], seed=passport.passport_id or "")
        except SandboxUnavailable:
            questions, reason = [], "The code runner was busy; re-run the analysis to enable it."
    if questions:
        defend.register(_passport_key(passport), item.name, questions)
        item.authorship_check = AuthorshipCheck(
            status=STATUS_AVAILABLE,
            question_count=len(questions),
            commits=sorted({f"{q['repo_url']}@{q['commit'][:7]}" for q in questions if q.get("commit")}),
        )
    else:
        item.authorship_check = AuthorshipCheck(status=STATUS_UNAVAILABLE, reason=reason)
    passport.tamper_proof_hash = CryptoSigner.sign_passport(passport.model_dump(mode="json"))
    return passport


def _demo_defend(passport: PassportDocument, persona: str) -> PassportDocument:
    spec = DEMO_DEFEND_FILES.get(persona)
    if not spec:
        return passport
    if persona not in _demo_defend_questions:
        functions = [
            f for path, source in spec["files"].items()
            for f in functions_from_source(source.lstrip("\n"), path, None, spec["repo_url"], spec["commit"])
        ]
        try:
            questions, _ = defend.build_questions(functions, seed=f"demo:{persona}")
        except SandboxUnavailable:
            return passport
        _demo_defend_questions[persona] = questions
    return _attach_defend(passport, prebuilt=_demo_defend_questions[persona])


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
def _passport_key(passport: PassportDocument) -> str:
    # passport_id survives re-signing; older passports without one fall back to their signature
    return passport.passport_id or passport.tamper_proof_hash


@app.post("/api/assessment/start")
def start_assessment(req: StartAssessmentRequest):
    """
    Starts an adaptive assessment for one claim of a signed passport. The passport decides the starting
    difficulty, and each passport gets a limited number of attempts per skill, so a grade can't be
    farmed by retrying until it comes out high.
    """
    passport = req.passport
    if not CryptoSigner.verify_passport_signature(passport.model_dump(mode="json"), passport.tamper_proof_hash)["valid"]:
        raise HTTPException(status_code=400, detail="This passport's signature is invalid, so an assessment can't be started for it.")
    target = normalize_skill(req.skill).lower()
    skill_item = next((s for s in passport.skills if normalize_skill(s.name).lower() == target), None)
    if not skill_item:
        raise HTTPException(status_code=404, detail=f"Skill '{req.skill}' is not one of this passport's claims.")
    if skill_item.verdict == VerdictEnum.CONTRADICTED:
        raise HTTPException(status_code=409, detail=f"{skill_item.name} is contradicted by repository evidence; an assessment can't override that.")
    try:
        return adaptive_engine.start_session(
            skill=skill_item.name,
            passport_hash=_passport_key(passport),
            initial_verdict=skill_item.verdict.value,
        )
    except AttemptLimitReached as e:
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/assessment/submit-step", response_model=StepEvaluationResult)
def submit_assessment_step(req: TaskSubmissionRequest):
    try:
        res = adaptive_engine.submit_step(req)
        if res.is_complete and res.final_grade:
            session = adaptive_engine.sessions[req.session_id]
            attempt_id = quiz_attempts.record(
                normalize_skill(session["skill"]),
                res.final_grade,
                res.final_weighted_score or 0.0,
                passport_key=session.get("passport_hash") or None,
                trajectory=res.trajectory,
            )
            res.attempt_id = attempt_id
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except SandboxUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
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

    if attempt.passport_key and attempt.passport_key != _passport_key(passport):
        raise HTTPException(status_code=400, detail="This assessment was taken for a different passport.")

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
    skill_item.final_points = _skill_points(skill_item)

    # Clean up pending quiz notice
    skill_item.signals = [s for s in skill_item.signals if "Quiz Pending" not in s]
    if skill_item.reasoning:
        skill_item.reasoning = re.sub(r"\s*Mandatory (?:skill )?challenge (?:quiz )?pending.*", "", skill_item.reasoning).strip()
        skill_item.reasoning += f" Completed skill challenge quiz (Grade {grade})."

    _rebalance(passport)
    _ensure_audit_log(passport)

    # The trajectory comes from the server's record, never from the request
    if attempt.trajectory:
        passport.audit_log.traces.append(AuditStep(
            step="ADAPTIVE_ASSESSMENT_COMPLETED",
            target=skill_item.name,
            rule_applied=f"Trajectory: {attempt.trajectory} | Weighted: {attempt.percentage}%",
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


def _skill_points(item) -> int:
    """Evidence x Grade Weight + Consistency Bonus, then the Defend Your Code effect if one was applied."""
    base = DeterministicScoringEngine.calculate_skill_points(
        item.evidence_score, item.test_grade, consistency_bonus=item.consistency_bonus
    )
    check = item.authorship_check
    return adjust_points(base, check.status if check else None)


def _ensure_audit_log(passport: PassportDocument) -> None:
    if passport.audit_log is None:
        passport.audit_log = RunAuditLog(
            audit_id=f"audit_{uuid.uuid4().hex[:10]}",
            candidate_name=passport.candidate_name,
            traces=[],
            generated_at=datetime.now(timezone.utc).isoformat()
        )


def _rebalance(passport: PassportDocument) -> None:
    """Recalculates pillar scores and the balanced overall score after a skill's points change."""
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


def _defend_target(passport: PassportDocument, skill: str):
    if not CryptoSigner.verify_passport_signature(passport.model_dump(mode="json"), passport.tamper_proof_hash)["valid"]:
        raise HTTPException(status_code=400, detail="This passport's signature is invalid.")
    target = normalize_skill(skill).lower()
    item = next((s for s in passport.skills if normalize_skill(s.name).lower() == target), None)
    if not item:
        raise HTTPException(status_code=404, detail=f"Skill '{skill}' is not one of this passport's claims.")
    if item.verdict == VerdictEnum.CONTRADICTED:
        raise HTTPException(status_code=409, detail=f"{item.name} is contradicted by repository evidence.")
    return item


@app.post("/api/defend/start")
def defend_start(req: DefendStartRequest):
    """Starts the optional, single-attempt Defend Your Code test for one claim of a signed passport."""
    item = _defend_target(req.passport, req.skill)
    check = item.authorship_check
    if not check or check.status == STATUS_UNAVAILABLE:
        raise HTTPException(status_code=409, detail=(check.reason if check and check.reason else
                                                     f"Defend Your Code isn't available for {item.name}."))
    if check.status != STATUS_AVAILABLE:
        raise HTTPException(status_code=409, detail="Defend Your Code was already taken for this passport.")
    try:
        return defend.start(_passport_key(req.passport), item.name, req.extended_time)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/api/defend/answer")
def defend_answer(req: DefendAnswerRequest):
    try:
        return defend.answer(req.session_id, req.question_id, req.choice, req.pastes, req.tab_switches)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/defend/apply", response_model=PassportDocument)
def defend_apply(req: DefendApplyRequest):
    """
    Applies a finished Defend Your Code attempt to the passport it was taken for and re-signs it.
    Confirmed: +BONUS_POINTS to that skill (max 100). Not explained: points x FAIL_FACTOR. Otherwise unchanged.
    """
    passport = req.passport
    attempt = defend.peek_attempt(req.attempt_id)
    if attempt is None:
        raise HTTPException(status_code=400, detail="Unknown, expired or already applied Defend Your Code attempt.")
    item = _defend_target(passport, attempt.skill)
    if attempt.passport_key != _passport_key(passport):
        raise HTTPException(status_code=400, detail="This attempt was taken for a different passport.")
    if not item.authorship_check or item.authorship_check.status != STATUS_AVAILABLE:
        raise HTTPException(status_code=409, detail="A Defend Your Code result is already on this passport.")
    defend.consume_attempt(req.attempt_id)

    before = item.final_points
    item.authorship_check = AuthorshipCheck(
        status=attempt.status,
        question_count=attempt.total,
        correct=attempt.correct,
        total=attempt.total,
        commits=attempt.commits,
    )
    item.final_points = _skill_points(item)
    item.authorship_check.points_effect = item.final_points - before
    if attempt.status == STATUS_CONFIRMED:
        item.signals.append(f"Authorship confirmed: explained {attempt.correct}/{attempt.total} of their own functions")
        effect = f"+{item.authorship_check.points_effect} points (bonus {BONUS_POINTS}, max 100)"
    elif attempt.status == STATUS_NOT_EXPLAINED:
        item.signals.append(f"Could not explain own code: {attempt.correct}/{attempt.total} of their own functions")
        effect = f"{item.authorship_check.points_effect} points (x{FAIL_FACTOR})"
    else:
        item.signals.append(f"Authorship check inconclusive: {attempt.correct}/{attempt.total} of their own functions")
        effect = "no change"

    _rebalance(passport)
    _ensure_audit_log(passport)
    passport.audit_log.traces.append(AuditStep(
        step="AUTHORSHIP_CHECK_COMPLETED",
        target=item.name,
        rule_applied=(
            f"Explained {attempt.correct}/{attempt.total} own functions ({', '.join(attempt.functions)}) "
            f"from {', '.join(attempt.commits) or 'the analysed repositories'}; "
            f"extended time: {'yes' if attempt.extended_time else 'no'}; "
            f"browser-reported pastes: {attempt.pastes}, tab switches: {attempt.tab_switches}"
        ),
        verdict_reached=f"{attempt.status}: {effect}; passport re-signed",
        timestamp=datetime.now(timezone.utc).isoformat(),
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
        return _demo_defend(passport_svc.generate_passport(PRIYA_CLAIMS, PRIYA_EVIDENCE, {"Python": "A", "FastAPI": "B", "Docker": "C"}, evidence_source="demo"), "priya")
    elif key in ["alex", "inflater", "spammer"]:
        return passport_svc.generate_passport(ALEX_CLAIMS, ALEX_EVIDENCE, {"Python": "D", "Kubernetes": "E"}, evidence_source="demo")
    elif key in ["jordan", "learner"]:
        return _demo_defend(passport_svc.generate_passport(JORDAN_CLAIMS, JORDAN_EVIDENCE, {"Python": "B", "Docker": "C"}, evidence_source="demo"), "jordan")
    elif key in ["redteam", "security", "adversary", "cheater"]:
        return passport_svc.generate_passport(RED_TEAM_CLAIMS, RED_TEAM_EVIDENCE, {"Python": "D"}, evidence_source="demo")
    else:
        raise HTTPException(status_code=404, detail="Persona not found. Use 'priya', 'alex', 'jordan', or 'redteam'.")
