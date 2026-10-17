import os
import re
from typing import Dict, Any

class TestDetector:
    """
    Detects unit test suites, test frameworks, test files, and counts assertions.
    """

    def detect_tests(self, repo_path: str) -> Dict[str, Any]:
        test_files = []
        framework = None
        assertion_count = 0

        for root, dirs, files in os.walk(repo_path):
            if any(p in root for p in ["node_modules", ".git", "venv", "__pycache__"]):
                continue

            for file in files:
                lower = file.lower()
                is_test_file = False
                if (lower.startswith("test_") or lower.endswith("_test.py") or
                    lower.endswith(".test.js") or lower.endswith(".test.ts") or
                    lower.endswith(".spec.js") or lower.endswith(".spec.ts")):
                    is_test_file = True

                if is_test_file:
                    rel_path = os.path.relpath(os.path.join(root, file), repo_path)
                    test_files.append(rel_path)

                    full_path = os.path.join(root, file)
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()

                        # Detect framework
                        if "pytest" in content or "def test_" in content:
                            framework = "pytest"
                        elif "unittest" in content or "TestCase" in content:
                            framework = "unittest" if not framework else framework
                        elif "describe(" in content or "test(" in content or "it(" in content:
                            framework = "jest" if not framework else framework

                        # Count assertions
                        assert_matches = re.findall(r'\bassert\b|expect\(|\.assertEqual|\.assertTrue', content)
                        assertion_count += len(assert_matches)
                    except Exception:
                        pass

        # Also check for config files if no test file found yet
        if not framework:
            if os.path.exists(os.path.join(repo_path, "pytest.ini")) or os.path.exists(os.path.join(repo_path, "conftest.py")):
                framework = "pytest"
            elif os.path.exists(os.path.join(repo_path, "jest.config.js")) or os.path.exists(os.path.join(repo_path, "jest.config.ts")):
                framework = "jest"

        return {
            "has_tests": len(test_files) > 0,
            "test_framework": framework,
            "test_file_count": len(test_files),
            "test_assertion_count": assertion_count,
            "test_files_list": test_files[:10]
        }
