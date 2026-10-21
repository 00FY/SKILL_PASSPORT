import re
import logging
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from .github_api import GitHubClient, github_problem_message
from .harvester_service import MAX_REPOS

logger = logging.getLogger(__name__)

USERNAME_CLEAN_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/([a-zA-Z0-9\-]{1,39})(?:/.*)?$",
    re.IGNORECASE
)
PLAIN_USERNAME_RE = re.compile(r"^[a-zA-Z0-9\-]{1,39}$")


def extract_github_username(input_str: str) -> Optional[str]:
    raw = (input_str or "").strip().rstrip("/")
    if not raw:
        return None
    m = USERNAME_CLEAN_RE.match(raw)
    if m:
        return m.group(1)
    if PLAIN_USERNAME_RE.match(raw):
        return raw
    return None


class RepoMetaItem(BaseModel):
    name: str
    html_url: str
    description: Optional[str] = None
    language: Optional[str] = None
    topics: List[str] = Field(default_factory=list)
    stars: int = 0
    pushed_at: Optional[str] = None


class DiscoveredProfile(BaseModel):
    username: str
    name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    public_repos_count: int = 0
    repo_urls: List[str] = Field(default_factory=list)
    repos: List[RepoMetaItem] = Field(default_factory=list)
    detected_languages: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ProfileScanner:
    def __init__(self, github_client: Optional[GitHubClient] = None):
        self.github = github_client or GitHubClient()

    def scan_profile(self, username_or_url: str, max_repos: int = MAX_REPOS) -> DiscoveredProfile:
        username = extract_github_username(username_or_url)
        if not username:
            raise ValueError(f"Invalid GitHub username or profile URL: '{username_or_url}'")

        problems: List[str] = []
        user_info = self.github.user_profile(username, problems=problems)
        repos_raw = self.github.user_repos(username, limit=max_repos, problems=problems)

        warnings: List[str] = []
        if not self.github.enabled:
            problems.append("disabled")
        if problems:
            warnings.append(github_problem_message(problems))
        elif not repos_raw:
            warnings.append(
                f"No public, non-fork repositories were found for @{username}. "
                "Check the username, make a repository public, or enter a public repository URL directly."
            )

        repos_meta: List[RepoMetaItem] = []
        repo_urls: List[str] = []
        languages: List[str] = []
        topics: List[str] = []

        for r in repos_raw:
            url = r.get("html_url")
            if url:
                repo_urls.append(url)
            lang = r.get("language")
            if lang and lang not in languages:
                languages.append(lang)
            for top in r.get("topics") or []:
                if top not in topics:
                    topics.append(top)
            repos_meta.append(RepoMetaItem(
                name=r.get("name") or "unknown",
                html_url=url or "",
                description=r.get("description"),
                language=lang,
                topics=r.get("topics") or [],
                stars=r.get("stargazers_count", 0),
                pushed_at=r.get("pushed_at"),
            ))

        return DiscoveredProfile(
            username=username,
            name=(user_info or {}).get("name") or username,
            bio=(user_info or {}).get("bio"),
            avatar_url=(user_info or {}).get("avatar_url"),
            public_repos_count=(user_info or {}).get("public_repos", len(repos_raw)),
            repo_urls=repo_urls,
            repos=repos_meta,
            detected_languages=languages,
            topics=topics,
            warnings=warnings,
        )
