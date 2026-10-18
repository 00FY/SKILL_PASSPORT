import re
from typing import List, Dict, Tuple, Optional
from ..schemas import (
    ClaimsDocument, ClaimItem, EvidenceDocument, VerdictEnum, SkillEvidence,
    SkillPassportItem, RefusalItem, LearningPlanItem
)
from ..skills import (
    normalize_skill, min_lines_for, ecosystem_for, TEST_FRAMEWORK_ECOSYSTEM, TESTING_SKILL_FRAMEWORKS
)
from ..module2_harvester.repo_source import parse_repo_source, RepoSourceError
from .scoring_engine import (
    DeterministicScoringEngine, GRADE_WEIGHTS, CONTRADICTED_POINTS, CLAIMED_ONLY_EVIDENCE, CLAIMED_ONLY_GRADE
)
from .audit_tracer import AuditTracer

CODE_HOSTS = ("github.com", "gitlab.com", "bitbucket.org")
CERT_MARKERS = ("coursera.org/verify", "coursera.org/account/accomplishments", "credly.com", "credential.net",
                "udemy.com/certificate", "/verify/", "/certificate", "certificates.", "verify.")
# A meaningful share of the files backing a skill counts as code evidence (PARTIALLY_SUPPORTED);
# VERIFIED additionally needs a majority share and sustained history.
MIN_AUTHORSHIP_FOR_CODE = 25.0
MIN_AUTHORSHIP_FOR_VERIFIED = 70.0
MIN_MONTHS_FOR_VERIFIED = 3
GIT_MIN_COMMITS = 10
# A learning-plan action is modelled as reaching the "tests verified" evidence tier
HYPOTHETICAL_EVIDENCE = 8


def _repo_key(url: str) -> Optional[str]:
    try:
        return parse_repo_source(url).url.lower()
    except RepoSourceError:
        return None


class FourStateVerifier:
    """
    Implements the 4-State Verdict Engine:
    - VERIFIED
    - PARTIALLY_SUPPORTED
    - CLAIMED_ONLY
    - CONTRADICTED

    Every rule reads only the claims and evidence documents; nothing is keyed to specific candidates.
    """

    def __init__(self, scoring_engine: Optional[DeterministicScoringEngine] = None):
        self.scoring = scoring_engine or DeterministicScoringEngine()

    def evaluate(
        self,
        claims_doc: ClaimsDocument,
        evidence_doc: EvidenceDocument,
        audit_tracer: AuditTracer,
        challenge_grades: Optional[Dict[str, str]] = None
    ) -> Tuple[List[SkillPassportItem], List[RefusalItem], List[LearningPlanItem], int, int]:
        challenge_grades = {normalize_skill(k).lower(): v for k, v in (challenge_grades or {}).items()}

        skills_out: List[SkillPassportItem] = []
        refusals: List[Tuple[Optional[str], RefusalItem]] = []
        plan_skills: List[Tuple[str, str, Optional[str]]] = []  # (skill, action, repo_context)

        analysed_repos = {k for k in (_repo_key(u) for u in (evidence_doc.repo_urls or [evidence_doc.repo_url])) if k}
        signals = evidence_doc.signals
        repo_label = ", ".join(evidence_doc.repo_urls or [evidence_doc.repo_url]) or "linked repositories"

        def refuse(skill: Optional[str], item: RefusalItem, step: str, rule: str):
            audit_tracer.record(step=step, target=skill or item.claim, rule_applied=rule, verdict_reached=item.verdict.value)
            refusals.append((skill, item))

        # 0. Repositories excluded from evidence (laundered / forked) when other repos were usable
        for ex in evidence_doc.excluded_repos:
            refuse(None, RefusalItem(
                claim=f"Authentic development in {ex.repo_url}",
                verdict=VerdictEnum.CONTRADICTED,
                reason=ex.reason,
                evidence_found="Repository excluded from evidence; claims were scored on the remaining repositories.",
                suggested_remedy="Link repositories with original, incrementally committed work."
            ), "REPO_EXCLUSION", "RULE_EXCLUDE_DISQUALIFIED_REPO")

        # 1. Contradiction checks on team-leadership and duration claims
        for claim in claims_doc.claims:
            if claim.category == "soft_skill" or "team" in claim.skill.lower():
                detail_text = (claim.claimed_detail or "").lower()
                size_match = re.search(r"(\d+)\s*[- ]*(person|member|people|engineer|developer)|team\s+of\s+(\d+)", detail_text)
                claimed_team_size = int(size_match.group(1) or size_match.group(3)) if size_match else 0

                if signals.commit_count > 0 and evidence_doc.is_fork and evidence_doc.candidate_authorship_pct < 10.0:
                    refuse(claim.skill, RefusalItem(
                        claim=claim.claimed_detail or claim.skill,
                        verdict=VerdictEnum.CONTRADICTED,
                        reason=f"Repository is a template fork where candidate authored only {round(evidence_doc.candidate_authorship_pct, 1)}% of lines.",
                        evidence_found="Forked commit tree with no original collaboration history.",
                        suggested_remedy="Provide repository with PR reviews and multi-author collaboration traces."
                    ), "CONTRADICTION_CHECK", "RULE_SOLE_OR_FORK_LEADERSHIP")
                elif (claimed_team_size > 1 and signals.commit_count > 0
                      and evidence_doc.unique_contributors is not None and evidence_doc.unique_contributors <= 1):
                    refuse(claim.skill, RefusalItem(
                        claim=claim.claimed_detail or claim.skill,
                        verdict=VerdictEnum.CONTRADICTED,
                        reason="Sole committer in every public repository linked (1 contributor found).",
                        evidence_found=f"1 contributor in git commit logs of {repo_label}; {signals.merged_prs} merged pull requests.",
                        suggested_remedy="Link repositories with pull requests merged across peer developers."
                    ), "CONTRADICTION_CHECK", "RULE_SOLE_CONTRIBUTOR_TEAM_MISMATCH")

            # Duration contradiction: e.g. claimed 3 years, git shows a one-day dump
            if (claim.claimed_duration_months and claim.claimed_duration_months >= 24
                    and signals.commit_count > 0 and self._in_scope(claim, analysed_repos)
                    and evidence_doc.active_months <= 1 and signals.single_day_commit_dump):
                refuse(claim.skill, RefusalItem(
                    claim=f"Claimed {claim.claimed_duration_months // 12} years experience in {claim.skill}",
                    verdict=VerdictEnum.CONTRADICTED,
                    reason=f"Git commit history spans only {evidence_doc.active_months} month(s) with single-day commit dumps.",
                    evidence_found=f"First commit {evidence_doc.first_commit} to last commit {evidence_doc.last_commit}.",
                    suggested_remedy="Publish repositories demonstrating continuous historical development."
                ), "DURATION_CONTRADICTION_CHECK", "RULE_DURATION_GIT_SPAN_MISMATCH")

        # 2. Evaluate Skill Claims Against Ground-Truth Evidence
        seen_skills = set()
        for claim in claims_doc.claims:
            if claim.category == "soft_skill":
                continue
            skill_name = normalize_skill(claim.skill)
            if skill_name.lower() in seen_skills:
                continue
            seen_skills.add(skill_name.lower())

            in_scope = self._in_scope(claim, analysed_repos)
            ev_skill = self._find_evidence(skill_name, evidence_doc) if in_scope else None
            is_testing_skill = claim.category == "testing" or skill_name in TESTING_SKILL_FRAMEWORKS
            has_certificate = any(any(m in l.lower() for m in CERT_MARKERS) for l in claim.evidence_links)

            if skill_name == "Git":
                has_code_blame = signals.candidate_commit_count >= GIT_MIN_COMMITS
                skill_pct = evidence_doc.candidate_authorship_pct if has_code_blame else None
            else:
                skill_pct = ev_skill.authorship_pct if ev_skill and ev_skill.authorship_pct is not None else evidence_doc.candidate_authorship_pct
                has_code_blame = (ev_skill is not None and ev_skill.lines_authored >= min_lines_for(skill_name)
                                  and skill_pct >= MIN_AUTHORSHIP_FOR_CODE)
            has_tests = self._has_tests_for(skill_name, ev_skill, evidence_doc) if in_scope else False
            has_deployed_or_pr = (signals.deployed_url is not None or signals.merged_prs > 0) and has_code_blame

            grade = challenge_grades.get(skill_name.lower(), "A" if (has_code_blame and has_tests) else ("B" if has_code_blame else "C"))

            # Testing claims with no matching test suite go straight to the refusal queue
            if is_testing_skill and not has_code_blame and not has_certificate:
                where = repo_label if in_scope else ", ".join(self._claim_repos(claim)) or repo_label
                if not in_scope:
                    reason = f"Listed on resume, but the linked repository ({where}) was not among the analysed repositories."
                elif ev_skill is not None and ev_skill.total_lines > 0:
                    reason = (f"Matching test files exist in {where}, but the candidate authored only "
                              f"{ev_skill.lines_authored} of {ev_skill.total_lines} test lines.")
                else:
                    reason = f"Listed on resume, but zero matching test files or assertions found in {where}."
                refuse(skill_name, RefusalItem(
                    claim=skill_name,
                    verdict=VerdictEnum.CLAIMED_ONLY,
                    reason=reason,
                    evidence_found=f"Scanned {signals.test_file_count} test files; frameworks found: {', '.join(signals.test_frameworks) or 'none'}.",
                    suggested_remedy=f"Add a {skill_name} suite with real assertions to {where}" + ("" if in_scope else ", and include that repository in the audit") + "."
                ), "EVALUATE_SKILL", "RULE_NO_CANDIDATE_TESTS")
                plan_skills.append((skill_name, f"Add {skill_name} tests to {where}", where))
                continue

            # Determine 4-state verdict
            months_ok = evidence_doc.active_months >= MIN_MONTHS_FOR_VERIFIED
            if has_code_blame and skill_pct >= MIN_AUTHORSHIP_FOR_VERIFIED and months_ok:
                verdict = VerdictEnum.VERIFIED
                level = "Advanced" if ev_skill and ev_skill.lines_authored > 2000 else "Intermediate"
            elif has_code_blame:
                verdict = VerdictEnum.PARTIALLY_SUPPORTED
                level = "Intermediate"
            elif has_certificate:
                verdict = VerdictEnum.PARTIALLY_SUPPORTED
                level = "Beginner"
            else:
                verdict = VerdictEnum.CLAIMED_ONLY
                level = "Beginner"

            # Contradicted by commit laundering or by a fork the candidate barely touched
            if signals.commit_laundering_detected:
                verdict = VerdictEnum.CONTRADICTED
                if not any("Commit Laundering" in r.reason for _, r in refusals):
                    refuse(skill_name, RefusalItem(
                        claim=f"Iterative development history in {skill_name}",
                        verdict=VerdictEnum.CONTRADICTED,
                        reason="Commit Laundering Detected: Bulk initial upload without iterative commit history.",
                        evidence_found=f"Initial commit accounts for >80% of lines across {signals.commit_count} total commit(s).",
                        suggested_remedy="Publish repositories demonstrating continuous incremental commits showing natural feature development."
                    ), "COMMIT_LAUNDERING_CHECK", "RULE_COMMIT_LAUNDERING_DUMP")
            elif evidence_doc.is_fork and evidence_doc.candidate_authorship_pct < 10.0:
                verdict = VerdictEnum.CONTRADICTED
                if not any("template fork" in r.reason.lower() and r.claim.startswith("Authentic") for _, r in refusals):
                    pct = round(evidence_doc.candidate_authorship_pct, 1)
                    refuse(skill_name, RefusalItem(
                        claim=f"Authentic repository development in {skill_name}",
                        verdict=VerdictEnum.CONTRADICTED,
                        reason=f"Repository is a template fork where candidate authored only {pct}% of lines.",
                        evidence_found=f"Forked upstream commit tree with negligible ({pct}%) candidate authorship.",
                        suggested_remedy="Provide original repositories or feature branches with authored commit history."
                    ), "FORK_CONTRADICTION_CHECK", "RULE_FORK_LOW_AUTHORSHIP")

            # Consistency bonus calculation:
            consistency_bonus = 0
            bonus_reasons: List[str] = []
            if has_code_blame:
                s_repo_count = ev_skill.repo_count if ev_skill else len(evidence_doc.repo_urls or [evidence_doc.repo_url])
                s_active_months = ev_skill.active_months if (ev_skill and ev_skill.active_months) else evidence_doc.active_months
                consistency_bonus, bonus_reasons = self.scoring.calculate_consistency_bonus(s_repo_count, s_active_months)

            evidence_score, ev_reason = self.scoring.calculate_evidence_score(
                has_deployed_or_pr=has_deployed_or_pr,
                has_tests=has_tests and has_code_blame,
                has_code_blame=has_code_blame,
                has_certificate=has_certificate
            )

            if verdict == VerdictEnum.CONTRADICTED:
                evidence_score = 1
                final_points = CONTRADICTED_POINTS
                consistency_bonus = 0
            elif verdict == VerdictEnum.CLAIMED_ONLY:
                evidence_score = CLAIMED_ONLY_EVIDENCE
                grade = CLAIMED_ONLY_GRADE  # the grade actually used, so the displayed formula adds up
                final_points = self.scoring.calculate_skill_points(evidence_score, grade)
                consistency_bonus = 0
            else:
                final_points = self.scoring.calculate_skill_points(evidence_score, grade, consistency_bonus=consistency_bonus)
                if consistency_bonus > 0 and bonus_reasons:
                    ev_reason += f" Includes {', '.join(bonus_reasons)}."

            snippet_str = None
            code_preview = None
            if ev_skill and ev_skill.sample_snippet:
                snippet_str = f"{ev_skill.sample_snippet.file}:L{ev_skill.sample_snippet.lines}"
                code_preview = ev_skill.sample_snippet.code_preview

            signals_list = self._signals_for(skill_name, ev_skill, skill_pct, has_code_blame, has_tests,
                                             has_deployed_or_pr, has_certificate, in_scope, claim, evidence_doc)

            if verdict == VerdictEnum.PARTIALLY_SUPPORTED:
                if not has_code_blame:
                    plan_skills.append((skill_name, f"Create a public repository demonstrating {skill_name} with a test suite", evidence_doc.repo_url))
                elif not months_ok or skill_pct < MIN_AUTHORSHIP_FOR_VERIFIED:
                    plan_skills.append((skill_name, f"Keep committing {skill_name} work over at least {MIN_MONTHS_FOR_VERIFIED} months", evidence_doc.repo_url))
            elif verdict == VerdictEnum.CLAIMED_ONLY:
                plan_skills.append((skill_name, f"Build and commit an open-source project showing {skill_name} in action", evidence_doc.repo_url))

            rule_label = f"RUBRIC_FORMULA({evidence_score}x{GRADE_WEIGHTS.get(grade, 6)})"
            if consistency_bonus > 0 and verdict not in (VerdictEnum.CONTRADICTED, VerdictEnum.CLAIMED_ONLY):
                rule_label += f"+BONUS({consistency_bonus})"

            audit_tracer.record(
                step="SCORE_SKILL",
                target=skill_name,
                rule_applied=rule_label,
                verdict_reached=verdict.value
            )

            skills_out.append(
                SkillPassportItem(
                    name=skill_name,
                    category=claim.category,
                    verdict=verdict,
                    level=level,
                    evidence_score=evidence_score,
                    test_grade=grade,
                    final_points=final_points,
                    consistency_bonus=consistency_bonus,
                    proof_snippet=snippet_str,
                    sample_code=code_preview,
                    authorship_pct=skill_pct if has_code_blame else None,
                    files_count=ev_skill.files_count if ev_skill else 0,
                    signals=signals_list,
                    reasoning=ev_reason
                )
            )

        refusal_items = [r for _, r in refusals]
        overall_score = self.scoring.overall_score([s.final_points for s in skills_out])
        role_match_pct = self.scoring.role_match_pct([s.verdict.value for s in skills_out], len(refusal_items))

        learning_plan = self._learning_plan(plan_skills, skills_out, refusals, role_match_pct)
        return skills_out, refusal_items, learning_plan, role_match_pct, overall_score

    # --- Helpers -------------------------------------------------------------------------------

    @staticmethod
    def _claim_repos(claim: ClaimItem) -> List[str]:
        return [l for l in claim.evidence_links if any(h in l.lower() for h in CODE_HOSTS)]

    def _in_scope(self, claim: ClaimItem, analysed_repos: set) -> bool:
        """A claim that links specific repositories can only be backed by evidence from those repositories."""
        linked = {k for k in (_repo_key(u) for u in self._claim_repos(claim)) if k}
        return not linked or not analysed_repos or bool(linked & analysed_repos)

    @staticmethod
    def _find_evidence(skill_name: str, evidence_doc: EvidenceDocument) -> Optional[SkillEvidence]:
        for key, ev in evidence_doc.skills_detected.items():
            if normalize_skill(key).lower() == skill_name.lower():
                return ev
        return None

    @staticmethod
    def _has_tests_for(skill_name: str, ev_skill: Optional[SkillEvidence], evidence_doc: EvidenceDocument) -> bool:
        """Test credit needs tests in the skill's ecosystem that the candidate actually wrote."""
        signals = evidence_doc.signals
        if not signals.has_tests or signals.test_file_count == 0:
            return False
        if skill_name in TESTING_SKILL_FRAMEWORKS:
            return ev_skill is not None
        frameworks = signals.test_frameworks or ([signals.test_framework] if signals.test_framework else [])
        ecosystem = ecosystem_for(skill_name)
        if ecosystem is None:
            return False
        for fw in frameworks:
            if TEST_FRAMEWORK_ECOSYSTEM.get(fw) != ecosystem:
                continue
            testing_skill = next((t for t, fws in TESTING_SKILL_FRAMEWORKS.items() if fw in fws), None)
            if testing_skill is None:
                return True  # framework without per-file evidence (e.g. go test): repo-level signal
            test_ev = FourStateVerifier._find_evidence(testing_skill, evidence_doc)
            # Test evidence is merged across repositories upstream, so tests the candidate wrote in
            # any analysed repo count here; tests written only by other people never do.
            if test_ev is not None and test_ev.lines_authored >= min_lines_for(testing_skill):
                return True
        return False

    @staticmethod
    def _signals_for(skill_name, ev_skill, skill_pct, has_code_blame, has_tests, has_deployed_or_pr,
                     has_certificate, in_scope, claim, evidence_doc) -> List[str]:
        out: List[str] = []
        if not in_scope:
            out.append(f"Linked repository ({', '.join(FourStateVerifier._claim_repos(claim))}) was not analysed")
        if skill_name == "Git" and has_code_blame:
            out.append(f"{evidence_doc.signals.candidate_commit_count} commits authored over {evidence_doc.active_months} months")
            eff_repo_count = len(evidence_doc.repo_urls or [evidence_doc.repo_url])
            if eff_repo_count >= 2:
                out.append(f"Evidence found across {eff_repo_count} repos")
        elif has_code_blame and ev_skill:
            out.append(f"Authored {ev_skill.lines_authored} lines across {ev_skill.files_count} files ({round(skill_pct, 1)}% of lines in those files)")
            if ev_skill.route_definitions:
                out.append(f"{ev_skill.route_definitions} API route definitions found by static analysis")
            eff_repo_count = ev_skill.repo_count if ev_skill else len(evidence_doc.repo_urls or [evidence_doc.repo_url])
            eff_active_months = ev_skill.active_months if (ev_skill and ev_skill.active_months) else evidence_doc.active_months
            if eff_repo_count >= 2:
                out.append(f"Evidence found across {eff_repo_count} repos")
            if eff_active_months >= 1:
                month_str = f"{eff_active_months} months" if eff_active_months > 1 else "1 month"
                out.append(f"Practiced over {month_str}")
        elif ev_skill and ev_skill.total_lines > 0:
            out.append(f"Found in repository, but the candidate authored {ev_skill.lines_authored} of {ev_skill.total_lines} lines (needs {min_lines_for(skill_name)}+ authored lines and {int(MIN_AUTHORSHIP_FOR_CODE)}%+ share)")
        if has_tests and has_code_blame:
            out.append(f"Matching tests found ({', '.join(evidence_doc.signals.test_frameworks) or evidence_doc.signals.test_framework})")
        if has_deployed_or_pr:
            if evidence_doc.signals.deployed_url:
                out.append(f"Deployment listed on the repository: {evidence_doc.signals.deployed_url}")
            if evidence_doc.signals.merged_prs:
                out.append(f"{evidence_doc.signals.merged_prs} merged pull request(s) by the candidate")
        if has_code_blame and evidence_doc.signals.has_error_handling and claim.category in ("language", "framework"):
            out.append("Error handling patterns found in the repository")
        if has_certificate:
            out.append("Certificate link provided (not code evidence)")
        if not out:
            out.append("No active repository commits or tests found")
        return out

    def _learning_plan(self, plan_skills, skills_out: List[SkillPassportItem],
                       refusals: List[Tuple[Optional[str], RefusalItem]], current_match: int) -> List[LearningPlanItem]:
        """Each item's impact is computed by re-running the role-match formula with that skill fixed."""
        items: List[LearningPlanItem] = []
        seen = set()
        for skill, action, repo in plan_skills:
            if action in seen:
                continue
            seen.add(action)
            verdicts = [s.verdict.value for s in skills_out if s.name != skill] + ["VERIFIED"]
            remaining_refusals = sum(1 for owner, _ in refusals if owner != skill)
            new_match = self.scoring.role_match_pct(verdicts, remaining_refusals)
            delta = max(0, new_match - current_match)
            items.append(LearningPlanItem(
                action=action,
                skill=skill,
                potential_impact=f"+{delta}% role match ({current_match}% → {new_match}%)",
                target_score_delta=delta,
                repo_context=repo
            ))
        return items
