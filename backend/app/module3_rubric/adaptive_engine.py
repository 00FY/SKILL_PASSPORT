import os
import json
import ast
import uuid
import concurrent.futures
from typing import Dict, Any, List, Optional, Union
from ..schemas import (
    StageType, DifficultyTier, PublicTaskItem,
    TaskSubmissionRequest, StepEvaluationResult
)
from .question_bank import ADAPTIVE_QUESTION_BANK, get_adaptive_tasks_for_skill, generate_generic_adaptive_tasks
from .dynamic_generator import DynamicQuestionGenerator
from ..module1_extractor.injection_guard import PromptInjectionDefense

BANNED_AST_NAMES = {
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "open", "eval", "exec", "__import__",
    "compile", "input", "breakpoint", "help", "globals", "locals", "vars"
}
BANNED_ATTRIBUTES = {"__subclasses__", "__globals__", "__code__", "__builtins__"}
STAGE_SEQUENCE = [StageType.COMPREHENSION, StageType.DEBUGGING, StageType.CODING, StageType.REASONING]
DIFFICULTY_WEIGHTS = {1: 1.0, 2: 1.5, 3: 2.2}
MAX_LOOP_ITERATIONS = 200_000


class LoopLimiter(ast.NodeTransformer):
    """
    Injects an iteration counter check into every loop body (while, for)
    to terminate runaway/infinite loops in-thread without hanging worker threads.
    """
    def visit_For(self, node):
        self.generic_visit(node)
        check_call = ast.Expr(
            value=ast.Call(
                func=ast.Name(id="__check_loop_iter__", ctx=ast.Load()),
                args=[],
                keywords=[]
            )
        )
        node.body.insert(0, check_call)
        return node

    def visit_While(self, node):
        self.generic_visit(node)
        check_call = ast.Expr(
            value=ast.Call(
                func=ast.Name(id="__check_loop_iter__", ctx=ast.Load()),
                args=[],
                keywords=[]
            )
        )
        node.body.insert(0, check_call)
        return node


class AdaptiveAssessmentEngine:
    """
    Stateful adaptive assessment engine managing staircase difficulty transitions,
    AST-sandboxed test execution, and deterministic rubric evaluations.
    """

    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = storage_dir
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.injection_guard = PromptInjectionDefense()
        self.generator = DynamicQuestionGenerator()

    def _get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
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
        if not self.storage_dir:
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
        initial_verdict: Optional[str] = None,
        candidate_name: Optional[str] = None,
        applied_role: Optional[str] = None,
        repo_context: Optional[Union[str, Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        session_id = f"asmt_{uuid.uuid4().hex[:12]}"

        # Repo-Seeded Starting Difficulty
        if initial_verdict == "CLAIMED_ONLY":
            start_diff = DifficultyTier.FOUNDATIONAL
        elif initial_verdict in ("VERIFIED", "PARTIALLY_SUPPORTED"):
            start_diff = DifficultyTier.INTERMEDIATE
        else:
            start_diff = DifficultyTier.INTERMEDIATE

        context = {
            "candidate_name": candidate_name,
            "applied_role": applied_role,
            "repo_context": repo_context,
            "initial_verdict": initial_verdict
        }

        first_task = self._select_task(skill, StageType.COMPREHENSION, start_diff, set(), context=context)
        self.sessions[session_id] = {
            "session_id": session_id,
            "skill": skill,
            "passport_hash": passport_hash,
            "initial_verdict": initial_verdict,
            "context": context,
            "current_stage_idx": 0,
            "current_difficulty": start_diff,
            "seen_task_ids": {first_task["task_id"]},
            "history": [],
            "completed": False,
        }
        self._save_session(session_id)
        return {"session_id": session_id, "task": self._to_public(first_task)}

    def submit_step(self, req: TaskSubmissionRequest) -> StepEvaluationResult:
        session = self._get_session(req.session_id)
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
        context = session.get("context", {})
        next_task = self._select_task(
            session["skill"], next_stage, next_diff, session["seen_task_ids"], context=context
        )
        session["seen_task_ids"].add(next_task["task_id"])
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

        # Transform AST to inject loop iteration checks
        tree = LoopLimiter().visit(tree)
        ast.fix_missing_locations(tree)

        iter_counter = [0]
        def check_loop_iter():
            iter_counter[0] += 1
            if iter_counter[0] > MAX_LOOP_ITERATIONS:
                raise RuntimeError("Execution stopped: loop iteration limit exceeded")

        safe_builtins = {
            "len": len, "range": range, "min": min, "max": max, "sum": sum,
            "abs": abs, "enumerate": enumerate, "zip": zip, "list": list,
            "dict": dict, "set": set, "tuple": tuple, "sorted": sorted,
            "int": int, "str": str, "float": float, "bool": bool,
            "all": all, "any": any, "round": round, "reversed": reversed,
            "map": map, "filter": filter,
            "__check_loop_iter__": check_loop_iter
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
            iter_counter[0] = 0
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            try:
                def run_single():
                    copied_args = [
                        arg.copy() if isinstance(arg, (list, dict)) else arg
                        for arg in t.get("args", [])
                    ]
                    return candidate_fn(*copied_args)

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
            finally:
                executor.shutdown(wait=False, cancel_futures=True)

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
        if hasattr(self, "generator") and task_id in self.generator.memory_cache:
            return self.generator.memory_cache[task_id]
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
        seen_task_ids: set,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return self.generator.generate_task(
            skill=skill,
            stage_type=stage_type,
            difficulty=difficulty,
            context=context or {},
            seen_task_ids=seen_task_ids
        )

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
