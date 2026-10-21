import logging
import hashlib
import os
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple
import httpx

RATE_LIMITED = "rate_limited"
CACHE_TTL_S = 15 * 60
MAX_CACHE_ENTRIES = 2000

logger = logging.getLogger(__name__)


def github_problem_message(problems: Iterable[str]) -> str:
    """Explain missing GitHub evidence without confusing it with a candidate's skill."""
    issues = set(problems)
    if "HTTP 401" in issues:
        return "GitHub rejected the configured API token. Ask the server administrator to update GITHUB_TOKEN and try again."
    if RATE_LIMITED in issues:
        return "GitHub API rate limit reached. Wait for the limit to reset, or ask the server administrator to configure GITHUB_TOKEN."
    if "HTTP 403" in issues:
        return "GitHub denied API access. Ask the server administrator to check GITHUB_TOKEN permissions and try again."
    if "HTTP 404" in issues:
        return "GitHub could not find the profile or repository, or it is private. Check the username or repository URL and use a public repository."
    if "network error" in issues or any(p.startswith("HTTP 5") for p in issues):
        return "GitHub is unavailable or cannot be reached from the server. Check the connection and try again later."
    if "disabled" in issues:
        return "GitHub API access is disabled on this server. Enter public repository URLs directly, or ask the administrator to enable it."
    return "GitHub returned an unexpected response. Some checks could not finish. Try again later."


class GitHubClient:
    """
    Minimal read-only GitHub REST client for signals that git history alone can't provide:
    fork status, the repo's listed homepage / deployments, and merged pull requests.
    Every method returns None when the API is unavailable, so missing data is never fabricated.
    Set GITHUB_TOKEN to raise the rate limit; set SKILL_PASSPORT_GITHUB_API=0 to disable.
    """

    # Shared by every client in the process: without a token GitHub allows 60 requests an hour per
    # address, so answers are reused for a while and no calls are made until a hit limit resets.
    _cache: Dict[Tuple[str, str, str], Tuple[float, Any]] = {}
    _limited_until: Dict[str, float] = {}
    _lock = threading.Lock()

    def __init__(self, token: Optional[str] = None, timeout: float = 8.0, enabled: Optional[bool] = None):
        self.token = token if token is not None else os.getenv("GITHUB_TOKEN")
        self.timeout = timeout
        self.enabled = enabled if enabled is not None else os.getenv("SKILL_PASSPORT_GITHUB_API", "1") != "0"

    def _get(self, path: str, params: Optional[Dict] = None, problems: Optional[List[str]] = None):
        """GET a REST path. Failures return None and, if `problems` is given, append why."""
        if not self.enabled:
            return None
        # A response fetched using a valid token must not mask a different, invalid token.
        auth = hashlib.sha256(self.token.encode()).hexdigest() if self.token else "anonymous"
        key = (auth, path, repr(sorted((params or {}).items())))
        now = time.time()
        with GitHubClient._lock:
            cached = GitHubClient._cache.get(key)
            if cached and now - cached[0] < CACHE_TTL_S:
                return cached[1]
            if GitHubClient._limited_until.get(auth, 0) > now:
                if problems is not None:
                    problems.append(RATE_LIMITED)
                return None
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            res = httpx.get(f"https://api.github.com{path}", headers=headers, params=params, timeout=self.timeout)
            if res.status_code != 200:
                logger.info("GitHub API %s returned %s", path, res.status_code)
                limited = res.status_code == 429 or res.status_code == 403 and (
                    res.headers.get("x-ratelimit-remaining") == "0" or "rate limit" in res.text.lower()
                )
                if limited:
                    try:
                        reset_at = float(res.headers.get("x-ratelimit-reset", "0"))
                    except ValueError:
                        reset_at = 0.0
                    with GitHubClient._lock:
                        GitHubClient._limited_until[auth] = max(reset_at, now + 60)
                if problems is not None:
                    problems.append(RATE_LIMITED if limited else f"HTTP {res.status_code}")
                return None
            data = res.json()
            with GitHubClient._lock:
                if len(GitHubClient._cache) >= MAX_CACHE_ENTRIES:
                    GitHubClient._cache.clear()
                GitHubClient._cache[key] = (now, data)
            return data
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
