import os
import ast
import re
from typing import Dict, Any, List

class ASTAnalyzer:
    """
    Performs static analysis on source files to discover:
    - Framework imports (e.g., FastAPI, Express, React, Pytest)
    - Route handlers / API endpoint definitions
    - Robust error handling patterns (try-except blocks, try-catch)
    """

    def analyze_directory(self, repo_path: str) -> Dict[str, Any]:
        results = {
            "fastapi_imports": [],
            "route_definitions_count": 0,
            "has_error_handling": False,
            "error_handling_blocks": 0,
            "frameworks_detected": set(),
        }

        for root, dirs, files in os.walk(repo_path):
            if any(p in root for p in ["node_modules", ".git", "venv", "__pycache__"]):
                continue

            for file in files:
                full_path = os.path.join(root, file)
                if file.endswith(".py"):
                    self._analyze_python_file(full_path, results)
                elif file.endswith((".js", ".ts", ".tsx", ".jsx")):
                    self._analyze_js_file(full_path, results)

        results["frameworks_detected"] = list(results["frameworks_detected"])
        return results

    def _analyze_python_file(self, file_path: str, results: Dict[str, Any]):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                code = f.read()

            tree = ast.parse(code)
            for node in ast.walk(tree):
                # Imports
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if "fastapi" in alias.name:
                            results["frameworks_detected"].add("FastAPI")
                            results["fastapi_imports"].append(alias.name)
                        if "pytest" in alias.name:
                            results["frameworks_detected"].add("pytest")
                elif isinstance(node, ast.ImportFrom):
                    if node.module and "fastapi" in node.module:
                        results["frameworks_detected"].add("FastAPI")
                        for alias in node.names:
                            results["fastapi_imports"].append(alias.name)

                # Decorators for routes: @app.get, @router.post, etc.
                elif isinstance(node, ast.FunctionDef):
                    for dec in node.decorator_list:
                        dec_name = ""
                        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                            dec_name = dec.func.attr
                        elif isinstance(dec, ast.Attribute):
                            dec_name = dec.attr
                        if dec_name in ["get", "post", "put", "delete", "patch", "options"]:
                            results["route_definitions_count"] += 1

                # Try-Except blocks
                elif isinstance(node, ast.Try):
                    results["has_error_handling"] = True
                    results["error_handling_blocks"] += 1

        except Exception:
            pass

    def _analyze_js_file(self, file_path: str, results: Dict[str, Any]):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                code = f.read()

            if re.search(r'\b(from\s+[\'"]react[\'"]|require\([\'"]react[\'"]\))', code):
                results["frameworks_detected"].add("React")
            if re.search(r'\b(from\s+[\'"]next|require\([\'"]next[\'"]\))', code):
                results["frameworks_detected"].add("Next.js")
            if re.search(r'\b(app\.(get|post|put|delete)|router\.(get|post|put|delete))', code):
                results["route_definitions_count"] += 1
            if re.search(r'try\s*\{', code):
                results["has_error_handling"] = True
                results["error_handling_blocks"] += 1
        except Exception:
            pass
