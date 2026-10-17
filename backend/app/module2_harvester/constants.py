import os
from typing import Iterator, Tuple

EXCLUDED_DIRS = {
    "node_modules", "vendor", "dist", "build", ".git", ".next", ".nuxt", "out", "target",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".tox", ".venv", "venv", "env",
    "migrations", "coverage", "htmlcov", "bower_components", "Pods", ".gradle", ".idea", ".vscode",
}

EXCLUDED_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Pipfile.lock",
    "Cargo.lock", "composer.lock", "Gemfile.lock", "go.sum",
}

GENERATED_SUFFIXES = (".min.js", ".min.css", ".bundle.js", ".map", "_pb2.py", ".pb.go", ".g.dart")

MAX_SOURCE_FILE_BYTES = 512 * 1024

# File extension -> language skill credited for authored lines
CODE_EXTENSIONS = {
    ".py": "Python",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".java": "Java",
    ".kt": "Kotlin", ".kts": "Kotlin",
    ".go": "Go",
    ".rs": "Rust",
    ".c": "C", ".h": "C",
    ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".hpp": "C++", ".hh": "C++",
    ".cs": "C#",
    ".swift": "Swift",
    ".rb": "Ruby",
    ".php": "PHP",
    ".scala": "Scala",
    ".dart": "Dart",
    ".sql": "SQL",
    ".sh": "Bash", ".bash": "Bash",
    ".html": "HTML/CSS", ".htm": "HTML/CSS", ".css": "HTML/CSS", ".scss": "HTML/CSS", ".sass": "HTML/CSS",
    ".vue": "Vue.js",
    ".svelte": "Svelte",
}


def is_boilerplate_file(name: str, full_path: str) -> bool:
    if name in EXCLUDED_FILES or name.endswith(GENERATED_SUFFIXES):
        return True
    try:
        size = os.path.getsize(full_path)
    except OSError:
        return True
    if size > MAX_SOURCE_FILE_BYTES:
        return True
    # Empty / whitespace-only __init__.py files carry no authorship signal
    if name == "__init__.py":
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                return not f.read().strip()
        except OSError:
            return True
    return False


def walk_repo_files(repo_path: str) -> Iterator[Tuple[str, str, str]]:
    """Yield (name, full_path, rel_path) for every non-boilerplate file outside excluded directories."""
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS)
        for name in sorted(files):
            full_path = os.path.join(root, name)
            if os.path.islink(full_path) or is_boilerplate_file(name, full_path):
                continue
            yield name, full_path, os.path.relpath(full_path, repo_path)
