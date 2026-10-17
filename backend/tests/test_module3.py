import pytest
from app.module3_rubric import (
    DeterministicScoringEngine,
    FourStateVerifier,
    QuestionBankEngine,
    CryptoSigner,
    AuditTracer,
    PassportService
)
from app.schemas import (
    ClaimsDocument, ClaimItem, EvidenceDocument,
    SkillEvidence, QualitySignals, VerdictEnum,
    SimulationRequest, SampleSnippet
)

def test_rubric_scoring_formula():
    engine = DeterministicScoringEngine()
    # Evidence score 8 (tests), Grade A (10) -> 80 points
    points = engine.calculate_skill_points(8, "A")
    assert points == 80

    # Evidence score 4 (cert), Grade C (6) -> 24 points
    points = engine.calculate_skill_points(4, "C")
    assert points == 24

def test_four_state_verifier_verdicts():
    verifier = FourStateVerifier()
    audit = AuditTracer("Priya S.")

    claims = ClaimsDocument(
        candidate_name="Priya S.",
        applied_role="Backend Developer",
        claims=[
            ClaimItem(id="c1", skill="Python", category="language", claimed_duration_months=36),
            ClaimItem(id="c2", skill="Docker", category="devops", claimed_duration_months=12, evidence_links=["https://coursera.org/verify/XYZ"]),
            ClaimItem(id="c3", skill="Team Leadership", category="soft_skill", claimed_detail="Led 5-person team on ShopAPI"),
            ClaimItem(id="c4", skill="Testing (pytest)", category="testing", claimed_detail="Expert in TDD")
        ]
    )

    evidence = EvidenceDocument(
        repo_url="https://github.com/priya/api-service",
        is_fork=False,
        candidate_authorship_pct=91.2,
        first_commit="2024-01-10",
        last_commit="2025-03-15",
        active_months=14,
        skills_detected={
            "Python": SkillEvidence(
                lines_authored=2450,
                files_count=18,
                sample_snippet=SampleSnippet(file="app/routes.py", lines="42-78", blame_match=0.95)
            )
        },
        signals=QualitySignals(
            has_tests=False, # Deliberately false to trigger refusal on testing
            test_file_count=0,
            commit_count=40
        )
    )

    skills, refusals, plans, role_match, overall = verifier.evaluate(claims, evidence, audit)

    # Python should be VERIFIED
    py = next(s for s in skills if s.name == "Python")
    assert py.verdict == VerdictEnum.VERIFIED
    assert py.final_points >= 56

    # Docker should be PARTIALLY_SUPPORTED
    docker = next(s for s in skills if s.name == "Docker")
    assert docker.verdict == VerdictEnum.PARTIALLY_SUPPORTED

    # Refusal panel should contain Team Leadership (CONTRADICTED) and Testing (CLAIMED_ONLY)
    contradicted = next((r for r in refusals if r.verdict == VerdictEnum.CONTRADICTED), None)
    assert contradicted is not None
    assert "Sole committer" in contradicted.reason or "1 contributor" in contradicted.evidence_found

    claimed_only = next((r for r in refusals if r.verdict == VerdictEnum.CLAIMED_ONLY), None)
    assert claimed_only is not None
    assert "Testing" in claimed_only.claim

def test_question_bank_and_grader():
    qb = QuestionBankEngine()
    questions = qb.get_questions_for_skill("Python")
    assert len(questions) == 15

    # Submit all correct answers
    answers = {q.id: q.correct_index for q in questions}
    res = qb.evaluate_quiz("Python", answers)
    assert res.correct_count == 15
    assert res.grade == "A"
    assert res.grade_weight == 10

def test_tamper_proof_crypto_signer():
    data = {"candidate_name": "Priya S.", "role_match_pct": 72, "overall_score": 62}
    signature = CryptoSigner.sign_passport(data)
    assert signature.startswith("hmac-sha256:")
    
    # Test helper function verify_passport_signature
    res = CryptoSigner.verify_passport_signature(data, signature)
    assert res["valid"] is True
    assert "HMAC-SHA256" in res["reason"]
    assert CryptoSigner.verify_passport(data, signature) is True

    # Tampered data should fail verification with descriptive reason
    tampered_data = {"candidate_name": "Priya S.", "role_match_pct": 99, "overall_score": 62}
    tampered_res = CryptoSigner.verify_passport_signature(tampered_data, signature)
    assert tampered_res["valid"] is False
    assert "Signature verification failed" in tampered_res["reason"]

def test_commit_laundering_detected_contradiction():
    verifier = FourStateVerifier()
    audit = AuditTracer("Alex R.")
    claims = ClaimsDocument(
        candidate_name="Alex R.",
        applied_role="Backend Developer",
        claims=[ClaimItem(id="c1", skill="Python", category="language", claimed_duration_months=36)]
    )
    evidence = EvidenceDocument(
        repo_url="https://github.com/alex/bulk-dump",
        candidate_authorship_pct=95.0,
        active_months=1,
        skills_detected={"Python": SkillEvidence(lines_authored=3000, files_count=5)},
        signals=QualitySignals(
            has_tests=False,
            commit_laundering_detected=True,
            commit_count=1
        )
    )
    skills, refusals, _, _, _ = verifier.evaluate(claims, evidence, audit)
    py_skill = next(s for s in skills if s.name == "Python")
    assert py_skill.verdict == VerdictEnum.CONTRADICTED
    contradicted_refusal = next(r for r in refusals if r.verdict == VerdictEnum.CONTRADICTED)
    assert "Commit Laundering Detected: Bulk initial upload without iterative commit history." in contradicted_refusal.reason

def test_what_if_simulator():
    service = PassportService()
    claims = ClaimsDocument(
        candidate_name="Priya S.",
        applied_role="Backend Developer",
        claims=[
            ClaimItem(id="c1", skill="Python", category="language", claimed_duration_months=36),
            ClaimItem(id="c2", skill="Docker", category="devops", evidence_links=["https://coursera.org/verify/123"])
        ]
    )
    evidence = EvidenceDocument(
        repo_url="https://github.com/priya/api-service",
        candidate_authorship_pct=91.2,
        active_months=14,
        skills_detected={"Python": SkillEvidence(lines_authored=2000, files_count=10)},
        signals=QualitySignals(has_tests=False, commit_count=30)
    )
    passport = service.generate_passport(claims, evidence)
    assert passport.role_match_pct > 0

    sim_req = SimulationRequest(
        base_passport=passport,
        toggles={"add_pytest": True}
    )
    sim_res = service.simulate_what_if(sim_req)
    assert sim_res.new_role_match_pct >= sim_res.previous_role_match_pct
    assert sim_res.score_delta >= 0
