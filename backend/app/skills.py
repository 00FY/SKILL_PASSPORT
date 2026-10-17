"""
Shared skill catalog.

One source of truth for:
- which skills the offline extractor recognises in resume text (aliases),
- how LLM-extracted skill names are normalised to canonical names,
- how much authored evidence a skill needs before it counts as code-backed,
- which test frameworks give test credit to which skills (ecosystem).
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class SkillSpec:
    category: str
    aliases: Tuple[str, ...]
    ecosystem: Optional[str] = None
    # Aliases that must match with exact casing (e.g. "Swift" the language vs "swift" the adjective)
    case_sensitive_aliases: Tuple[str, ...] = field(default_factory=tuple)
    # Minimum candidate-authored lines before the skill counts as backed by code
    min_lines: Optional[int] = None


DEFAULT_MIN_LINES = {
    "language": 100,
    "framework": 50,
    "library": 30,
    "ml": 30,
    "database": 10,
    "devops": 10,
    "cloud": 10,
    "testing": 10,
    "api": 20,
    "web": 50,
}

SKILL_CATALOG: Dict[str, SkillSpec] = {
    # Languages
    "Python": SkillSpec("language", ("python", "python3"), "python"),
    "JavaScript": SkillSpec("language", ("javascript", "ecmascript", "es6"), "js"),
    "TypeScript": SkillSpec("language", ("typescript",), "js"),
    "Java": SkillSpec("language", ("java", "java 8", "java 11", "java 17"), "java"),
    "Kotlin": SkillSpec("language", ("kotlin",), "java"),
    "Go": SkillSpec("language", ("golang", "go language", "go lang"), "go"),
    "Rust": SkillSpec("language", ("rust", "rustlang"), "rust"),
    "C++": SkillSpec("language", ("c++", "cpp"), "cpp"),
    "C#": SkillSpec("language", ("c#", "csharp", "c sharp"), "dotnet"),
    "Swift": SkillSpec("language", ("swiftui",), "swift", case_sensitive_aliases=("Swift",)),
    "Ruby": SkillSpec("language", ("ruby",), "ruby"),
    "PHP": SkillSpec("language", ("php",), "php"),
    "Scala": SkillSpec("language", ("scala",), "java"),
    "Dart": SkillSpec("language", ("dart",), "dart"),
    "SQL": SkillSpec("database", ("sql", "t-sql", "pl/sql", "plsql"), min_lines=20),
    "Bash": SkillSpec("devops", ("bash", "shell scripting", "shell script", "zsh"), min_lines=20),
    "HTML/CSS": SkillSpec("web", ("html", "html5", "css", "css3", "scss", "sass"), "js"),
    # Frameworks
    "FastAPI": SkillSpec("framework", ("fastapi",), "python"),
    "Django": SkillSpec("framework", ("django", "django rest framework", "drf"), "python"),
    "Flask": SkillSpec("framework", ("flask",), "python"),
    "React": SkillSpec("framework", ("react", "react.js", "reactjs"), "js"),
    "React Native": SkillSpec("framework", ("react native", "react-native"), "js"),
    "Next.js": SkillSpec("framework", ("next.js", "nextjs"), "js"),
    "Vue.js": SkillSpec("framework", ("vue", "vue.js", "vuejs", "nuxt", "nuxt.js"), "js"),
    "Angular": SkillSpec("framework", ("angular", "angularjs"), "js"),
    "Svelte": SkillSpec("framework", ("svelte", "sveltekit"), "js"),
    "Node.js": SkillSpec("framework", ("node.js", "nodejs"), "js"),
    # Bare lowercase "express" is an ordinary English word; only the capitalised name counts
    "Express": SkillSpec("framework", ("express.js", "expressjs"), "js", case_sensitive_aliases=("Express",)),
    "NestJS": SkillSpec("framework", ("nestjs", "nest.js"), "js"),
    "Tailwind CSS": SkillSpec("web", ("tailwind", "tailwindcss", "tailwind css"), "js", min_lines=10),
    "Spring Boot": SkillSpec("framework", ("spring boot", "springboot", "spring framework", "spring mvc"), "java"),
    ".NET": SkillSpec("framework", (".net", "asp.net", ".net core", "dotnet"), "dotnet"),
    "Flutter": SkillSpec("framework", ("flutter",), "dart"),
    "Laravel": SkillSpec("framework", ("laravel",), "php"),
    "Ruby on Rails": SkillSpec("framework", ("ruby on rails", "rails"), "ruby"),
    "GraphQL": SkillSpec("api", ("graphql", "apollo"), None),
    # Data / ML
    "Pandas": SkillSpec("library", ("pandas",), "python"),
    "NumPy": SkillSpec("library", ("numpy",), "python"),
    "scikit-learn": SkillSpec("ml", ("scikit-learn", "sklearn", "scikit learn"), "python"),
    "TensorFlow": SkillSpec("ml", ("tensorflow", "keras"), "python"),
    "PyTorch": SkillSpec("ml", ("pytorch",), "python"),
    "Machine Learning": SkillSpec("ml", ("machine learning", "deep learning"), "python"),
    # Databases
    "PostgreSQL": SkillSpec("database", ("postgresql", "postgres", "psql")),
    "MySQL": SkillSpec("database", ("mysql", "mariadb")),
    "MongoDB": SkillSpec("database", ("mongodb", "mongo", "mongoose")),
    "Redis": SkillSpec("database", ("redis",)),
    "SQLite": SkillSpec("database", ("sqlite", "sqlite3")),
    "Firebase": SkillSpec("cloud", ("firebase", "firestore")),
    # DevOps / Cloud
    "Docker": SkillSpec("devops", ("docker", "containerization", "containerised", "containerized", "docker compose", "docker-compose")),
    "Kubernetes": SkillSpec("devops", ("kubernetes", "k8s", "helm")),
    "Terraform": SkillSpec("devops", ("terraform",)),
    "CI/CD": SkillSpec("devops", ("ci/cd", "github actions", "gitlab ci", "jenkins", "circleci", "continuous integration", "continuous delivery", "continuous deployment")),
    # "github"/"gitlab" deliberately excluded: nearly every resume links a GitHub profile
    "Git": SkillSpec("devops", ("git", "version control")),
    "AWS": SkillSpec("cloud", ("aws", "amazon web services", "ec2", "aws lambda")),
    "GCP": SkillSpec("cloud", ("gcp", "google cloud", "google cloud platform")),
    "Azure": SkillSpec("cloud", ("azure", "microsoft azure")),
    # Testing
    "Testing (pytest)": SkillSpec("testing", ("pytest", "unittest", "tdd", "test-driven development", "unit tests", "unit testing"), "python"),
    "Jest": SkillSpec("testing", ("jest", "vitest", "react testing library"), "js"),
    "Cypress": SkillSpec("testing", ("cypress",), "js"),
    "Playwright": SkillSpec("testing", ("playwright",), "js"),
    "Selenium": SkillSpec("testing", ("selenium",), None),
    "JUnit": SkillSpec("testing", ("junit",), "java"),
}

# Which detected test frameworks give credit to which ecosystem / testing skill
TEST_FRAMEWORK_ECOSYSTEM = {
    "pytest": "python",
    "unittest": "python",
    "jest": "js",
    "vitest": "js",
    "mocha": "js",
    "cypress": "js",
    "playwright": "js",
    "go test": "go",
    "junit": "java",
    "rspec": "ruby",
    "phpunit": "php",
    "cargo test": "rust",
    "xunit": "dotnet",
}

TESTING_SKILL_FRAMEWORKS = {
    "Testing (pytest)": {"pytest", "unittest"},
    "Jest": {"jest", "vitest"},
    "Cypress": {"cypress"},
    "Playwright": {"playwright"},
    "JUnit": {"junit"},
    "Selenium": {"selenium"},
}

_BOUNDARY_BEFORE = r"(?<![A-Za-z0-9_+#])"
_BOUNDARY_AFTER = r"(?![A-Za-z0-9_+#])"


def _alias_regex(alias: str, case_sensitive: bool = False) -> "re.Pattern[str]":
    body = re.escape(alias).replace(r"\ ", r"[\s\-]+")
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(_BOUNDARY_BEFORE + body + _BOUNDARY_AFTER, flags)


_ALIAS_PATTERNS: List[Tuple[str, "re.Pattern[str]"]] = []
_ALIAS_LOOKUP: Dict[str, str] = {}
for _name, _spec in SKILL_CATALOG.items():
    _ALIAS_LOOKUP[_name.lower()] = _name
    for _alias in _spec.aliases:
        _ALIAS_PATTERNS.append((_name, _alias_regex(_alias)))
        _ALIAS_LOOKUP.setdefault(_alias.lower(), _name)
    for _alias in _spec.case_sensitive_aliases:
        _ALIAS_PATTERNS.append((_name, _alias_regex(_alias, case_sensitive=True)))
        _ALIAS_LOOKUP.setdefault(_alias.lower(), _name)


def find_skill_mentions(text: str) -> Dict[str, List[Tuple[int, int]]]:
    """Return {canonical skill: [(start, end), ...]} for every catalog alias found in text."""
    found: Dict[str, List[Tuple[int, int]]] = {}
    for name, pattern in _ALIAS_PATTERNS:
        for m in pattern.finditer(text):
            found.setdefault(name, []).append((m.start(), m.end()))
    return found


def normalize_skill(name: str) -> str:
    """Map a free-form skill name (e.g. from an LLM) to its canonical catalog name when known."""
    cleaned = re.sub(r"\s+", " ", (name or "").strip())
    key = cleaned.lower()
    if key in _ALIAS_LOOKUP:
        return _ALIAS_LOOKUP[key]
    # Strip trailing qualifiers like "Python 3" / "React (hooks)"
    base = re.sub(r"[\s(].*$", "", key)
    if base in _ALIAS_LOOKUP and len(base) > 2:
        return _ALIAS_LOOKUP[base]
    return cleaned


def skill_spec(name: str) -> Optional[SkillSpec]:
    return SKILL_CATALOG.get(normalize_skill(name))


def category_for(name: str, fallback: str = "language") -> str:
    spec = skill_spec(name)
    return spec.category if spec else fallback


def min_lines_for(name: str) -> int:
    spec = skill_spec(name)
    if spec is None:
        return 50
    if spec.min_lines is not None:
        return spec.min_lines
    return DEFAULT_MIN_LINES.get(spec.category, 50)


def ecosystem_for(name: str) -> Optional[str]:
    spec = skill_spec(name)
    return spec.ecosystem if spec else None


def same_skill(a: str, b: str) -> bool:
    return normalize_skill(a).lower() == normalize_skill(b).lower()
