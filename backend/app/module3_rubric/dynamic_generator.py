import os
import ast
import json
import uuid
import random
import logging
import httpx
from typing import Dict, Any, List, Optional
from ..schemas import StageType, DifficultyTier
from .question_bank import get_adaptive_tasks_for_skill, generate_generic_adaptive_tasks, ADAPTIVE_QUESTION_BANK

logger = logging.getLogger(__name__)

GENERATOR_SYSTEM_PROMPT = """You are an elite software engineering interviewer and evaluation engine for Skill Passport.
Your mission is to generate novel, non-leaked, production-grade technical evaluation challenges tailored to a candidate's background.

You MUST respond with a single valid JSON object strictly matching the schema for the requested stage.

RULES:
1. For COMPREHENSION:
   - Provide a realistic 4-10 line code snippet testing a subtle language/framework behavior (e.g., scoping, closures, async, memory, immutability, type coercion).
   - Provide exactly 4 distinct plausible options.
   - Provide "correct_option" as an integer index (0, 1, 2, or 3).
   - Provide a technical "explanation".

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
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

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

        try:
            res = httpx.post(url, json=payload, headers={"x-goog-api-key": api_key}, timeout=15.0)
            res.raise_for_status()
            text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
            data = json.loads(text)
            return self._normalize_generated_task(data, skill, stage_type, difficulty)
        except Exception as exc:
            logger.warning("Gemini task generation failed, falling back to curated bank: %s", exc)
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
            res = httpx.post(url, headers=headers, json=payload, timeout=15.0)
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
            parts.append(f"GitHub Repository & Evidence Context: {repo_context}")

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
            stage_tasks.sort(key=lambda t: abs(t["difficulty"] - difficulty.value))
            return stage_tasks[0]

        # Generic procedural generation
        fallbacks = generate_generic_adaptive_tasks(skill)
        matches = [t for t in fallbacks if t["stage_type"] == stage_type.value and t["difficulty"] == difficulty.value]
        if matches:
            return random.choice(matches)
        return fallbacks[0]
