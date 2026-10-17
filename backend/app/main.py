import os
from typing import Optional, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .schemas import (
    ClaimsDocument, EvidenceDocument, PassportDocument,
    SimulationRequest, SimulationResult, QuizResult, QuizSubmission
)
from .module1_extractor import LLMClaimExtractor, PDFParser
from .module2_harvester import EvidenceHarvesterService
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
    version="1.0.0"
)

# Enable CORS for local Next.js / Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

class ExtractTextRequest(BaseModel):
    text: str
    links: Optional[list[str]] = None

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

@app.post("/api/extract/file", response_model=ClaimsDocument)
async def extract_from_file(file: UploadFile = File(...)):
    contents = await file.read()
    if file.filename.lower().endswith(".pdf"):
        text, links = pdf_parser.parse_pdf_bytes(contents)
    else:
        text, links = pdf_parser.parse_text_or_markdown(contents.decode("utf-8", errors="ignore"))
    return extractor.extract_from_text(text, links)

# --- Module 2: Code Evidence Harvester ---
@app.post("/api/harvest", response_model=EvidenceDocument)
def harvest_evidence(req: HarvestRequest):
    return harvester.harvest_repo(req.repo_url, req.candidate_name)

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
    return {"skill": skill, "questions": questions}

@app.post("/api/quiz/submit", response_model=QuizResult)
def submit_quiz(sub: QuizSubmission):
    return quiz_engine.evaluate_quiz(sub.skill, sub.answers)

# --- Cryptographic Verification ---
@app.post("/api/verify-signature")
def verify_signature(payload: Dict[str, Any] = Body(...), claimed_hash: str = Form(...)):
    is_valid = CryptoSigner.verify_passport(payload, claimed_hash)
    return {"is_valid": is_valid, "claimed_hash": claimed_hash}

# --- Pre-computed Demo Personas (Offline Hackathon Reliability) ---
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
