import os
import git
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

EXCLUDED_DIRS = {
    "node_modules", "vendor", "dist", "build", ".git", ".next",
    "__pycache__", ".pytest_cache", ".venv", "venv", "env", "migrations"
}

EXCLUDED_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml"
}

EXCLUDED_EXTENSIONS = {
    ".lock", ".json", ".md", ".txt", ".csv", ".svg", ".png",
    ".jpg", ".ico", ".map", ".yaml", ".yml", ".toml"
}

CODE_EXTENSIONS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "React",
    ".jsx": "React",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
}

class GitBlameAnalyzer:
    """
    Crawls a Git repository, parses commit logs, extracts commit spans,
    and runs git blame with -w -M -C --line-porcelain on source files
    to calculate author attribution percentage while ignoring formatting/moves
    and filtering boilerplate/single-commit laundering.
    """

    def analyze_repo(self, repo_path: str, candidate_email_or_name: Optional[str] = None) -> Dict[str, Any]:
        if not os.path.exists(repo_path) or not os.path.exists(os.path.join(repo_path, ".git")):
            return self._empty_analysis()

        try:
            repo = git.Repo(repo_path)
        except Exception:
            return self._empty_analysis()

        commits = list(repo.iter_commits())
        if not commits:
            return self._empty_analysis()

        # 1. Timeline metrics & Root commit identification
        commit_dates = [datetime.fromtimestamp(c.committed_date) for c in commits]
        first_commit_date = min(commit_dates)
        last_commit_date = max(commit_dates)

        diff_days = (last_commit_date - first_commit_date).days
        active_months = max(1, round(diff_days / 30.0)) if diff_days > 0 else 1
        is_single_day_dump = (diff_days == 0 and len(commits) > 0)

        # Root commits (max-parents=0)
        root_commit_hashes = {c.hexsha for c in commits if len(c.parents) == 0}

        # 2. Candidate identity matching
        authors = {c.author.name: c.author.email for c in commits}
        primary_candidate = candidate_email_or_name
        if not primary_candidate and commits:
            author_counts = {}
            for c in commits:
                name = c.author.name or "Unknown"
                author_counts[name] = author_counts.get(name, 0) + 1
            primary_candidate = max(author_counts, key=author_counts.get)

        # 3. Blame analysis per file using -w -M -C --line-porcelain
        total_code_lines = 0
        candidate_code_lines = 0
        root_commit_lines = 0
        language_lines: Dict[str, int] = {}
        candidate_language_lines: Dict[str, int] = {}
        snippets_by_lang: Dict[str, Dict[str, Any]] = {}

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            for file in files:
                if file in EXCLUDED_FILES:
                    continue

                full_file_path = os.path.join(root, file)

                # Boilerplate filter: ignore empty __init__.py files
                if file == "__init__.py":
                    try:
                        with open(full_file_path, "r", encoding="utf-8", errors="ignore") as f:
                            if not f.read().strip():
                                continue
                    except Exception:
                        continue

                ext = os.path.splitext(file)[1].lower()
                if ext not in CODE_EXTENSIONS:
                    continue

                lang = CODE_EXTENSIONS[ext]
                rel_path = os.path.relpath(full_file_path, repo_path)

                blame_entries = self._run_porcelain_blame(repo, rel_path)
                if not blame_entries:
                    continue

                file_total_lines = 0
                file_candidate_lines = 0
                candidate_line_start = None
                candidate_line_count = 0

                current_line_no = 1
                for c_hash, author_name, author_email in blame_entries:
                    file_total_lines += 1

                    if c_hash in root_commit_hashes:
                        root_commit_lines += 1

                    is_match = False
                    if primary_candidate:
                        cand_low = primary_candidate.lower()
                        if cand_low in author_name.lower() or cand_low in author_email.lower():
                            is_match = True
                    else:
                        is_match = True

                    if is_match:
                        file_candidate_lines += 1
                        if candidate_line_start is None:
                            candidate_line_start = current_line_no
                        candidate_line_count += 1

                    current_line_no += 1

                total_code_lines += file_total_lines
                candidate_code_lines += file_candidate_lines

                language_lines[lang] = language_lines.get(lang, 0) + file_total_lines
                candidate_language_lines[lang] = candidate_language_lines.get(lang, 0) + file_candidate_lines

                # Save sample snippet for the language
                if lang not in snippets_by_lang and candidate_line_start is not None and candidate_line_count >= 3:
                    end_line = candidate_line_start + min(candidate_line_count, 35) - 1
                    snippets_by_lang[lang] = {
                        "file": rel_path,
                        "lines": f"{candidate_line_start}-{end_line}",
                        "blame_match": round(file_candidate_lines / max(1, file_total_lines), 2)
                    }

        authorship_pct = round((candidate_code_lines / max(1, total_code_lines)) * 100.0, 1)

        # Single-Commit Dump Detector:
        # If >80% of lines were committed in initial commit (max-parents=0) with <3 total commits
        initial_commit_pct = (root_commit_lines / max(1, total_code_lines)) * 100.0 if total_code_lines > 0 else 0.0
        commit_laundering = (initial_commit_pct > 80.0 and len(commits) < 3)

        return {
            "candidate_authorship_pct": authorship_pct,
            "total_commits": len(commits),
            "unique_contributors": len(authors),
            "first_commit": first_commit_date.strftime("%Y-%m-%d"),
            "last_commit": last_commit_date.strftime("%Y-%m-%d"),
            "active_months": active_months,
            "single_day_commit_dump": is_single_day_dump or commit_laundering,
            "commit_laundering_detected": commit_laundering,
            "initial_commit_line_pct": round(initial_commit_pct, 1),
            "language_lines": language_lines,
            "candidate_language_lines": candidate_language_lines,
            "snippets_by_lang": snippets_by_lang,
            "primary_author_identified": primary_candidate
        }

    def _run_porcelain_blame(self, repo: git.Repo, rel_path: str) -> List[Tuple[str, str, str]]:
        """
        Executes git blame with -w -M -C --line-porcelain to ignore whitespace formatting
        and detect moved/copied lines. Returns list of (commit_hash, author_name, author_email) per line.
        """
        try:
            output = repo.git.blame('-w', '-M', '-C', '--line-porcelain', 'HEAD', '--', rel_path)
            lines = output.split('\n')
            results: List[Tuple[str, str, str]] = []
            cur_hash = ""
            cur_author = ""
            cur_email = ""

            for line in lines:
                if not line:
                    continue
                if line.startswith('\t'):
                    results.append((cur_hash, cur_author, cur_email))
                elif line.startswith('author '):
                    cur_author = line[7:].strip()
                elif line.startswith('author-mail '):
                    cur_email = line[12:].strip().strip('<>')
                elif len(line.split()) >= 4 and len(line.split()[0]) == 40:
                    cur_hash = line.split()[0]

            return results
        except Exception:
            # Fallback to standard repo.blame
            entries: List[Tuple[str, str, str]] = []
            try:
                blame_chunks = repo.blame('HEAD', rel_path)
                for commit, chunk in blame_chunks:
                    c_hash = commit.hexsha
                    author_name = commit.author.name or ""
                    author_email = commit.author.email or ""
                    for _ in chunk:
                        entries.append((c_hash, author_name, author_email))
            except Exception:
                pass
            return entries

    def _empty_analysis(self) -> Dict[str, Any]:
        return {
            "candidate_authorship_pct": 0.0,
            "total_commits": 0,
            "unique_contributors": 0,
            "first_commit": None,
            "last_commit": None,
            "active_months": 0,
            "single_day_commit_dump": False,
            "commit_laundering_detected": False,
            "initial_commit_line_pct": 0.0,
            "language_lines": {},
            "candidate_language_lines": {},
            "snippets_by_lang": {},
            "primary_author_identified": None
        }
