"""GitHub API use without a token: answers are reused, a hit limit stops further calls, and a profile
that can't be listed fails the analysis with a clear message instead of an empty passport."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.module2_harvester import github_api
from app.module2_harvester.github_api import GitHubClient, RATE_LIMITED

client = TestClient(app)


class FakeResponse:
    def __init__(self, status, data=None, headers=None, text=""):
        self.status_code = status
        self._data = data
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._data


@pytest.fixture(autouse=True)
def fresh_state():
    GitHubClient._cache.clear()
    GitHubClient._limited_until.clear()
    yield
    GitHubClient._cache.clear()
    GitHubClient._limited_until.clear()


def test_successful_answers_are_reused(monkeypatch):
    calls = []
    monkeypatch.setattr(github_api.httpx, "get", lambda url, **kw: calls.append(url) or FakeResponse(200, {"login": "dev"}))
    gh = GitHubClient(token="", enabled=True)
    assert gh.user_profile("dev")["login"] == "dev"
    assert GitHubClient(token="", enabled=True).user_profile("dev")["login"] == "dev"
    assert len(calls) == 1


def test_a_hit_limit_stops_further_calls_until_reset(monkeypatch):
    calls = []
    limited = FakeResponse(403, headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "9999999999"},
                           text="API rate limit exceeded")
    monkeypatch.setattr(github_api.httpx, "get", lambda url, **kw: calls.append(url) or limited)
    gh = GitHubClient(token="", enabled=True)
    problems = []
    assert gh.user_profile("dev", problems=problems) is None
    assert gh.user_repos("dev", problems=problems) == []
    assert gh.repo_meta("dev", "app", problems=problems) is None
    assert len(calls) == 1
    assert problems.count(RATE_LIMITED) == 3


def test_token_and_anonymous_limits_are_tracked_separately(monkeypatch):
    def fake(url, headers=None, **kw):
        if "Authorization" in (headers or {}):
            return FakeResponse(200, {"login": "dev"})
        return FakeResponse(403, headers={"x-ratelimit-remaining": "0"}, text="rate limit")
    monkeypatch.setattr(github_api.httpx, "get", fake)
    assert GitHubClient(token="", enabled=True).user_profile("dev") is None
    assert GitHubClient(token="ghp_example", enabled=True).user_profile("dev")["login"] == "dev"


def test_username_only_analysis_fails_clearly_when_repos_cant_be_listed(monkeypatch):
    limited = FakeResponse(403, headers={"x-ratelimit-remaining": "0"}, text="rate limit")
    monkeypatch.setattr(github_api.httpx, "get", lambda url, **kw: limited)
    monkeypatch.setenv("SKILL_PASSPORT_GITHUB_API", "1")
    res = client.post("/api/analyze", json={"github_username": "someone"})
    assert res.status_code == 503
    detail = res.json()["detail"]
    assert "Couldn't list @someone's repositories" in detail
    assert "Paste the repository URLs" in detail and "GITHUB_TOKEN" in detail


@pytest.mark.parametrize("status, expected", [
    (401, "rejected the configured API token"),
    (403, "denied API access"),
    (404, "private"),
    (500, "unavailable"),
    (502, "unavailable"),
    (503, "unavailable"),
    (429, "rate limit"),
])
def test_discovery_explains_github_failures(monkeypatch, status, expected):
    response = FakeResponse(status)
    monkeypatch.setattr(github_api.httpx, "get", lambda *a, **kw: response)
    monkeypatch.setenv("SKILL_PASSPORT_GITHUB_API", "1")
    res = client.post("/api/discover-repos", json={"username": "dev"})
    assert res.status_code == 200
    assert res.json()["repo_urls"] == []
    assert expected in " ".join(res.json()["warnings"])


def test_discovery_explains_network_outage(monkeypatch):
    def offline(*a, **kw):
        raise github_api.httpx.ConnectError("Connection failed")
    monkeypatch.setattr(github_api.httpx, "get", offline)
    monkeypatch.setenv("SKILL_PASSPORT_GITHUB_API", "1")
    result = client.post("/api/discover-repos", json={"username": "dev"}).json()
    assert "cannot be reached" in result["warnings"][0]
    assert result["repo_urls"] == []


def test_discovery_warns_when_no_public_repositories_exist(monkeypatch):
    monkeypatch.setattr(github_api.httpx, "get", lambda url, **kw: FakeResponse(
        200, [] if url.endswith("/repos") else {"login": "dev", "public_repos": 0}
    ))
    monkeypatch.setenv("SKILL_PASSPORT_GITHUB_API", "1")
    result = client.post("/api/discover-repos", json={"username": "dev"}).json()
    assert "No public, non-fork repositories" in result["warnings"][0]


def test_cached_valid_token_cannot_hide_invalid_token(monkeypatch):
    def fake(url, headers=None, **kw):
        return (FakeResponse(200, {"login": "dev"})
                if headers.get("Authorization") == "Bearer valid-token"
                else FakeResponse(401))
    monkeypatch.setattr(github_api.httpx, "get", fake)
    assert GitHubClient(token="valid-token", enabled=True).user_profile("dev")
    problems = []
    assert GitHubClient(token="bad-token", enabled=True).user_profile("dev", problems) is None
    assert problems == ["HTTP 401"]


def test_profile_warning_survives_successful_direct_repo_analysis(monkeypatch):
    import app.main as main
    from app.schemas import EvidenceDocument, QualitySignals

    monkeypatch.setattr(github_api.httpx, "get", lambda *a, **kw: FakeResponse(401))
    monkeypatch.setenv("SKILL_PASSPORT_GITHUB_API", "1")
    monkeypatch.setattr(main.harvester, "harvest_many", lambda *a, **kw: EvidenceDocument(
        repo_url="https://github.com/dev/app",
        signals=QualitySignals(commit_count=3),
    ))
    passport = main._run_analysis(main.AnalyzeRequest(
        github_username="dev", repo_urls=["https://github.com/dev/app"], resume_text="Dev Engineer\nPython"
    ))
    assert any("rejected the configured API token" in warning for warning in passport.warnings)


@pytest.mark.parametrize("stderr, expected", [
    ("remote: Repository not found.", "doesn't exist or is private"),
    ("fatal: could not read Username: terminal prompts disabled", "doesn't exist or is private"),
    ("fatal: unable to access https://github.com/dev/app: error 503", "unavailable"),
    ("fatal: Could not resolve host: github.com", "cannot be reached"),
])
def test_clone_failure_has_actionable_error(monkeypatch, tmp_path, stderr, expected):
    from types import SimpleNamespace
    from app.module2_harvester import repo_source

    monkeypatch.setattr(repo_source.shutil, "disk_usage", lambda _: SimpleNamespace(free=10**12))
    monkeypatch.setattr(repo_source.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1, stderr=stderr))
    with pytest.raises(repo_source.RepoAccessError, match=expected):
        repo_source.clone_repo(repo_source.parse_repo_source("https://github.com/dev/app"), str(tmp_path))
