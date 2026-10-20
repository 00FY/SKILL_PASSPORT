"""
Finds Python functions the candidate wrote, for "Defend Your Code" questions.

Selection is static (AST + blame line ownership). Whether a function can actually run on its own is
decided later, in the sandbox, by module3_rubric/defend_your_code.py.
"""
import ast
import os
from typing import Any, Dict, List, Optional

MIN_FUNCTION_LINES = 8
MAX_FUNCTION_LINES = 60
MIN_OWNERSHIP = 0.6
MAX_PER_REPO = 8
MAX_FILE_BYTES = 200_000
MAX_CONSTANT_LINES = 400
MAX_CONSTANT_CHARS = 40_000
MAX_LITERALS = 6
LOGIC_NODES = (ast.If, ast.For, ast.While, ast.Try, ast.ListComp, ast.DictComp, ast.SetComp,
               ast.GeneratorExp, ast.BoolOp, ast.IfExp)
DISALLOWED_NODES = (ast.Global, ast.Nonlocal, ast.Yield, ast.YieldFrom, ast.Await, ast.Import, ast.ImportFrom,
                    ast.AsyncFunctionDef, ast.ClassDef)


def _is_test_or_generated(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").lower().split("/")
    name = parts[-1]
    return (
        name.startswith("test_") or name.endswith("_test.py") or name in ("conftest.py", "setup.py", "manage.py")
        or any(p in ("tests", "test", "migrations", "alembic") for p in parts[:-1])
    )


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
    import copy
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


def _module_context(tree: ast.Module, lines: List[str]):
    """Literal module constants and top-level functions, by name, so helpers can travel with a function."""
    constants: Dict[str, str] = {}
    functions: Dict[str, ast.FunctionDef] = {}
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
    return constants, functions


def _resolve(fn: ast.FunctionDef, constants: Dict[str, str], functions: Dict[str, ast.FunctionDef]):
    """Returns (context definitions in dependency order, names still unresolved)."""
    context: List[str] = []
    seen = {fn.name}
    unresolved = set()

    def visit(node: ast.FunctionDef, depth: int):
        for name in free_names(node):
            if name in seen:
                continue
            seen.add(name)
            if name in constants:
                context.append(constants[name])
            elif name in functions and depth < 2:
                helper = functions[name]
                if any(isinstance(n, DISALLOWED_NODES) for n in ast.walk(helper)):
                    unresolved.add(name)
                    continue
                visit(helper, depth + 1)
                context.append(ast.unparse(strip_annotations(helper)))
            else:
                unresolved.add(name)

    visit(fn, 0)
    return context, sorted(unresolved)


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


def pick_functions(repo_path: str, per_file: Dict[str, Dict[str, Any]], repo_url: str,
                   commit: str) -> List[Dict[str, Any]]:
    picked: List[Dict[str, Any]] = []
    for rel_path in sorted(per_file):
        info = per_file[rel_path]
        owned = set(info.get("candidate_lines") or [])
        if not owned or info.get("lang") != "Python" or _is_test_or_generated(rel_path):
            continue
        full_path = os.path.join(repo_path, rel_path)
        try:
            if os.path.getsize(full_path) > MAX_FILE_BYTES:
                continue
            with open(full_path, "r", encoding="utf-8") as f:
                source = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        picked.extend(functions_from_source(source, rel_path, owned, repo_url, commit))
        if len(picked) >= MAX_PER_REPO:
            return picked[:MAX_PER_REPO]
    return picked


def functions_from_source(source: str, rel_path: str, owned: Optional[set], repo_url: str,
                          commit: str) -> List[Dict[str, Any]]:
    """Qualifying top-level functions in one file. owned=None treats every line as the candidate's."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    lines = source.splitlines()
    constants, functions = _module_context(tree, lines)
    picked: List[Dict[str, Any]] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.decorator_list:
            continue
        start, end = node.lineno, node.end_lineno or node.lineno
        code_lines = [n for n in range(start, end + 1) if lines[n - 1].strip()]
        if not MIN_FUNCTION_LINES <= len(code_lines) <= MAX_FUNCTION_LINES:
            continue
        ownership = 1.0 if owned is None else sum(1 for n in code_lines if n in owned) / len(code_lines)
        if ownership < MIN_OWNERSHIP:
            continue
        walked = list(ast.walk(node))
        if any(isinstance(n, DISALLOWED_NODES) for n in walked):
            continue
        if not any(isinstance(n, LOGIC_NODES) for n in walked):
            continue
        if not any(isinstance(n, ast.Return) and n.value is not None for n in walked):
            continue
        params = _param_info(node, constants)
        if params is None:
            continue
        for p in params:
            keys = _dict_keys_read(node, p["name"])
            if keys:
                p["dict_keys"] = keys
        context, unresolved = _resolve(node, constants, functions)
        literal_sources = [node] + [ast.parse(c) for c in context]
        picked.append({
            "repo_url": repo_url,
            "commit": commit,
            "path": rel_path,
            "name": node.name,
            "line": start,
            "source": "\n".join(lines[start - 1:end]),
            "context": context,
            "exec_source": "\n\n".join(context + [ast.unparse(strip_annotations(node))]),
            "params": params,
            "free_names": unresolved,
            "literals": _literals(literal_sources),
            "ownership": round(ownership, 2),
        })
    return picked
