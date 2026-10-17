"""
In-process background jobs for long-running analyses.

Cloning and blaming several repositories can take minutes, longer than browsers and proxies
will hold a request open, so the API queues the work and the client polls for the result.
State lives in memory: it is per server process and lost on restart.
"""
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

QUEUED, RUNNING, DONE, FAILED = "queued", "running", "done", "failed"


class QueueFullError(RuntimeError):
    pass


class JobFailure(Exception):
    """Raised by job functions to fail with a user-facing message and HTTP-style status."""

    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


@dataclass
class Job:
    id: str
    status: str = QUEUED
    message: str = "Waiting to start"
    created_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_status: Optional[int] = None


class JobManager:
    def __init__(self, workers: Optional[int] = None, max_pending: Optional[int] = None, ttl_s: Optional[float] = None):
        self.workers = workers or int(os.getenv("SKILL_PASSPORT_WORKERS", "2"))
        self.max_pending = max_pending or int(os.getenv("SKILL_PASSPORT_MAX_PENDING_JOBS", "20"))
        self.ttl_s = ttl_s or float(os.getenv("SKILL_PASSPORT_JOB_TTL_S", "3600"))
        self._executor = ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix="analysis")
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    def submit(self, fn: Callable[[Callable[[str], None]], Dict[str, Any]]) -> Job:
        """Queue `fn(progress)`. It returns the result dict or raises JobFailure."""
        with self._lock:
            self._purge_expired()
            pending = sum(1 for j in self._jobs.values() if j.status in (QUEUED, RUNNING))
            if pending >= self.max_pending:
                raise QueueFullError("The server is busy with other analyses. Please try again in a few minutes.")
            job = Job(id=uuid.uuid4().hex)
            self._jobs[job.id] = job
        self._executor.submit(self._run, job, fn)
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            self._purge_expired()
            job = self._jobs.get(job_id)
            if job and job.status == QUEUED:
                ahead = sum(1 for j in self._jobs.values() if j.status == QUEUED and j.created_at < job.created_at)
                job.message = f"Waiting in queue ({ahead} ahead)" if ahead else "Starting"
            return job

    def _run(self, job: Job, fn: Callable[[Callable[[str], None]], Dict[str, Any]]) -> None:
        def progress(message: str) -> None:
            job.message = message

        job.status = RUNNING
        job.message = "Starting"
        try:
            job.result = fn(progress)
            job.status = DONE
            job.message = "Finished"
        except JobFailure as exc:
            job.error, job.error_status, job.status = str(exc), exc.status, FAILED
        except Exception as exc:  # never let a worker die silently
            job.error, job.error_status, job.status = f"Analysis failed unexpectedly: {exc}", 500, FAILED
        finally:
            job.finished_at = time.time()

    def _purge_expired(self) -> None:
        cutoff = time.time() - self.ttl_s
        for job_id in [j.id for j in self._jobs.values() if j.finished_at and j.finished_at < cutoff]:
            del self._jobs[job_id]
