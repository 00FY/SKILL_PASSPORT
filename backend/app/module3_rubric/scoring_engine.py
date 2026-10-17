from typing import Dict, Tuple

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
            return EVIDENCE_WEIGHTS["COMMITS_AUTHORED"], "Sustained git history with >70% line authorship"
        elif has_certificate:
            return EVIDENCE_WEIGHTS["CERTIFICATE_ONLY"], "Verified certification link without production repo"
        else:
            return EVIDENCE_WEIGHTS["RESUME_ONLY"], "Claimed on resume only with no code ground-truth"

    @staticmethod
    def calculate_skill_points(evidence_score: int, grade: str) -> int:
        grade_weight = GRADE_WEIGHTS.get(grade.upper(), 6)
        points = evidence_score * grade_weight
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
