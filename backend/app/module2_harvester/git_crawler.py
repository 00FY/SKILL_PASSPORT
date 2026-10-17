import os
import subprocess
import time
from collections import Counter
from datetime import datetime
from typing import Dict, Any, List, Optional, Iterable, Tuple
from .constants import CODE_EXTENSIONS, walk_repo_files
from .identity import IdentityMatcher

BOT_MARKERS = ("[bot]", "dependabot", "github-actions", "renovate")


class GitBlameAnalyzer:
    """
    Crawls a Git repository, parses commit logs, extracts commit spans,
    and runs git blame with -w -M -C --line-porcelain on source files
    to calculate author attribution percentage while ignoring formatting/moves
    and filtering boilerplate/single-commit laundering.
    """

    def __init__(self, blame_timeout_s: Optional[float] = None, total_budget_s: Optional[float] = None,
                 max_files: Optional[int] = None):
        self.blame_timeout_s = blame_timeout_s or float(os.getenv("SKILL_PASSPORT_BLAME_FILE_TIMEOUT_S", "20"))
        self.total_budget_s = total_budget_s or float(os.getenv("SKILL_PASSPORT_BLAME_BUDGET_S", "120"))
        self.max_files = max_files or int(os.getenv("SKILL_PASSPORT_MAX_BLAME_FILES", "1500"))

    def analyze_repo(
        self,
        repo_path: str,
        candidate_email_or_name: Optional[str] = None,
        identities: Optional[Iterable[str]] = None,
        extra_files: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        if not os.path.exists(os.path.join(repo_path, ".git")):
            return self._empty_analysis()

        commits = self._read_commits(repo_path)
        if not commits:
            return self._empty_analysis()

        # 1. Candidate identity matching. With no identity at all, fall back to the top committer.
        matcher = IdentityMatcher(identities, candidate_email_or_name)
        matcher_mode = "identities"
        human_commits = [c for c in commits if not self._is_bot(c["name"], c["email"])]
        author_counts = Counter((c["email"].lower() or c["name"].lower()) for c in human_commits)
        display = {}
        for c in human_commits:
            display.setdefault(c["email"].lower() or c["name"].lower(), f"{c['name']} <{c['email']}>")
        if matcher.is_empty and author_counts:
            top = author_counts.most_common(1)[0][0]
            matcher = IdentityMatcher([top])
            matcher_mode = "top_committer"

        candidate_commits = [c for c in commits if matcher.matches(c["name"], c["email"])]

        # 2. Timeline metrics from the candidate's own commits (an old upstream history isn't theirs)
        span_source = candidate_commits or commits
        dates = [datetime.fromtimestamp(c["ts"]) for c in span_source]
        first_commit_date, last_commit_date = min(dates), max(dates)
        diff_days = (last_commit_date - first_commit_date).days
        active_months = max(1, round(diff_days / 30.0)) if diff_days > 0 else 1
        is_single_day_dump = diff_days == 0

        root_commit_hashes = {c["hash"] for c in commits if not c["parents"]}
        is_shallow = self._git(repo_path, ["rev-parse", "--is-shallow-repository"]).strip() == "true"

        # 3. Blame analysis per file using -w -M -C --line-porcelain
        files: List[Tuple[str, Optional[str]]] = []
        for name, _, rel_path in walk_repo_files(repo_path):
            lang = CODE_EXTENSIONS.get(os.path.splitext(name)[1].lower())
            if lang:
                files.append((rel_path, lang))
        code_paths = {p for p, _ in files}
        for rel_path in extra_files or []:
            if rel_path not in code_paths:
                files.append((rel_path, None))

        started = time.monotonic()
        truncated = False
        per_file: Dict[str, Dict[str, Any]] = {}
        total_code_lines = candidate_code_lines = root_commit_lines = 0
        language_lines: Dict[str, int] = {}
        candidate_language_lines: Dict[str, int] = {}

        for idx, (rel_path, lang) in enumerate(files):
            if idx >= self.max_files or time.monotonic() - started > self.total_budget_s:
                truncated = True
                break
            entries = self._run_porcelain_blame(repo_path, rel_path)
            if not entries:
                continue

            total = cand = roots = 0
            best_run, run_start, run_end = (None, 0), None, None
            for line_no, (c_hash, author, email, content) in enumerate(entries, start=1):
                if not content.strip():
                    continue  # blank lines carry no authorship
                total += 1
                if c_hash in root_commit_hashes:
                    roots += 1
                if matcher.matches(author, email):
                    cand += 1
                    if run_start is None:
                        run_start = line_no
                    run_end = line_no
                    if run_end - run_start + 1 > best_run[1]:
                        best_run = (run_start, run_end - run_start + 1)
                else:
                    run_start = run_end = None

            per_file[rel_path] = {"lang": lang, "total": total, "candidate": cand, "best_run": best_run}
            if lang:
                total_code_lines += total
                candidate_code_lines += cand
                root_commit_lines += roots
                language_lines[lang] = language_lines.get(lang, 0) + total
                candidate_language_lines[lang] = candidate_language_lines.get(lang, 0) + cand

        authorship_pct = round((candidate_code_lines / max(1, total_code_lines)) * 100.0, 1)

        # Single-Commit Dump Detector: >80% of lines from the root commit(s) with <3 total commits.
        # A shallow clone has no real root commit, so the check is skipped rather than guessed.
        initial_commit_pct = (root_commit_lines / max(1, total_code_lines)) * 100.0 if total_code_lines else 0.0
        commit_laundering = (not is_shallow) and initial_commit_pct > 80.0 and len(commits) < 3

        return {
            "candidate_authorship_pct": authorship_pct,
            "total_commits": len(commits),
            "candidate_commit_count": len(candidate_commits),
            "unique_contributors": len(author_counts),
            "authors_found": [f"{display[k]} ({n} commits)" for k, n in author_counts.most_common(5)],
            "identities_used": matcher.describe(),
            "matcher_mode": matcher_mode,
            "first_commit": first_commit_date.strftime("%Y-%m-%d"),
            "last_commit": last_commit_date.strftime("%Y-%m-%d"),
            "active_months": active_months,
            "single_day_commit_dump": is_single_day_dump or commit_laundering,
            "commit_laundering_detected": commit_laundering,
            "initial_commit_line_pct": round(initial_commit_pct, 1),
            "is_shallow": is_shallow,
            "truncated": truncated,
            "files_blamed": len(per_file),
            "total_code_lines": total_code_lines,
            "candidate_code_lines": candidate_code_lines,
            "language_lines": language_lines,
            "candidate_language_lines": candidate_language_lines,
            "per_file": per_file,
            "snippets_by_lang": self._snippets_by_lang(per_file),
            "primary_author_identified": ", ".join(matcher.describe()) or None,
        }

    @staticmethod
    def _snippets_by_lang(per_file: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        snippets: Dict[str, Dict[str, Any]] = {}
        for rel_path, info in per_file.items():
            lang = info["lang"]
            start, length = info["best_run"]
            if not lang or start is None or length < 3:
                continue
            if lang not in snippets or length > snippets[lang]["_len"]:
                snippets[lang] = {
                    "file": rel_path,
                    "lines": f"{start}-{start + min(length, 35) - 1}",
                    "blame_match": round(info["candidate"] / max(1, info["total"]), 2),
                    "_len": length,
                }
        for s in snippets.values():
            s.pop("_len")
        return snippets

    @staticmethod
    def _is_bot(name: str, email: str) -> bool:
        ident = f"{name} {email}".lower()
        return any(m in ident for m in BOT_MARKERS)

    def _git(self, repo_path: str, args: List[str], timeout: Optional[float] = None) -> str:
        try:
            proc = subprocess.run(
                ["git", "-C", repo_path, *args], capture_output=True, timeout=timeout or self.blame_timeout_s,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""
        if proc.returncode != 0:
            return ""
        return proc.stdout.decode("utf-8", errors="replace")

    def _read_commits(self, repo_path: str) -> List[Dict[str, Any]]:
        out = self._git(repo_path, ["log", "--format=%H%x1f%P%x1f%an%x1f%ae%x1f%ct%x1e", "HEAD"], timeout=60)
        commits = []
        for record in out.split("\x1e"):
            record = record.strip()
            if not record:
                continue
            parts = record.split("\x1f")
            if len(parts) != 5:
                continue
            c_hash, parents, name, email, ts = parts
            try:
                commits.append({"hash": c_hash, "parents": parents.split(), "name": name, "email": email, "ts": int(ts)})
            except ValueError:
                continue
        return commits

    def _run_porcelain_blame(self, repo_path: str, rel_path: str) -> List[Tuple[str, str, str, str]]:
        """
        Executes git blame with -w -M -C --line-porcelain to ignore whitespace formatting
        and detect moved/copied lines. Returns (commit_hash, author_name, author_email, line_content) per line.
        """
        output = self._git(repo_path, ["blame", "-w", "-M", "-C", "--line-porcelain", "HEAD", "--", rel_path])
        results: List[Tuple[str, str, str, str]] = []
        cur_hash = cur_author = cur_email = ""
        for line in output.split("\n"):
            if line.startswith("\t"):
                results.append((cur_hash, cur_author, cur_email, line[1:]))
            elif line.startswith("author "):
                cur_author = line[7:].strip()
            elif line.startswith("author-mail "):
                cur_email = line[12:].strip().strip("<>")
            else:
                head = line.split(" ", 1)[0]
                if len(head) in (40, 64) and all(ch in "0123456789abcdef" for ch in head):
                    cur_hash = head
        return results

    def _empty_analysis(self) -> Dict[str, Any]:
        return {
            "candidate_authorship_pct": 0.0,
            "total_commits": 0,
            "candidate_commit_count": 0,
            "unique_contributors": 0,
            "authors_found": [],
            "identities_used": [],
            "matcher_mode": "none",
            "first_commit": None,
            "last_commit": None,
            "active_months": 0,
            "single_day_commit_dump": False,
            "commit_laundering_detected": False,
            "initial_commit_line_pct": 0.0,
            "is_shallow": False,
            "truncated": False,
            "files_blamed": 0,
            "total_code_lines": 0,
            "candidate_code_lines": 0,
            "language_lines": {},
            "candidate_language_lines": {},
            "per_file": {},
            "snippets_by_lang": {},
            "primary_author_identified": None,
        }
