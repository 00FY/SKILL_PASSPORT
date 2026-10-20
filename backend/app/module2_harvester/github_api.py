import logging
import os
from typing import Dict, Iterable, List, Optional
import httpx

RATE_LIMITED = "rate_limited"

logger = logging.getLogger(__name__)


class GitHubClient:
    """
    Minimal read-only GitHub REST client for signals that git history alone can't provide:
    fork status, the repo's listed homepage / deployments, and merged pull requests.
    Every method returns None when the API is unavailable, so missing data is never fabricated.
    Set GITHUB_TOKEN to raise the rate limit; set SKILL_PASSPORT_GITHUB_API=0 to disable.
    """

    def __init__(self, token: Optional[str] = None, timeout: float = 8.0, enabled: Optional[bool] = None):
        self.token = token if token is not None else os.getenv("GITHUB_TOKEN")
        self.timeout = timeout
        self.enabled = enabled if enabled is not None else os.getenv("SKILL_PASSPORT_GITHUB_API", "1") != "0"

    def _get(self, path: str, params: Optional[Dict] = None, problems: Optional[List[str]] = None):
        """GET a REST path. Failures return None and, if `problems` is given, append why."""
        if not self.enabled:
            return None
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            res = httpx.get(f"https://api.github.com{path}", headers=headers, params=params, timeout=self.timeout)
            if res.status_code != 200:
                logger.info("GitHub API %s returned %s", path, res.status_code)
                if problems is not None:
                    limited = res.status_code in (403, 429) and (
                        res.headers.get("x-ratelimit-remaining") == "0" or "rate limit" in res.text.lower()
                    )
                    problems.append(RATE_LIMITED if limited else f"HTTP {res.status_code}")
                return None
            return res.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.info("GitHub API %s failed: %s", path, exc)
            if problems is not None:
                problems.append("network error")
            return None

    def repo_meta(self, owner: str, repo: str, problems: Optional[List[str]] = None) -> Optional[Dict]:
        data = self._get(f"/repos/{owner}/{repo}", problems=problems)
        if not isinstance(data, dict):
            return None
        homepage = (data.get("homepage") or "").strip() or None
        if homepage and not homepage.startswith(("http://", "https://")):
            homepage = "https://" + homepage
        deployments = self._get(f"/repos/{owner}/{repo}/deployments", {"per_page": 1}, problems)
        return {
            "fork": bool(data.get("fork")),
            "parent": (data.get("parent") or {}).get("full_name"),
            "homepage": homepage,
            "has_deployments": bool(deployments) if isinstance(deployments, list) else False,
        }

    def merged_pr_count(self, owner: str, repo: str, logins: Iterable[str],
                        problems: Optional[List[str]] = None) -> Optional[int]:
        logins = {l.lower() for l in logins if l}
        data = self._get(f"/repos/{owner}/{repo}/pulls", {"state": "closed", "per_page": 100}, problems)
        if not isinstance(data, list):
            return None
        return sum(
            1 for pr in data
            if pr.get("merged_at") and (not logins or (pr.get("user") or {}).get("login", "").lower() in logins)
        )

    def user_profile(self, username: str, problems: Optional[List[str]] = None) -> Optional[Dict]:
        """Fetch basic public GitHub profile info: name, bio, public_repos, avatar_url, etc."""
        data = self._get(f"/users/{username}", problems=problems)
        if not isinstance(data, dict):
            return None
        return {
            "login": data.get("login") or username,
            "name": data.get("name"),
            "bio": data.get("bio"),
            "avatar_url": data.get("avatar_url"),
            "public_repos": data.get("public_repos", 0),
            "blog": data.get("blog"),
            "location": data.get("location"),
        }

    def user_repos(self, username: str, limit: int = 5, problems: Optional[List[str]] = None) -> List[Dict]:
        """
        Fetch public non-fork repositories for a user, sorted by pushed_at descending.
        Returns top `limit` original repositories.
        """
        data = self._get(
            f"/users/{username}/repos",
            params={"sort": "pushed", "direction": "desc", "per_page": 30, "type": "owner"},
            problems=problems
        )
        if not isinstance(data, list):
            return []
        
        original_repos: List[Dict] = []
        for r in data:
            if not isinstance(r, dict):
                continue
            if r.get("fork"):
                continue  # skip forks to evaluate original work
            original_repos.append({
                "html_url": r.get("html_url"),
                "name": r.get("name"),
                "description": r.get("description"),
                "language": r.get("language"),
                "topics": r.get("topics") or [],
                "stargazers_count": r.get("stargazers_count", 0),
                "forks_count": r.get("forks_count", 0),
                "pushed_at": r.get("pushed_at"),
            })
            if len(original_repos) >= limit:
                break
        return original_repos
