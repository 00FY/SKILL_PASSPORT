import os
import ast
import re
from typing import Dict, Any, Set
from .constants import walk_repo_files

# Top-level Python module -> skills it evidences
PYTHON_IMPORT_SKILLS = {
    "fastapi": ["FastAPI"],
    "django": ["Django"],
    "rest_framework": ["Django"],
    "flask": ["Flask"],
    "pandas": ["Pandas"],
    "numpy": ["NumPy"],
    "sklearn": ["scikit-learn", "Machine Learning"],
    "tensorflow": ["TensorFlow", "Machine Learning"],
    "keras": ["TensorFlow", "Machine Learning"],
    "torch": ["PyTorch", "Machine Learning"],
    "psycopg2": ["PostgreSQL"],
    "psycopg": ["PostgreSQL"],
    "asyncpg": ["PostgreSQL"],
    "pymysql": ["MySQL"],
    "MySQLdb": ["MySQL"],
    "pymongo": ["MongoDB"],
    "motor": ["MongoDB"],
    "mongoengine": ["MongoDB"],
    "redis": ["Redis"],
    "sqlite3": ["SQLite"],
    "boto3": ["AWS"],
    "botocore": ["AWS"],
    "azure": ["Azure"],
    "firebase_admin": ["Firebase"],
    "graphene": ["GraphQL"],
    "strawberry": ["GraphQL"],
    "ariadne": ["GraphQL"],
    "selenium": ["Selenium"],
}

# npm package -> skills it evidences
JS_PACKAGE_SKILLS = {
    "react": ["React"],
    "react-dom": ["React"],
    "next": ["Next.js", "React"],
    "vue": ["Vue.js"],
    "nuxt": ["Vue.js"],
    "svelte": ["Svelte"],
    "@sveltejs/kit": ["Svelte"],
    "express": ["Express", "Node.js"],
    "koa": ["Node.js"],
    "fastify": ["Node.js"],
    "react-native": ["React Native", "React"],
    "mongoose": ["MongoDB"],
    "mongodb": ["MongoDB"],
    "pg": ["PostgreSQL"],
    "postgres": ["PostgreSQL"],
    "mysql": ["MySQL"],
    "mysql2": ["MySQL"],
    "redis": ["Redis"],
    "ioredis": ["Redis"],
    "graphql": ["GraphQL"],
    "aws-sdk": ["AWS"],
    "firebase": ["Firebase"],
    "firebase-admin": ["Firebase"],
}
JS_SCOPE_SKILLS = {
    "@angular": ["Angular"],
    "@nestjs": ["NestJS", "Node.js"],
    "@apollo": ["GraphQL"],
    "@aws-sdk": ["AWS"],
    "@google-cloud": ["GCP"],
    "@azure": ["Azure"],
}
NODE_BUILTINS = {"fs", "path", "http", "https", "os", "child_process", "crypto", "url", "stream", "events", "util", "net", "cluster"}

JS_IMPORT_RE = re.compile(r"""(?:import\s+(?:[\w*{}\s,]+\s+from\s+)?|import\s*\(\s*|require\s*\(\s*)['"]([^'"]+)['"]""")
JS_ROUTE_RE = re.compile(r"\b(app|router|server)\.(get|post|put|delete|patch)\s*\(")

# Regexes over source text for other ecosystems
SOURCE_SKILL_PATTERNS = {
    ".java": [(re.compile(r"^\s*import\s+org\.springframework", re.M), "Spring Boot")],
    ".kt": [(re.compile(r"^\s*import\s+org\.springframework", re.M), "Spring Boot")],
    ".dart": [(re.compile(r"""import\s+['"]package:flutter/"""), "Flutter")],
    ".php": [(re.compile(r"^\s*use\s+Illuminate\\", re.M), "Laravel")],
    ".rb": [(re.compile(r"<\s*(ApplicationController|ApplicationRecord|ActiveRecord::Base)|\bRails\."), "Ruby on Rails")],
    ".cs": [(re.compile(r"^\s*using\s+Microsoft\.AspNetCore", re.M), ".NET")],
}

COMPOSE_IMAGE_SKILLS = [
    (re.compile(r"image:\s*['\"]?(?:[\w.\-]+/)?postgres", re.I), "PostgreSQL"),
    (re.compile(r"image:\s*['\"]?(?:[\w.\-]+/)?(mysql|mariadb)", re.I), "MySQL"),
    (re.compile(r"image:\s*['\"]?(?:[\w.\-]+/)?mongo", re.I), "MongoDB"),
    (re.compile(r"image:\s*['\"]?(?:[\w.\-]+/)?redis", re.I), "Redis"),
]
K8S_RE = re.compile(r"^apiVersion:\s*\S+", re.M)
K8S_KIND_RE = re.compile(r"^kind:\s*(Deployment|Service|Pod|StatefulSet|DaemonSet|Ingress|ConfigMap|Secret|Job|CronJob|Namespace)\b", re.M)
TF_PROVIDER_SKILLS = [
    (re.compile(r'provider\s+"aws"'), "AWS"),
    (re.compile(r'provider\s+"google"'), "GCP"),
    (re.compile(r'provider\s+"azurerm"'), "Azure"),
]
CI_FILES = {".gitlab-ci.yml", "jenkinsfile", ".travis.yml", "azure-pipelines.yml", "bitbucket-pipelines.yml"}


class ASTAnalyzer:
    """
    Performs static analysis on source and config files (never executing them) to discover:
    - Framework / library / database / cloud usage via imports (AST for Python, regex elsewhere)
    - Infrastructure evidence: Dockerfiles, compose files, Kubernetes manifests, Terraform, CI pipelines
    - Route handlers / API endpoint definitions
    - Robust error handling patterns (try-except blocks, try-catch)

    Returns, per detected skill, the files that evidence it so authorship can be measured on exactly those files.
    """

    def analyze_directory(self, repo_path: str) -> Dict[str, Any]:
        results: Dict[str, Any] = {
            "fastapi_imports": [],
            "route_definitions_count": 0,
            "has_error_handling": False,
            "error_handling_blocks": 0,
            "frameworks_detected": set(),
            "skill_files": {},
            "skill_imports": {},
            "skill_routes": {},
        }

        for name, full_path, rel_path in walk_repo_files(repo_path):
            lower = name.lower()
            ext = os.path.splitext(lower)[1]
            rel_lower = rel_path.replace(os.sep, "/").lower()
            try:
                if ext == ".py":
                    self._analyze_python_file(full_path, rel_path, results)
                elif ext in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte"):
                    self._analyze_js_file(full_path, rel_path, results)
                elif ext in SOURCE_SKILL_PATTERNS:
                    code = self._read(full_path)
                    for pattern, skill in SOURCE_SKILL_PATTERNS[ext]:
                        if pattern.search(code):
                            self._add(results, skill, rel_path)
                    if re.search(r"\btry\s*\{|\bbegin\b[\s\S]*?\brescue\b", code):
                        results["has_error_handling"] = True
                        results["error_handling_blocks"] += 1

                # Infrastructure / config evidence
                if lower.startswith("dockerfile") or lower.endswith(".dockerfile"):
                    self._add(results, "Docker", rel_path)
                if re.match(r"(docker-)?compose(\.[\w-]+)?\.ya?ml$", lower):
                    self._add(results, "Docker", rel_path)
                    code = self._read(full_path)
                    for pattern, skill in COMPOSE_IMAGE_SKILLS:
                        if pattern.search(code):
                            self._add(results, skill, rel_path)
                if ext == ".tf":
                    self._add(results, "Terraform", rel_path)
                    code = self._read(full_path)
                    for pattern, skill in TF_PROVIDER_SKILLS:
                        if pattern.search(code):
                            self._add(results, skill, rel_path)
                if rel_lower.startswith(".github/workflows/") and ext in (".yml", ".yaml") \
                        or lower in CI_FILES or rel_lower == ".circleci/config.yml":
                    self._add(results, "CI/CD", rel_path)
                elif ext in (".yml", ".yaml"):
                    if lower == "chart.yaml":
                        self._add(results, "Kubernetes", rel_path)
                    else:
                        code = self._read(full_path)
                        if K8S_RE.search(code) and K8S_KIND_RE.search(code):
                            self._add(results, "Kubernetes", rel_path)
                if re.match(r"tailwind\.config\.(js|cjs|mjs|ts)$", lower):
                    self._add(results, "Tailwind CSS", rel_path)
            except Exception:
                continue

        results["frameworks_detected"] = sorted(results["frameworks_detected"])
        results["skill_files"] = {k: sorted(v) for k, v in results["skill_files"].items()}
        results["skill_imports"] = {k: sorted(v) for k, v in results["skill_imports"].items()}
        return results

    @staticmethod
    def _read(full_path: str) -> str:
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    @staticmethod
    def _add(results: Dict[str, Any], skill: str, rel_path: str, import_name: str = None):
        results["frameworks_detected"].add(skill)
        results["skill_files"].setdefault(skill, set()).add(rel_path)
        if import_name:
            results["skill_imports"].setdefault(skill, set()).add(import_name)

    def _analyze_python_file(self, file_path: str, rel_path: str, results: Dict[str, Any]):
        try:
            tree = ast.parse(self._read(file_path))
        except (SyntaxError, ValueError):
            return

        file_skills: Set[str] = set()
        file_routes = 0
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [(alias.name, alias.name) for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                modules = [(node.module, alias.name) for alias in node.names]

            for module, imported in modules:
                top = module.split(".")[0]
                skills = list(PYTHON_IMPORT_SKILLS.get(top, []))
                if module.startswith("google.cloud"):
                    skills.append("GCP")
                for skill in skills:
                    file_skills.add(skill)
                    self._add(results, skill, rel_path, imported)
                if top == "fastapi":
                    results["fastapi_imports"].append(imported)
                if top == "pytest":
                    results["frameworks_detected"].add("pytest")

            # Decorators for routes: @app.get, @router.post, @app.route, etc.
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    target = dec.func if isinstance(dec, ast.Call) else dec
                    if isinstance(target, ast.Attribute) and target.attr in ("get", "post", "put", "delete", "patch", "options", "route", "api_route"):
                        results["route_definitions_count"] += 1
                        file_routes += 1

            # Try-Except blocks
            if isinstance(node, ast.Try):
                results["has_error_handling"] = True
                results["error_handling_blocks"] += 1

        for skill in file_skills & {"FastAPI", "Flask"}:
            results["skill_routes"][skill] = results["skill_routes"].get(skill, 0) + file_routes

    def _analyze_js_file(self, file_path: str, rel_path: str, results: Dict[str, Any]):
        code = self._read(file_path)
        for spec in JS_IMPORT_RE.findall(code):
            if spec.startswith((".", "/")):
                continue
            if spec.startswith("node:") or spec.split("/")[0] in NODE_BUILTINS:
                self._add(results, "Node.js", rel_path, spec)
                continue
            if spec.startswith("@"):
                scope = spec.split("/")[0]
                package = "/".join(spec.split("/")[:2])
                skills = JS_PACKAGE_SKILLS.get(package) or JS_SCOPE_SKILLS.get(scope, [])
            else:
                skills = JS_PACKAGE_SKILLS.get(spec.split("/")[0], [])
            for skill in skills:
                self._add(results, skill, rel_path, spec)

        routes = len(JS_ROUTE_RE.findall(code))
        if routes:
            results["route_definitions_count"] += routes
            for skill in ("Express", "Node.js"):
                if rel_path in results["skill_files"].get(skill, set()):
                    results["skill_routes"][skill] = results["skill_routes"].get(skill, 0) + routes
        if re.search(r"\btry\s*\{", code):
            results["has_error_handling"] = True
            results["error_handling_blocks"] += 1
