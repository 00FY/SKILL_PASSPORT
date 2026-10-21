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
    res = client.post("/api/analyze", json={"candidate_name": "Some One", "github_username": "someone"})
    assert res.status_code == 503
    detail = res.json()["detail"]
    assert "Couldn't list @someone's repositories" in detail
    assert "Paste the repository URLs" in detail and "GITHUB_TOKEN" in detail
