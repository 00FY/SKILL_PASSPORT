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
    assert data["tamper_proof_hash"].startswith("sha256:")
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
    assert any(a["flag_type"] == "PROMPT_INJECTION_DETECTED" for a in data["security_alerts"])

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
