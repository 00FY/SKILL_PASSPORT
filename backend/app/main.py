import os
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .schemas import (
    ClaimsDocument, EvidenceDocument, PassportDocument,
    SimulationRequest, SimulationResult, QuizResult, QuizSubmission
)
from .module1_extractor import LLMClaimExtractor, PDFParser
from .module1_extractor.pdf_parser import ResumeParseError
from .module2_harvester import EvidenceHarvesterService, RepoSourceError, RepoAccessError, parse_repo_source
from .module2_harvester.harvester_service import MAX_REPOS
from .module3_rubric import (
    PassportService, QuestionBankEngine, CryptoSigner
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
    allow_headers=["Content-Type"],
)

extractor = LLMClaimExtractor()
pdf_parser = PDFParser()
harvester = EvidenceHarvesterService()
passport_svc = PassportService()
quiz_engine = QuestionBankEngine()


class VerifyRequest(BaseModel):
    claims: ClaimsDocument
    evidence: EvidenceDocument
    challenge_grades: Optional[Dict[str, str]] = None


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
@app.post("/api/harvest", response_model=EvidenceDocument)
def harvest_evidence(req: HarvestRequest):
    try:
        return harvester.harvest_repo(req.repo_url, req.candidate_name, req.git_identities)
    except RepoSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RepoAccessError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# --- Unified End-to-End Analysis Pipeline ---
@app.post("/api/analyze", response_model=PassportDocument)
def analyze_candidate(req: AnalyzeRequest):
    repos = [u for u in ([req.repo_url] if req.repo_url else []) + req.repo_urls if u and u.strip()]
    links = list(repos) + list(req.links or [])

    # 1. Module 1: Extract claims and guard against prompt injection
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
        evidence_doc = harvester.harvest_many(repos, claims_doc.candidate_name, req.git_identities)
    except RepoSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RepoAccessError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if auto_detected:
        evidence_doc.warnings.insert(0, f"No repository was entered; analysed repositories linked in the resume: {', '.join(repos)}.")

    # 3. Module 3: 4-State Rubric Engine & Cryptographic Signer
    return passport_svc.generate_passport(claims_doc, evidence_doc)


# --- Module 3: Rubric Verifier & Passport ---
@app.post("/api/verify", response_model=PassportDocument)
def verify_pipeline(req: VerifyRequest):
    return passport_svc.generate_passport(req.claims, req.evidence, req.challenge_grades)


# --- Module 3 & 4: What-If Simulator ---
@app.post("/api/simulate", response_model=SimulationResult)
def simulate_what_if(req: SimulationRequest):
    return passport_svc.simulate_what_if(req)


# --- Challenge Quiz Engine ---
@app.get("/api/quiz/{skill}")
def get_quiz(skill: str):
    questions = quiz_engine.get_questions_for_skill(skill)
    if not questions:
        raise HTTPException(status_code=404, detail=f"No Skill Challenge exists for '{skill}' yet.")
    return {"skill": skill, "questions": questions}


@app.post("/api/quiz/submit", response_model=QuizResult)
def submit_quiz(sub: QuizSubmission):
    if not quiz_engine.get_questions_for_skill(sub.skill):
        raise HTTPException(status_code=404, detail=f"No Skill Challenge exists for '{sub.skill}' yet.")
    return quiz_engine.evaluate_quiz(sub.skill, sub.answers)


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
        return passport_svc.generate_passport(PRIYA_CLAIMS, PRIYA_EVIDENCE, {"Python": "A", "FastAPI": "B", "Docker": "C"})
    elif key in ["alex", "inflater", "spammer"]:
        return passport_svc.generate_passport(ALEX_CLAIMS, ALEX_EVIDENCE, {"Python": "D", "Kubernetes": "E"})
    elif key in ["jordan", "learner"]:
        return passport_svc.generate_passport(JORDAN_CLAIMS, JORDAN_EVIDENCE, {"Python": "B", "Docker": "C"})
    elif key in ["redteam", "security", "adversary", "cheater"]:
        return passport_svc.generate_passport(RED_TEAM_CLAIMS, RED_TEAM_EVIDENCE, {"Python": "D"})
    else:
        raise HTTPException(status_code=404, detail="Persona not found. Use 'priya', 'alex', 'jordan', or 'redteam'.")
