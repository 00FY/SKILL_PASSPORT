from typing import Dict, List, Tuple, Optional, Set

GRADE_WEIGHTS = {
    "A": 10,
    "B": 8,
    "C": 6,
    "D": 4,
    "E": 2
}

EVIDENCE_WEIGHTS = {
    "DEPLOYED_OR_PR": 10,  # Merged PR or Live Deployed URL
    "TESTS_VERIFIED": 8,   # Unit tests with active assertions
    "COMMITS_AUTHORED": 7, # Sustained commits & >70% authorship
    "CERTIFICATE_ONLY": 4, # Verified external certificate
    "RESUME_ONLY": 2       # Claimed on resume only
}

# Role match weights per verdict and the per-refusal penalty
VERDICT_MATCH_WEIGHTS = {"VERIFIED": 100, "PARTIALLY_SUPPORTED": 55}
REFUSAL_PENALTY = 7

# Fixed points for verdicts that don't use the evidence x grade product
CONTRADICTED_POINTS = 10
CLAIMED_ONLY_EVIDENCE = 2
CLAIMED_ONLY_GRADE = "D"
# Adaptive weights for the 4-pillar scoring system (Code, Resume, Certs, Quiz)
ADAPTIVE_WEIGHTS = {
    (True, True, True): {"code": 0.40, "resume": 0.20, "certs": 0.15, "quiz": 0.25},
    (True, True, False): {"code": 0.50, "resume": 0.25, "certs": 0.00, "quiz": 0.25},
    (True, False, True): {"code": 0.55, "resume": 0.00, "certs": 0.20, "quiz": 0.25},
    (False, True, True): {"code": 0.00, "resume": 0.45, "certs": 0.30, "quiz": 0.25},
    (True, False, False): {"code": 0.75, "resume": 0.00, "certs": 0.00, "quiz": 0.25},
    (False, True, False): {"code": 0.00, "resume": 0.75, "certs": 0.00, "quiz": 0.25},
    (False, False, True): {"code": 0.00, "resume": 0.00, "certs": 0.75, "quiz": 0.25},
    (False, False, False): {"code": 0.00, "resume": 0.00, "certs": 0.00, "quiz": 1.00},
}

class DeterministicScoringEngine:
    """
    Implements the published, auditable rubric scoring formula:
    Skill Points (0-100) = Evidence Score (0-10) * Challenge Grade Weight (2-10)
    """

    @staticmethod
    def calculate_evidence_score(
        has_deployed_or_pr: bool,
        has_tests: bool,
        has_code_blame: bool,
        has_certificate: bool
    ) -> Tuple[int, str]:
        if has_deployed_or_pr:
            return EVIDENCE_WEIGHTS["DEPLOYED_OR_PR"], "Production deployment or merged PR with review"
        elif has_tests:
            return EVIDENCE_WEIGHTS["TESTS_VERIFIED"], "Unit test suite with passing assertions"
        elif has_code_blame:
            return EVIDENCE_WEIGHTS["COMMITS_AUTHORED"], "Candidate-authored code in linked repositories"
        elif has_certificate:
            return EVIDENCE_WEIGHTS["CERTIFICATE_ONLY"], "Certificate link only (the certificate itself is not checked)"
        else:
            return EVIDENCE_WEIGHTS["RESUME_ONLY"], "Claimed on resume only with no code ground-truth"

    @staticmethod
    def calculate_consistency_bonus(repo_count: int, active_months: int) -> Tuple[int, List[str]]:
        """
        Consistency bonus:
        +5 pts for evidence in 2+ repos
        +3 pts for 6+ months of practice
        """
        bonus = 0
        reasons = []
        if repo_count >= 2:
            bonus += 5
            reasons.append(f"+5 pts consistency bonus (evidence across {repo_count} repositories)")
        if active_months >= 6:
            bonus += 3
            reasons.append(f"+3 pts consistency bonus (practiced over {active_months} months)")
        return bonus, reasons

    @staticmethod
    def calculate_skill_points(evidence_score: int, grade: str, consistency_bonus: int = 0) -> int:
        grade_weight = GRADE_WEIGHTS.get(grade.upper(), 6)
        points = evidence_score * grade_weight + consistency_bonus
        return min(100, max(0, points))

    @staticmethod
    def grade_from_percentage(pct: float) -> str:
        if pct >= 85.0:
            return "A"
        elif pct >= 70.0:
            return "B"
        elif pct >= 55.0:
            return "C"
        elif pct >= 40.0:
            return "D"
        else:
            return "E"

    @staticmethod
    def calculate_pillar_scores(
        code_score: Optional[int],
        resume_score: Optional[int],
        cert_score: Optional[int],
        quiz_score: Optional[int]
    ) -> Tuple[int, Dict[str, float]]:
        """
        Calculates the balanced overall score across active pillars according to adaptive weights.
        Returns (balanced_overall_score, weights_used).
        """
        has_code = code_score is not None
        has_resume = resume_score is not None
        has_certs = cert_score is not None

        weights = ADAPTIVE_WEIGHTS.get(
            (has_code, has_resume, has_certs),
            {"code": 0.50, "resume": 0.25, "certs": 0.00, "quiz": 0.25}
        )

        c_score = code_score if code_score is not None else 0
        r_score = resume_score if resume_score is not None else 0
        ct_score = cert_score if cert_score is not None else 0
        q_score = quiz_score if quiz_score is not None else 0

        composite = (
            weights["code"] * c_score +
            weights["resume"] * r_score +
            weights["certs"] * ct_score +
            weights["quiz"] * q_score
        )
        return min(100, max(0, round(composite))), weights

    @staticmethod
    def overall_score(skill_points: List[int]) -> int:
        """Overall Audit Score: mean of per-skill points (0-100)."""
        return round(sum(skill_points) / len(skill_points)) if skill_points else 0

    @staticmethod
    def role_match_pct(verdicts: List[str], refusal_count: int) -> int:
        """
        Role Match % = (100 x VERIFIED + 55 x PARTIALLY_SUPPORTED) / scored skills
                       - 7 x refusals, clipped to [10, 95].
        """
        if not verdicts:
            return 10
        verified = sum(1 for v in verdicts if v == "VERIFIED")
        partial = sum(1 for v in verdicts if v == "PARTIALLY_SUPPORTED")
        raw = (verified * VERDICT_MATCH_WEIGHTS["VERIFIED"] + partial * VERDICT_MATCH_WEIGHTS["PARTIALLY_SUPPORTED"]) / len(verdicts)
        return max(10, min(95, round(raw - REFUSAL_PENALTY * refusal_count)))

