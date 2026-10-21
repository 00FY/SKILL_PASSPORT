"""
Defend Your Code: an optional check that the candidate understands code `git blame` says they wrote.

At analysis time, functions the candidate owns (see module2_harvester/function_picker.py) are run in the
sandbox on generated inputs. Each one that returns a value becomes a multiple-choice question: "what does
this call return?", with wrong options taken from the same function's outputs on other inputs and from
small mutations of the right answer. Questions are kept on the server; the candidate gets one attempt per
passport, one question at a time, with a time limit per question.

Outcome (applied to that skill's code points, never to the quiz pillar):
- at least CONFIRM_PCT correct: +BONUS_POINTS (capped at 100) and "Authorship confirmed"
- below FAIL_PCT correct: points x FAIL_FACTOR and "Could not explain own code"
- anything in between, or not taken: no change
"""
import copy
import json
import os
import random
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .sandbox import CodeSandbox
from .sandbox_runner import SAFE_BUILTIN_NAMES

QUESTION_COUNT = 5
MAX_PREDICT = 2
KIND_PREDICT = "predict"
KIND_HIDDEN_LINE = "hidden_line"
KIND_NAME = "name"
# Standard-library modules a "what does this return?" function may import inside the sandbox.
# Set SKILL_PASSPORT_DEFEND_STDLIB=0 to allow none (then only self-contained functions are run).
STDLIB_MODULES = {
    "math", "json", "re", "datetime", "collections", "itertools", "functools", "string", "statistics",
    "decimal", "fractions", "operator", "heapq", "bisect", "copy", "textwrap", "unicodedata", "typing",
    "calendar", "base64", "hashlib",
}
MIN_QUESTIONS = int(os.getenv("SKILL_PASSPORT_DEFEND_MIN_QUESTIONS", "3"))
MAX_FUNCTIONS_TRIED = 12
TIME_LIMIT_S = 90
EXTENDED_TIME_LIMIT_S = 180
GRACE_S = 5
CONFIRM_PCT = 80
FAIL_PCT = 40
BONUS_POINTS = 5
FAIL_FACTOR = 0.4
MAX_RENDER_CHARS = 120
MAX_CALL_CHARS = 220
POOL_TTL_S = 24 * 3600
ID_RE = re.compile(r"^dyc_[0-9a-f]{32}$")

STATUS_AVAILABLE = "available"
STATUS_UNAVAILABLE = "unavailable"
STATUS_CONFIRMED = "confirmed"
STATUS_INCONCLUSIVE = "inconclusive"
STATUS_NOT_EXPLAINED = "not_explained"

# --- Input generation ---------------------------------------------------------------------------

VALUES = {
    "int": [3, 7, 0, 12, 5, 2],
    "float": [2.5, 10.0, 0.5, 3.75],
    "str": ["hello world", "Skill Passport", "a,b,c", "racecar", "Data Science 101", ""],
    "bool": [True, False],
    "list_int": [[3, 1, 2], [5, 8, 5, 1], [10], [4, -1, 7, 2], []],
    "list_float": [[1.5, 2.0, 3.5], [10.0, 0.5], []],
    "list_str": [["apple", "banana", "cherry"], ["b", "a", "b"], ["hello"], []],
    "list_dict": [
        [{"id": 1, "name": "alpha", "value": 10}, {"id": 2, "name": "beta", "value": 4}],
        [{"id": 3, "name": "gamma", "value": 7}],
        [],
    ],
    "list_list": [[[1, 2], [3, 4]], [[1, 3], [2, 6], [8, 10]], []],
    "dict": [{"a": 1, "b": 2}, {"x": 10}, {}],
}
NAME_HINTS = [
    ("bool", r"^(is_|has_|should_|use_|enable|allow)|^(flag|verbose|reverse|strict|debug|force|active|enabled)$"),
    ("list_list", r"^(matrix|grid|intervals|pairs|board|rows_of)$"),
    ("list_dict", r"^(records|rows|entries|users|items_list|objects|facilities|events|logs)$"),
    ("list_str", r"^(words|names|tags|labels|lines|tokens|strings|keys|columns|fields)$"),
    ("list_int", r"^(nums|numbers|arr|array|lst|values|scores|xs|seq|items|elements|data|prices|counts_list|ids)$"),
    ("dict", r"^(d|mapping|config|counts|record|row|obj|params|options|settings|payload|meta|facility|item)$"),
    ("float", r"^(ratio|rate|percent|pct|price|weight|score|lat|lng|lon|latitude|longitude|temperature)$"),
    ("int", r"^(n|num|count|k|i|j|size|limit|x|y|age|year|index|idx|start|end|amount|total|width|height|"
            r"length|depth|level|step|steps|times|offset|top|base|port|id|minutes|seconds|days|hours)$|_(count|id|size|n)$"),
    ("str", r"^(s|text|string|name|word|path|url|key|prefix|suffix|sep|char|line|sentence|msg|message|title|"
            r"query|email|username|filename|label|code|slug|status|value_str|date_str|phone|type|kind|category|"
            r"country|city|state|region|mode|role|description|note)$|_(name|str|text|path|url|type|category)$"),
]


def _kind_for(name: str, annotation: str = "", default: Any = None, has_default: bool = False) -> Optional[str]:
    if has_default and default is not None:
        for kind, sample in (("bool", True), ("int", 1), ("float", 1.0), ("str", "")):
            if type(default) is type(sample):
                return kind
        if isinstance(default, (list, tuple)):
            return "list_str" if default and isinstance(default[0], str) else "list_int"
        if isinstance(default, dict):
            return "dict"
    a = annotation.lower().replace("typing.", "").replace(" ", "")
    a = re.sub(r"\|none$|^none\|", "", a)
    if a.startswith("optional[") and a.endswith("]"):
        a = a[len("optional["):-1]
    if a:
        head = a.split("[", 1)[0]
        inner = a[len(head) + 1:] if "[" in a else ""
        if head in ("list", "sequence", "iterable", "tuple", "set", "frozenset", "collection"):
            if inner.startswith("str"):
                return "list_str"
            if inner.startswith(("dict", "mapping")):
                return "list_dict"
            if inner.startswith(("list", "tuple")):
                return "list_list"
            if inner.startswith("float"):
                return "list_float"
            return "list_int"
        if head in ("dict", "mapping"):
            return "dict"
        if head in ("bool", "int", "float", "str"):
            return head
        return "unsupported"
    lowered = name.lower()
    for kind, pattern in NAME_HINTS:
        if re.search(pattern, lowered):
            return kind
    return None


def _dict_from_keys(keys: List[str], variant: int) -> Dict[str, Any]:
    out = {}
    for j, key in enumerate(keys):
        # Keys with no recognisable name alternate between text and numbers across variants
        kind = _kind_for(key) or ("float" if variant % 2 else "str")
        if kind.startswith("list") or kind in ("dict", "unsupported"):
            kind = "str"
        pool = [v for v in VALUES[kind] if v != ""] or VALUES[kind]
        out[key] = pool[(variant + j) % len(pool)]
    return out


def _param_values(param: Dict[str, Any], literals: Dict[str, List[Any]]) -> Optional[List[Any]]:
    if param.get("dict_keys"):
        return [_dict_from_keys(param["dict_keys"], v) for v in range(4)]
    kind = _kind_for(param["name"], param.get("annotation", ""), param.get("default"), "default" in param)
    if kind == "unsupported":
        return None
    if kind is None:
        return [3, "hello world", [3, 1, 2], {"a": 1}]
    # Values the code itself mentions come first: they reach the interesting branches
    mined = literals.get(kind, [])
    if kind == "list_str" and literals.get("str"):
        words = literals["str"]
        mined = [[words[i % len(words)] for i in range(k, k + 3)] for k in range(min(3, len(words)))]
    values = list(mined) + [v for v in VALUES[kind] if v not in mined]
    if "default" in param and param["default"] not in values:
        values.insert(0, param["default"])
    return values


def _arg_sets(params: List[Dict[str, Any]], literals: Optional[Dict[str, List[Any]]] = None,
              limit: int = 10) -> Optional[List[List[Any]]]:
    per_param = []
    for p in params:
        values = _param_values(p, literals or {})
        if values is None:
            return None
        per_param.append(values)
    sets, seen = [], set()
    for v in range(limit * 2):
        args = [copy.deepcopy(vals[(v + j * (v // len(vals) + 1)) % len(vals)]) for j, vals in enumerate(per_param)]
        key = json.dumps(args, sort_keys=True)
        if key not in seen:
            seen.add(key)
            sets.append(args)
        if len(sets) >= limit:
            break
    return sets


# --- Wrong answers ------------------------------------------------------------------------------

def _mutations(value: Any) -> List[Any]:
    if isinstance(value, bool):
        return [not value]
    if isinstance(value, int):
        return [value + 1, value - 1, value * 2, -value, 0]
    if isinstance(value, float):
        return [round(value + 1, 2), round(value * 2, 2), round(value / 2, 2), int(value)]
    if isinstance(value, str):
        return [value.upper(), value.title(), value + "s", value[:-1], value.replace("-", "_"), ""]
    if isinstance(value, list):
        out = [list(reversed(value)), value[:-1], value + value[-1:], []]
        try:
            out.append(sorted(value, reverse=True))
        except TypeError:
            pass
        return out
    if isinstance(value, dict):
        keys = list(value)
        return [{k: value[k] for k in keys[:-1]}, {k: value[k] for k in keys[1:]}, {}]
    if value is None:
        return [0, "", []]
    return []


def render(value: Any) -> str:
    return repr(value)


def _best_outcomes(outcomes: List[tuple], literals: Dict[str, List[Any]]) -> List[tuple]:
    """Prefer calls that use values from the code itself and whose result isn't just an input echoed back."""
    mined = {render(v) for vals in literals.values() for v in vals}

    def echoes(o):
        return render(o[1]) in {render(a) for a in o[0]}

    def uses_literal(o):
        text = render(o[0])
        return any(m in text for m in mined)

    def trivial(o):
        return o[1] in (0, False, 1) and not isinstance(o[1], float)

    for tier in (
        [o for o in outcomes if uses_literal(o) and not echoes(o) and not trivial(o)],
        [o for o in outcomes if not echoes(o) and not trivial(o)],
        [o for o in outcomes if not echoes(o)],
    ):
        if tier:
            return tier
    return outcomes


def _safe_get(get, value) -> bool:
    try:
        get(value)
        return True
    except (KeyError, TypeError, IndexError):
        return False


def _projection(answer: Any, others: List[Any]):
    """('{call}[key]' or 'len({call})', getter) for a result too long to show as an option."""
    if isinstance(answer, dict):
        best = None
        for key, val in answer.items():
            if not isinstance(key, str) or isinstance(val, (dict, list)) or len(render(val)) > 40:
                continue
            variety = len({render(o.get(key)) for o in others if isinstance(o, dict)})
            if best is None or variety > best[1]:
                best = (key, variety)
        if best:
            key = best[0]
            return "{call}[" + render(key).replace("{", "{{").replace("}", "}}") + "]", (lambda v, k=key: v[k])
    if isinstance(answer, (list, str)):
        return "len({call})", len
    return None


# --- Pools, sessions, attempts ------------------------------------------------------------------

@dataclass
class DefendSession:
    session_id: str
    passport_key: str
    skill: str
    questions: List[Dict[str, Any]]
    time_limit_s: int
    extended_time: bool
    index: int = 0
    served_at: float = field(default_factory=time.time)
    answers: List[Dict[str, Any]] = field(default_factory=list)
    pastes: int = 0
    tab_switches: int = 0
    completed: bool = False


@dataclass
class DefendAttempt:
    passport_key: str
    skill: str
    correct: int
    total: int
    status: str
    commits: List[str]
    functions: List[str]
    extended_time: bool
    pastes: int
    tab_switches: int
    created_at: float = field(default_factory=time.time)


class DefendYourCode:
    def __init__(self, sandbox: Optional[CodeSandbox] = None):
        self.sandbox = sandbox or CodeSandbox()
        self._pools: Dict[Tuple[str, str], Tuple[float, List[Dict[str, Any]]]] = {}
        self._started: set = set()
        self._sessions: Dict[str, DefendSession] = {}
        self._attempts: Dict[str, DefendAttempt] = {}
        self._lock = threading.Lock()

    # Building questions -------------------------------------------------------------------------

    def build_questions(self, functions: List[Dict[str, Any]], seed: str) -> Tuple[List[Dict[str, Any]], str]:
        """
        Questions for one language's functions. Returns (questions, reason when there are too few).
        Up to MAX_PREDICT "what does this return?" questions (Python code that runs on its own), then
        "which line is hidden?" and "which function is this?" questions, each from a different function.
        """
        language = functions[0]["language"] if functions else ""
        if not functions:
            return [], "No functions of at least 8 lines that you wrote were found."
        rng = random.Random(f"{seed}:{language}")
        # The same function copied into two folders or repos is one function
        unique: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for f in functions:
            unique.setdefault((f["name"], os.path.basename(f["path"].replace("\\", "/"))), f)
        ordered = _spread_by_file(list(unique.values()), rng)

        questions: List[Dict[str, Any]] = []
        used: set = set()

        runnable = [f for f in ordered if _runnable(f)][:MAX_FUNCTIONS_TRIED]
        for fn in runnable:
            if sum(1 for q in questions if q["kind"] == KIND_PREDICT) >= MAX_PREDICT:
                break
            q = self._predict_question(fn, seed)
            if q:
                questions.append(q)
                used.add(_fn_id(fn))

        builders = [_hidden_line_question, _name_question]
        turn = 0
        for fn in ordered:
            if len(questions) >= QUESTION_COUNT:
                break
            if _fn_id(fn) in used:
                continue
            for k in range(len(builders)):
                q = builders[(turn + k) % len(builders)](fn, ordered, rng)
                if q:
                    questions.append(q)
                    used.add(_fn_id(fn))
                    turn += 1
                    break

        if len(questions) < MIN_QUESTIONS:
            return [], (f"Only {len(questions)} question{'s' if len(questions) != 1 else ''} could be made from "
                        f"your {language} functions; at least {MIN_QUESTIONS} are needed for a fair test.")
        rng.shuffle(questions)
        return questions[:QUESTION_COUNT], ""

    def _predict_question(self, fn: Dict[str, Any], seed: str) -> Optional[Dict[str, Any]]:
        arg_sets = _arg_sets(fn["params"], fn.get("literals"))
        if not arg_sets:
            return None
        run = self.sandbox.run(fn["exec_source"], fn["name"], arg_sets, allowed_modules=_allowed_modules())
        if run.definition_error:
            return None
        outcomes = []
        for args, entry in zip(arg_sets, run.results):
            if entry.get("kind") != "json":
                continue
            ok, value = CodeSandbox.decode(entry)
            call = f"{fn['name']}({', '.join(render(a) for a in args)})"
            if ok and len(call) <= MAX_CALL_CHARS:
                outcomes.append((args, value, call))
        interesting = [o for o in outcomes if o[1] not in (None, "", [], {})]
        if not interesting:
            return None
        rng = random.Random(f"{seed}:{fn['repo_url']}:{fn['path']}:{fn['name']}")
        args, answer, call = rng.choice(_best_outcomes(interesting, fn.get("literals") or {}))

        if len(render(answer)) > MAX_RENDER_CHARS:
            # Too long to be an option: ask about one field (or the length) of the result instead
            project = _projection(answer, [o[1] for o in outcomes])
            if project is None:
                return None
            suffix, get = project
            call = suffix.format(call=call)
            answer = get(answer)
            outcomes = [(a, get(v), c) for a, v, c in outcomes if _safe_get(get, v)]
        outcomes = [o for o in outcomes if len(render(o[1])) <= MAX_RENDER_CHARS]

        correct = render(answer)
        # Real outputs of the same function make the best wrong answers; invented ones only fill gaps
        real, invented = [], []
        for bucket, values in ((real, [o[1] for o in outcomes]), (invented, _mutations(answer))):
            for candidate in values:
                text = render(candidate)
                if text != correct and text not in real and text not in invented and len(text) <= MAX_RENDER_CHARS:
                    bucket.append(text)
        rng.shuffle(real)
        wrong = (real + invented)[:3]
        if len(wrong) < 3:
            wrong.append("It raises an exception")
        if len(wrong) < 3:
            return None
        return _question(fn, KIND_PREDICT, "What does this call return?", fn["source"], [correct] + wrong, rng,
                         call=call, context=fn.get("context", []))

    # Pools ---------------------------------------------------------------------------------------

    def register(self, passport_key: str, skill: str, questions: List[Dict[str, Any]]) -> None:
        with self._lock:
            self._purge()
            self._pools[(passport_key, skill.lower())] = (time.time(), [dict(q) for q in questions])

    def has_pool(self, passport_key: str, skill: str) -> bool:
        with self._lock:
            self._purge()
            return (passport_key, skill.lower()) in self._pools

    def _purge(self) -> None:
        cutoff = time.time() - POOL_TTL_S
        for key in [k for k, (t, _) in self._pools.items() if t < cutoff]:
            del self._pools[key]
        for key in [k for k, s in self._sessions.items() if s.served_at < cutoff]:
            del self._sessions[key]
        for key in [k for k, a in self._attempts.items() if a.created_at < cutoff]:
            del self._attempts[key]

    # Taking the test -----------------------------------------------------------------------------

    def start(self, passport_key: str, skill: str, extended_time: bool = False) -> Dict[str, Any]:
        key = (passport_key, skill.lower())
        with self._lock:
            self._purge()
            if key not in self._pools:
                raise LookupError("Defend Your Code isn't available for this skill on this passport. "
                                  "Re-run the analysis if the server restarted.")
            if key in self._started:
                raise PermissionError("Defend Your Code can be taken once per passport, and it was already started.")
            self._started.add(key)
            session = DefendSession(
                session_id=f"dyc_{secrets.token_hex(16)}",
                passport_key=passport_key,
                skill=skill,
                questions=self._pools[key][1],
                time_limit_s=EXTENDED_TIME_LIMIT_S if extended_time else TIME_LIMIT_S,
                extended_time=extended_time,
            )
            self._sessions[session.session_id] = session
        return {
            "session_id": session.session_id,
            "total": len(session.questions),
            "time_limit_s": session.time_limit_s,
            "question": self._public(session.questions[0], 1),
        }

    def answer(self, session_id: str, question_id: str, choice: Optional[int],
               pastes: int = 0, tab_switches: int = 0) -> Dict[str, Any]:
        with self._lock:
            session = self._sessions.get(session_id) if ID_RE.match(session_id or "") else None
            if not session or session.completed:
                raise ValueError("Unknown or finished Defend Your Code session.")
            q = session.questions[session.index]
            if question_id != q["question_id"]:
                raise ValueError("This is not the current question.")
            elapsed = time.time() - session.served_at
            timed_out = elapsed > session.time_limit_s + GRACE_S
            correct = (not timed_out) and choice is not None and choice == q["answer_index"]
            # Browser-reported signals: recorded in the audit trail, never used to fail anyone
            session.pastes += max(0, min(int(pastes or 0), 1000))
            session.tab_switches += max(0, min(int(tab_switches or 0), 1000))
            session.answers.append({
                "question_id": q["question_id"],
                "choice": choice,
                "correct": correct,
                "timed_out": timed_out,
                "seconds": round(elapsed, 1),
            })
            session.index += 1
            if session.index < len(session.questions):
                session.served_at = time.time()
                return {"done": False, "question": self._public(session.questions[session.index], session.index + 1)}

            session.completed = True
            n_correct = sum(1 for a in session.answers if a["correct"])
            total = len(session.questions)
            status = outcome_for(n_correct, total)
            attempt_id = secrets.token_urlsafe(16)
            self._attempts[attempt_id] = DefendAttempt(
                passport_key=session.passport_key,
                skill=session.skill,
                correct=n_correct,
                total=total,
                status=status,
                commits=sorted({f"{x['repo_url']}@{x['commit'][:7]}" for x in session.questions if x.get("commit")}),
                functions=[f"{x['path']}:{x['function']}" for x in session.questions],
                extended_time=session.extended_time,
                pastes=session.pastes,
                tab_switches=session.tab_switches,
            )
            review = []
            for x, a in zip(session.questions, session.answers):
                review.append({
                    "path": x["path"],
                    "function": x["function"],
                    "kind": x.get("kind", KIND_PREDICT),
                    "prompt": x.get("prompt", ""),
                    "call": x.get("call", ""),
                    "your_answer": x["options"][a["choice"]] if isinstance(a["choice"], int) and 0 <= a["choice"] < len(x["options"]) else None,
                    "correct_answer": x["options"][x["answer_index"]],
                    "correct": a["correct"],
                    "timed_out": a["timed_out"],
                })
            return {
                "done": True,
                "result": {
                    "attempt_id": attempt_id,
                    "correct": n_correct,
                    "total": total,
                    "status": status,
                    "review": review,
                },
            }

    def consume_attempt(self, attempt_id: str) -> Optional[DefendAttempt]:
        with self._lock:
            return self._attempts.pop(attempt_id, None)

    def peek_attempt(self, attempt_id: str) -> Optional[DefendAttempt]:
        with self._lock:
            return self._attempts.get(attempt_id)

    @staticmethod
    def _public(q: Dict[str, Any], number: int) -> Dict[str, Any]:
        public = {k: v for k, v in q.items() if k != "answer_index"}
        public["number"] = number
        return public


# --- Question helpers ---------------------------------------------------------------------------

def _allowed_modules() -> List[str]:
    return sorted(STDLIB_MODULES) if os.getenv("SKILL_PASSPORT_DEFEND_STDLIB", "1") != "0" else []


def _runnable(fn: Dict[str, Any]) -> bool:
    return (
        bool(fn.get("runnable_candidate")) and fn.get("language") == "Python"
        and set(fn.get("free_names", [])) <= set(SAFE_BUILTIN_NAMES)
        and set(fn.get("import_roots", [])) <= set(_allowed_modules())
    )


def _fn_id(fn: Dict[str, Any]) -> str:
    return f"{fn['repo_url']}::{fn['path']}::{fn['name']}::{fn['line']}"


def _spread_by_file(functions: List[Dict[str, Any]], rng: random.Random) -> List[Dict[str, Any]]:
    """Round-robin across files so one big file doesn't supply every question."""
    by_file: Dict[str, List[Dict[str, Any]]] = {}
    for f in functions:
        by_file.setdefault(f"{f['repo_url']}::{f['path']}", []).append(f)
    keys = sorted(by_file)
    rng.shuffle(keys)
    ordered: List[Dict[str, Any]] = []
    while any(by_file[k] for k in keys):
        for k in keys:
            if by_file[k]:
                ordered.append(by_file[k].pop(0))
    return ordered


def _question(fn, kind, prompt, code, options, rng, call="", context=None, extra=None) -> Dict[str, Any]:
    correct = options[0]
    options = list(options)
    rng.shuffle(options)
    q = {
        "question_id": f"q_{secrets.token_hex(6)}",
        "kind": kind,
        "prompt": prompt,
        "language": fn.get("language", ""),
        "repo_url": fn["repo_url"],
        "commit": fn.get("commit", ""),
        "path": fn["path"],
        "line": fn["line"],
        "function": fn["name"],
        "code": code,
        "context": context or [],
        "call": call,
        "options": options,
        "answer_index": options.index(correct),
    }
    q.update(extra or {})
    return q


def _comment(language: str) -> str:
    return "#" if language == "Python" else "//"


# "Which line is hidden?": one meaningful line is replaced; the options are near-misses of it
CMP_RE = re.compile(r"(?<=\s)(===|!==|==|!=|<=|>=|<|>)(?=\s)")
CMP_SWAPS = {"<": ["<=", ">"], "<=": ["<", ">="], ">": [">=", "<"], ">=": [">", "<="], "==": ["!="], "!=": ["=="],
             "===": ["!=="], "!==": ["==="]}
ARITH_RE = re.compile(r"(?<=\s)([+\-*/])(?=\s)")
ARITH_SWAPS = {"+": "-", "-": "+", "*": "/", "/": "*"}
AUG_RE = re.compile(r"(\+=|-=|\*=)")
NUM_RE = re.compile(r"(?<![\w.])(\d+)(?![\w.])")
WORD_SWAPS = [(r"\band\b", "or"), (r"\bor\b", "and"), (r"&&", "||"), (r"\|\|", "&&"), (r"\bTrue\b", "False"),
              (r"\bFalse\b", "True"), (r"\btrue\b", "false"), (r"\bfalse\b", "true"), (r"\bmin\(", "max("),
              (r"\bmax\(", "min("), (r"\bany\(", "all("), (r"\ball\(", "any("), (r"\.append\(", ".extend("),
              (r"\.push\(", ".unshift("), (r"\.lower\(", ".upper("), (r"\.upper\(", ".lower("),
              (r"\.startswith\(", ".endswith("), (r"\.endswith\(", ".startswith("), (r"\.keys\(", ".values("),
              (r"\.values\(", ".keys("), (r"\.strip\(", ".split("), (r"\.filter\(", ".map("), (r"\.map\(", ".filter("),
              (r"\bnot\s+", ""), (r"!(?=[A-Za-z_(])", ""), (r"\bbreak\b", "continue"), (r"\bcontinue\b", "break")]
SKIP_LINE_RE = re.compile(r"^(\}|\{|\)|\]|else\s*:?|try\s*:?|finally\s*:?|pass|break;?|continue;?|return;?|"
                          r"return None|default:|\};?|\);?|\}\)?;?|else\s*\{|\}\s*else\s*\{)$")
NESTED_HEADER_RE = re.compile(r"\b(def|fun|function|func|fn)\s+\w+\s*\(")
IDENT_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
COMMON_WORDS = {"if", "else", "elif", "for", "while", "in", "not", "and", "or", "return", "def", "class", "None",
                "True", "False", "const", "let", "var", "function", "new", "this", "self", "null", "true", "false",
                "is", "of", "await", "async", "import", "from", "with", "as", "try", "except", "catch", "finally",
                "int", "str", "len", "range", "print", "string", "number", "boolean", "void", "public", "private",
                "static", "final", "return", "throw", "raise", "lambda", "yield", "func", "fn", "fun", "val",
                "export", "default", "override", "protected", "internal", "abstract", "interface", "type", "enum",
                "extends", "implements", "super", "typeof", "instanceof", "delete", "void", "undefined", "nil",
                "pub", "mut", "impl", "struct", "match", "when", "object", "companion", "package", "require",
                "module", "exports", "echo", "global", "nonlocal", "del", "pass", "assert", "with", "elif"}
STRING_RE = re.compile(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`")


def _mutate_line(line: str, fn_source: str, fn_name: str = "") -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    # Text inside string literals is never changed: a wrong option should differ in logic, not wording
    in_string = set()
    for m in STRING_RE.finditer(line):
        in_string.update(range(m.start(), m.end()))

    def add(kind, text):
        if text.strip() != line.strip() and text.strip() and (kind, text) not in out:
            out.append((kind, text))

    def code_matches(regex):
        return [m for m in regex.finditer(line) if m.start() not in in_string]

    for m in code_matches(CMP_RE):
        for alt in CMP_SWAPS[m.group(1)]:
            add("compare", line[:m.start()] + alt + line[m.end():])
    for m in code_matches(ARITH_RE):
        add("arith", line[:m.start()] + ARITH_SWAPS[m.group(1)] + line[m.end():])
    for m in code_matches(AUG_RE):
        alt = {"+=": "-=", "-=": "+=", "*=": "+="}[m.group(1)]
        add("arith", line[:m.start()] + alt + line[m.end():])
    for m in code_matches(NUM_RE):
        n = int(m.group(1))
        for alt in ([n + 1, n - 1] if n > 0 else [n + 1]):
            add("number", line[:m.start()] + str(alt) + line[m.end():])
    for pattern, alt in WORD_SWAPS:
        m = next(iter(code_matches(re.compile(pattern))), None)
        if m:
            add("word", line[:m.start()] + alt + line[m.end():])
    # Swap one variable for another variable the same function uses (lower-case names, used more than once)
    source_code = STRING_RE.sub('""', fn_source)
    counts: Dict[str, int] = {}
    for w in IDENT_RE.findall(source_code):
        counts[w] = counts.get(w, 0) + 1
    members = set(re.findall(r"(?:\.|\?\.|::|->)\s*([A-Za-z_]\w*)", source_code))  # attributes and methods
    variables = [w for w, c in counts.items()
                 if c >= 2 and len(w) > 1 and w not in COMMON_WORDS and w not in members and w != fn_name
                 and (w[0].islower() or w[0] == "_")]
    line_vars = [m for m in IDENT_RE.finditer(line) if m.start() not in in_string and m.group(0) in variables]
    seen = {m.group(0) for m in line_vars}
    others = [w for w in variables if w not in seen]
    for m in line_vars[:3]:
        prev = line[m.start() - 1] if m.start() > 0 else ""
        if prev == ".":
            continue  # an attribute or method name, not a variable
        for alt in others[:2]:
            add("name", line[:m.start()] + alt + line[m.end():])
    return out


def _hidden_line_question(fn: Dict[str, Any], pool: List[Dict[str, Any]], rng: random.Random):
    lines = fn["source"].split("\n")
    first_body = fn.get("header_lines", 1)
    last = len(lines) - (0 if fn.get("language") == "Python" else 1)
    skip = set(fn.get("doc_lines", []))
    choices = []
    for idx in range(first_body, last):
        stripped = lines[idx].strip()
        if idx in skip or not 12 <= len(stripped) <= 110 or SKIP_LINE_RE.match(stripped):
            continue
        if stripped.startswith(("#", "//", "/*", "*", "@", "import ", "from ", "print(", "console.", "logger.", "log.")):
            continue
        if NESTED_HEADER_RE.search(stripped):
            continue  # a nested function's signature says little about understanding
        mutations = _mutate_line(stripped, fn["source"], fn["name"])
        if len({t for _, t in mutations}) >= 3:
            # Lines with comparisons or arithmetic test understanding best
            weight = 2 if any(k in ("compare", "arith") for k, _ in mutations) else 1
            choices += [(idx, mutations)] * weight
    if not choices:
        return None
    idx, mutations = rng.choice(choices)
    original = lines[idx].strip()
    # One wrong option per kind of change first, so the options differ in different ways
    by_kind: Dict[str, List[str]] = {}
    for kind, text in mutations:
        by_kind.setdefault(kind, []).append(text.strip())
    kinds = list(by_kind)
    rng.shuffle(kinds)
    wrong: List[str] = []
    while len(wrong) < 3 and any(by_kind.values()):
        for kind in kinds:
            if by_kind[kind] and len(wrong) < 3:
                candidate = by_kind[kind].pop(rng.randrange(len(by_kind[kind])))
                if candidate not in wrong and candidate != original:
                    wrong.append(candidate)
    if len(wrong) < 3:
        return None
    indent = lines[idx][:len(lines[idx]) - len(lines[idx].lstrip())]
    shown = lines[:idx] + [f"{indent}{_comment(fn.get('language', ''))} ??? (hidden line)"] + lines[idx + 1:]
    return _question(fn, KIND_HIDDEN_LINE, "Which line was hidden from this function?", "\n".join(shown),
                     [original] + wrong, rng, extra={"hidden_line": idx})


def _name_question(fn: Dict[str, Any], pool: List[Dict[str, Any]], rng: random.Random):
    """"Which of your functions is this?": the body with its name hidden, and four of the candidate's names."""
    name = fn["name"]
    others = [f["name"] for f in pool if f["name"].lower() != name.lower() and len(f["name"]) > 2]
    same_repo = [f["name"] for f in pool if f["repo_url"] == fn["repo_url"] and f["name"] in others]
    candidates = list(dict.fromkeys(same_repo + others))
    if len(name) <= 2 or len(candidates) < 3:
        return None
    wrong = rng.sample(candidates[:12], 3)
    skip = set(fn.get("doc_lines", []))
    shown = []
    for idx, line in enumerate(fn["source"].split("\n")):
        stripped = line.strip()
        if idx in skip or stripped.startswith(("#", "//", "/*", "* ", "*/")) or stripped == "*":
            continue  # Docstrings and comments would give the name away
        shown.append(re.sub(rf"\b{re.escape(name)}\b", "???", line))
    return _question(fn, KIND_NAME, "Which of your functions is this? (its name is hidden)", "\n".join(shown),
                     [name] + wrong, rng)


def outcome_for(correct: int, total: int) -> str:
    pct = 100.0 * correct / max(1, total)
    if pct >= CONFIRM_PCT:
        return STATUS_CONFIRMED
    if pct < FAIL_PCT:
        return STATUS_NOT_EXPLAINED
    return STATUS_INCONCLUSIVE


def adjust_points(base_points: int, status: Optional[str]) -> int:
    if status == STATUS_CONFIRMED:
        return min(100, base_points + BONUS_POINTS)
    if status == STATUS_NOT_EXPLAINED:
        return int(round(base_points * FAIL_FACTOR))
    return base_points
