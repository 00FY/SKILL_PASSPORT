import re
import uuid
import logging
from typing import Optional, List, Dict, Any, Tuple

from ..schemas import CertificateEvidence
from .pointer_extractor import PointerExtractor, ExtractedPointers
from .allowlist import validate_issuer_url
from .issuer_adapters import get_adapter_for_url, IssuerRecord, compute_evidence_hash
from .matching import name_match, title_match, fuzzy_contains, fuzzy_eq, GENERIC_TITLES

logger = logging.getLogger(__name__)

KNOWN_ISSUER_PATTERNS = [
    (re.compile(r"coursera(?:\.org)?", re.IGNORECASE), "Coursera"),
    (re.compile(r"amazon\s*web\s*services|aws\b", re.IGNORECASE), "AWS"),
    (re.compile(r"credly(?:\.com)?", re.IGNORECASE), "Credly"),
    (re.compile(r"nptel(?:\.ac\.in)?|swayam", re.IGNORECASE), "NPTEL"),
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


def decide(
    extracted: ExtractedPointers,
    record: Optional[IssuerRecord],
    candidate_name: Optional[str]
) -> Tuple[str, Optional[str]]:
    """
    Practical 3-Status Credibility Decision for Hackathon MVP:
    - 'verified': Official issuer record found and key details matched (recipient, title).
    - 'pending': Official page found on genuine issuer domain, but details could not be
                 confirmed automatically (e.g. client-rendered Coursera specialization).
                 Never declared fake; provides a 'Verify manually' link.
    - 'unverified': No sufficient authoritative evidence found, invalid/404 URL, or explicit contradiction.
    """
    if record is None:
        return "unverified", "No official issuer verification link found in document"

    if not record.is_valid:
        return "unverified", record.error_message or "Official issuer page unreachable or invalid"

    # If issuer record fields could not be extracted automatically (e.g. client-rendered Coursera specialization)
    # -> Mark as 'pending' rather than declaring fake!
    if not record.credential_title or not record.recipient_name or record.credential_title.lower().strip() in GENERIC_TITLES:
        return "pending", "Official issuer page found, but details could not be confirmed automatically. Use 'Verify manually' link."

    doc_text = extracted.raw_text or ""
    name_ok = fuzzy_contains(doc_text, record.recipient_name)
    title_ok = fuzzy_contains(doc_text, record.credential_title)

    # Scanned/image cert fallback where raw_text is sparse
    if not name_ok and candidate_name and name_match(record.recipient_name, candidate_name):
        name_ok = True
    if not name_ok and extracted.candidate_name and name_match(record.recipient_name, extracted.candidate_name):
        name_ok = True

    # Title fallback comparison against extracted certificate title
    if not title_ok and extracted.certificate_title:
        if title_match(record.credential_title, extracted.certificate_title):
            title_ok = True
        elif fuzzy_contains(record.credential_title, extracted.certificate_title):
            title_ok = True

    if name_ok and title_ok:
        # The document matches the issuer's record; it must also be the candidate's own certificate
        if candidate_name and not name_match(record.recipient_name, candidate_name):
            return "unverified", (f"Official issuer record lists a different recipient ('{record.recipient_name}') "
                                  f"than the candidate ('{candidate_name}')")
        return "verified", None

    if not name_ok:
        return "unverified", f"Official issuer record lists a different recipient ('{record.recipient_name}')"
    else:
        return "unverified", f"Issuer title ('{record.credential_title}') not found in uploaded document"


class CertificateVerifierService:
    """
    Practical certificate verification pipeline for Skill Passport MVP:
    1. Extracts certificate details (title, recipient, date, verify URL) from PDF/image.
    2. Validates official issuer domain against trusted allowlist.
    3. Matches issuer record against uploaded certificate.
    4. Awards transparent credibility status:
       - 'verified': Official record confirmed & details matched.
       - 'pending': Official page found, automated extraction pending manual review.
       - 'unverified': No authoritative evidence or contradiction.
    """

    def __init__(self):
        self.extractor = PointerExtractor()

    def verify(
        self,
        filename: str,
        contents: bytes,
        candidate_name: Optional[str] = None
    ) -> CertificateEvidence:
        cert_id = f"cert-{uuid.uuid4().hex}"

        # 1. Extract details from file
        extracted = self.extractor.extract(filename, contents, candidate_name)

        # 2. Select verify URL pointer
        selected_url = None
        for u in extracted.qr_code_urls + extracted.embedded_hyperlinks + extracted.verify_urls:
            if u and u.startswith(("http://", "https://")):
                selected_url = u
                break

        # Identify primary issuer name
        issuer_name = "Certificate Issuer"
        search_blob = f"{filename}\n{extracted.raw_text}\n{' '.join(extracted.all_pointers)}"
        for pattern, name in KNOWN_ISSUER_PATTERNS:
            if pattern.search(search_blob):
                issuer_name = name
                break

        # 3. Check official issuer domain & fetch issuer record
        issuer_record: Optional[IssuerRecord] = None
        status = "unverified"
        mismatch_reason = None

        if selected_url:
            valid, err = validate_issuer_url(selected_url)
            if not valid:
                status = "unverified"
                mismatch_reason = f"Verification link rejected: {err}"
            else:
                adapter = get_adapter_for_url(selected_url)
                if adapter:
                    issuer_record = adapter.fetch_and_parse(selected_url)
                    status, mismatch_reason = decide(extracted, issuer_record, candidate_name)
                    if issuer_record.issuer_name:
                        issuer_name = issuer_record.issuer_name
                else:
                    # Recognized allowed domain, but no specific adapter -> pending manual verification
                    status = "pending"
                    mismatch_reason = "Official issuer domain recognized; automated parsing pending manual review"
        else:
            status = "unverified"
            mismatch_reason = "No official verification URL or QR code found in certificate"

        # Consolidate candidate and recipient details
        recipient = (issuer_record.recipient_name if issuer_record and issuer_record.recipient_name else None) or extracted.candidate_name or candidate_name
        cert_title = (issuer_record.credential_title if issuer_record and issuer_record.credential_title else None) or extracted.certificate_title or f"{issuer_name} Certificate"
        issue_date = (issuer_record.issue_date if issuer_record and issuer_record.issue_date else None) or extracted.issue_date
        cred_id = (issuer_record.credential_id if issuer_record and issuer_record.credential_id else None) or (extracted.credential_ids[0] if extracted.credential_ids else None)

        # Calculate confidence and score tier
        name_matched = bool(recipient and candidate_name and name_match(recipient, candidate_name))
        is_contradicted = status == "unverified" and any(w in (mismatch_reason or "").lower() for w in ["different recipient", "mismatch"])

        if is_contradicted:
            confidence = 0.0
            score_tier = 0
        elif status == "verified":
            confidence = 1.0
            score_tier = 100
        elif status == "pending":
            confidence = 0.85 if name_matched else 0.70
            score_tier = 50
        elif name_matched:
            confidence = 0.85
            score_tier = 50
        else:
            confidence = 0.60
            score_tier = 25

        record_dict = issuer_record.model_dump() if issuer_record else None
        ev_hash = issuer_record.raw_evidence_hash if issuer_record else compute_evidence_hash(contents)
        fetch_ts = issuer_record.fetch_timestamp if issuer_record else None

        snippet = extracted.raw_text.strip()[:300] if extracted.raw_text.strip() else None

        return CertificateEvidence(
            id=cert_id,
            filename=filename,
            certificate_name=cert_title,
            issuer=issuer_name,
            candidate_name=recipient,
            issue_date=issue_date,
            credential_id=cred_id,
            verify_url=selected_url,
            skills=extracted.skills,
            confidence_score=round(confidence, 2),
            raw_text_snippet=snippet,
            issuer_status=status,
            issuer_record=record_dict,
            verification_timestamp=fetch_ts,
            evidence_hash=ev_hash,
            extracted_pointers=extracted.all_pointers,
            mismatch_reason=mismatch_reason,
            score_tier=score_tier,
        )
