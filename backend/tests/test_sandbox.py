import os
import time

import pytest

from app.module3_rubric.adaptive_engine import AdaptiveAssessmentEngine
from app.module3_rubric.sandbox import CodeSandbox, SandboxUnavailable

posix_only = pytest.mark.skipif(os.name == "nt", reason="kernel resource limits are POSIX-only")


@pytest.fixture
def engine():
    return AdaptiveAssessmentEngine(sandbox=CodeSandbox(mode="process", per_test_timeout=1.0, memory_mb=256))


def test_code_runs_in_a_separate_process(engine):
    # A plain value round-trips; the API process id is never visible to candidate code
    code = "def f(x):\n    return x * 2\n"
    score, results, _ = engine._evaluate_code_safely(code, "f", [{"args": [21], "expected": 42}])
    assert score == 1.0
    assert results[0]["passed"] is True


def test_expected_values_never_enter_the_sandbox():
    sandbox = CodeSandbox(mode="process")
    captured = {}
    original = sandbox._run_process

    def spy(request, wall_timeout, n_tests):
        captured["request"] = request
        return original(request, wall_timeout, n_tests)

    sandbox._run_process = spy
    AdaptiveAssessmentEngine(sandbox=sandbox)._evaluate_code_safely(
        "def f(x):\n    return x\n", "f", [{"args": [1], "expected": "SECRET-EXPECTED-VALUE"}]
    )
    assert "SECRET-EXPECTED-VALUE" not in captured["request"]


@posix_only
def test_cpu_heavy_code_without_loops_is_stopped(engine):
    code = "def f():\n    return 10 ** (10 ** 9)\n"
    started = time.monotonic()
    score, results, _ = engine._evaluate_code_safely(code, "f", [{"args": [], "expected": 0}])
    assert score == 0.0
    assert results[0]["passed"] is False
    assert time.monotonic() - started < 15


@posix_only
def test_memory_exhaustion_is_stopped(engine):
    code = "def f():\n    return len([0] * (10 ** 10))\n"
    score, results, _ = engine._evaluate_code_safely(code, "f", [{"args": [], "expected": 0}])
    assert score == 0.0
    assert results[0]["passed"] is False


def test_deep_recursion_fails_cleanly(engine):
    code = "def f(n):\n    return f(n + 1)\n"
    score, results, _ = engine._evaluate_code_safely(code, "f", [{"args": [0], "expected": 0}])
    assert score == 0.0
    assert "RecursionError" in results[0]["error"]


def test_swallowed_timeouts_still_hit_the_wall_clock_limit(engine):
    # The bare except swallows the in-process timeout and recursion errors, so only the
    # parent's wall-clock kill (or the CPU limit) can stop this
    code = (
        "def f():\n"
        "    try:\n"
        "        return f()\n"
        "    except:\n"
        "        return f()\n"
    )
    started = time.monotonic()
    score, results, _ = engine._evaluate_code_safely(code, "f", [{"args": [], "expected": 0}])
    assert score == 0.0
    assert results[0]["passed"] is False
    assert results[0]["error"] in (
        "Execution timed out (limit: 1.0s)", "Execution stopped: resource limit exceeded"
    )
    assert time.monotonic() - started < 15


def test_later_tests_still_run_after_one_fails(engine):
    code = "def f(x):\n    return 10 // x\n"
    tests = [{"args": [0], "expected": 0}, {"args": [5], "expected": 2}]
    score, results, _ = engine._evaluate_code_safely(code, "f", tests)
    assert score == 0.5
    assert "ZeroDivisionError" in results[0]["error"]
    assert results[1]["passed"] is True


def test_non_json_return_value_never_matches(engine):
    code = "def f():\n    return {1, 2}\n"
    score, results, _ = engine._evaluate_code_safely(code, "f", [{"args": [], "expected": "{1, 2}"}])
    assert score == 0.0
    assert results[0]["passed"] is False


def test_oversized_submission_is_rejected(engine):
    code = "def f():\n    return 1\n" + "#" * 25_000
    score, _, msg = engine._evaluate_code_safely(code, "f", [{"args": [], "expected": 1}])
    assert score == 0.0
    assert "too long" in msg


def test_unknown_mode_is_refused():
    with pytest.raises(ValueError):
        CodeSandbox(mode="inline")


def test_docker_mode_without_docker_reports_unavailable(monkeypatch):
    monkeypatch.setattr("app.module3_rubric.sandbox.shutil.which", lambda name: None)
    with pytest.raises(SandboxUnavailable):
        CodeSandbox(mode="docker").run("def f():\n    return 1\n", "f", [[]])
