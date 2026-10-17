import os
import git
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

EXCLUDED_DIRS = {
    "node_modules", "vendor", "dist", "build", ".git", ".next",
    "__pycache__", ".pytest_cache", ".venv", "venv", "env"
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
    and runs git blame on source files to calculate author attribution percentage.
    """

    def analyze_repo(self, repo_path: str, candidate_email_or_name: Optional[str] = None) -> Dict[str, Any]:
        if not os.path.exists(repo_path) or not os.path.exists(os.path.join(repo_path, ".git")):
            # Fallback or error if not a git directory
            return self._empty_analysis()

        try:
            repo = git.Repo(repo_path)
        except Exception:
            return self._empty_analysis()

        commits = list(repo.iter_commits())
        if not commits:
            return self._empty_analysis()

        # 1. Timeline metrics
        commit_dates = [datetime.fromtimestamp(c.committed_date) for c in commits]
        first_commit_date = min(commit_dates)
        last_commit_date = max(commit_dates)

        diff_days = (last_commit_date - first_commit_date).days
        active_months = max(1, round(diff_days / 30.0)) if diff_days > 0 else 1
        is_single_day_dump = (diff_days == 0 and len(commits) > 0)

        # 2. Candidate identity matching
        authors = {c.author.name: c.author.email for c in commits}
        primary_candidate = candidate_email_or_name
        if not primary_candidate and commits:
            # Default to most frequent committer
            author_counts = {}
            for c in commits:
                name = c.author.name or "Unknown"
                author_counts[name] = author_counts.get(name, 0) + 1
            primary_candidate = max(author_counts, key=author_counts.get)

        # 3. Blame analysis per file
        total_code_lines = 0
        candidate_code_lines = 0
        language_lines: Dict[str, int] = {}
        candidate_language_lines: Dict[str, int] = {}
        snippets_by_lang: Dict[str, Dict[str, Any]] = {}

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext not in CODE_EXTENSIONS:
                    continue

                lang = CODE_EXTENSIONS[ext]
                rel_path = os.path.relpath(os.path.join(root, file), repo_path)

                try:
                    blame_entries = repo.blame('HEAD', rel_path)
                except Exception:
                    continue

                file_total_lines = 0
                file_candidate_lines = 0
                candidate_line_start = None
                candidate_line_count = 0

                current_line_no = 1
                for commit, lines_chunk in blame_entries:
                    chunk_len = len(lines_chunk)
                    file_total_lines += chunk_len
                    author_name = commit.author.name or ""
                    author_email = commit.author.email or ""

                    is_match = False
                    if primary_candidate:
                        cand_low = primary_candidate.lower()
                        if cand_low in author_name.lower() or cand_low in author_email.lower():
                            is_match = True
                    else:
                        is_match = True

                    if is_match:
                        file_candidate_lines += chunk_len
                        if candidate_line_start is None and chunk_len >= 5:
                            candidate_line_start = current_line_no
                            candidate_line_count = chunk_len

                    current_line_no += chunk_len

                total_code_lines += file_total_lines
                candidate_code_lines += file_candidate_lines

                language_lines[lang] = language_lines.get(lang, 0) + file_total_lines
                candidate_language_lines[lang] = candidate_language_lines.get(lang, 0) + file_candidate_lines

                # Save a high-quality sample snippet for the language if not already saved
                if lang not in snippets_by_lang and candidate_line_start is not None:
                    end_line = candidate_line_start + min(candidate_line_count, 35) - 1
                    snippets_by_lang[lang] = {
                        "file": rel_path,
                        "lines": f"{candidate_line_start}-{end_line}",
                        "blame_match": round(file_candidate_lines / max(1, file_total_lines), 2)
                    }

        authorship_pct = round((candidate_code_lines / max(1, total_code_lines)) * 100.0, 1)

        return {
            "candidate_authorship_pct": authorship_pct,
            "total_commits": len(commits),
            "unique_contributors": len(authors),
            "first_commit": first_commit_date.strftime("%Y-%m-%d"),
            "last_commit": last_commit_date.strftime("%Y-%m-%d"),
            "active_months": active_months,
            "single_day_commit_dump": is_single_day_dump,
            "language_lines": language_lines,
            "candidate_language_lines": candidate_language_lines,
            "snippets_by_lang": snippets_by_lang,
            "primary_author_identified": primary_candidate
        }

    def _empty_analysis(self) -> Dict[str, Any]:
        return {
            "candidate_authorship_pct": 0.0,
            "total_commits": 0,
            "unique_contributors": 0,
            "first_commit": None,
            "last_commit": None,
            "active_months": 0,
            "single_day_commit_dump": False,
            "language_lines": {},
            "candidate_language_lines": {},
            "snippets_by_lang": {},
            "primary_author_identified": None
        }
