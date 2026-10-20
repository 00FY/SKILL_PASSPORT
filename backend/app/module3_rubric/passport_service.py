from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from ..schemas import (
    ClaimsDocument, EvidenceDocument, PassportDocument,
    SimulationRequest, SimulationResult, SkillPassportItem, VerdictEnum
)
from .verifier import FourStateVerifier
from .audit_tracer import AuditTracer
from .crypto_signer import CryptoSigner
from .scoring_engine import DeterministicScoringEngine, EVIDENCE_WEIGHTS, GRADE_WEIGHTS
from ..skills import skill_spec

class PassportService:
    def __init__(self):
        self.verifier = FourStateVerifier()

    def generate_passport(
        self,
        claims_doc: ClaimsDocument,
        evidence_doc: EvidenceDocument,
        challenge_grades: Optional[Dict[str, str]] = None,
        evidence_source: str = "harvested",
        github_username: Optional[str] = None
    ) -> PassportDocument:
        """
        Only call this with evidence the server harvested itself (or clearly labelled demo data):
        the signature vouches for the evidence, so caller-supplied evidence must never be signed.
        """
        audit = AuditTracer(candidate_name=claims_doc.candidate_name)
        audit.record(
            step="INIT_PIPELINE",
            target=claims_doc.candidate_name,
            rule_applied="RULE_INGEST_CONTRACTS",
            verdict_reached="SUCCESS"
        )

        skills, refusals, learning_plan, role_match_pct, raw_overall_score = self.verifier.evaluate(
            claims_doc=claims_doc,
            evidence_doc=evidence_doc,
            audit_tracer=audit,
            challenge_grades=challenge_grades if challenge_grades is not None else {}
        )

        # 4-Pillar Balanced Scoring:
        # Pillar 1: Code Profile score
        code_skills = [s for s in skills if s.authorship_pct is not None or s.evidence_score >= 7]
        code_score: Optional[int] = None
        if evidence_doc.signals.commit_count > 0 or code_skills:
            code_score = round(sum(s.final_points for s in skills) / max(1, len(skills)))

        # Pillar 2: Resume / Bio score (None if candidate did not provide a resume)
        has_resume = (claims_doc.raw_text_length or 0) > 0
        resume_score: Optional[int] = role_match_pct if has_resume else None

        # Pillar 3: Certificate score (0–100 Noisy-OR combination of verified credentials)
        cert_score: Optional[int] = DeterministicScoringEngine.calculate_cert_pillar_score(
            claims_doc.certificates,
            candidate_name=claims_doc.candidate_name
        )

        # Pillar 4: Mandatory Quiz score
        tested_skills = [s for s in skills if challenge_grades and s.name.lower() in {k.lower(): v for k, v in challenge_grades.items()}]
        if tested_skills:
            quiz_weights = [GRADE_WEIGHTS.get(s.test_grade, 6) * 10 for s in tested_skills]
            quiz_score = round(sum(quiz_weights) / len(quiz_weights))
        else:
            quiz_score = 20  # Base level (Grade E) until quizzes are attempted

        balanced_overall, weights_used = DeterministicScoringEngine.calculate_pillar_scores(
            code_score=code_score,
            resume_score=resume_score,
            cert_score=cert_score,
            quiz_score=quiz_score
        )

        from ..schemas import PillarScores
        pillar_scores = PillarScores(
            code_score=code_score,
            resume_score=resume_score,
            cert_score=cert_score,
            quiz_score=quiz_score,
            overall_score=balanced_overall,
            weights_used=weights_used
        )

        audit_log = audit.finalize()

        issued_at_str = datetime.now(timezone.utc).isoformat()

        passport = PassportDocument(
            evidence_source=evidence_source,
            candidate_name=claims_doc.candidate_name,
            applied_role=claims_doc.applied_role,
            role_match_pct=role_match_pct,
            overall_score=balanced_overall,
            candidate_authorship_pct=evidence_doc.candidate_authorship_pct,
            active_months=evidence_doc.active_months,
            total_commits=evidence_doc.signals.commit_count,
            repo_url=evidence_doc.repo_url,
            repo_urls=evidence_doc.repo_urls,
            github_username=github_username,
            is_fork=evidence_doc.is_fork,
            skills=skills,
            refusal_panel=refusals,
            learning_plan=learning_plan,
            security_alerts=claims_doc.security_flags,
            warnings=evidence_doc.warnings,
            pillar_scores=pillar_scores,
            certificates=claims_doc.certificates,
            tamper_proof_hash="",
            issued_at=issued_at_str,
            audit_log=audit_log
        )

        passport_dict = passport.model_dump()
        signature_hash = CryptoSigner.sign_passport(passport_dict)
        passport.tamper_proof_hash = signature_hash
        return passport

    def simulate_what_if(self, req: SimulationRequest) -> SimulationResult:
        """
        Interactive What-If Simulator:
        Applies hypothetical improvements to a passport and re-runs the same published formulas
        (evidence tier x grade, overall mean, role match) used to issue it. Nothing is hardcoded.

        Toggles:
        - add_pytest / add_tests: code-backed skills reach the "tests verified" tier (8);
          CLAIMED_ONLY testing refusals are resolved as a verified testing skill.
        - add_deploy / deployed_url: code-backed skills reach the "deployed / merged PR" tier (10).
        - sustained_commits / author_more: partially supported code-backed skills become VERIFIED.
        """
        base = req.base_passport
        updated_skills = [s.model_copy(deep=True) for s in base.skills]
        remaining_refusals = list(base.refusal_panel)
        resolved_refusals: List[str] = []

        add_tests = req.toggles.get("add_pytest", False) or req.toggles.get("add_tests", False)
        add_deploy = req.toggles.get("deployed_url", False) or req.toggles.get("add_deploy", False)
        author_more = req.toggles.get("sustained_commits", False) or req.toggles.get("author_more", False)

        for s in updated_skills:
            code_backed = s.authorship_pct is not None and s.verdict in (VerdictEnum.VERIFIED, VerdictEnum.PARTIALLY_SUPPORTED)
            if not code_backed:
                continue
            if add_tests and s.evidence_score < EVIDENCE_WEIGHTS["TESTS_VERIFIED"]:
                s.evidence_score = EVIDENCE_WEIGHTS["TESTS_VERIFIED"]
                s.signals.append("Simulated: added a test suite with real assertions")
            if add_deploy and s.evidence_score < EVIDENCE_WEIGHTS["DEPLOYED_OR_PR"]:
                s.evidence_score = EVIDENCE_WEIGHTS["DEPLOYED_OR_PR"]
                s.signals.append("Simulated: live deployment / merged pull request")
            if author_more and s.verdict == VerdictEnum.PARTIALLY_SUPPORTED:
                s.verdict = VerdictEnum.VERIFIED
                s.signals.append("Simulated: sustained authorship over 3+ months")
            s.final_points = DeterministicScoringEngine.calculate_skill_points(
                s.evidence_score, s.test_grade, consistency_bonus=s.consistency_bonus
            )

        if add_tests:
            for r in list(remaining_refusals):
                if r.verdict == VerdictEnum.CLAIMED_ONLY and skill_spec(r.claim) and skill_spec(r.claim).category == "testing":
                    remaining_refusals.remove(r)
                    resolved_refusals.append(r.claim)
                    updated_skills.append(SkillPassportItem(
                        name=r.claim, category="testing", verdict=VerdictEnum.VERIFIED, level="Intermediate",
                        evidence_score=EVIDENCE_WEIGHTS["TESTS_VERIFIED"], test_grade="B",
                        final_points=DeterministicScoringEngine.calculate_skill_points(EVIDENCE_WEIGHTS["TESTS_VERIFIED"], "B"),
                        signals=["Simulated: added a test suite with real assertions"],
                    ))

        new_overall = DeterministicScoringEngine.overall_score([s.final_points for s in updated_skills]) if updated_skills else base.overall_score
        new_role_match = DeterministicScoringEngine.role_match_pct([s.verdict.value for s in updated_skills], len(remaining_refusals))
        # Improvements can't make the match worse than what was issued
        new_role_match = max(new_role_match, base.role_match_pct)

        return SimulationResult(
            previous_score=base.overall_score,
            new_score=new_overall,
            previous_role_match_pct=base.role_match_pct,
            new_role_match_pct=new_role_match,
            score_delta=new_role_match - base.role_match_pct,
            updated_skills=updated_skills,
            resolved_refusals=resolved_refusals
        )
