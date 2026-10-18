import os
import shutil
import tempfile
from typing import Optional, Dict, Any, List, Iterable, Callable

Progress = Optional[Callable[[str], None]]
from ..schemas import EvidenceDocument, SkillEvidence, QualitySignals, SampleSnippet, ExcludedRepo
from ..skills import TESTING_SKILL_FRAMEWORKS
from .git_crawler import GitBlameAnalyzer
from .ast_analyzer import ASTAnalyzer
from .test_detector import TestDetector
from .fork_detector import ForkAndTemplateDetector
from .github_api import GitHubClient, RATE_LIMITED
from .repo_source import (
    RepoRef, RepoSourceError, RepoAccessError, parse_repo_source, clone_repo, local_repos_allowed
)

MAX_REPOS = 5
SNIPPET_PREVIEW_LINES = 25


class EvidenceHarvesterService:
    def __init__(self, github_client: Optional[GitHubClient] = None):
        self.blame_analyzer = GitBlameAnalyzer()
        self.ast_analyzer = ASTAnalyzer()
        self.test_detector = TestDetector()
        self.fork_detector = ForkAndTemplateDetector()
        self.github = github_client or GitHubClient()

    # --- Public API ----------------------------------------------------------------------------

    def harvest_repo(
        self,
        repo_url_or_path: str,
        candidate_name: Optional[str] = None,
        identities: Optional[Iterable[str]] = None,
        allow_local: Optional[bool] = None,
        progress: Progress = None,
    ) -> EvidenceDocument:
        """
        Gathers evidence from one public repository (or a local path when allowed).
        Returns an EvidenceDocument conforming to evidence.json schema contract.
        Raises RepoSourceError for invalid input and RepoAccessError when the repo can't be fetched.
        Never substitutes demo data.
        """
        allow_local = local_repos_allowed() if allow_local is None else allow_local
        ref = parse_repo_source(repo_url_or_path, allow_local=allow_local)
        idents = list(identities or [])
        if ref.owner and "/" not in ref.owner:
            # The repo owner's login is a strong default identity (matches GitHub noreply emails)
            idents.append(ref.owner)

        report = progress or (lambda _msg: None)
        if ref.local_path:
            report(f"Analysing who wrote the code in {ref.url}")
            return self._analyze_path(ref.local_path, ref, candidate_name, idents)

        temp_dir = tempfile.mkdtemp(prefix="skill_passport_repo_")
        try:
            report(f"Cloning {ref.url}")
            clone_repo(ref, temp_dir)
            report(f"Analysing who wrote the code in {ref.url}")
            return self._analyze_path(temp_dir, ref, candidate_name, idents)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def harvest_many(
        self,
        sources: List[str],
        candidate_name: Optional[str] = None,
        identities: Optional[Iterable[str]] = None,
        allow_local: Optional[bool] = None,
        progress: Progress = None,
    ) -> EvidenceDocument:
        """Harvest several repositories and merge them. Fails only if every repository fails."""
        unique: List[str] = []
        for s in sources:
            s = (s or "").strip()
            if s and s not in unique:
                unique.append(s)
        if not unique:
            return EvidenceDocument(repo_url="", warnings=["No repository was provided, so no claim can be backed by code."])
        if len(unique) > MAX_REPOS:
            raise RepoSourceError(f"At most {MAX_REPOS} repositories can be analysed per candidate.")

        docs: List[EvidenceDocument] = []
        errors: List[str] = []
        only_input_errors = True
        for idx, source in enumerate(unique, start=1):
            step = (lambda msg, i=idx: progress(f"Repository {i} of {len(unique)}: {msg}")) if progress else None
            try:
                docs.append(self.harvest_repo(source, candidate_name, identities, allow_local, step))
            except RepoSourceError as exc:
                errors.append(str(exc))
            except RepoAccessError as exc:
                only_input_errors = False
                errors.append(str(exc))
        if not docs:
            raise (RepoSourceError if only_input_errors else RepoAccessError)(" ".join(errors))

        merged = merge_evidence(docs)
        merged.warnings = errors + merged.warnings
        return merged

    # --- Single-repo analysis ------------------------------------------------------------------

    def _analyze_path(self, path: str, ref: RepoRef, candidate_name: Optional[str], identities: List[str]) -> EvidenceDocument:
        ast_res = self.ast_analyzer.analyze_directory(path)
        tests_res = self.test_detector.detect_tests(path)
        config_files = {f for files in ast_res["skill_files"].values() for f in files}

        blame_res = self.blame_analyzer.analyze_repo(path, candidate_name, identities, extra_files=sorted(config_files))
        if blame_res["total_commits"] == 0:
            raise RepoAccessError(f"{ref.url} has no commits to analyse.")
        per_file = blame_res["per_file"]

        # Skill evidence = authorship measured on exactly the files that evidence the skill
        skill_files: Dict[str, List[str]] = {}
        for rel_path, info in per_file.items():
            if info["lang"]:
                skill_files.setdefault(info["lang"], []).append(rel_path)
        for skill, files in ast_res["skill_files"].items():
            skill_files.setdefault(skill, [])
            skill_files[skill] = sorted(set(skill_files[skill]) | set(files))
        for skill, frameworks in TESTING_SKILL_FRAMEWORKS.items():
            files = [f for fw in frameworks for f in tests_res["files_by_framework"].get(fw, [])]
            if files:
                skill_files[skill] = sorted(set(files))

        skills_detected: Dict[str, SkillEvidence] = {}
        for skill, files in skill_files.items():
            ev = self._skill_evidence(path, files, per_file)
            if ev is None:
                continue
            ev.imports_found = ast_res["skill_imports"].get(skill, [])[:10]
            ev.route_definitions = ast_res["skill_routes"].get(skill, 0)
            skills_detected[skill] = ev

        api_problems: List[str] = []
        host_meta = self.github.repo_meta(ref.owner, ref.name, api_problems) if ref.is_github else None
        logins = [i for i in identities if "@" not in i and " " not in i]
        merged_prs = self.github.merged_pr_count(ref.owner, ref.name, logins, api_problems) if ref.is_github else None

        deployed_url = None
        if host_meta:
            if host_meta.get("homepage"):
                deployed_url = host_meta["homepage"]
            elif host_meta.get("has_deployments"):
                deployed_url = f"{ref.url}/deployments"

        fork_res = self.fork_detector.inspect_repo(
            path, blame_res["candidate_authorship_pct"], blame_res["total_commits"], host_meta
        )

        signals = QualitySignals(
            has_tests=tests_res["has_tests"],
            test_framework=tests_res["test_framework"],
            test_frameworks=tests_res["test_frameworks"],
            test_file_count=tests_res["test_file_count"],
            test_assertion_count=tests_res["test_assertion_count"],
            has_error_handling=ast_res["has_error_handling"],
            merged_prs=merged_prs or 0,
            deployed_url=deployed_url,
            single_day_commit_dump=blame_res["single_day_commit_dump"],
            commit_laundering_detected=blame_res["commit_laundering_detected"],
            commit_count=blame_res["total_commits"],
            candidate_commit_count=blame_res["candidate_commit_count"],
        )

        notes = [
            f"[{ref.url}] Evaluated {blame_res['total_commits']} commits ({blame_res['candidate_commit_count']} by the candidate) across {blame_res['active_months']} active months.",
            f"[{ref.url}] Candidate code authorship calculated at {blame_res['candidate_authorship_pct']}% over {blame_res['files_blamed']} blamed files.",
        ]
        if tests_res["has_tests"]:
            notes.append(f"[{ref.url}] Identified {', '.join(tests_res['test_frameworks'])} tests in {tests_res['test_file_count']} files.")
        if deployed_url:
            notes.append(f"[{ref.url}] Deployment signal from GitHub: {deployed_url}")
        if merged_prs:
            notes.append(f"[{ref.url}] {merged_prs} merged pull request(s) authored by the candidate.")
        notes.extend(f"[{ref.url}] {i}" for i in fork_res["indicators"])

        warnings: List[str] = []
        if blame_res["candidate_code_lines"] == 0 and blame_res["total_code_lines"] > 0:
            warnings.append(
                f"No code in {ref.url} matched the candidate's identity ({', '.join(blame_res['identities_used']) or 'none given'}). "
                f"Commit authors found: {'; '.join(blame_res['authors_found']) or 'none'}. "
                "If one of these is the candidate, add that email or username under Git identities and re-run."
            )
        if blame_res["matcher_mode"] == "top_committer":
            warnings.append(f"No candidate identity was given for {ref.url}; assumed the top committer is the candidate.")
        if blame_res["truncated"]:
            warnings.append(f"{ref.url} is large: authorship was measured on the first {blame_res['files_blamed']} files only.")
        if blame_res["is_shallow"]:
            warnings.append(f"{ref.url} has truncated history, so the single-commit dump check was skipped.")
        if ref.is_github and self.github.enabled and (host_meta is None or merged_prs is None):
            skipped = "fork, deployment and pull request checks" if host_meta is None else "the pull request check"
            if RATE_LIMITED in api_problems:
                warnings.append(
                    f"GitHub API rate limit reached, so {skipped} were skipped for {ref.url}. "
                    "Set GITHUB_TOKEN on the server to raise the limit."
                )
            else:
                reason = ", ".join(sorted(set(api_problems))) or "unavailable"
                warnings.append(f"GitHub API {reason}: {skipped} were skipped for {ref.url}.")

        return EvidenceDocument(
            repo_url=ref.url,
            repo_urls=[ref.url],
            is_fork=fork_res["is_fork"],
            is_cloned_template=fork_res["is_cloned_template"],
            candidate_authorship_pct=blame_res["candidate_authorship_pct"],
            first_commit=blame_res["first_commit"],
            last_commit=blame_res["last_commit"],
            active_months=blame_res["active_months"],
            unique_contributors=blame_res["unique_contributors"],
            total_code_lines=blame_res["total_code_lines"],
            candidate_code_lines=blame_res["candidate_code_lines"],
            authors_found=blame_res["authors_found"],
            identities_used=blame_res["identities_used"],
            skills_detected=skills_detected,
            signals=signals,
            warnings=warnings,
            raw_audit_notes=notes,
        )

    @staticmethod
    def _skill_evidence(repo_path: str, files: List[str], per_file: Dict[str, Dict[str, Any]]) -> Optional[SkillEvidence]:
        infos = [(f, per_file[f]) for f in files if f in per_file]
        if not infos:
            return None
        total = sum(i["total"] for _, i in infos)
        cand = sum(i["candidate"] for _, i in infos)

        snippet = None
        best_file, best_info = max(infos, key=lambda fi: fi[1]["best_run"][1])
        start, length = best_info["best_run"]
        if start is not None and length >= 1:
            shown = min(length, SNIPPET_PREVIEW_LINES)
            preview = None
            try:
                with open(os.path.join(repo_path, best_file), "r", encoding="utf-8", errors="ignore") as fh:
                    preview = "".join(fh.readlines()[start - 1:start - 1 + shown]).rstrip("\n")
            except OSError:
                pass
            snippet = SampleSnippet(
                file=best_file,
                lines=f"{start}-{start + shown - 1}",
                blame_match=round(best_info["candidate"] / max(1, best_info["total"]), 2),
                code_preview=preview,
            )

        skill_months = set()
        for _, i in infos:
            skill_months.update(i.get("candidate_months", []))
        sorted_months = sorted(skill_months)

        return SkillEvidence(
            lines_authored=cand,
            total_lines=total,
            authorship_pct=round(cand / max(1, total) * 100.0, 1),
            files_count=sum(1 for _, i in infos if i["candidate"] > 0),
            sample_snippet=snippet,
            repo_count=1 if (cand > 0 or total > 0) else 0,
            active_months=len(sorted_months),
            distinct_months=sorted_months,
        )


def _is_disqualified(doc: EvidenceDocument) -> Optional[str]:
    if doc.signals.commit_laundering_detected:
        return "Commit laundering: bulk initial upload without iterative history."
    if doc.is_fork and doc.candidate_authorship_pct < 10.0:
        return f"Fork where the candidate authored only {round(doc.candidate_authorship_pct, 1)}% of lines."
    return None


def merge_evidence(docs: List[EvidenceDocument]) -> EvidenceDocument:
    """
    Merge per-repository evidence. Repositories disqualified by laundering or forking are excluded
    from the merged evidence (and reported) instead of contaminating claims backed by other repos.
    If every repository is disqualified, the first one is returned so its contradictions surface.
    """
    if len(docs) == 1:
        return docs[0]

    clean: List[EvidenceDocument] = []
    excluded: List[ExcludedRepo] = []
    for d in docs:
        reason = _is_disqualified(d)
        if reason:
            excluded.append(ExcludedRepo(repo_url=d.repo_url, reason=reason))
        else:
            clean.append(d)
    if not clean:
        first = docs[0].model_copy(deep=True)
        first.repo_urls = [d.repo_url for d in docs]
        first.warnings = [w for d in docs for w in d.warnings]
        first.raw_audit_notes = [n for d in docs for n in d.raw_audit_notes]
        return first

    skills: Dict[str, SkillEvidence] = {}
    skill_repos: Dict[str, set] = {}
    for d in clean:
        for name, ev in d.skills_detected.items():
            skill_repos.setdefault(name, set()).add(d.repo_url)
            if name not in skills:
                cur = ev.model_copy(deep=True)
                cur.repo_count = len(skill_repos[name])
                skills[name] = cur
                continue
            cur = skills[name]
            better_snippet = ev.lines_authored > cur.lines_authored and ev.sample_snippet
            cur.lines_authored += ev.lines_authored
            cur.total_lines += ev.total_lines
            cur.files_count += ev.files_count
            cur.route_definitions += ev.route_definitions
            cur.imports_found = sorted(set(cur.imports_found) | set(ev.imports_found))[:10]
            cur.authorship_pct = round(cur.lines_authored / max(1, cur.total_lines) * 100.0, 1)
            all_months = set(cur.distinct_months) | set(ev.distinct_months)
            cur.distinct_months = sorted(all_months)
            cur.active_months = len(cur.distinct_months)
            cur.repo_count = len(skill_repos[name])
            if better_snippet:
                cur.sample_snippet = ev.sample_snippet

    total_lines = sum(d.total_code_lines for d in clean)
    cand_lines = sum(d.candidate_code_lines for d in clean)
    firsts = [d.first_commit for d in clean if d.first_commit]
    lasts = [d.last_commit for d in clean if d.last_commit]
    frameworks = sorted({f for d in clean for f in d.signals.test_frameworks})

    signals = QualitySignals(
        has_tests=any(d.signals.has_tests for d in clean),
        test_framework=next((d.signals.test_framework for d in clean if d.signals.test_framework), None),
        test_frameworks=frameworks,
        test_file_count=sum(d.signals.test_file_count for d in clean),
        test_assertion_count=sum(d.signals.test_assertion_count for d in clean),
        has_error_handling=any(d.signals.has_error_handling for d in clean),
        merged_prs=sum(d.signals.merged_prs for d in clean),
        deployed_url=next((d.signals.deployed_url for d in clean if d.signals.deployed_url), None),
        single_day_commit_dump=all(d.signals.single_day_commit_dump for d in clean),
        commit_laundering_detected=False,
        commit_count=sum(d.signals.commit_count for d in clean),
        candidate_commit_count=sum(d.signals.candidate_commit_count for d in clean),
    )

    return EvidenceDocument(
        repo_url=clean[0].repo_url,
        repo_urls=[d.repo_url for d in docs],
        is_fork=False,
        is_cloned_template=any(d.is_cloned_template for d in clean),
        candidate_authorship_pct=round(cand_lines / max(1, total_lines) * 100.0, 1),
        first_commit=min(firsts) if firsts else None,
        last_commit=max(lasts) if lasts else None,
        active_months=max(d.active_months for d in clean),
        unique_contributors=max((d.unique_contributors or 0) for d in clean),
        total_code_lines=total_lines,
        candidate_code_lines=cand_lines,
        authors_found=[a for d in clean for a in d.authors_found][:10],
        identities_used=sorted({i for d in docs for i in d.identities_used}),
        skills_detected=skills,
        signals=signals,
        excluded_repos=excluded,
        warnings=[w for d in docs for w in d.warnings],
        raw_audit_notes=[n for d in docs for n in d.raw_audit_notes],
    )
