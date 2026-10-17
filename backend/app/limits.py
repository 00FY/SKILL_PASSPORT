"""
Abuse protection for endpoints that make the server clone and analyse repositories.
"""
import hmac
import math
import os
import re
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional

from fastapi import HTTPException, Request

_PERIODS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}


def parse_rate(spec: str):
    """'20/hour' -> (20, 3600). '0' or 'off' disables limiting."""
    spec = (spec or "").strip().lower()
    if spec in ("", "0", "off", "none"):
        return 0, 1
    m = re.fullmatch(r"(\d+)\s*/\s*(second|minute|hour|day)", spec)
    if not m:
        raise ValueError(f"Invalid rate limit '{spec}'. Use e.g. '20/hour'.")
    return int(m.group(1)), _PERIODS[m.group(2)]


class RateLimiter:
    """Sliding-window limiter keyed by client address (in memory, per process)."""

    def __init__(self, limit: int, window_s: float):
        self.limit = limit
        self.window_s = window_s
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    @classmethod
    def from_env(cls, var: str, default: str) -> "RateLimiter":
        return cls(*parse_rate(os.getenv(var, default)))

    def hit(self, key: str) -> Optional[int]:
        """Record a request. Returns seconds to wait if the limit is exceeded, else None."""
        if self.limit <= 0:
            return None
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - self.window_s:
                hits.popleft()
            if len(hits) >= self.limit:
                return max(1, math.ceil(hits[0] + self.window_s - now))
            hits.append(now)
            return None


def client_key(request: Request) -> str:
    # Only trust X-Forwarded-For behind a reverse proxy you control, or clients can spoof it
    if os.getenv("SKILL_PASSPORT_TRUST_PROXY", "0") in ("1", "true", "yes"):
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce(limiter: RateLimiter, request: Request) -> None:
    retry_after = limiter.hit(client_key(request))
    if retry_after is not None:
        minutes = math.ceil(retry_after / 60)
        raise HTTPException(
            status_code=429,
            detail=f"Too many analyses from your address. Try again in {minutes} minute{'s' if minutes != 1 else ''}.",
            headers={"Retry-After": str(retry_after)},
        )


def require_api_key(request: Request) -> None:
    """If SKILL_PASSPORT_API_KEY is set, expensive endpoints need a matching X-API-Key header."""
    expected = os.getenv("SKILL_PASSPORT_API_KEY")
    if not expected:
        return
    supplied = request.headers.get("x-api-key", "")
    if not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="A valid API key is required (X-API-Key header).")
