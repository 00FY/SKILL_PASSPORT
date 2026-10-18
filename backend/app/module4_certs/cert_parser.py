import io
import re
import uuid
import logging
from typing import Optional, List, Tuple
from PIL import Image
import pypdf

from ..schemas import CertificateEvidence
from ..skills import SKILL_CATALOG, normalize_skill

logger = logging.getLogger(__name__)

# Known issuer patterns
ISSUER_PATTERNS = [
    (re.compile(r"coursera(?:\.org)?", re.IGNORECASE), "Coursera"),
    (re.compile(r"amazon\s*web\s*services|aws\b", re.IGNORECASE), "AWS"),
    (re.compile(r"udemy(?:\.com)?", re.IGNORECASE), "Udemy"),
    (re.compile(r"freecodecamp(?:\.org)?", re.IGNORECASE), "freeCodeCamp"),
    (re.compile(r"hackerrank(?:\.com)?", re.IGNORECASE), "HackerRank"),
    (re.compile(r"deeplearning\.ai", re.IGNORECASE), "DeepLearning.AI"),
    (re.compile(r"google\s*cloud|google\b", re.IGNORECASE), "Google Cloud"),
    (re.compile(r"microsoft|azure\b", re.IGNORECASE), "Microsoft Azure"),
    (re.compile(r"meta(?:\s+platforms)?", re.IGNORECASE), "Meta"),
    (re.compile(r"oracle(?:\s+corporation)?", re.IGNORECASE), "Oracle"),
    (re.compile(r"linkedin\s*learning", re.IGNORECASE), "LinkedIn Learning"),
    (re.compile(r"edx(?:\.org)?|harvardx", re.IGNORECASE), "edX"),
]

# Verification URL and Credential ID patterns
VERIFY_URL_RE = re.compile(
    r"(https?://(?:www\.)?(?:coursera\.org/verify/[A-Z0-9]+|credly\.com/badges/[a-z0-9\-]+|udemy\.com/certificate/[A-Z0-9\-]+|verify\.[\w\.\-]+/[^\s]+|[\w\.\-]+/verify/[^\s]+))",
    re.IGNORECASE
)
CREDENTIAL_ID_RE = re.compile(
    r"(?:credential\s*id|certificate\s*id|license\s*number|cert\s*#|verification\s*code)[\s:]*([A-Za-z0-9\-]{6,40})",
    re.IGNORECASE
)

DATE_PATTERNS = [
    re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b", re.IGNORECASE),
    re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\b", re.IGNORECASE),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b"),
]

RECIPIENT_PATTERNS = [
    re.compile(r"(?:this\s+is\s+to\s+certify\s+that|certifies\s+that|awarded\s+to|presented\s+to|proudly\s+presented\s+to|granted\s+to)\s+([A-Za-z\.\s]{2,40}?)(?:\s+has|\s+for|\s+on|\n|\r)", re.IGNORECASE),
    re.compile(r"(?:certificate\s+of\s+completion\s+presented\s+to)\s+([A-Za-z\.\s]{2,40})", re.IGNORECASE),
]


class CertificateParser:
    """
    Parses certificate files (PDFs, images) to extract structured credentials:
    issuer, title, candidate recipient, issue date, credential ID, verification URL,
    and associated skills mapped to canonical skills.
    """

    def parse_file(
        self,
        filename: str,
        contents: bytes,
        candidate_name: Optional[str] = None
    ) -> CertificateEvidence:
        lower_name = filename.lower()
        extracted_text = ""

        if lower_name.endswith(".pdf"):
            extracted_text = self._extract_pdf_text(contents)
        elif lower_name.endswith((".png", ".jpg", ".jpeg", ".webp")):
            extracted_text = self._extract_image_text(contents, filename)
        else:
            try:
                extracted_text = contents.decode("utf-8", errors="ignore")
            except Exception:
                extracted_text = ""

        return self._extract_metadata(filename, extracted_text, candidate_name)

    def _extract_pdf_text(self, contents: bytes) -> str:
        try:
            reader = pypdf.PdfReader(io.BytesIO(contents))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(pages)
        except Exception as exc:
            logger.warning("Failed to extract PDF text from certificate: %s", exc)
            return ""

    def _extract_image_text(self, contents: bytes, filename: str) -> str:
        try:
            img = Image.open(io.BytesIO(contents))
            # If pytesseract is installed in the system, try OCR
            try:
                import pytesseract
                return pytesseract.image_to_string(img)
            except (ImportError, Exception):
                pass
            # Fall back to image info / EXIF if present
            info_strs = []
            if hasattr(img, "info") and isinstance(img.info, dict):
                for k, v in img.info.items():
                    if isinstance(v, str):
                        info_strs.append(v)
            return " ".join(info_strs)
        except Exception as exc:
            logger.warning("Failed to inspect certificate image %s: %s", filename, exc)
            return ""

    def _extract_metadata(
        self,
        filename: str,
        text: str,
        candidate_name: Optional[str] = None
    ) -> CertificateEvidence:
        cert_id = f"cert-{uuid.uuid4().hex[:8]}"
        search_blob = f"{filename}\n{text}"

        # 1. Identify Issuer
        issuer = "Verified Issuer"
        for pattern, name in ISSUER_PATTERNS:
            if pattern.search(search_blob):
                issuer = name
                break

        # 2. Identify Verification URL
        url_match = VERIFY_URL_RE.search(search_blob)
        verify_url = url_match.group(1) if url_match else None

        # 3. Identify Credential ID
        cred_match = CREDENTIAL_ID_RE.search(search_blob)
        credential_id = cred_match.group(1) if cred_match else None
        if not credential_id and verify_url:
            parts = verify_url.rstrip("/").split("/")
            if len(parts) > 1 and len(parts[-1]) >= 6:
                credential_id = parts[-1]

        # 4. Identify Issue Date
        issue_date = None
        for dp in DATE_PATTERNS:
            dm = dp.search(search_blob)
            if dm:
                issue_date = dm.group(0)
                break

        # 5. Identify Recipient
        recipient = None
        for rp in RECIPIENT_PATTERNS:
            rm = rp.search(text)
            if rm:
                candidate_str = rm.group(1).strip()
                if 2 <= len(candidate_str) <= 40 and not any(w in candidate_str.lower() for w in ["course", "completion", "university", "online"]):
                    recipient = candidate_str
                    break
        if not recipient and candidate_name:
            recipient = candidate_name

        # 6. Extract Certificate Title
        cert_name = self._extract_title(filename, text, issuer)

        # 7. Identify Skills
        skills = self._detect_skills(search_blob)

        # 8. Calculate Confidence
        confidence = 0.65
        if text.strip():
            confidence += 0.15
        if verify_url or credential_id:
            confidence += 0.15
        if recipient and candidate_name and (candidate_name.lower() in recipient.lower() or recipient.lower() in candidate_name.lower()):
            confidence += 0.05
        confidence = min(1.0, confidence)

        raw_snippet = text.strip()[:300] if text.strip() else None

        return CertificateEvidence(
            id=cert_id,
            filename=filename,
            certificate_name=cert_name,
            issuer=issuer,
            candidate_name=recipient,
            issue_date=issue_date,
            credential_id=credential_id,
            verify_url=verify_url,
            skills=skills,
            confidence_score=round(confidence, 2),
            raw_text_snippet=raw_snippet,
        )

    def _extract_title(self, filename: str, text: str, issuer: str) -> str:
        # Heuristic title extraction
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for i, line in enumerate(lines):
            if re.search(r"(?:successfully\s+completed|certificate\s+of\s+completion\s+in)\s*[:\-]?\s*(.+)", line, re.IGNORECASE):
                m = re.search(r"(?:successfully\s+completed|certificate\s+of\s+completion\s+in)\s*[:\-]?\s*(.+)", line, re.IGNORECASE)
                val = m.group(1).strip()
                if len(val) > 3:
                    return val[:80]
            if "certificate of" in line.lower() and i + 1 < len(lines):
                candidate_line = lines[i + 1]
                if 4 <= len(candidate_line) <= 80:
                    return candidate_line

        # Fallback to cleaning up the filename
        base = re.sub(r"\.[a-zA-Z0-9]+$", "", filename)
        base = re.sub(r"[_\-]+", " ", base).strip()
        if base:
            return base.title()
        return f"{issuer} Certificate"

    def _detect_skills(self, text: str) -> List[str]:
        found: List[str] = []
        lower = text.lower()
        for canonical, spec in SKILL_CATALOG.items():
            # Check canonical name
            if re.search(r"\b" + re.escape(canonical.lower()) + r"\b", lower):
                if canonical not in found:
                    found.append(canonical)
                continue
            # Check aliases
            for alias in spec.aliases:
                if re.search(r"\b" + re.escape(alias.lower()) + r"\b", lower):
                    if canonical not in found:
                        found.append(canonical)
                    break
        return found
