"""PDF report: made only from signed passports, contains what the passport says, escapes candidate text."""
import unicodedata

import pymupdf
from fastapi.testclient import TestClient

from app.main import app
from app.module3_rubric import CryptoSigner

client = TestClient(app)


def _text(pdf: bytes) -> str:
    doc = pymupdf.open("pdf", pdf)
    # Fold ligatures ("ﬁ") and line wraps so phrases can be searched
    return " ".join(unicodedata.normalize("NFKC", " ".join(page.get_text() for page in doc)).split())


def test_report_for_a_signed_passport():
    passport = client.get("/api/demo/priya").json()
    res = client.post("/api/report/pdf", json=passport)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert 'filename="skill-passport-priya-s.pdf"' in res.headers["content-disposition"]
    assert res.content.startswith(b"%PDF")
    text = _text(res.content)
    for expected in ["DEMO DATA", "Priya S.", "Claims and evidence", "Verified by code", "Python",
                     "Problems found", "Verification", passport["tamper_proof_hash"][-16:], "Page 1 of"]:
        assert expected in text, expected


def test_edited_passport_gets_no_report():
    passport = client.get("/api/demo/priya").json()
    passport["overall_score"] = 99
    res = client.post("/api/report/pdf", json=passport)
    assert res.status_code == 400 and "signature is invalid" in res.json()["detail"]


def test_candidate_text_is_escaped():
    passport = client.get("/api/demo/jordan").json()
    passport["candidate_name"] = "<b>Mallory</b> <img src='https://example.com/x.png'>"
    passport["tamper_proof_hash"] = CryptoSigner.sign_passport(passport)
    res = client.post("/api/report/pdf", json=passport)
    assert res.status_code == 200
    assert "<b>Mallory</b>" in _text(res.content)


def test_security_alerts_and_certificates_are_listed():
    text = _text(client.post("/api/report/pdf", json=client.get("/api/demo/redteam").json()).content)
    assert "Security alerts in the resume" in text and "CRITICAL" in text
    assert "Certificates" in text
