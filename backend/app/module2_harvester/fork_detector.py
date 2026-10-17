import os
import git
from typing import Dict, Any, List

KNOWN_TUTORIAL_PATTERNS = [
    "freecodecamp", "traversy", "academind", "fireship",
    "course-starter", "boilerplate-mern", "fastapi-template"
]

class ForkAndTemplateDetector:
    """
    Detects if a candidate repository is a fork, a template clone, or an unmodified clone of a tutorial.
    """

    def inspect_repo(self, repo_path: str, candidate_authorship_pct: float, total_commits: int) -> Dict[str, Any]:
        is_fork = False
        is_cloned_template = False
        indicators: List[str] = []

        if not os.path.exists(repo_path):
            return {"is_fork": False, "is_cloned_template": False, "indicators": []}

        try:
            repo = git.Repo(repo_path)
            # Check remotes
            for remote in repo.remotes:
                for url in remote.urls:
                    url_lower = url.lower()
                    if any(t in url_lower for t in KNOWN_TUTORIAL_PATTERNS):
                        is_cloned_template = True
                        indicators.append(f"Remote origin tracks known tutorial repository: {url}")
        except Exception:
            pass

        # Check README or package.json for fork/template indicators
        for f in ["README.md", "readme.md", "package.json"]:
            full_path = os.path.join(repo_path, f)
            if os.path.exists(full_path):
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as file:
                        txt = file.read().lower()
                        if "forked from" in txt:
                            is_fork = True
                            indicators.append("README explicitly indicates repository was forked.")
                        if any(t in txt for t in KNOWN_TUTORIAL_PATTERNS):
                            indicators.append(f"Tutorial keywords detected in {f}.")
                except Exception:
                    pass

        # High risk: Authorship < 10% in a repository with more than 50 commits
        if candidate_authorship_pct < 10.0 and total_commits > 20:
            is_cloned_template = True
            indicators.append(f"Candidate authored only {candidate_authorship_pct}% of total code base.")

        return {
            "is_fork": is_fork,
            "is_cloned_template": is_cloned_template,
            "indicators": indicators
        }
