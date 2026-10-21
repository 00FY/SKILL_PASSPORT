"""
Standalone runner for candidate code. Started by sandbox.py as a separate, short-lived process:

    python -I -S -B sandbox_runner.py   (request JSON on stdin, results JSON on stdout)

It must not import anything from the app package: it only uses the standard library so it can also
run inside a bare container. The request never contains the expected test results, so whatever the
candidate code does in here, it can only influence its own return values, which the parent compares.
"""
import ast
import json
import sys

MAX_VALUE_CHARS = 20_000

SAFE_BUILTIN_NAMES = (
    "len", "range", "min", "max", "sum", "abs", "enumerate", "zip", "list", "dict", "set", "tuple",
    "sorted", "int", "str", "float", "bool", "all", "any", "round", "reversed", "map", "filter",
    "isinstance", "ValueError", "TypeError", "KeyError", "IndexError", "Exception",
)


def _apply_limits(cpu_seconds, memory_mb):
    # Kernel-enforced limits on POSIX. Windows has no resource module; there the parent's
    # wall-clock timeout and the loop counter are the limits (use Docker mode for real isolation).
    try:
        import resource
    except ImportError:
        return
    limits = [
        ("RLIMIT_CPU", cpu_seconds),
        ("RLIMIT_AS", memory_mb * 1024 * 1024),
        ("RLIMIT_FSIZE", 0),
        ("RLIMIT_NPROC", 0),
        ("RLIMIT_CORE", 0),
    ]
    for name, value in limits:
        rlimit = getattr(resource, name, None)
        if rlimit is None:
            continue
        try:
            resource.setrlimit(rlimit, (value, value))
        except (ValueError, OSError):
            pass


class _LoopLimiter(ast.NodeTransformer):
    """Puts an iteration counter call at the top of every loop body."""

    def _guard(self, node):
        self.generic_visit(node)
        node.body.insert(0, ast.Expr(value=ast.Call(
            func=ast.Name(id="__check_loop_iter__", ctx=ast.Load()), args=[], keywords=[]
        )))
        return node

    visit_For = _guard
    visit_While = _guard


class _TestTimeout(BaseException):
    pass


def _encode(value):
    try:
        text = json.dumps(value)
    except (TypeError, ValueError):
        return {"kind": "repr", "value": repr(value)[:200]}
    if len(text) > MAX_VALUE_CHARS:
        return {"kind": "error", "error": "Return value too large"}
    return {"kind": "json", "value": text}


def _run(request):
    try:
        tree = ast.parse(request["code"])
    except SyntaxError as e:
        return {"definition_error": f"SyntaxError on line {e.lineno}: {e.msg}"}
    tree = _LoopLimiter().visit(tree)
    ast.fix_missing_locations(tree)

    max_iters = int(request.get("max_loop_iterations", 200_000))
    counter = [0]

    def check_loop_iter():
        counter[0] += 1
        if counter[0] > max_iters:
            raise RuntimeError("Execution stopped: loop iteration limit exceeded")

    import builtins
    safe = {name: getattr(builtins, name) for name in SAFE_BUILTIN_NAMES}
    safe["__check_loop_iter__"] = check_loop_iter
    namespace = {"__builtins__": safe}
    try:
        exec(compile(tree, filename="<candidate_code>", mode="exec"), namespace)
    except Exception as e:
        return {"definition_error": f"Runtime error during definition: {type(e).__name__}: {e}"}

    fn_name = request["fn_name"]
    candidate_fn = namespace.get(fn_name)
    if not callable(candidate_fn):
        return {"definition_error": f"Function `{fn_name}` was not found or is not callable."}

    timeout = float(request.get("per_test_timeout", 2.0))
    signal = None
    try:
        import signal as _signal
        if hasattr(_signal, "setitimer"):
            signal = _signal

            def on_alarm(signum, frame):
                raise _TestTimeout()

            signal.signal(signal.SIGALRM, on_alarm)
    except ImportError:
        pass

    results = []
    for args in request["tests"]:
        counter[0] = 0
        try:
            if signal:
                signal.setitimer(signal.ITIMER_REAL, timeout)
            try:
                actual = candidate_fn(*args)
            finally:
                if signal:
                    signal.setitimer(signal.ITIMER_REAL, 0)
            results.append(_encode(actual))
        except _TestTimeout:
            results.append({"kind": "error", "error": f"Execution timed out (limit: {timeout}s)"})
        except Exception as e:
            results.append({"kind": "error", "error": f"{type(e).__name__}: {e}"})
    return {"results": results}


def main():
    out = sys.stdout
    request = json.loads(sys.stdin.read())
    _apply_limits(int(request.get("cpu_seconds", 5)), int(request.get("memory_mb", 256)))
    # Candidate code gets no print/open, but keep the result channel separate anyway
    sys.stdout = sys.stderr
    try:
        response = _run(request)
    except MemoryError:
        response = {"definition_error": "Execution stopped: memory limit exceeded"}
    except RecursionError:
        response = {"definition_error": "Execution stopped: recursion limit exceeded"}
    out.write(json.dumps(response))
    out.flush()


if __name__ == "__main__":
    main()
