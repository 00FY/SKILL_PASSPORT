import io
import pytest
from app.main import app
from app.schemas import CertificateEvidence, PillarScores
from app.module2_harvester.profile_scanner import ProfileScanner, extract_github_username
from app.module3_rubric.scoring_engine import DeterministicScoringEngine, ADAPTIVE_WEIGHTS
from app.module4_certs.cert_parser import CertificateParser
from starlette.testclient import TestClient

client = TestClient(app)


def test_extract_github_username():
    assert extract_github_username("torvalds") == "torvalds"
    assert extract_github_username("https://github.com/torvalds") == "torvalds"
    assert extract_github_username("http://www.github.com/torvalds/repo") == "torvalds"
    assert extract_github_username("github.com/torvalds") == "torvalds"
    assert extract_github_username("   ") is None


def test_certificate_parser_text_and_skills():
    parser = CertificateParser()
    text = (
        b"This is to certify that Jane Doe has successfully completed "
        b"Python for Everybody and Docker for DevOps by Coursera. "
        b"Credential ID: COURSERA-12345-XYZ Issued on: January 15, 2025"
    )
    cert = parser.parse_file("Coursera_Cert.txt", text, candidate_name="Jane Doe")
    assert cert.issuer == "Coursera"
    assert "Python" in cert.skills
    assert "Docker" in cert.skills
    assert cert.candidate_name == "Jane Doe"
    assert cert.credential_id == "COURSERA-12345-XYZ"
    assert cert.confidence_score >= 0.85


def test_adaptive_weights_and_pillar_scores():
    # 1. All 4 active (Code, Resume, Certs, Quiz)
    overall, weights = DeterministicScoringEngine.calculate_pillar_scores(
        code_score=80, resume_score=70, cert_score=90, quiz_score=100
    )
    assert weights["code"] == 0.40
    assert weights["resume"] == 0.20
    assert weights["certs"] == 0.15
    assert weights["quiz"] == 0.25
    expected = round(0.40 * 80 + 0.20 * 70 + 0.15 * 90 + 0.25 * 100)
    assert overall == expected

    # 2. Code + Quiz only (No resume, no certs)
    overall_code_only, weights_code = DeterministicScoringEngine.calculate_pillar_scores(
        code_score=80, resume_score=None, cert_score=None, quiz_score=60
    )
    assert weights_code["code"] == 0.75
    assert weights_code["quiz"] == 0.25
    assert weights_code["resume"] == 0.00
    assert overall_code_only == round(0.75 * 80 + 0.25 * 60)


def test_upload_cert_endpoint():
    content = b"Awarded to Alex Smith for passing AWS Certified Solutions Architect. Credential ID: AWS-999"
    file = ("aws_cert.txt", io.BytesIO(content), "text/plain")
    res = client.post("/api/upload-cert", files={"file": file}, data={"candidate_name": "Alex Smith"})
    assert res.status_code == 200
    data = res.json()
    assert data["issuer"] == "AWS"
    assert "AWS" in data["skills"]
    assert data["credential_id"] == "AWS-999"


def test_discover_repos_endpoint():
    res = client.post("/api/discover-repos", json={"username": "torvalds"})
    assert res.status_code == 200
    data = res.json()
    assert data["username"] == "torvalds"
    assert "repo_urls" in data
