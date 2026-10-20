from typing import Dict, List, Tuple

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
    def calculate_skill_points(evidence_score: int, grade: str, consistency_bonus: int = 0, verdict: Optional[str] = None) -> int:
        if verdict == "CONTRADICTED":
            return CONTRADICTED_POINTS
        grade_weight = GRADE_WEIGHTS.get(grade.upper(), 6)
        points = evidence_score * grade_weight + consistency_bonus
        return min(100, max(0, points))

    @staticmethod
    def starting_difficulty_for_verdict(verdict: Optional[str]) -> int:
        """
        Repo-Seeded Starting Difficulty:
        If CLAIMED_ONLY, start at Tier 1 (Foundational).
        If VERIFIED or PARTIALLY_SUPPORTED, start at Tier 2 (Intermediate).
        """
        if verdict == "CLAIMED_ONLY":
            return 1
        return 2

    @staticmethod
    def adaptive_grade_from_performance(pct: float, max_tier_passed: int = 1) -> str:
        """
        Maps continuous adaptive percentage and difficulty ceiling reached into Grade (A-E).
        Grade A strictly requires passing at least one Tier 3 (Advanced) task.
        """
        if pct >= 85.0 and max_tier_passed >= 3:
            return "A"
        elif pct >= 70.0 and max_tier_passed >= 2:
            return "B"
        elif pct >= 55.0:
            return "C"
        elif pct >= 40.0:
            return "D"
        else:
            return "E"

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
