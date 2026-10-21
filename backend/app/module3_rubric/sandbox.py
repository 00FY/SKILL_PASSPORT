"""
Runs candidate code outside the API process.

Modes (SKILL_PASSPORT_SANDBOX):
- "process" (default): a separate Python process per submission, started in isolated mode (-I -S) with an
  empty environment, a throwaway working directory, kernel CPU/memory/file/process limits (POSIX) and a hard
  wall-clock timeout. Good for local use; on Windows the kernel limits are not available.
- "docker": the same runner inside a container with no network, a read-only filesystem, dropped capabilities,
  a non-root user and memory/pids limits. Use this for any server reachable by other people.

Expected results never enter the sandbox: it returns the candidate's values and this module compares them.
"""
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

RUNNER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sandbox_runner.py")
MAX_OUTPUT_BYTES = 1_000_000
MAX_CODE_CHARS = 20_000
STARTUP_ALLOWANCE_S = {"process": 3.0, "docker": 15.0}
MAX_WALL_TIMEOUT_S = 30.0


class SandboxUnavailable(RuntimeError):
    pass


@dataclass
class SandboxResult:
    # One entry per test: {"kind": "json"|"repr"|"error", "value"|"error": ...}
    results: List[Dict[str, Any]] = field(default_factory=list)
    definition_error: Optional[str] = None


class CodeSandbox:
    def __init__(self, mode: Optional[str] = None, per_test_timeout: float = 2.0, cpu_seconds: int = 5,
                 memory_mb: int = 256, max_loop_iterations: int = 200_000, max_concurrent: int = 4,
                 docker_image: Optional[str] = None):
        self.mode = (mode or os.getenv("SKILL_PASSPORT_SANDBOX", "process")).strip().lower()
        if self.mode not in ("process", "docker"):
            raise ValueError(f"Unknown sandbox mode '{self.mode}' (use 'process' or 'docker')")
        self.per_test_timeout = per_test_timeout
        self.cpu_seconds = cpu_seconds
        self.memory_mb = memory_mb
        self.max_loop_iterations = max_loop_iterations
        self.docker_image = docker_image or os.getenv("SKILL_PASSPORT_SANDBOX_IMAGE", "python:3.11-slim")
        # Bounds how many sandboxes one server runs at once, so a burst of submissions can't exhaust it
        self._slots = threading.BoundedSemaphore(max_concurrent)
        if self.mode == "process" and os.name == "nt":
            logger.warning("Sandbox: process mode on Windows has no kernel CPU/memory limits; "
                           "set SKILL_PASSPORT_SANDBOX=docker before exposing the server to others.")

    def run(self, code: str, fn_name: str, test_args: List[List[Any]],
            allowed_modules: Optional[List[str]] = None) -> SandboxResult:
        if len(code) > MAX_CODE_CHARS:
            return SandboxResult(definition_error=f"Submission too long (limit {MAX_CODE_CHARS} characters).")
        request = json.dumps({
            "code": code,
            "fn_name": fn_name,
            "tests": test_args,
            "per_test_timeout": self.per_test_timeout,
            "cpu_seconds": self.cpu_seconds,
            "memory_mb": self.memory_mb,
            "max_loop_iterations": self.max_loop_iterations,
            # Standard-library modules the code may import (none unless the caller allows some)
            "allowed_modules": sorted(allowed_modules or []),
        })
        wall_timeout = min(
            MAX_WALL_TIMEOUT_S,
            STARTUP_ALLOWANCE_S[self.mode] + self.per_test_timeout * max(1, len(test_args)),
        )
        if not self._slots.acquire(timeout=wall_timeout):
            raise SandboxUnavailable("Code runner is busy, please retry in a moment.")
        try:
            if self.mode == "docker":
                return self._run_docker(request, wall_timeout, len(test_args))
            return self._run_process(request, wall_timeout, len(test_args))
        finally:
            self._slots.release()

    def _run_process(self, request: str, wall_timeout: float, n_tests: int) -> SandboxResult:
        workdir = tempfile.mkdtemp(prefix="sp_sandbox_")
        env = {"PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1"}
        if os.name == "nt":
            # Python on Windows needs SYSTEMROOT to start
            env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")
        popen_kwargs: Dict[str, Any] = {}
        if os.name == "nt":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True
        try:
            proc = subprocess.Popen(
                [sys.executable, "-I", "-S", "-B", RUNNER_PATH],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                cwd=workdir, env=env, **popen_kwargs,
            )
            return self._collect(proc, request, wall_timeout, n_tests, kill=lambda: self._kill_process(proc))
        except OSError as e:
            raise SandboxUnavailable(f"Could not start code runner: {e}") from e
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def _run_docker(self, request: str, wall_timeout: float, n_tests: int) -> SandboxResult:
        docker = shutil.which("docker")
        if not docker:
            raise SandboxUnavailable("SKILL_PASSPORT_SANDBOX=docker but the docker command was not found.")
        name = f"sp-sandbox-{uuid.uuid4().hex[:12]}"
        cmd = [
            docker, "run", "--rm", "-i", "--name", name,
            "--network", "none", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--user", "65534:65534",
            "--memory", f"{self.memory_mb}m", "--memory-swap", f"{self.memory_mb}m",
            "--pids-limit", "16", "--cpus", "1", "--tmpfs", "/tmp:size=1m",
            "-v", f"{RUNNER_PATH}:/sandbox/runner.py:ro",
            self.docker_image, "python", "-I", "-S", "-B", "/sandbox/runner.py",
        ]

        def kill():
            subprocess.run([docker, "kill", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)

        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except OSError as e:
            raise SandboxUnavailable(f"Could not start docker: {e}") from e
        return self._collect(proc, request, wall_timeout, n_tests, kill=kill)

    def _collect(self, proc, request: str, wall_timeout: float, n_tests: int, kill) -> SandboxResult:
        try:
            stdout, _ = proc.communicate(request.encode(), timeout=wall_timeout)
        except subprocess.TimeoutExpired:
            kill()
            proc.kill()
            proc.communicate()
            return self._all_failed(n_tests, f"Execution timed out (limit: {self.per_test_timeout}s)")
        if len(stdout) > MAX_OUTPUT_BYTES:
            return self._all_failed(n_tests, "Output too large")
        try:
            response = json.loads(stdout.decode("utf-8")) if stdout else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            response = None
        if not isinstance(response, dict):
            # Killed by a CPU or memory limit, or crashed before answering
            return self._all_failed(n_tests, "Execution stopped: resource limit exceeded")
        if response.get("definition_error"):
            return SandboxResult(definition_error=str(response["definition_error"]))
        results = response.get("results")
        if not isinstance(results, list) or len(results) != n_tests:
            return self._all_failed(n_tests, "Execution stopped: invalid runner response")
        return SandboxResult(results=results)

    @staticmethod
    def _kill_process(proc):
        try:
            if os.name == "nt":
                proc.kill()
            else:
                os.killpg(proc.pid, 9)
        except (ProcessLookupError, PermissionError, OSError):
            pass

    @staticmethod
    def _all_failed(n_tests: int, message: str) -> SandboxResult:
        return SandboxResult(results=[{"kind": "error", "error": message} for _ in range(n_tests)])

    @staticmethod
    def decode(entry: Dict[str, Any]):
        """Returns (ok, value_or_error) for one runner entry."""
        if entry.get("kind") == "json":
            try:
                return True, json.loads(entry.get("value", "null"))
            except (TypeError, json.JSONDecodeError):
                return False, "Invalid return value"
        if entry.get("kind") == "repr":
            return True, entry.get("value")
        return False, entry.get("error", "Unknown error")
