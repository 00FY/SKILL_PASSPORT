import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert "golden_rule" in res.json()

def test_demo_priya_endpoint():
    res = client.get("/api/demo/priya")
    assert res.status_code == 200
    data = res.json()
    assert data["candidate_name"] == "Priya S."
    assert data["role_match_pct"] > 60
    assert data["tamper_proof_hash"].startswith("hmac-sha256:")
    assert len(data["skills"]) >= 2
    assert len(data["refusal_panel"]) >= 1

def test_demo_alex_spammer_endpoint():
    res = client.get("/api/demo/alex")
    assert res.status_code == 200
    data = res.json()
    assert data["candidate_name"] == "Alex R."
    # Alex should have prominent refusal panel items due to fork / template / sole committer
    assert len(data["refusal_panel"]) >= 1
    contradictions = [r for r in data["refusal_panel"] if r["verdict"] == "CONTRADICTED"]
    assert len(contradictions) >= 1

def test_demo_redteam_security_alert():
    res = client.get("/api/demo/redteam")
    assert res.status_code == 200
    data = res.json()
    assert len(data["security_alerts"]) >= 1
    assert any(a["flag_type"] == "STEGANOGRAPHY_OR_INJECTION" and a["severity"] == "CRITICAL" for a in data["security_alerts"])

def test_verify_signature_endpoint():
    priya_res = client.get("/api/demo/priya")
    priya_data = priya_res.json()
    verify_res = client.post("/api/verify-signature", json=priya_data)
    assert verify_res.status_code == 200
    verify_data = verify_res.json()
    assert verify_data["valid"] is True
    assert "HMAC-SHA256" in verify_data["reason"]

    # Tamper payload
    priya_data["overall_score"] = 99
    tamper_res = client.post("/api/verify-signature", json=priya_data)
    tamper_data = tamper_res.json()
    assert tamper_data["valid"] is False
    assert "Signature verification failed" in tamper_data["reason"]

def test_quiz_and_submission():
    res = client.get("/api/quiz/Python")
    assert res.status_code == 200
    questions = res.json()["questions"]
    assert len(questions) == 15

    # Submit quiz
    answers = {q["id"]: q["correct_index"] for q in questions}
    sub_res = client.post("/api/quiz/submit", json={"skill": "Python", "answers": answers})
    assert sub_res.status_code == 200
    result = sub_res.json()
    assert result["grade"] == "A"
    assert result["grade_weight"] == 10

def test_simulate_what_if_endpoint():
    priya_res = client.get("/api/demo/priya")
    passport = priya_res.json()

    sim_res = client.post(
        "/api/simulate",
        json={
            "base_passport": passport,
            "toggles": {"add_pytest": True}
        }
    )
    assert sim_res.status_code == 200
    result = sim_res.json()
    assert result["new_role_match_pct"] >= result["previous_role_match_pct"]
