import os
import re
import json
import ast
import secrets
import threading
from typing import Dict, Any, List, Optional
from ..schemas import (
    StageType, DifficultyTier, PublicTaskItem,
    TaskSubmissionRequest, StepEvaluationResult
)
from .question_bank import ADAPTIVE_QUESTION_BANK, get_adaptive_tasks_for_skill, generate_generic_adaptive_tasks
from ..module1_extractor.injection_guard import PromptInjectionDefense
from .sandbox import CodeSandbox, SandboxUnavailable
from ..skills import normalize_skill

BANNED_AST_NAMES = {
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "open", "eval", "exec", "__import__",
    "compile", "input", "breakpoint", "help", "globals", "locals", "vars"
}
BANNED_ATTRIBUTES = {"__subclasses__", "__globals__", "__code__", "__builtins__"}
STAGE_SEQUENCE = [StageType.COMPREHENSION, StageType.DEBUGGING, StageType.CODING, StageType.REASONING]
DIFFICULTY_WEIGHTS = {1: 1.0, 2: 1.5, 3: 2.2}
# Session ids are generated here and only ever used in this exact shape, including as file names
SESSION_ID_RE = re.compile(r"^asmt_[0-9a-f]{32}$")
MAX_ATTEMPTS_PER_SKILL = int(os.getenv("SKILL_PASSPORT_ASSESSMENT_ATTEMPTS", "2"))


class AttemptLimitReached(ValueError):
    pass


class AdaptiveAssessmentEngine:
    """
    Stateful adaptive assessment engine managing staircase difficulty transitions,
    AST-sandboxed test execution, and deterministic rubric evaluations.
    """

    def __init__(self, storage_dir: Optional[str] = None, sandbox: Optional[CodeSandbox] = None):
        self.storage_dir = storage_dir
        self.sandbox = sandbox or CodeSandbox()
        self.max_attempts = MAX_ATTEMPTS_PER_SKILL
        # (passport key, skill) -> sessions started; in memory, like the quiz attempt store
        self._attempts: Dict[tuple, int] = {}
        self._lock = threading.Lock()
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.injection_guard = PromptInjectionDefense()

    def _get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        if not isinstance(session_id, str) or not SESSION_ID_RE.match(session_id):
            return None
        if session_id in self.sessions:
            return self.sessions[session_id]
        if self.storage_dir:
            path = os.path.join(self.storage_dir, f"{session_id}.json")
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data["seen_task_ids"] = set(data.get("seen_task_ids", []))
                    if isinstance(data.get("current_difficulty"), int):
                        data["current_difficulty"] = DifficultyTier(data["current_difficulty"])
                    self.sessions[session_id] = data
                    return data
                except Exception:
                    return None
        return None

    def _save_session(self, session_id: str) -> None:
        if not self.storage_dir or not SESSION_ID_RE.match(session_id):
            return
        session = self.sessions.get(session_id)
        if not session:
            return
        try:
            os.makedirs(self.storage_dir, exist_ok=True)
            path = os.path.join(self.storage_dir, f"{session_id}.json")
            dumpable = dict(session)
            dumpable["seen_task_ids"] = list(session["seen_task_ids"])
            curr_diff = session.get("current_difficulty")
            dumpable["current_difficulty"] = curr_diff.value if isinstance(curr_diff, DifficultyTier) else curr_diff
            with open(path, "w", encoding="utf-8") as f:
                json.dump(dumpable, f)
        except Exception:
            pass

    def start_session(
        self,
        skill: str,
        passport_hash: str = "",
        initial_verdict: Optional[str] = None
    ) -> Dict[str, Any]:
        if passport_hash:
            key = (passport_hash, normalize_skill(skill).lower())
            with self._lock:
                used = self._attempts.get(key, 0)
                if used >= self.max_attempts:
                    raise AttemptLimitReached(
                        f"The {skill} assessment can be taken {self.max_attempts} times per passport; "
                        "all attempts are used."
                    )
                self._attempts[key] = used + 1
        session_id = f"asmt_{secrets.token_hex(16)}"

        # Repo-Seeded Starting Difficulty
        if initial_verdict == "CLAIMED_ONLY":
            start_diff = DifficultyTier.FOUNDATIONAL
        elif initial_verdict in ("VERIFIED", "PARTIALLY_SUPPORTED"):
            start_diff = DifficultyTier.INTERMEDIATE
        else:
            start_diff = DifficultyTier.INTERMEDIATE

        first_task = self._select_task(skill, StageType.COMPREHENSION, start_diff, set())
        self.sessions[session_id] = {
            "session_id": session_id,
            "skill": skill,
            "passport_hash": passport_hash,
            "initial_verdict": initial_verdict,
            "current_stage_idx": 0,
            "current_difficulty": start_diff,
            "seen_task_ids": {first_task["task_id"]},
            "current_task_id": first_task["task_id"],
            "history": [],
            "completed": False,
        }
        self._save_session(session_id)
        return {"session_id": session_id, "task": self._to_public(first_task)}

    def submit_step(self, req: TaskSubmissionRequest) -> StepEvaluationResult:
        with self._lock:
            session = self._get_session(req.session_id)
            if not session or session["completed"]:
                raise ValueError("Invalid or already completed assessment session.")
            # Only the task this session served last can be answered, and only once
            if not session.get("current_task_id") or req.task_id != session["current_task_id"]:
                raise ValueError("This task is not the current step of the assessment.")
            session["current_task_id"] = None
        try:
            return self._grade_step(session, req)
        except Exception:
            # Nothing was recorded (e.g. the code runner was busy), so the same step can be submitted again
            session["current_task_id"] = req.task_id
            raise

    def _grade_step(self, session: Dict[str, Any], req: TaskSubmissionRequest) -> StepEvaluationResult:
        task = self._get_task_by_id(session["skill"], req.task_id)
        stage_type = StageType(task["stage_type"])

        # 1. Grade current task deterministically
        if stage_type == StageType.COMPREHENSION:
            passed = (req.selected_option is not None and req.selected_option == task.get("correct_option"))
            step_score = 1.0 if passed else 0.0
            feedback = task.get("explanation", "Evaluated comprehension choice.")
            test_results, rubric_hits = [], []

        elif stage_type in (StageType.DEBUGGING, StageType.CODING):
            step_score, test_results, feedback = self._evaluate_code_safely(
                req.submitted_code or "",
                task.get("entry_function", ""),
                task.get("hidden_tests", [])
            )
            passed = step_score >= 0.75
            rubric_hits = []

        elif stage_type == StageType.REASONING:
            step_score, rubric_hits, feedback = self._evaluate_reasoning_rubric(
                req.reasoning_text or "",
                task.get("required_concepts", [])
            )
            passed = step_score >= 0.75
            test_results = []
        else:
            passed = False
            step_score = 0.0
            feedback = "Unknown stage type."
            test_results, rubric_hits = [], []

        # 2. Record weighted step performance
        diff = DifficultyTier(task["difficulty"])
        session["history"].append({
            "task_id": task["task_id"],
            "stage": stage_type.value,
            "difficulty": diff.value,
            "raw_score": step_score,
            "weighted_points": step_score * DIFFICULTY_WEIGHTS[diff.value],
            "max_weighted_points": DIFFICULTY_WEIGHTS[diff.value],
        })

        # Calculate live trajectory string
        trajectory = "->".join(
            f"T{h['difficulty']}({'Pass' if h['raw_score'] >= 0.75 else 'Fail'})"
            for h in session["history"]
        )

        # 3. Adapt difficulty for next stage
        if step_score >= 0.75:
            next_diff = DifficultyTier(min(3, diff.value + 1))
        elif step_score < 0.50:
            next_diff = DifficultyTier(max(1, diff.value - 1))
        else:
            next_diff = diff

        session["current_difficulty"] = next_diff
        session["current_stage_idx"] += 1

        # 4. Check completion or select next stage
        if session["current_stage_idx"] >= len(STAGE_SEQUENCE):
            session["completed"] = True
            final_score, final_grade = self._compute_final_grade(session["history"])
            session["final_score"] = final_score
            session["final_grade"] = final_grade
            session["trajectory"] = trajectory
            self._save_session(req.session_id)
            return StepEvaluationResult(
                task_id=task["task_id"],
                passed=passed,
                step_score=step_score,
                difficulty_attempted=diff,
                next_difficulty=None,
                feedback=feedback,
                test_results=test_results,
                rubric_hits=rubric_hits,
                is_complete=True,
                final_grade=final_grade,
                final_weighted_score=final_score,
                trajectory=trajectory,
            )

        next_stage = STAGE_SEQUENCE[session["current_stage_idx"]]
        next_task = self._select_task(
            session["skill"], next_stage, next_diff, session["seen_task_ids"]
        )
        session["seen_task_ids"].add(next_task["task_id"])
        session["current_task_id"] = next_task["task_id"]
        self._save_session(req.session_id)

        return StepEvaluationResult(
            task_id=task["task_id"],
            passed=passed,
            step_score=step_score,
            difficulty_attempted=diff,
            next_difficulty=next_diff,
            feedback=feedback,
            test_results=test_results,
            rubric_hits=rubric_hits,
            is_complete=False,
            next_task=self._to_public(next_task),
            trajectory=trajectory,
        )


    def _evaluate_code_safely(self, code: str, fn_name: str, tests: List[Dict]):
        # Static AST Security Gate before execution
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return 0.0, [], f"SyntaxError on line {e.lineno}: {e.msg}"

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                return 0.0, [], "Security policy: Import statements are blocked in assessment functions."
            if isinstance(node, ast.Name) and node.id in BANNED_AST_NAMES:
                return 0.0, [], f"Security policy: Restricted identifier '{node.id}' detected."
            if isinstance(node, ast.Attribute) and node.attr in BANNED_ATTRIBUTES:
                return 0.0, [], f"Security policy: Restricted attribute '{node.attr}' detected."

        # Candidate code only ever runs in a separate sandboxed process (see sandbox.py).
        # The checks above are an early, readable rejection, not the security boundary.
        # SandboxUnavailable propagates so the step is not recorded and can be resubmitted
        run = self.sandbox.run(code, fn_name, [list(t.get("args", [])) for t in tests])
        if run.definition_error:
            return 0.0, [], run.definition_error

        results = []
        passed_count = 0
        for idx, (t, entry) in enumerate(zip(tests, run.results), 1):
            kind = entry.get("kind")
            if kind == "error":
                results.append({"test_case": idx, "passed": False, "error": entry.get("error", "Unknown error")})
                continue
            ok_value, actual = CodeSandbox.decode(entry)
            # A value that could not be sent back as JSON (e.g. a set) is shown but never matches
            ok = ok_value and kind == "json" and actual == t.get("expected")
            if ok:
                passed_count += 1
            # Hidden tests stay hidden: the candidate sees pass/fail, not the expected values
            results.append({"test_case": idx, "passed": ok})

        score = round(passed_count / len(tests), 2) if tests else 0.0
        return score, results, f"Passed {passed_count}/{len(tests)} automated test cases."

    def _evaluate_reasoning_rubric(self, text: str, concepts: List[Dict]):
        # Run existing injection guard first
        sanitized, flags = self.injection_guard.sanitize(text)
        if flags:
            return 0.0, [], "Security Alert: Prompt injection pattern detected in reasoning response."

        lowered = sanitized.lower()
        hits = []
        for concept in concepts:
            if any(kw.lower() in lowered for kw in concept.get("keywords", [])):
                hits.append(concept["name"])

        word_count_ok = len(sanitized.split()) >= 12
        if not concepts:
            score = 1.0 if word_count_ok else 0.5
        else:
            score = (len(hits) / len(concepts)) * (1.0 if word_count_ok else 0.5)

        score = round(score, 2)
        feedback = f"Matched {len(hits)}/{len(concepts)} core engineering concepts: {', '.join(hits) or 'None'}."
        if not word_count_ok:
            feedback += " (Penalty: response under 12 words)"
        return score, hits, feedback

    def _compute_final_grade(self, history: List[Dict]):
        earned = sum(h["weighted_points"] for h in history)
        possible = sum(h["max_weighted_points"] for h in history)
        pct = round((earned / possible) * 100, 1) if possible else 0.0
        max_tier_passed = max((h["difficulty"] for h in history if h["raw_score"] >= 0.75), default=1)

        # Require passing at least one Tier 3 (Advanced) task to earn Grade A
        if pct >= 85 and max_tier_passed == 3:
            grade = "A"
        elif pct >= 70 and max_tier_passed >= 2:
            grade = "B"
        elif pct >= 55:
            grade = "C"
        elif pct >= 40:
            grade = "D"
        else:
            grade = "E"
        return pct, grade

    def _get_task_by_id(self, skill: str, task_id: str) -> Dict[str, Any]:
        tasks = get_adaptive_tasks_for_skill(skill)
        for t in tasks:
            if t["task_id"] == task_id:
                return t
        for task_list in ADAPTIVE_QUESTION_BANK.values():
            for t in task_list:
                if t["task_id"] == task_id:
                    return t
        raise ValueError(f"Task with id '{task_id}' not found.")

    def _select_task(
        self,
        skill: str,
        stage_type: StageType,
        difficulty: DifficultyTier,
        seen_task_ids: set
    ) -> Dict[str, Any]:
        tasks = get_adaptive_tasks_for_skill(skill)
        stage_tasks = [
            t for t in tasks
            if t["stage_type"] == stage_type.value and t["task_id"] not in seen_task_ids
        ]
        if not stage_tasks:
            stage_tasks = [t for t in tasks if t["stage_type"] == stage_type.value]

        # 1. Exact difficulty match
        diff_matches = [t for t in stage_tasks if t["difficulty"] == difficulty.value]
        if diff_matches:
            return diff_matches[0]

        # 2. Closest available difficulty
        if stage_tasks:
            stage_tasks.sort(key=lambda t: abs(t["difficulty"] - difficulty.value))
            return stage_tasks[0]

        # 3. Dynamic generic fallback
        fallbacks = generate_generic_adaptive_tasks(skill)
        for t in fallbacks:
            if t["stage_type"] == stage_type.value and t["difficulty"] == difficulty.value:
                return t
        return fallbacks[0]

    def _to_public(self, task: Dict[str, Any]) -> PublicTaskItem:
        return PublicTaskItem(
            task_id=task["task_id"],
            skill=task["skill"],
            stage_type=StageType(task["stage_type"]),
            difficulty=DifficultyTier(task["difficulty"]),
            prompt=task["prompt"],
            starter_code=task.get("starter_code"),
            options=task.get("options"),
            sample_tests=task.get("sample_tests"),
        )
