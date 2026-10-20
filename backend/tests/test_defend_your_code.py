"""
Tests for Defend Your Code: picking the candidate's own functions, building questions in the sandbox,
the single-attempt test flow, and how a result changes the signed passport.
"""
import os
import subprocess
import tempfile

import pytest
from fastapi.testclient import TestClient

from app.main import app, defend, harvester
from app.module2_harvester import GitHubClient
from app.module2_harvester.function_picker import functions_from_source, pick_functions
from app.module2_harvester.git_crawler import GitBlameAnalyzer
from app.module3_rubric import CryptoSigner
from app.module3_rubric import defend_your_code as dyc
from app.module3_rubric.defend_your_code import DefendYourCode, adjust_points, outcome_for

client = TestClient(app)
harvester.github = GitHubClient(enabled=False)

OWN_FILE = '''
LIMITS = {"free": 3, "pro": 10}


def quota_left(plan: str, used: int) -> int:
    """Remaining requests for a plan."""
    limit = LIMITS.get(plan, 0)
    if used < 0:
        used = 0
    left = limit - used
    if left < 0:
        return 0
    return left


def initials(name: str) -> str:
    """First letter of each word, upper-cased."""
    parts = []
    for word in name.split():
        if word:
            parts.append(word[0].upper())
    if not parts:
        return "?"
    return "".join(parts)


def summarize(order: dict) -> str:
    """One-line description of an order."""
    qty = order.get("quantity", 0)
    item = order["item"]
    if qty == 1:
        return f"1 x {item}"
    if qty > 1:
        return f"{qty} x {item}s"
    return f"no {item}"
'''

TEAMMATE_FILE = '''
def teammate_logic(values: list[int]) -> int:
    """Written by someone else."""
    best = 0
    for v in values:
        if v > best:
            best = v
    if best > 100:
        best = 100
    return best
'''


def _commit(repo, files, author, email):
    for rel, content in files.items():
        path = os.path.join(repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
    env = {**os.environ, "GIT_AUTHOR_NAME": author, "GIT_AUTHOR_EMAIL": email,
           "GIT_COMMITTER_NAME": author, "GIT_COMMITTER_EMAIL": email}
    subprocess.run(["git", "-C", repo, "add", "-A"], check=True, env=env)
    subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "work"], check=True, env=env)


@pytest.fixture
def mixed_repo():
    repo = tempfile.mkdtemp(prefix="sp_defend_")
    subprocess.run(["git", "init", "-q", repo], check=True)
    _commit(repo, {"app/own.py": OWN_FILE.lstrip("\n")}, "Dev One", "dev@example.com")
    _commit(repo, {"app/team.py": TEAMMATE_FILE.lstrip("\n"),
                   "tests/test_own.py": "def test_x():\n    assert True\n"}, "Other Person", "other@example.com")
    return repo


def _functions(source=OWN_FILE):
    return functions_from_source(source.lstrip("\n"), "app/own.py", None, "https://github.com/dev/app", "a" * 40)


# --- Picking functions ----------------------------------------------------------------------------

def test_only_functions_the_candidate_wrote_are_picked(mixed_repo):
    res = GitBlameAnalyzer().analyze_repo(mixed_repo, identities=["dev@example.com"])
    assert len(res["head_sha"]) == 40
    picked = pick_functions(mixed_repo, res["per_file"], "repo", res["head_sha"])
    names = {f["name"] for f in picked}
    assert names == {"quota_left", "initials", "summarize"}
    assert all(f["commit"] == res["head_sha"] for f in picked)


def test_harvest_keeps_functions_server_side(mixed_repo):
    doc = harvester.harvest_repo(mixed_repo, identities=["dev@example.com"], allow_local=True)
    assert {f["name"] for f in doc.authored_functions} == {"quota_left", "initials", "summarize"}
    assert "authored_functions" not in doc.model_dump()


def test_constants_and_dict_keys_travel_with_a_function():
    fns = {f["name"]: f for f in _functions()}
    assert fns["quota_left"]["context"] == ["LIMITS = {'free': 3, 'pro': 10}"]
    assert fns["quota_left"]["free_names"] == []
    assert "free" in fns["quota_left"]["literals"]["str"]
    assert fns["summarize"]["params"][0]["dict_keys"] == ["quantity", "item"]


def test_short_trivial_and_test_functions_are_skipped():
    short = "def f(x):\n    return x\n"
    no_logic = "def g(x):\n" + "".join(f"    x = x + {i}\n" for i in range(9)) + "    return x\n"
    assert functions_from_source(short, "a.py", None, "r", "c") == []
    assert functions_from_source(no_logic, "a.py", None, "r", "c") == []


# --- Building questions ---------------------------------------------------------------------------

def test_questions_have_one_correct_option_matching_the_real_output():
    questions, reason = DefendYourCode().build_questions(_functions(), seed="pp_seed")
    assert reason == "" and len(questions) == 3
    namespace = {}
    exec(OWN_FILE, namespace)  # trusted test code: recompute each answer directly
    for q in questions:
        assert len(q["options"]) == 4 and len(set(q["options"])) == 4
        expected = repr(eval(q["call"], namespace))
        assert q["options"][q["answer_index"]] == expected


def test_questions_are_deterministic_per_seed():
    a, _ = DefendYourCode().build_questions(_functions(), seed="pp_same")
    b, _ = DefendYourCode().build_questions(_functions(), seed="pp_same")
    assert [(q["call"], q["options"]) for q in a] == [(q["call"], q["options"]) for q in b]


def test_too_few_runnable_functions_gives_a_reason():
    uses_import = "import json\n\n\ndef dump(x):\n    out = []\n    for i in x:\n        if i:\n            out.append(json.dumps(i))\n    out.sort()\n    out.reverse()\n    return out\n"
    questions, reason = DefendYourCode().build_questions(
        functions_from_source(uses_import, "a.py", None, "r", "c"), seed="s")
    assert questions == []
    assert "can't run on their own" in reason


# --- Scoring rules --------------------------------------------------------------------------------

@pytest.mark.parametrize("correct,total,status", [(5, 5, "confirmed"), (4, 5, "confirmed"), (3, 5, "inconclusive"),
                                                  (2, 5, "inconclusive"), (1, 5, "not_explained"), (0, 3, "not_explained")])
def test_outcome_thresholds(correct, total, status):
    assert outcome_for(correct, total) == status


def test_point_adjustments():
    assert adjust_points(70, "confirmed") == 75
    assert adjust_points(98, "confirmed") == 100
    assert adjust_points(70, "not_explained") == 28
    assert adjust_points(70, "inconclusive") == 70
    assert adjust_points(70, None) == 70


# --- The test flow through the API ----------------------------------------------------------------

def _take(passport, pick_correct, extended=False):
    start = client.post("/api/defend/start", json={"passport": passport, "extended_time": extended})
    assert start.status_code == 200, start.text
    data = start.json()
    sid, q = data["session_id"], data["question"]
    assert "answer_index" not in q
    pool = next(p for k, (_, p) in defend._pools.items() if k[0] == (passport.get("passport_id")))
    answers = {x["question_id"]: x["answer_index"] for x in pool}
    while True:
        right = answers[q["question_id"]]
        choice = right if pick_correct(q) else (right + 1) % 4
        r = client.post("/api/defend/answer", json={"session_id": sid, "question_id": q["question_id"], "choice": choice})
        assert r.status_code == 200
        body = r.json()
        if body["done"]:
            return body["result"]
        q = body["question"]


def _python(passport):
    return next(s for s in passport["skills"] if s["name"] == "Python")


def test_demo_passport_offers_the_check_and_stays_signed():
    p = client.get("/api/demo/priya").json()
    check = _python(p)["authorship_check"]
    assert check["status"] == "available" and check["question_count"] >= 3
    assert check["commits"] == ["https://github.com/priya/api-service@4f2c9a1"]
    assert client.post("/api/verify-signature", json=p).json()["valid"]


def test_contradicted_python_gets_no_check():
    p = client.get("/api/demo/alex").json()
    assert _python(p)["authorship_check"] is None


def test_confirmed_adds_bonus_and_is_single_attempt():
    p = client.get("/api/demo/jordan").json()
    before = _python(p)["final_points"]
    result = _take(p, lambda q: True)
    assert result["status"] == "confirmed" and result["correct"] == result["total"]
    assert all(r["correct"] for r in result["review"])

    updated = client.post("/api/defend/apply", json={"passport": p, "attempt_id": result["attempt_id"]})
    assert updated.status_code == 200
    up = updated.json()
    py = _python(up)
    assert py["final_points"] == min(100, before + 5)
    assert py["authorship_check"]["status"] == "confirmed"
    assert py["authorship_check"]["points_effect"] == py["final_points"] - before
    assert any("Authorship confirmed" in s for s in py["signals"])
    assert up["audit_log"]["traces"][-1]["step"] == "AUTHORSHIP_CHECK_COMPLETED"
    assert client.post("/api/verify-signature", json=up).json()["valid"]

    # One attempt per passport: neither the old nor the updated passport can start again
    assert client.post("/api/defend/start", json={"passport": p}).status_code == 409
    assert client.post("/api/defend/start", json={"passport": up}).status_code == 409
    assert client.post("/api/defend/apply", json={"passport": p, "attempt_id": result["attempt_id"]}).status_code == 400


def test_not_explained_reduces_points_and_survives_a_later_quiz():
    from app.main import quiz_attempts
    p = client.get("/api/demo/priya").json()
    before = _python(p)["final_points"]
    result = _take(p, lambda q: False)
    assert result["status"] == "not_explained"
    up = client.post("/api/defend/apply", json={"passport": p, "attempt_id": result["attempt_id"]}).json()
    py = _python(up)
    assert py["final_points"] == round(before * 0.4)
    assert any("Could not explain own code" in s for s in py["signals"])

    # A later quiz recomputes the skill's points with the authorship effect still applied
    attempt = quiz_attempts.record("Python", "A", 100.0, passport_key=up["passport_id"])
    after_quiz = client.post("/api/quiz/apply", json={"passport": up, "attempt_id": attempt}).json()
    py = _python(after_quiz)
    assert py["final_points"] == round(min(100, py["evidence_score"] * 10 + py["consistency_bonus"]) * 0.4)


def test_answers_must_follow_the_served_order():
    p = client.get("/api/demo/jordan").json()
    data = client.post("/api/defend/start", json={"passport": p}).json()
    bad = client.post("/api/defend/answer", json={"session_id": data["session_id"], "question_id": "q_other", "choice": 0})
    assert bad.status_code == 400
    bad = client.post("/api/defend/answer", json={"session_id": "../../etc", "question_id": "x", "choice": 0})
    assert bad.status_code == 400


def test_late_answers_count_as_wrong(monkeypatch):
    p = client.get("/api/demo/jordan").json()
    data = client.post("/api/defend/start", json={"passport": p}).json()
    pool = next(pl for k, (_, pl) in defend._pools.items() if k[0] == p["passport_id"])
    q = data["question"]
    right = next(x["answer_index"] for x in pool if x["question_id"] == q["question_id"])
    real_time = dyc.time.time
    monkeypatch.setattr(dyc.time, "time", lambda: real_time() + dyc.TIME_LIMIT_S + dyc.GRACE_S + 1)
    r = client.post("/api/defend/answer", json={"session_id": data["session_id"], "question_id": q["question_id"], "choice": right})
    assert r.status_code == 200
    session = defend._sessions[data["session_id"]]
    assert session.answers[0]["timed_out"] is True and session.answers[0]["correct"] is False


def test_extended_time_is_offered_and_recorded():
    p = client.get("/api/demo/jordan").json()
    start = client.post("/api/defend/start", json={"passport": p, "extended_time": True}).json()
    assert start["time_limit_s"] == dyc.EXTENDED_TIME_LIMIT_S


def test_attempt_cannot_be_applied_to_another_passport():
    p1 = client.get("/api/demo/jordan").json()
    p2 = client.get("/api/demo/jordan").json()
    result = _take(p1, lambda q: True)
    res = client.post("/api/defend/apply", json={"passport": p2, "attempt_id": result["attempt_id"]})
    assert res.status_code == 400
    assert "different passport" in res.json()["detail"]


def test_edited_passport_is_refused():
    p = client.get("/api/demo/jordan").json()
    p["overall_score"] = 99
    assert client.post("/api/defend/start", json={"passport": p}).status_code == 400
