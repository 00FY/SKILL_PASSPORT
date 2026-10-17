import os
import subprocess
from typing import Dict, Any, List, Optional

KNOWN_TUTORIAL_PATTERNS = [
    "freecodecamp", "traversy", "academind", "fireship",
    "course-starter", "boilerplate-mern", "fastapi-template"
]


class ForkAndTemplateDetector:
    """
    Detects if a candidate repository is a fork, a template clone, or an unmodified clone of a tutorial.
    Uses the code host's own fork flag when available, then local heuristics.
    """

    def inspect_repo(self, repo_path: str, candidate_authorship_pct: float, total_commits: int,
                     host_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        is_fork = False
        is_cloned_template = False
        indicators: List[str] = []

        if host_meta and host_meta.get("fork"):
            is_fork = True
            parent = host_meta.get("parent")
            indicators.append(f"GitHub reports this repository is a fork{f' of {parent}' if parent else ''}.")

        if not os.path.exists(repo_path):
            return {"is_fork": is_fork, "is_cloned_template": False, "indicators": indicators}

        try:
            remotes = subprocess.run(["git", "-C", repo_path, "remote", "-v"], capture_output=True, text=True, timeout=10).stdout
            for line in remotes.splitlines():
                url_lower = line.lower()
                if any(t in url_lower for t in KNOWN_TUTORIAL_PATTERNS):
                    is_cloned_template = True
                    indicators.append(f"Remote tracks known tutorial repository: {line.split()[1] if len(line.split()) > 1 else line}")
                    break
        except (subprocess.SubprocessError, OSError):
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
                except OSError:
                    pass

        # High risk: authorship < 10% in a repository with real history the candidate didn't write
        if candidate_authorship_pct < 10.0 and total_commits > 20:
            is_cloned_template = True
            indicators.append(f"Candidate authored only {candidate_authorship_pct}% of total code base.")

        return {
            "is_fork": is_fork,
            "is_cloned_template": is_cloned_template,
            "indicators": indicators
        }
