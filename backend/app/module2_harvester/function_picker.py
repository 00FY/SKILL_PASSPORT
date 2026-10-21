"""
Finds functions the candidate wrote, for "Defend Your Code" questions.

Selection is static (blame line ownership + parsing): Python through its AST, brace languages (JavaScript,
TypeScript, Java, Go, C#, Kotlin, Rust, C/C++, PHP, Swift, Dart, Scala) through function-header patterns
and brace matching. Every picked function can be asked about statically (a hidden line, its name); Python
functions that can run on their own also carry what the sandbox needs to ask what a call returns.
"""
import ast
import copy
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .constants import CODE_EXTENSIONS

MIN_FUNCTION_LINES = 8
MAX_FUNCTION_LINES = 60
MIN_OWNERSHIP = 0.6
MAX_PER_REPO = 25
MAX_FILE_BYTES = 200_000
MAX_CONSTANT_LINES = 400
MAX_CONSTANT_CHARS = 40_000
MAX_LITERALS = 6

BRACE_LANGUAGES = {"JavaScript", "TypeScript", "Java", "Kotlin", "Go", "Rust", "C", "C++", "C#", "Swift", "PHP",
                   "Scala", "Dart"}
QUIZ_LANGUAGES = BRACE_LANGUAGES | {"Python"}

LOGIC_NODES = (ast.If, ast.For, ast.While, ast.Try, ast.ListComp, ast.DictComp, ast.SetComp,
               ast.GeneratorExp, ast.BoolOp, ast.IfExp)
# Constructs that keep a function from running on its own in the sandbox (it can still be asked about)
NOT_RUNNABLE_NODES = (ast.Global, ast.Nonlocal, ast.Yield, ast.YieldFrom, ast.Await, ast.Import, ast.ImportFrom,
                      ast.AsyncFunctionDef, ast.ClassDef)
NONDETERMINISTIC_CALLS = {"now", "today", "utcnow", "time", "random", "randint", "choice", "shuffle", "uuid4",
                          "perf_counter", "monotonic", "getenv", "input"}
BRACE_LOGIC_RE = re.compile(r"\b(if|for|while|switch|case|catch|foreach|match|when)\b|\?|&&|\|\||=>")
BRACE_KEYWORDS = {"if", "for", "while", "switch", "catch", "return", "else", "do", "try", "function", "new",
                  "typeof", "sizeof", "await", "yield", "using", "lock", "foreach", "when", "match",
                  "synchronized", "with", "elif", "case", "throw", "delete", "in", "of"}
TYPE_DECLARATION_RE = re.compile(r"^\s*(?:[\w@]+\s+)*(?:class|interface|object|struct|enum|record|trait|impl|"
                                 r"namespace|module|extension|protocol|mixin)\b")
HEADER_PATTERNS = [
    re.compile(r"\bfunction\s*\*?\s*([A-Za-z_$][\w$]*)\s*(?:<[^>]*>)?\s*\("),                    # JS, TS, PHP
    re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*(?:async\s+)?"
               r"(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*(?::\s*[^=]+?)?=>\s*\{"),                         # arrow functions
    re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*[\[(<]"),                           # Go, Swift
    re.compile(r"\bfn\s+([A-Za-z_]\w*)\s*[<(]"),                                                  # Rust
    re.compile(r"\bfun\s+(?:<[^>]*>\s*)?(?:[\w.]+\.)?([A-Za-z_]\w*)\s*\("),                       # Kotlin
    re.compile(r"^\s*(?:override\s+)?def\s+([A-Za-z_]\w*)\s*[\[(]"),                              # Scala
    re.compile(r"^\s*(?:(?:public|private|protected|internal|static|final|abstract|override|virtual|async|"
               r"export|default|readonly|synchronized|inline|constexpr|unsafe|extern|const)\s+)*"
               r"(?:[\w<>\[\]?,.*&:]+\s+)*([A-Za-z_]\w*)\s*\([^;{}]*\)\s*(?::\s*[^{;=]+)?"
               r"(?:throws\s+[\w.,\s]+)?\s*\{\s*$"),                                              # methods
]


def _is_test_or_generated(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").lower().split("/")
    name = parts[-1]
    stem = name.rsplit(".", 1)[0]
    return (
        name.startswith("test_") or stem.endswith(("_test", ".test", ".spec", "test", "tests", "_spec"))
        or name in ("conftest.py", "setup.py", "manage.py")
        or any(p in ("tests", "test", "__tests__", "spec", "migrations", "alembic") for p in parts[:-1])
    )


# --- Python ------------------------------------------------------------------------------------------------

class _StripAnnotations(ast.NodeTransformer):
    """Type hints don't change what a function returns, and their names may not exist in the sandbox."""

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        node.returns = None
        for a in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
            a.annotation = None
        return node

    def visit_AnnAssign(self, node):
        if node.value is None:
            return ast.Pass()
        return ast.Assign(targets=[node.target], value=node.value)


def strip_annotations(fn: ast.FunctionDef) -> ast.FunctionDef:
    return ast.fix_missing_locations(_StripAnnotations().visit(copy.deepcopy(fn)))


def free_names(fn: ast.FunctionDef) -> List[str]:
    """Names the function reads but never binds itself (module globals, imports, builtins)."""
    fn = strip_annotations(fn)
    bound = {a.arg for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs}
    loaded = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Name):
            (bound.add if isinstance(node.ctx, (ast.Store, ast.Del)) else loaded.add)(node.id)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, ast.FunctionDef) and node is not fn:
            bound.add(node.name)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
    return sorted(loaded - bound)


def _dict_keys_read(fn: ast.FunctionDef, param: str) -> List[str]:
    """String keys the function reads from a parameter: param["key"] and param.get("key")."""
    keys: List[str] = []
    for node in ast.walk(fn):
        key = None
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == param:
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                key = node.slice.value
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get"
              and isinstance(node.func.value, ast.Name) and node.func.value.id == param
              and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
            key = node.args[0].value
        if key and key not in keys:
            keys.append(key)
    return keys[:12]


def _literals(nodes: List[ast.AST]) -> Dict[str, List[Any]]:
    """Short strings and small ints from the code itself: realistic inputs (e.g. a lookup table's keys)."""
    strings: List[str] = []
    ints: List[int] = []
    for root in nodes:
        for node in ast.walk(root):
            if isinstance(node, ast.Dict):
                for k in node.keys:
                    if isinstance(k, ast.Constant) and isinstance(k.value, str) and 1 <= len(k.value) <= 40:
                        if k.value not in strings:
                            strings.append(k.value)
            elif isinstance(node, ast.Compare):
                operands = [node.left] + node.comparators
                operands += [e for c in operands if isinstance(c, (ast.Tuple, ast.List, ast.Set)) for e in c.elts]
                for c in operands:
                    if isinstance(c, ast.Constant) and isinstance(c.value, str) and 1 <= len(c.value) <= 40:
                        if c.value not in strings:
                            strings.append(c.value)
                    elif isinstance(c, ast.Constant) and type(c.value) is int and abs(c.value) <= 10_000:
                        if c.value not in ints:
                            ints.append(c.value)
    return {"str": strings[:MAX_LITERALS], "int": ints[:MAX_LITERALS]}


def _module_context(tree: ast.Module):
    """Literal module constants, top-level functions and imports by name, so they can travel with a function."""
    constants: Dict[str, str] = {}
    functions: Dict[str, ast.FunctionDef] = {}
    imports: Dict[str, Tuple[str, str]] = {}  # bound name -> (top-level module, import statement)
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if len(targets) != 1 or not isinstance(targets[0], ast.Name) or node.value is None:
                continue
            span = (node.end_lineno or node.lineno) - node.lineno + 1
            try:
                ast.literal_eval(node.value)
            except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
                continue
            text = f"{targets[0].id} = {ast.unparse(node.value)}"
            if span <= MAX_CONSTANT_LINES and len(text) <= MAX_CONSTANT_CHARS:
                constants[targets[0].id] = text
        elif isinstance(node, ast.FunctionDef) and not node.decorator_list:
            functions[node.name] = node
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                stmt = f"import {alias.name}" + (f" as {alias.asname}" if alias.asname else "")
                imports[bound] = (alias.name.split(".")[0], stmt)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for alias in node.names:
                if alias.name == "*":
                    continue
                bound = alias.asname or alias.name
                stmt = f"from {node.module} import {alias.name}" + (f" as {alias.asname}" if alias.asname else "")
                imports[bound] = (node.module.split(".")[0], stmt)
    return constants, functions, imports


def _resolve(fn: ast.FunctionDef, constants, functions, imports):
    """Returns (import statements, context definitions in dependency order, imported roots, unresolved names)."""
    context: List[str] = []
    import_stmts: List[str] = []
    roots: List[str] = []
    seen = {fn.name}
    unresolved = set()

    def visit(node: ast.FunctionDef, depth: int):
        for name in free_names(node):
            if name in seen:
                continue
            seen.add(name)
            if name in constants:
                context.append(constants[name])
            elif name in imports:
                root, stmt = imports[name]
                import_stmts.append(stmt)
                if root not in roots:
                    roots.append(root)
            elif name in functions and depth < 2:
                helper = functions[name]
                if any(isinstance(n, NOT_RUNNABLE_NODES) for n in ast.walk(helper)):
                    unresolved.add(name)
                    continue
                visit(helper, depth + 1)
                context.append(ast.unparse(strip_annotations(helper)))
            else:
                unresolved.add(name)

    visit(fn, 0)
    return import_stmts, context, roots, sorted(unresolved)


def _param_info(fn: ast.FunctionDef, constants: Optional[Dict[str, str]] = None) -> Optional[List[Dict[str, Any]]]:
    args = fn.args
    if args.vararg or args.kwarg or args.kwonlyargs or args.posonlyargs:
        return None
    params = []
    defaults = [None] * (len(args.args) - len(args.defaults)) + list(args.defaults)
    for arg, default in zip(args.args, defaults):
        info: Dict[str, Any] = {"name": arg.arg, "annotation": ast.unparse(arg.annotation) if arg.annotation else ""}
        if default is not None:
            try:
                if isinstance(default, ast.Name) and constants and default.id in constants:
                    # A default that names a literal module constant, e.g. size=DEFAULT_PAGE_SIZE
                    info["default"] = ast.literal_eval(constants[default.id].split(" = ", 1)[1])
                else:
                    info["default"] = ast.literal_eval(default)
            except (ValueError, SyntaxError, IndexError):
                return None
        params.append(info)
    if not 1 <= len(params) <= 3 or params[0]["name"] in ("self", "cls"):
        return None
    return params


def _unsafe_to_run(fn: ast.FunctionDef) -> bool:
    """Dunder access or time/randomness: never run (dunders) or no single right answer (time, randomness)."""
    for node in ast.walk(fn):
        if isinstance(node, ast.Attribute) and (node.attr.startswith("__") or node.attr in NONDETERMINISTIC_CALLS):
            return True
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            return True
    return False


def _python_functions(source: str, rel_path: str, owned: Optional[set], repo_url: str, commit: str):
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    lines = source.splitlines()
    constants, functions, imports = _module_context(tree)

    candidates: List[Tuple[ast.FunctionDef, bool]] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            candidates.append((node, True))
        elif isinstance(node, ast.ClassDef):
            candidates += [(n, False) for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

    picked: List[Dict[str, Any]] = []
    for node, top_level in candidates:
        start, end = node.lineno, node.end_lineno or node.lineno
        if node.decorator_list:
            start = min(d.lineno for d in node.decorator_list)
        entry = _common_entry(lines, start, end, owned, rel_path, repo_url, commit, node.name, "Python")
        if entry is None:
            continue
        walked = list(ast.walk(node))
        if not any(isinstance(n, LOGIC_NODES) for n in walked):
            continue
        # Signature (and decorators) up to the first body statement; the docstring, if any
        body_first = node.body[0]
        doc_lines: List[int] = []
        if isinstance(body_first, ast.Expr) and isinstance(getattr(body_first, "value", None), ast.Constant) \
                and isinstance(body_first.value.value, str):
            doc_lines = list(range(body_first.lineno - start, (body_first.end_lineno or body_first.lineno) - start + 1))
        entry["header_lines"] = max(1, body_first.lineno - start)
        entry["doc_lines"] = doc_lines

        params = _param_info(node, constants) if top_level and isinstance(node, ast.FunctionDef) else None
        runnable = (
            params is not None and not node.decorator_list
            and not any(isinstance(n, NOT_RUNNABLE_NODES) for n in walked)
            and any(isinstance(n, ast.Return) and n.value is not None for n in walked)
            and not _unsafe_to_run(node)
        )
        entry["runnable_candidate"] = runnable
        if runnable:
            for p in params:
                keys = _dict_keys_read(node, p["name"])
                if keys:
                    p["dict_keys"] = keys
            import_stmts, context, roots, unresolved = _resolve(node, constants, functions, imports)
            entry.update({
                "context": context,
                "exec_source": "\n\n".join(import_stmts + context + [ast.unparse(strip_annotations(node))]),
                "params": params,
                "free_names": unresolved,
                "import_roots": roots,
                "literals": _literals([node] + [ast.parse(c) for c in context]),
            })
        picked.append(entry)
    return picked


# --- Brace languages ---------------------------------------------------------------------------------------

def _match_braces(lines: List[str], line_idx: int, col: int) -> Optional[int]:
    """Index of the line holding the brace that closes the one at (line_idx, col); skips strings and comments."""
    depth = 0
    in_block_comment = False
    for i in range(line_idx, min(len(lines), line_idx + MAX_FUNCTION_LINES * 2)):
        text = lines[i]
        j = col if i == line_idx else 0
        quote = None
        while j < len(text):
            ch = text[j]
            nxt = text[j + 1] if j + 1 < len(text) else ""
            if in_block_comment:
                if ch == "*" and nxt == "/":
                    in_block_comment = False
                    j += 1
            elif quote:
                if ch == "\\":
                    j += 1
                elif ch == quote:
                    quote = None
            elif ch == "/" and nxt == "/":
                break
            elif ch == "/" and nxt == "*":
                in_block_comment = True
                j += 1
            elif ch in "\"'`":
                quote = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
            j += 1
    return None


def _brace_functions(source: str, rel_path: str, owned: Optional[set], repo_url: str, commit: str, language: str):
    lines = source.splitlines()
    picked: List[Dict[str, Any]] = []
    i = 0
    while i < len(lines):
        text = lines[i]
        name = None
        for pattern in HEADER_PATTERNS:
            m = pattern.search(text)
            if m and m.group(1) not in BRACE_KEYWORDS:
                name = m.group(1)
                break
        if not name or text.lstrip().startswith(("//", "*", "/*", "#", "}")) or TYPE_DECLARATION_RE.match(text):
            i += 1
            continue
        # The body's opening brace: on the header line or within the next few lines
        open_at = None
        for k in range(i, min(len(lines), i + 4)):
            col = lines[k].find("{", m.start(1) if k == i else 0)
            if col >= 0:
                open_at = (k, col)
                break
            if lines[k].rstrip().endswith(";"):
                break
        if open_at is None:
            i += 1
            continue
        end = _match_braces(lines, *open_at)
        if end is None:
            i += 1
            continue
        start = i + 1
        entry = _common_entry(lines, start, end + 1, owned, rel_path, repo_url, commit, name, language)
        if entry is not None and BRACE_LOGIC_RE.search("\n".join(lines[open_at[0] + 1:end])):
            entry["header_lines"] = open_at[0] - i + 1
            entry["doc_lines"] = []
            entry["runnable_candidate"] = False
            picked.append(entry)
        i = end + 1 if entry is not None else i + 1
    return picked


# --- Shared ------------------------------------------------------------------------------------------------

def _common_entry(lines, start: int, end: int, owned: Optional[set], rel_path: str, repo_url: str, commit: str,
                  name: str, language: str) -> Optional[Dict[str, Any]]:
    code_lines = [n for n in range(start, end + 1) if n - 1 < len(lines) and lines[n - 1].strip()]
    if not MIN_FUNCTION_LINES <= len(code_lines) <= MAX_FUNCTION_LINES:
        return None
    ownership = 1.0 if owned is None else sum(1 for n in code_lines if n in owned) / len(code_lines)
    if ownership < MIN_OWNERSHIP:
        return None
    return {
        "repo_url": repo_url,
        "commit": commit,
        "path": rel_path,
        "name": name,
        "line": start,
        "language": language,
        "source": "\n".join(lines[start - 1:end]),
        "ownership": round(ownership, 2),
    }


def functions_from_source(source: str, rel_path: str, owned: Optional[set], repo_url: str,
                          commit: str, language: Optional[str] = None) -> List[Dict[str, Any]]:
    """Qualifying functions in one file. owned=None treats every line as the candidate's."""
    language = language or CODE_EXTENSIONS.get(os.path.splitext(rel_path)[1].lower())
    if language == "Python":
        return _python_functions(source, rel_path, owned, repo_url, commit)
    if language in BRACE_LANGUAGES:
        return _brace_functions(source, rel_path, owned, repo_url, commit, language)
    return []


def pick_functions(repo_path: str, per_file: Dict[str, Dict[str, Any]], repo_url: str,
                   commit: str) -> List[Dict[str, Any]]:
    picked: List[Dict[str, Any]] = []
    per_language: Dict[str, int] = {}
    for rel_path in sorted(per_file):
        info = per_file[rel_path]
        owned = set(info.get("candidate_lines") or [])
        language = info.get("lang")
        if not owned or language not in QUIZ_LANGUAGES or _is_test_or_generated(rel_path):
            continue
        if per_language.get(language, 0) >= MAX_PER_REPO:
            continue
        full_path = os.path.join(repo_path, rel_path)
        try:
            if os.path.getsize(full_path) > MAX_FILE_BYTES:
                continue
            with open(full_path, "r", encoding="utf-8") as f:
                source = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        found = functions_from_source(source, rel_path, owned, repo_url, commit, language)
        found = found[:MAX_PER_REPO - per_language.get(language, 0)]
        per_language[language] = per_language.get(language, 0) + len(found)
        picked.extend(found)
    return picked
