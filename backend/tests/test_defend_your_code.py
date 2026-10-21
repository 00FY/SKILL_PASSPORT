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

def test_questions_have_one_correct_option_matching_the_real_code():
    questions, reason = DefendYourCode().build_questions(_functions(), seed="pp_seed")
    assert reason == "" and len(questions) == 3
    namespace = {}
    exec(OWN_FILE, namespace)  # trusted test code: recompute each answer directly
    source_lines = OWN_FILE.lstrip("\n").split("\n")
    kinds = set()
    for q in questions:
        kinds.add(q["kind"])
        assert len(q["options"]) == 4 and len(set(q["options"])) == 4
        answer = q["options"][q["answer_index"]]
        if q["kind"] == "predict":
            assert answer == repr(eval(q["call"], namespace))
        elif q["kind"] == "hidden_line":
            assert "??? (hidden line)" in q["code"] and answer not in q["code"]
            assert source_lines[q["line"] - 1 + q["hidden_line"]].strip() == answer
        else:
            assert answer == q["function"] and q["function"] not in q["code"]
    assert "predict" in kinds


def test_questions_are_deterministic_per_seed():
    a, _ = DefendYourCode().build_questions(_functions(), seed="pp_same")
    b, _ = DefendYourCode().build_questions(_functions(), seed="pp_same")
    assert [(q["call"], q["options"]) for q in a] == [(q["call"], q["options"]) for q in b]


def test_too_few_functions_gives_a_reason():
    one_function = "def dump(x):\n    out = []\n    for i in x:\n        if i:\n            out.append(i * 2)\n    out.sort()\n    out.reverse()\n    return out\n"
    questions, reason = DefendYourCode().build_questions(
        functions_from_source(one_function, "a.py", None, "r", "c"), seed="s")
    assert questions == []
    assert "Only 1 question could be made from your Python functions" in reason
    _, reason = DefendYourCode().build_questions([], seed="s")
    assert "No functions" in reason


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


# --- Any language, any code ------------------------------------------------------------------------

JS_FILE = '''
import { api } from './api';

export function totalPrice(items, discount) {
  let total = 0;
  for (const item of items) {
    if (item.qty > 0) {
      total += item.price * item.qty;
    }
  }
  const off = discount > 50 ? 50 : discount;
  return total * (100 - off) / 100;
}

export const loadUser = async (id) => {
  const res = await api.get(`/users/${id}`);
  if (res.status !== 200) {
    throw new Error('User not found');
  }
  const user = res.data;
  user.fullName = user.first + ' ' + user.last;
  return user;
};

class Cart {
  removeItem(items, sku) {
    const kept = [];
    for (const item of items) {
      if (item.sku !== sku) {
        kept.push(item);
      }
    }
    return kept;
  }
}
'''

KOTLIN_FILE = '''
class Overlay : Service() {
    override fun onStart(intent: Intent?, flags: Int): Int {
        val upiId = intent?.getStringExtra("upiId") ?: "Unknown"
        if (overlayView == null) {
            showOverlay(upiId)
        } else {
            updateOverlay(upiId)
        }
        val retries = flags + 1
        log("started $upiId")
        return START_STICKY
    }
}
'''


def test_brace_languages_and_methods_are_found():
    js = functions_from_source(JS_FILE.lstrip("\n"), "src/cart.js", None, "r", "c")
    assert {f["name"] for f in js} == {"totalPrice", "loadUser", "removeItem"}
    assert all(f["language"] == "JavaScript" and not f["runnable_candidate"] for f in js)
    kt = functions_from_source(KOTLIN_FILE.lstrip("\n"), "app/Overlay.kt", None, "r", "c")
    assert [f["name"] for f in kt] == ["onStart"]  # the class line isn't mistaken for a function


def test_static_questions_work_without_running_code():
    fns = functions_from_source(JS_FILE.lstrip("\n"), "src/cart.js", None, "https://github.com/dev/shop", "c" * 40)
    questions, reason = DefendYourCode().build_questions(fns, seed="js")
    assert reason == "" and len(questions) == 3
    assert {q["kind"] for q in questions} <= {"hidden_line", "name"}
    for q in questions:
        answer = q["options"][q["answer_index"]]
        if q["kind"] == "hidden_line":
            assert answer in JS_FILE and "// ??? (hidden line)" in q["code"]
            for wrong in q["options"]:
                # Wrong options change logic, never the text inside string literals
                assert ("'User not found'" in wrong) == ("'User not found'" in answer)


def test_hidden_line_options_are_near_misses_of_the_real_line():
    from app.module3_rubric.defend_your_code import _mutate_line
    line = "if (item.qty > 0 && item.price <= limit) {"
    kinds = {k for k, _ in _mutate_line(line, "item item limit limit qty", "fn")}
    assert {"compare", "number", "word"} <= kinds
    texts = [t for _, t in _mutate_line("const msg = 'a > b and c';", "msg msg", "fn")]
    assert all("'a > b and c'" in t for t in texts)


def test_name_question_hides_the_name_and_comments():
    from app.module3_rubric.defend_your_code import _name_question
    import random
    fns = functions_from_source(OWN_FILE.lstrip("\n"), "app/own.py", None, "r", "c")
    pool = fns + [dict(fns[0], name="load_settings"), dict(fns[0], name="render_page")]
    q = _name_question(next(f for f in fns if f["name"] == "initials"), pool, random.Random(1))
    assert "initials" not in q["code"] and "First letter" not in q["code"] and "def ???(" in q["code"]
    assert q["options"][q["answer_index"]] == "initials"


def test_stdlib_imports_can_run_but_other_modules_cannot():
    uses_stdlib = (
        "import json\nimport math\n\n\n"
        "def summary(values: list[int]) -> str:\n"
        "    clean = []\n"
        "    for v in values:\n"
        "        if v >= 0:\n"
        "            clean.append(v)\n"
        "    top = max(clean) if clean else 0\n"
        "    top = top * top\n"
        "    return json.dumps({'n': len(clean), 'root': math.isqrt(top)})\n"
    )
    uses_os = uses_stdlib.replace("import json\n", "import os\nimport json\n").replace("json.dumps(", "os.getcwd() + json.dumps(")
    fn = functions_from_source(uses_stdlib, "a.py", None, "r", "c")[0]
    assert fn["import_roots"] == ["json", "math"] and dyc._runnable(fn)
    q = DefendYourCode()._predict_question(fn, "seed")
    assert q is not None and q["options"][q["answer_index"]].startswith("'{\"n\":")
    blocked = functions_from_source(uses_os, "a.py", None, "r", "c")[0]
    assert not dyc._runnable(blocked)


def test_copies_of_the_same_function_count_once():
    fns = _functions()
    copies = [dict(f, repo_url="https://github.com/dev/app-copy") for f in fns]
    questions, _ = DefendYourCode().build_questions(fns + copies, seed="dup")
    assert len({q["function"] for q in questions}) == len(questions)


def test_every_language_skill_gets_its_own_check(tmp_path):
    from app.main import _attach_defend
    from app.schemas import PassportDocument, SkillPassportItem, VerdictEnum
    js = functions_from_source(JS_FILE.lstrip("\n"), "src/cart.js", None, "r", "c")
    py = _functions()
    passport = PassportDocument(
        candidate_name="Dev", applied_role="Engineer", role_match_pct=50, overall_score=50,
        skills=[
            SkillPassportItem(name="JavaScript", verdict=VerdictEnum.VERIFIED, evidence_score=7, test_grade="B", final_points=56),
            SkillPassportItem(name="Python", verdict=VerdictEnum.PARTIALLY_SUPPORTED, evidence_score=7, test_grade="B", final_points=56),
            SkillPassportItem(name="Go", verdict=VerdictEnum.VERIFIED, evidence_score=7, test_grade="B", final_points=56),
            SkillPassportItem(name="React", verdict=VerdictEnum.VERIFIED, evidence_score=7, test_grade="B", final_points=56),
        ],
        refusal_panel=[], learning_plan=[], security_alerts=[], tamper_proof_hash="", issued_at="2026-01-01",
        passport_id="pp_multi_language",
    )
    passport = _attach_defend(passport, functions=js + py)
    checks = {s.name: s.authorship_check for s in passport.skills}
    assert checks["JavaScript"].status == "available"
    assert checks["Python"].status == "available"
    assert checks["Go"].status == "unavailable" and "No Go functions" in checks["Go"].reason
    assert checks["React"] is None  # frameworks are covered through their language
    assert CryptoSigner.verify_passport_signature(passport.model_dump(mode="json"), passport.tamper_proof_hash)["valid"]
