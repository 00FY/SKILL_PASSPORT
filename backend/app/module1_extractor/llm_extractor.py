import os
import json
import re
from typing import Dict, Any, List, Optional
import httpx
from ..schemas import ClaimsDocument, ClaimItem, SecurityFlag
from .injection_guard import PromptInjectionDefense
from .pdf_parser import PDFParser

EXTRACTION_SYSTEM_PROMPT = """
You are a strict Resume Claim Extraction Engine for Skill Passport.
Your ONLY role is to extract factual text declarations into a structured JSON schema.

GOLDEN RULE:
You NEVER assign scores, grades, ratings, verdicts, or judgment.
Only extract the text claims made by the candidate.

Return a JSON object conforming strictly to this format:
{
  "candidate_name": "Full Name",
  "applied_role": "Target or current role",
  "claims": [
    {
      "id": "claim_01",
      "skill": "Python",
      "category": "language",
      "claimed_duration_months": 36,
      "claimed_detail": "Led API design",
      "evidence_links": ["https://github.com/user/repo"]
    }
  ]
}
"""

class LLMClaimExtractor:
    def __init__(self):
        self.injection_guard = PromptInjectionDefense()
        self.pdf_parser = PDFParser()

    def extract_from_text(self, raw_text: str, links: Optional[List[str]] = None) -> ClaimsDocument:
        if links is None:
            links = []

        # 1. Defend against prompt injection and sanitize
        sanitized_text, security_flags = self.injection_guard.sanitize(raw_text)

        # 2. Extract links from text if not provided
        _, extracted_links = self.pdf_parser.parse_text_or_markdown(sanitized_text)
        all_links = list(dict.fromkeys(links + extracted_links))

        # 3. Attempt LLM call if API keys are configured, otherwise use high-fidelity rule extractor
        claims_doc = None
        gemini_key = os.getenv("GEMINI_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")

        if gemini_key:
            claims_doc = self._call_gemini_api(sanitized_text, all_links, gemini_key)
        elif openai_key:
            claims_doc = self._call_openai_api(sanitized_text, all_links, openai_key)

        if not claims_doc:
            claims_doc = self._rule_based_extraction(sanitized_text, all_links)

        claims_doc.security_flags = security_flags
        claims_doc.raw_text_length = len(raw_text)
        claims_doc.sanitized_text_preview = sanitized_text[:300] + ("..." if len(sanitized_text) > 300 else "")

        return claims_doc

    def _call_gemini_api(self, text: str, links: List[str], api_key: str) -> Optional[ClaimsDocument]:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": EXTRACTION_SYSTEM_PROMPT},
                            {"text": f"Candidate Resume:\n{text}\n\nCandidate Links:\n{json.dumps(links)}"}
                        ]
                    }
                ],
                "generationConfig": {
                    "response_mime_type": "application/json"
                }
            }
            res = httpx.post(url, json=payload, timeout=15.0)
            if res.status_code == 200:
                data = res.json()
                content = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(content)
                return ClaimsDocument(**parsed)
        except Exception:
            pass
        return None

    def _call_openai_api(self, text: str, links: List[str], api_key: str) -> Optional[ClaimsDocument]:
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Resume Text:\n{text}\nLinks:\n{json.dumps(links)}"}
                ],
                "response_format": {"type": "json_object"}
            }
            res = httpx.post(url, headers=headers, json=payload, timeout=15.0)
            if res.status_code == 200:
                data = res.json()
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                return ClaimsDocument(**parsed)
        except Exception:
            pass
        return None

    def _rule_based_extraction(self, text: str, links: List[str]) -> ClaimsDocument:
        """
        Deterministic, offline extraction engine.
        Parses skills, claimed duration, categories, and leadership claims without external network dependencies.
        """
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # 1. Identify candidate name
        candidate_name = "Candidate"
        if lines:
            first_line = lines[0]
            # Strip titles if any
            clean_name = re.sub(r'(?i)resume|curriculum vitae|cv', '', first_line).strip()
            if len(clean_name.split()) <= 4 and len(clean_name) > 2:
                candidate_name = clean_name

        # 2. Identify role
        applied_role = "Software Engineer"
        for line in lines[:5]:
            lower = line.lower()
            if any(k in lower for k in ["backend", "frontend", "full stack", "fullstack", "devops", "cloud", "data engineer", "software engineer", "developer", "architect"]):
                applied_role = line.strip(" |,-")
                break

        # 3. Known skill lexicon with categories
        skill_catalog = {
            "Python": ("language", ["python", "python3", "py"]),
            "JavaScript": ("language", ["javascript", "js", "ecmascript"]),
            "TypeScript": ("language", ["typescript", "ts"]),
            "Go": ("language", ["golang", "go language"]),
            "Rust": ("language", ["rust", "cargo"]),
            "FastAPI": ("framework", ["fastapi"]),
            "Django": ("framework", ["django"]),
            "React": ("framework", ["react", "react.js", "reactjs"]),
            "Next.js": ("framework", ["next.js", "nextjs", "next 14", "next 15"]),
            "Docker": ("devops", ["docker", "containerization"]),
            "Kubernetes": ("devops", ["kubernetes", "k8s"]),
            "PostgreSQL": ("database", ["postgresql", "postgres", "psql"]),
            "Redis": ("database", ["redis"]),
            "Testing (pytest)": ("testing", ["pytest", "unit tests", "testing", "tdd"]),
            "Git & CI/CD": ("devops", ["git", "github actions", "ci/cd", "continuous integration"]),
        }

        claims: List[ClaimItem] = []
        claim_counter = 1

        # Check for skills in text
        for skill_name, (category, aliases) in skill_catalog.items():
            matched = False
            for alias in aliases:
                pattern = rf"\b{re.escape(alias)}\b"
                if re.search(pattern, text, re.IGNORECASE):
                    matched = True
                    break

            if matched:
                # Look for claimed duration near the skill (e.g. "3 years", "24 months")
                duration = 12  # default baseline 12 months
                duration_match = re.search(rf"\b(\d+)\+?\s*(years?|yrs?|months?)\b.*?\b{re.escape(skill_name)}\b", text, re.IGNORECASE)
                if not duration_match:
                    duration_match = re.search(rf"\b{re.escape(skill_name)}\b.*?\b(\d+)\+?\s*(years?|yrs?|months?)\b", text, re.IGNORECASE)

                if duration_match:
                    num = int(duration_match.group(1))
                    unit = duration_match.group(2).lower()
                    if "year" in unit or "yr" in unit:
                        duration = num * 12
                    else:
                        duration = num

                # Find relevant links (github repos, certs)
                relevant_links = [l for l in links if any(sub in l.lower() for sub in [skill_name.lower()[:4], "github", "coursera", "verify"])]
                if not relevant_links and links:
                    relevant_links = links[:1]

                claims.append(
                    ClaimItem(
                        id=f"claim_{claim_counter:02d}",
                        skill=skill_name,
                        category=category,
                        claimed_duration_months=duration,
                        claimed_detail=f"Mentioned in resume as core {category} competence.",
                        evidence_links=relevant_links
                    )
                )
                claim_counter += 1

        # 4. Check for Leadership / Team claims (e.g., "Led team of 5", "Led 5-person team")
        leadership_match = re.search(r"(?i)(led|managed|guided)\s+(a\s+)?(\d+[\s-]*(person|member|engineer|developer))\s+team\s*(on|for|at)?\s*([a-zA-Z0-9_\-\s]+)?", text)
        if leadership_match:
            detail = leadership_match.group(0).strip()
            claims.append(
                ClaimItem(
                    id=f"claim_{claim_counter:02d}",
                    skill="Team Leadership",
                    category="soft_skill",
                    claimed_duration_months=12,
                    claimed_detail=detail,
                    evidence_links=[l for l in links if "github" in l]
                )
            )

        return ClaimsDocument(
            candidate_name=candidate_name,
            applied_role=applied_role,
            claims=claims
        )
