from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from ..schemas import (
    ClaimsDocument, EvidenceDocument, PassportDocument,
    SimulationRequest, SimulationResult, SkillPassportItem, VerdictEnum
)
from .verifier import FourStateVerifier
from .audit_tracer import AuditTracer
from .crypto_signer import CryptoSigner
from .scoring_engine import DeterministicScoringEngine, EVIDENCE_WEIGHTS
from ..skills import skill_spec

class PassportService:
    def __init__(self):
        self.verifier = FourStateVerifier()

    def generate_passport(
        self,
        claims_doc: ClaimsDocument,
        evidence_doc: EvidenceDocument,
        challenge_grades: Optional[Dict[str, str]] = None
    ) -> PassportDocument:
        audit = AuditTracer(candidate_name=claims_doc.candidate_name)
        audit.record(
            step="INIT_PIPELINE",
            target=claims_doc.candidate_name,
            rule_applied="RULE_INGEST_CONTRACTS",
            verdict_reached="SUCCESS"
        )

        skills, refusals, learning_plan, role_match_pct, overall_score = self.verifier.evaluate(
            claims_doc=claims_doc,
            evidence_doc=evidence_doc,
            audit_tracer=audit,
            challenge_grades=challenge_grades
        )

        audit_log = audit.finalize()

        passport_dict = {
            "candidate_name": claims_doc.candidate_name,
            "applied_role": claims_doc.applied_role,
            "role_match_pct": role_match_pct,
            "overall_score": overall_score,
            "candidate_authorship_pct": evidence_doc.candidate_authorship_pct,
            "active_months": evidence_doc.active_months,
            "total_commits": evidence_doc.signals.commit_count,
            "repo_url": evidence_doc.repo_url,
            "repo_urls": evidence_doc.repo_urls,
            "is_fork": evidence_doc.is_fork,
            "skills": [s.model_dump() for s in skills],
            "refusal_panel": [r.model_dump() for r in refusals],
            "learning_plan": [lp.model_dump() for lp in learning_plan],
            "security_alerts": [sf.model_dump() for sf in claims_doc.security_flags],
            "warnings": evidence_doc.warnings,
            "issued_at": datetime.now(timezone.utc).isoformat()
        }

        # Cryptographically sign the passport
        signature_hash = CryptoSigner.sign_passport(passport_dict)

        return PassportDocument(
            candidate_name=claims_doc.candidate_name,
            applied_role=claims_doc.applied_role,
            role_match_pct=role_match_pct,
            overall_score=overall_score,
            candidate_authorship_pct=evidence_doc.candidate_authorship_pct,
            active_months=evidence_doc.active_months,
            total_commits=evidence_doc.signals.commit_count,
            repo_url=evidence_doc.repo_url,
            repo_urls=evidence_doc.repo_urls,
            is_fork=evidence_doc.is_fork,
            skills=skills,
            refusal_panel=refusals,
            learning_plan=learning_plan,
            security_alerts=claims_doc.security_flags,
            warnings=evidence_doc.warnings,
            tamper_proof_hash=signature_hash,
            issued_at=passport_dict["issued_at"],
            audit_log=audit_log
        )

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
            s.final_points = DeterministicScoringEngine.calculate_skill_points(s.evidence_score, s.test_grade)

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
