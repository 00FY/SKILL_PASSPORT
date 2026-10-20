import io
import pytest
import pymupdf
import qrcode
import cv2
import numpy as np
from unittest.mock import patch, MagicMock

from app.schemas import (
    ClaimsDocument, ClaimItem, CertificateEvidence, EvidenceDocument,
    QualitySignals, VerdictEnum
)
from app.module4_certs.allowlist import (
    is_allowed_domain, validate_issuer_url, safe_fetch_issuer_page
)
from app.module4_certs.matching import name_match, title_match
from app.module4_certs.pointer_extractor import PointerExtractor
from app.module4_certs.issuer_adapters import (
    CourseraAdapter, CredlyAdapter, NptelAdapter, IssuerRecord
)
from app.module4_certs.cert_verifier import CertificateVerifierService, decide
from app.module3_rubric.passport_service import PassportService


def create_test_pdf_with_qr_and_link(text: str, link_url: str, qr_url: str) -> bytes:
    """Helper to generate a realistic test certificate PDF with embedded hyperlink and QR code."""
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=800)
    page.insert_text((50, 50), text)
    page.insert_link({
        "kind": pymupdf.LINK_URI,
        "from": pymupdf.Rect(50, 60, 300, 80),
        "uri": link_url
    })

    # Generate QR code
    qr = qrcode.QRCode(box_size=4, border=2)
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    qr_buf = io.BytesIO()
    img.save(qr_buf, format="PNG")
    page.insert_image(pymupdf.Rect(350, 50, 500, 200), stream=qr_buf.getvalue())

    return doc.tobytes()


def create_test_qr_png(qr_url: str) -> bytes:
    """Helper to generate a PNG image containing a QR code."""
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 1. Pointer Extraction Tests
# ---------------------------------------------------------------------------
def test_pointer_extractor_pdf_links_and_qr():
    extractor = PointerExtractor()
    pdf_bytes = create_test_pdf_with_qr_and_link(
        text="This is to certify that Rahul Verma completed Machine Learning on Coursera. ID: COURSERA-9988",
        link_url="https://www.coursera.org/verify/COURSERA-9988",
        qr_url="https://nptel.ac.in/noc/Ecertificate/?q=NPTEL24CS01"
    )

    ptrs = extractor.extract("test_cert.pdf", pdf_bytes, target_candidate_name="Rahul Verma")

    assert "https://www.coursera.org/verify/COURSERA-9988" in ptrs.embedded_hyperlinks
    assert "https://nptel.ac.in/noc/Ecertificate/?q=NPTEL24CS01" in ptrs.qr_code_urls
    assert ptrs.candidate_name == "Rahul Verma"
    assert "COURSERA-9988" in ptrs.credential_ids


def test_pointer_extractor_image_qr():
    extractor = PointerExtractor()
    png_bytes = create_test_qr_png("https://nptel.ac.in/noc/Ecertificate/?q=NPTEL_QR_TEST")
    ptrs = extractor.extract("nptel_badge.png", png_bytes)

    assert "https://nptel.ac.in/noc/Ecertificate/?q=NPTEL_QR_TEST" in ptrs.qr_code_urls


# ---------------------------------------------------------------------------
# 2. Host Allowlist Security Tests
# ---------------------------------------------------------------------------
def test_allowlist_domain_matching():
    # Allowed domains
    assert is_allowed_domain("coursera.org")
    assert is_allowed_domain("www.coursera.org")
    assert is_allowed_domain("credly.com")
    assert is_allowed_domain("www.credly.com")
    assert is_allowed_domain("nptel.ac.in")
    assert is_allowed_domain("archive.nptel.ac.in")
    assert is_allowed_domain("swayam.gov.in")

    # Lookalikes and malicious domains MUST be rejected
    assert not is_allowed_domain("coursera-verify.com")
    assert not is_allowed_domain("credly.attacker.com")
    assert not is_allowed_domain("fake-nptel.ac.in")
    assert not is_allowed_domain("coursera.org.phishing.io")
    assert not is_allowed_domain("localhost")
    assert not is_allowed_domain("127.0.0.1")
    assert not is_allowed_domain("192.168.1.1")


def test_validate_issuer_url():
    ok, _ = validate_issuer_url("https://www.coursera.org/verify/ABC123XYZ")
    assert ok

    ok, _ = validate_issuer_url("https://www.credly.com/badges/uuid-12345/public_url")
    assert ok

    ok, _ = validate_issuer_url("https://nptel.ac.in/noc/Ecertificate/?q=TEST")
    assert ok

    # Reject non-https
    ok, reason = validate_issuer_url("http://www.coursera.org/verify/ABC123XYZ")
    assert not ok
    assert "only https is permitted" in reason

    # Reject lookalikes
    ok, reason = validate_issuer_url("https://coursera-verify.com/verify/ABC123XYZ")
    assert not ok
    assert "not on the trusted issuer allowlist" in reason

    # Reject embedded credentials (e.g. https://user:pass@coursera.org)
    ok, reason = validate_issuer_url("https://admin:secret@www.coursera.org/verify/123")
    assert not ok
    assert "Credentials in URL" in reason


# ---------------------------------------------------------------------------
# 3. Name & Title Matching Tests
# ---------------------------------------------------------------------------
def test_name_matching():
    # Exact match
    assert name_match("Jane Doe", "Jane Doe")

    # Case & whitespace insensitive
    assert name_match("jane doe", "  Jane  Doe ")

    # Initials: Priya S. matches Priya Sharma
    assert name_match("Priya Sharma", "Priya S.")
    assert name_match("Priya S.", "Priya Sharma")

    # Initials with period: A. R. Smith matches Alex R. Smith
    assert name_match("A. R. Smith", "Alex R. Smith")

    # Subset: John Doe matches John Doe Jr or Dr. John Doe
    assert name_match("Dr. John Doe", "John Doe")

    # Mismatches: Must NOT match different people!
    assert not name_match("Marcus Brody", "RedTeam Adversary")
    assert not name_match("Alice Smith", "Bob Jones")
    assert not name_match("John Doe", "Jane Doe")


def test_title_matching():
    # Exact and subset
    assert title_match("AWS Certified Solutions Architect - Associate", "AWS Solutions Architect")
    assert title_match("Containerized Microservices with Docker", "Docker")
    assert title_match("Deep Learning Specialization", "Deep Learning")

    # Mismatch
    assert not title_match("Financial Accounting 101", "Advanced Kubernetes DevOps")


# ---------------------------------------------------------------------------
# 4. Issuer Adapters with Mock Responses
# ---------------------------------------------------------------------------
def test_coursera_adapter_parsing():
    adapter = CourseraAdapter()
    mock_html = """
    <html>
      <head>
        <meta property="og:title" content="Priya Sharma has completed Containerized Microservices with Docker" />
      </head>
      <body>
        <h3>Completed by</h3>
        <p>Priya Sharma</p>
      </body>
    </html>
    """

    with patch("app.module4_certs.issuer_adapters.safe_fetch_issuer_page", return_value=(200, mock_html.encode(), mock_html, "https://www.coursera.org/verify/XYZ123")):
        rec = adapter.fetch_and_parse("https://www.coursera.org/verify/XYZ123")
        assert rec.is_valid
        assert rec.issuer_name == "Coursera"
        assert rec.recipient_name == "Priya Sharma"
        assert "Docker" in (rec.credential_title or "")
        assert len(rec.raw_evidence_hash) == 64


def test_credly_adapter_parsing():
    adapter = CredlyAdapter()
    mock_html = """
    <html>
      <head>
        <meta property="og:title" content="Marcus Brody earned AWS Certified Solutions Architect - Associate from Amazon Web Services" />
      </head>
      <body>
        <div>Issued to Marcus Brody</div>
      </body>
    </html>
    """

    with patch("app.module4_certs.issuer_adapters.safe_fetch_issuer_page", return_value=(200, mock_html.encode(), mock_html, "https://www.credly.com/badges/123/public_url")):
        rec = adapter.fetch_and_parse("https://www.credly.com/badges/123/public_url")
        assert rec.is_valid
        assert rec.issuer_name == "Amazon Web Services"
        assert rec.recipient_name == "Marcus Brody"
        assert "Solutions Architect" in (rec.credential_title or "")


def test_nptel_adapter_parsing():
    adapter = NptelAdapter()
    mock_html = """
    <html>
      <body>
        <table>
          <tr><td>Name of Candidate:</td><td>Aarav Patel</td></tr>
          <tr><td>Course Name:</td><td>Programming, Data Structures And Algorithms Using Python</td></tr>
          <tr><td>Consolidated Score:</td><td>88%</td></tr>
        </table>
      </body>
    </html>
    """

    with patch("app.module4_certs.issuer_adapters.safe_fetch_issuer_page", return_value=(200, mock_html.encode(), mock_html, "https://nptel.ac.in/noc/Ecertificate/?q=NPTEL23")):
        rec = adapter.fetch_and_parse("https://nptel.ac.in/noc/Ecertificate/?q=NPTEL23")
        assert rec.is_valid
        assert rec.issuer_name == "NPTEL"
        assert rec.recipient_name == "Aarav Patel"
        assert "Python" in (rec.credential_title or "")
        assert rec.metadata.get("nptel_score") == "88%"


# ---------------------------------------------------------------------------
# 5. Decision Logic & Status Ladder Tests
# ---------------------------------------------------------------------------
def test_decision_logic_verified():
    extracted = MagicMock()
    extracted.raw_text = "This certifies that Priya Sharma has completed Docker for DevOps Specialization"
    extracted.candidate_name = "Priya S."
    extracted.certificate_title = "Docker for DevOps"

    record = IssuerRecord(
        issuer_name="Coursera",
        recipient_name="Priya Sharma",
        credential_title="Docker for DevOps Specialization",
        verify_url="https://coursera.org/verify/123",
        raw_evidence_hash="hash123",
        fetch_timestamp="2026-10-20T00:00:00Z",
        is_valid=True
    )

    status, reason = decide(extracted, record, candidate_name="Priya Sharma")
    assert status in ("verified", "issuer_verified")
    assert reason is None


def test_decision_logic_name_mismatch():
    extracted = MagicMock()
    extracted.raw_text = "RedTeam Adversary completed AWS Certified Solutions Architect"
    extracted.candidate_name = "RedTeam Adversary"
    extracted.certificate_title = "AWS Certified Solutions Architect"

    record = IssuerRecord(
        issuer_name="Amazon Web Services",
        recipient_name="Marcus Brody",  # Mismatch!
        credential_title="AWS Certified Solutions Architect",
        verify_url="https://credly.com/badges/123",
        raw_evidence_hash="hash123",
        fetch_timestamp="2026-10-20T00:00:00Z",
        is_valid=True
    )

    status, reason = decide(extracted, record, candidate_name="RedTeam Adversary")
    assert status in ("unverified", "issuer_mismatch")
    assert "Marcus Brody" in reason


def test_title_never_extracted_from_filename():
    extractor = PointerExtractor()
    # PDF text with no title pattern
    res = extractor._extract_title("Some random text without title markers")
    assert res is None  # Must never fall back to filename!


def test_stray_spaces_removed_from_verify_url():
    extractor = PointerExtractor()
    extracted = MagicMock()
    extracted.raw_text = "Verify at coursera.org/verify/ 13MRJDMJF8TK or https:// coursera.org / verify / ABC123XYZ"
    extracted.verify_urls = []
    extracted.qr_code_urls = []
    extracted.embedded_hyperlinks = []
    extracted.credential_ids = []

    extractor._extract_text_pointers(extracted)
    assert any("13MRJDMJF8TK" in u for u in extracted.verify_urls)
    assert any("ABC123XYZ" in u for u in extracted.verify_urls)


def test_generic_title_yields_issuer_unparsed():
    extracted = MagicMock()
    extracted.raw_text = "Some text"
    record = IssuerRecord(
        issuer_name="Coursera",
        recipient_name=None,  # Unreadable recipient
        credential_title="Skills",  # Generic title
        verify_url="https://coursera.org/verify/123",
        raw_evidence_hash="h",
        fetch_timestamp="ts",
        is_valid=True
    )
    status, reason = decide(extracted, record, candidate_name="Arnav")
    assert status in ("pending", "issuer_unparsed")
    assert any(w in reason.lower() for w in ["not confirmed", "not readable", "manually", "automatically"])


def test_noisy_or_certificate_pillar_scores():
    from app.module3_rubric.scoring_engine import DeterministicScoringEngine
    from app.schemas import CertificateEvidence

    # 1. Single verified coding cert -> 75
    cert1 = CertificateEvidence(
        id="c1", filename="c1.pdf", certificate_name="Docker", issuer="Coursera",
        skills=["Docker"], confidence_score=1.0, issuer_status="issuer_verified"
    )
    s1 = DeterministicScoringEngine.calculate_cert_pillar_score([cert1])
    assert s1 == 75

    # 2. Two verified coding certs -> 100 * (1 - 0.25 * 0.25) = 94
    cert2 = CertificateEvidence(
        id="c2", filename="c2.pdf", certificate_name="Kubernetes", issuer="Coursera",
        skills=["Kubernetes"], confidence_score=1.0, issuer_status="issuer_verified"
    )
    s2 = DeterministicScoringEngine.calculate_cert_pillar_score([cert1, cert2])
    assert s2 == 94

    # 3. Single verified non-coding cert -> 50
    cert_non_coding = CertificateEvidence(
        id="c3", filename="c3.pdf", certificate_name="FinTech Foundations", issuer="Coursera",
        skills=[], confidence_score=1.0, issuer_status="issuer_verified"
    )
    s3 = DeterministicScoringEngine.calculate_cert_pillar_score([cert_non_coding])
    assert s3 == 50

    # 4. Parsed / unparsed cert -> 20
    cert_unparsed = CertificateEvidence(
        id="c4", filename="c4.pdf", certificate_name="Course", issuer="Coursera",
        skills=[], confidence_score=0.7, issuer_status="issuer_unparsed"
    )
    s4 = DeterministicScoringEngine.calculate_cert_pillar_score([cert_unparsed])
    assert s4 == 20


def test_decision_logic_unreachable():
    extracted = MagicMock()
    extracted.candidate_name = "Alex"
    extracted.certificate_title = "Cert"

    record = IssuerRecord(
        issuer_name="Coursera",
        verify_url="https://coursera.org/verify/missing",
        raw_evidence_hash="hash123",
        fetch_timestamp="2026-10-20T00:00:00Z",
        is_valid=False,
        error_message="404 Not Found"
    )

    status, reason = decide(extracted, record, candidate_name="Alex")
    assert status in ("unverified", "issuer_unreachable")
    assert "404" in reason


# ---------------------------------------------------------------------------
# 6. Forged Certificate Red-Team Live Story: Refusal Queue Routing
# ---------------------------------------------------------------------------
def test_forged_certificate_lands_in_refusal_queue():
    """
    Test the live Red Team story: A candidate edits the PDF name to 'RedTeam Adversary',
    points to a real Credly badge URL, but the issuer record proves the recipient is 'Marcus Brody'.
    The engine flags issuer_mismatch and places it in the Refusal Queue as 'Needs Review'.
    """
    svc = PassportService()

    claims_doc = ClaimsDocument(
        candidate_name="RedTeam Adversary",
        applied_role="Security Engineer",
        claims=[
            ClaimItem(
                id="claim_01",
                skill="AWS",
                category="devops",
                claimed_detail="Certified AWS Solutions Architect"
            )
        ],
        certificates=[
            CertificateEvidence(
                id="cert-forged-01",
                filename="aws_solutions_architect.pdf",
                certificate_name="AWS Certified Solutions Architect - Associate",
                issuer="Credly",
                candidate_name="RedTeam Adversary",  # Edited PDF
                verify_url="https://www.credly.com/badges/sample-uuid/public_url",
                skills=["AWS"],
                confidence_score=0.0,
                issuer_status="issuer_mismatch",
                issuer_record={
                    "issuer_name": "Amazon Web Services",
                    "recipient_name": "Marcus Brody",  # Real holder!
                    "credential_title": "AWS Certified Solutions Architect - Associate",
                    "verify_url": "https://www.credly.com/badges/sample-uuid/public_url",
                    "raw_evidence_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    "fetch_timestamp": "2026-10-20T12:00:00Z",
                    "is_valid": True
                },
                mismatch_reason="Issuer record recipient 'Marcus Brody' does not match candidate 'RedTeam Adversary'."
            )
        ]
    )

    evidence_doc = EvidenceDocument(
        repo_url="https://github.com/redteam/poc",
        repo_urls=["https://github.com/redteam/poc"],
        candidate_authorship_pct=15.0,
        active_months=1,
        signals=QualitySignals(commit_count=2)
    )

    passport = svc.generate_passport(claims_doc, evidence_doc)

    # 1. Assert refusal panel contains the mismatched certificate
    mismatch_refusals = [
        r for r in passport.refusal_panel
        if "Needs Review" in r.reason or "Marcus Brody" in (r.evidence_found or "")
    ]
    assert len(mismatch_refusals) > 0, "Forged certificate must land in the Refusal Queue!"
    refusal = mismatch_refusals[0]
    assert refusal.verdict == VerdictEnum.CONTRADICTED
    assert "Needs Review" in refusal.reason
    assert "Marcus Brody" in (refusal.evidence_found or refusal.reason)

    # 2. Assert AWS skill does NOT get verified certificate tier credit
    aws_skill = next((s for s in passport.skills if s.name == "AWS"), None)
    if aws_skill:
        assert aws_skill.evidence_score <= 2, "Unverified/mismatched cert must not grant E=4"
