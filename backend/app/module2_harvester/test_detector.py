import os
import re
from collections import Counter
from typing import Dict, Any, List, Optional
from .constants import walk_repo_files

JS_TEST_RE = re.compile(r"\.(test|spec|cy)\.(js|jsx|ts|tsx|mjs|cjs)$")
ASSERTION_RE = re.compile(
    r"\bassert\b|\bexpect\s*\(|\.assert\w*\s*\(|\bassert(Equals|True|False|That|Throws|NotNull)\s*\(|"
    r"\bt\.(Error|Errorf|Fatal|Fatalf)\s*\(|\bassert(_eq|_ne)?!\s*\(|\bAssert\.\w+\s*\(|\bshould\b"
)


class TestDetector:
    """
    Detects unit test suites, test frameworks, test files, and counts assertions
    across Python, JavaScript/TypeScript, Go, Java/Kotlin, Ruby, PHP, Rust and C#.
    """

    def detect_tests(self, repo_path: str) -> Dict[str, Any]:
        files_by_framework: Dict[str, List[str]] = {}
        assertion_count = 0

        for name, full_path, rel_path in walk_repo_files(repo_path):
            lower = name.lower()
            ext = os.path.splitext(lower)[1]
            parts = rel_path.replace(os.sep, "/").lower().split("/")
            in_test_dir = any(p in ("tests", "test", "__tests__", "spec", "e2e", "cypress") for p in parts[:-1])

            candidate = (
                (ext == ".py" and (lower.startswith("test_") or lower.endswith("_test.py") or (in_test_dir and lower != "conftest.py")))
                or JS_TEST_RE.search(lower) is not None
                or (ext in (".js", ".ts", ".jsx", ".tsx") and "__tests__" in parts)
                or lower.endswith("_test.go")
                or (ext in (".java", ".kt") and re.search(r"(test|tests|it)\.(java|kt)$", lower) is not None)
                or lower.endswith("_spec.rb") or lower.endswith("_test.rb")
                or (ext == ".php" and lower.endswith("test.php"))
                or (ext == ".cs" and lower.endswith(("tests.cs", "test.cs")))
                or ext == ".rs"
            )
            if not candidate:
                continue

            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except OSError:
                continue

            framework = self._framework_for(ext, lower, content)
            if not framework:
                continue
            files_by_framework.setdefault(framework, []).append(rel_path)
            assertion_count += len(ASSERTION_RE.findall(content))

        # Also check for config files if no test file found yet
        config_framework = None
        if not files_by_framework:
            if os.path.exists(os.path.join(repo_path, "pytest.ini")) or os.path.exists(os.path.join(repo_path, "conftest.py")):
                config_framework = "pytest"
            elif any(os.path.exists(os.path.join(repo_path, f"jest.config.{e}")) for e in ("js", "ts", "cjs", "mjs")):
                config_framework = "jest"

        test_files = [f for files in files_by_framework.values() for f in files]
        counts = Counter({fw: len(files) for fw, files in files_by_framework.items()})
        primary = counts.most_common(1)[0][0] if counts else config_framework

        return {
            "has_tests": len(test_files) > 0,
            "test_framework": primary,
            "test_frameworks": sorted(files_by_framework),
            "test_file_count": len(test_files),
            "test_assertion_count": assertion_count,
            "test_files_list": test_files[:10],
            "files_by_framework": files_by_framework,
        }

    @staticmethod
    def _framework_for(ext: str, lower: str, content: str) -> Optional[str]:
        if ext == ".py":
            if re.search(r"^\s*(import|from)\s+unittest\b", content, re.M) or "TestCase" in content:
                return "unittest" if "pytest" not in content else "pytest"
            if "pytest" in content or re.search(r"^\s*(async\s+)?def\s+test_", content, re.M):
                return "pytest"
            return None
        if ext in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"):
            if "@playwright/test" in content:
                return "playwright"
            if ".cy." in lower or re.search(r"\bcy\.(visit|get)\(", content):
                return "cypress"
            if re.search(r"""from\s+['"]vitest['"]""", content):
                return "vitest"
            if re.search(r"""require\(\s*['"](mocha|chai)['"]|from\s+['"]chai['"]""", content):
                return "mocha"
            if re.search(r"\b(describe|test|it)\s*\(", content):
                return "jest"
            return None
        if ext == ".go":
            return "go test" if re.search(r"func\s+Test\w*\(\s*\w+\s+\*testing\.T", content) else None
        if ext in (".java", ".kt"):
            return "junit" if re.search(r"org\.junit|@Test\b", content) else None
        if ext == ".rb":
            return "rspec" if re.search(r"\b(describe|it)\b", content) else None
        if ext == ".php":
            return "phpunit" if "TestCase" in content else None
        if ext == ".rs":
            return "cargo test" if "#[test]" in content else None
        if ext == ".cs":
            return "xunit" if re.search(r"\[(Fact|Theory|Test|TestMethod)\]", content) else None
        return None
