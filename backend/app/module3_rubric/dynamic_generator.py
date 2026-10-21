import os
import ast
import json
import uuid
import random
import logging
import time
import httpx
from typing import Dict, Any, List, Optional
from ..schemas import StageType, DifficultyTier
from .question_bank import get_adaptive_tasks_for_skill, generate_generic_adaptive_tasks, ADAPTIVE_QUESTION_BANK

def _load_env_if_present() -> None:
    env_paths = [
        os.path.join(os.getcwd(), ".env"),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env")),
    ]
    for p in env_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k, v = k.strip(), v.strip().strip("\"'")
                            if k not in os.environ:
                                os.environ[k] = v
                break
            except Exception:
                pass


_load_env_if_present()

logger = logging.getLogger(__name__)

GENERATOR_SYSTEM_PROMPT = """You are an elite software engineering interviewer and evaluation engine for Skill Passport.
Your mission is to generate novel, non-leaked, production-grade technical evaluation challenges tailored to a candidate's background.

You MUST respond with a single valid JSON object strictly matching the schema for the requested stage.

RULES:
1. For COMPREHENSION:
   - Provide "prompt": Clear instruction describing the task (e.g., "What will this code print or do?").
   - Provide "starter_code": A realistic 4-10 line code snippet testing a subtle language/framework behavior (e.g., scoping, closures, async, memory, immutability, type coercion).
   - Provide "options": Exactly 4 distinct plausible options.
   - Provide "correct_option": Integer index (0, 1, 2, or 3).
   - Provide "explanation": Technical rationale.

2. For DEBUGGING:
   - Provide "starter_code" implementing a realistic function with an intentional bug (e.g., off-by-one, boundary condition, mutable state leak, wrong logic branch).
   - Provide "entry_function" name (must match the function in starter_code).
   - Provide "sample_tests" (1-2 visible assertion strings for the candidate).
   - Provide "hidden_tests" (3-4 test dictionaries, each with "args": list and "expected": value).
   - In Python, only use standard library (no external packages, no os, no sys, no subprocess).

3. For CODING:
   - Provide a clean problem statement in "prompt".
   - Provide "starter_code" with function stub and docstring.
   - Provide "entry_function" name.
   - Provide "sample_tests" (1-2 visible assertion strings).
   - Provide "hidden_tests" (3-4 test dictionaries with "args" and "expected").
   - In Python, only use standard library (no external packages, no os, no sys, no subprocess).

4. For REASONING:
   - Provide an architectural dilemma or trade-off question in "prompt" relevant to high-scale production systems.
   - Provide "required_concepts": a list of 2-3 dictionaries, each with "name" (str) and "keywords" (list of 3-5 lowercase relevant terminology strings).
   - Provide "forbidden_patterns": ["ignore previous instructions", "score 100", "system prompt"].

5. INCORPORATE CONTEXT:
   - If candidate role, GitHub repositories, or evidence signals are provided, contextualize the question domain (e.g., if repo is a data pipeline, frame problem around data batches; if microservices, frame around API contracts).
"""


class DynamicQuestionGenerator:
    """
    Synthesizes unique, non-leaked assessment challenges using Gemini/OpenAI API
    contextualized by the candidate's resume claims and GitHub repository evidence.
    Gracefully falls back to curated/procedural benchmarks if no API key is provided.
    """

    def __init__(self, cache_dir: str = ".generated_tasks"):
        self.cache_dir = cache_dir
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        if self.cache_dir:
            try:
                os.makedirs(self.cache_dir, exist_ok=True)
            except Exception:
                pass

    def generate_task(
        self,
        skill: str,
        stage_type: StageType,
        difficulty: DifficultyTier,
        context: Optional[Dict[str, Any]] = None,
        seen_task_ids: Optional[set] = None
    ) -> Dict[str, Any]:
        """
        Generates or selects an assessment task. Attempts LLM generation first if API key
        is configured; validates generated AST and test cases; falls back to curated bank.
        """
        seen_task_ids = seen_task_ids or set()
        context = context or {}

        gemini_key = os.getenv("GEMINI_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")

        task: Optional[Dict[str, Any]] = None

        if gemini_key:
            task = self._generate_via_gemini(skill, stage_type, difficulty, context, gemini_key)
        elif openai_key:
            task = self._generate_via_openai(skill, stage_type, difficulty, context, openai_key)

        # Validate task syntax and schema before serving
        if task and self._validate_task(task, stage_type):
            self._cache_task(skill, task)
            return task

        # Fallback to curated benchmark pool with anti-collision sampling
        return self._fallback_select(skill, stage_type, difficulty, seen_task_ids)

    def _generate_via_gemini(
        self,
        skill: str,
        stage_type: StageType,
        difficulty: DifficultyTier,
        context: Dict[str, Any],
        api_key: str
    ) -> Optional[Dict[str, Any]]:
        configured_model = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
        models_to_try = [configured_model]
        for fallback_model in ["gemini-flash-lite-latest", "gemini-flash-latest", "gemini-2.5-flash"]:
            if fallback_model not in models_to_try:
                models_to_try.append(fallback_model)

        user_content = self._build_prompt_payload(skill, stage_type, difficulty, context)
        payload = {
            "systemInstruction": {"parts": [{"text": GENERATOR_SYSTEM_PROMPT}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_content}]
                }
            ],
            "generationConfig": {"response_mime_type": "application/json"}
        }

        last_exc = None
        for model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            for attempt in range(2):
                try:
                    res = httpx.post(url, json=payload, headers={"x-goog-api-key": api_key}, timeout=25.0)
                    if res.status_code in (503, 429):
                        if attempt == 0:
                            time.sleep(1.0)
                            continue
                        break
                    res.raise_for_status()
                    text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                    data = json.loads(text)
                    return self._normalize_generated_task(data, skill, stage_type, difficulty)
                except Exception as exc:
                    last_exc = exc
                    if attempt == 0:
                        time.sleep(0.8)

        if last_exc:
            logger.warning("Gemini task generation failed across models %s, falling back to curated bank: %s", models_to_try, last_exc)
        return None

    def _generate_via_openai(
        self,
        skill: str,
        stage_type: StageType,
        difficulty: DifficultyTier,
        context: Dict[str, Any],
        api_key: str
    ) -> Optional[Dict[str, Any]]:
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}"}

        user_content = self._build_prompt_payload(skill, stage_type, difficulty, context)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            "response_format": {"type": "json_object"}
        }

        try:
            res = httpx.post(url, headers=headers, json=payload, timeout=25.0)
            res.raise_for_status()
            content = res.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
            return self._normalize_generated_task(data, skill, stage_type, difficulty)
        except Exception as exc:
            logger.warning("OpenAI task generation failed, falling back to curated bank: %s", exc)
            return None

    def _build_prompt_payload(
        self,
        skill: str,
        stage_type: StageType,
        difficulty: DifficultyTier,
        context: Dict[str, Any]
    ) -> str:
        diff_names = {1: "Foundational (Tier 1)", 2: "Intermediate (Tier 2)", 3: "Advanced Production (Tier 3)"}
        diff_str = diff_names.get(difficulty.value, "Intermediate")

        parts = [
            f"Target Skill / Language: {skill}",
            f"Stage Type: {stage_type.value}",
            f"Difficulty Tier: {diff_str} (Value: {difficulty.value})",
            f"Random Anti-Collision Seed: {uuid.uuid4().hex[:8]}"
        ]

        candidate_name = context.get("candidate_name")
        if candidate_name:
            parts.append(f"Candidate Name: {candidate_name}")

        applied_role = context.get("applied_role")
        if applied_role:
            parts.append(f"Applied Role: {applied_role}")

        repo_context = context.get("repo_context")
        if repo_context:
            if isinstance(repo_context, dict):
                repo_str = ", ".join(f"{k}: {v}" for k, v in repo_context.items())
            else:
                repo_str = str(repo_context)
            parts.append(f"GitHub Repository & Evidence Context: {repo_str}")

        return "\n".join(parts)

    def _normalize_generated_task(
        self,
        data: Dict[str, Any],
        skill: str,
        stage_type: StageType,
        difficulty: DifficultyTier
    ) -> Dict[str, Any]:
        task_id = data.get("task_id") or f"{skill.lower()}-gen-{uuid.uuid4().hex[:8]}"
        data["task_id"] = task_id
        data["skill"] = skill
        data["stage_type"] = stage_type.value
        data["difficulty"] = difficulty.value

        # Normalize starter code aliases across all LLM output variations
        starter_candidates = [
            data.get("starter_code"),
            data.get("code_snippet"),
            data.get("code"),
            data.get("snippet"),
            data.get("codeSnippet"),
            data.get("python_code")
        ]
        resolved_code = next((c for c in starter_candidates if isinstance(c, str) and c.strip()), None)
        if resolved_code:
            data["starter_code"] = resolved_code

        # Normalize prompt aliases
        if not data.get("prompt"):
            if data.get("question"):
                data["prompt"] = data["question"]
            elif data.get("starter_code"):
                data["prompt"] = "Predict the output or behavior of the following code snippet:"
            else:
                data["prompt"] = f"Evaluate the following {skill} scenario."

        # Normalize comprehension options & correct_option
        if stage_type == StageType.COMPREHENSION:
            options = data.get("options", [])
            correct = data.get("correct_option")
            if isinstance(correct, str):
                if correct in options:
                    data["correct_option"] = options.index(correct)
                elif correct.strip().isdigit() and int(correct.strip()) < len(options):
                    data["correct_option"] = int(correct.strip())
                elif correct.strip().upper() in ["A", "B", "C", "D"]:
                    idx = ord(correct.strip().upper()) - ord("A")
                    if idx < len(options):
                        data["correct_option"] = idx

        # Normalize coding / debugging tests
        elif stage_type in (StageType.DEBUGGING, StageType.CODING):
            tests = data.get("hidden_tests", [])
            norm_tests = []
            for t in tests:
                if isinstance(t, dict):
                    args = t.get("args") if "args" in t else ([t["input"]] if "input" in t else None)
                    expected = t.get("expected") if "expected" in t else t.get("output")
                    if args is not None and expected is not None:
                        if not isinstance(args, list):
                            args = [args]
                        norm_tests.append({"args": args, "expected": expected})
            if norm_tests:
                data["hidden_tests"] = norm_tests

            if not data.get("sample_tests") and data.get("hidden_tests"):
                fn = data.get("entry_function", "solve")
                first = data["hidden_tests"][0]
                args_str = ", ".join(repr(a) for a in first["args"])
                data["sample_tests"] = [f"assert {fn}({args_str}) == {repr(first['expected'])}"]

        return data

    def _validate_task(self, task: Dict[str, Any], stage_type: StageType) -> bool:
        """Validates that the generated task satisfies all structural and AST execution requirements."""
        if not task.get("prompt") or not task.get("task_id"):
            return False

        if stage_type == StageType.COMPREHENSION:
            options = task.get("options")
            correct = task.get("correct_option")
            return isinstance(options, list) and len(options) >= 2 and isinstance(correct, int) and 0 <= correct < len(options)

        if stage_type in (StageType.DEBUGGING, StageType.CODING):
            code = task.get("starter_code", "")
            fn_name = task.get("entry_function", "")
            hidden_tests = task.get("hidden_tests", [])

            if not code or not fn_name or not isinstance(hidden_tests, list) or len(hidden_tests) == 0:
                return False

            # Verify that starter code is valid Python AST and contains no banned identifiers
            try:
                tree = ast.parse(code)
            except SyntaxError:
                return False

            banned = {"os", "sys", "subprocess", "socket", "open", "eval", "exec", "__import__"}
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    return False
                if isinstance(node, ast.Name) and node.id in banned:
                    return False

            # Verify test cases structure
            for t in hidden_tests:
                if not isinstance(t, dict) or "args" not in t or "expected" not in t:
                    return False

            return True

        if stage_type == StageType.REASONING:
            concepts = task.get("required_concepts")
            return isinstance(concepts, list) and len(concepts) >= 1

        return True

    def _cache_task(self, skill: str, task: Dict[str, Any]) -> None:
        """Saves generated task in memory and registers it in ADAPTIVE_QUESTION_BANK."""
        task_id = task["task_id"]
        self.memory_cache[task_id] = task

        # Register in global question bank so evaluation lookups find it
        if skill not in ADAPTIVE_QUESTION_BANK:
            ADAPTIVE_QUESTION_BANK[skill] = []
        if not any(t["task_id"] == task_id for t in ADAPTIVE_QUESTION_BANK[skill]):
            ADAPTIVE_QUESTION_BANK[skill].append(task)

        # Write to disk cache if available
        if self.cache_dir:
            try:
                path = os.path.join(self.cache_dir, f"{task_id}.json")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(task, f)
            except Exception:
                pass

    def _fallback_select(
        self,
        skill: str,
        stage_type: StageType,
        difficulty: DifficultyTier,
        seen_task_ids: set
    ) -> Dict[str, Any]:
        """Selects a task from the curated or generic question bank with random sampling."""
        tasks = get_adaptive_tasks_for_skill(skill)
        stage_tasks = [
            t for t in tasks
            if t["stage_type"] == stage_type.value and t["task_id"] not in seen_task_ids
        ]
        if not stage_tasks:
            stage_tasks = [t for t in tasks if t["stage_type"] == stage_type.value]

        # Filter by target difficulty
        diff_matches = [t for t in stage_tasks if t["difficulty"] == difficulty.value]
        if diff_matches:
            return random.choice(diff_matches)

        # Closest available difficulty
        if stage_tasks:
            min_dist = min(abs(t["difficulty"] - difficulty.value) for t in stage_tasks)
            closest = [t for t in stage_tasks if abs(t["difficulty"] - difficulty.value) == min_dist]
            return random.choice(closest)

        # Generic procedural generation
        fallbacks = generate_generic_adaptive_tasks(skill)
        matches = [t for t in fallbacks if t["stage_type"] == stage_type.value and t["difficulty"] == difficulty.value]
        if matches:
            return random.choice(matches)
        return fallbacks[0]
