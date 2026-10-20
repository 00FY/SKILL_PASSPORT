import ast
import uuid
import concurrent.futures
from typing import Dict, Any, List, Optional
from ..schemas import (
    StageType, DifficultyTier, PublicTaskItem,
    TaskSubmissionRequest, StepEvaluationResult
)
from .question_bank import ADAPTIVE_QUESTION_BANK, get_adaptive_tasks_for_skill, generate_generic_adaptive_tasks
from ..module1_extractor.injection_guard import PromptInjectionDefense

BANNED_AST_NAMES = {
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "open", "eval", "exec", "__import__",
    "compile", "input", "breakpoint", "help", "globals", "locals", "vars"
}
BANNED_ATTRIBUTES = {"__subclasses__", "__globals__", "__code__", "__builtins__"}
STAGE_SEQUENCE = [StageType.COMPREHENSION, StageType.DEBUGGING, StageType.CODING, StageType.REASONING]
DIFFICULTY_WEIGHTS = {1: 1.0, 2: 1.5, 3: 2.2}


class AdaptiveAssessmentEngine:
    """
    Stateful adaptive assessment engine managing staircase difficulty transitions,
    AST-sandboxed test execution, and deterministic rubric evaluations.
    """

    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.injection_guard = PromptInjectionDefense()

    def start_session(
        self,
        skill: str,
        passport_hash: str = "",
        initial_verdict: Optional[str] = None
    ) -> Dict[str, Any]:
        session_id = f"asmt_{uuid.uuid4().hex[:12]}"

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
            "history": [],
            "completed": False,
        }
        return {"session_id": session_id, "task": self._to_public(first_task)}

    def submit_step(self, req: TaskSubmissionRequest) -> StepEvaluationResult:
        session = self.sessions.get(req.session_id)
        if not session or session["completed"]:
            raise ValueError("Invalid or already completed assessment session.")

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

        safe_builtins = {
            "len": len, "range": range, "min": min, "max": max, "sum": sum,
            "abs": abs, "enumerate": enumerate, "zip": zip, "list": list,
            "dict": dict, "set": set, "tuple": tuple, "sorted": sorted,
            "int": int, "str": str, "float": float, "bool": bool,
            "all": all, "any": any, "round": round, "reversed": reversed,
            "map": map, "filter": filter
        }
        namespace: Dict[str, Any] = {"__builtins__": safe_builtins}
        try:
            exec(compile(tree, filename="<candidate_code>", mode="exec"), namespace)
        except Exception as e:
            return 0.0, [], f"Runtime error during definition: {type(e).__name__}: {e}"

        candidate_fn = namespace.get(fn_name)
        if not callable(candidate_fn):
            return 0.0, [], f"Function `{fn_name}` was not found or is not callable."

        results = []
        passed_count = 0
        for idx, t in enumerate(tests, 1):
            try:
                def run_single():
                    copied_args = [
                        arg.copy() if isinstance(arg, (list, dict)) else arg
                        for arg in t.get("args", [])
                    ]
                    return candidate_fn(*copied_args)

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_single)
                    actual = future.result(timeout=2.0)

                ok = (actual == t.get("expected"))
                if ok:
                    passed_count += 1
                results.append({"test_case": idx, "passed": ok, "expected": t.get("expected"), "actual": actual})
            except concurrent.futures.TimeoutError:
                results.append({"test_case": idx, "passed": False, "error": "Execution timed out (limit: 2.0s)"})
            except Exception as e:
                results.append({"test_case": idx, "passed": False, "error": f"{type(e).__name__}: {e}"})

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
