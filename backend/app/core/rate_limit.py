"""Sliding window in-memory rate limiting dependency for FastAPI."""
from collections import defaultdict
from datetime import datetime, timezone
import threading
from typing import Dict, List

from fastapi import HTTPException, Request, status


class SlidingWindowStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._hits: Dict[str, List[float]] = defaultdict(list)

    def check(self, request: Request, max_requests: int, window_seconds: int) -> bool:
        forwarded = request.headers.get("X-Forwarded-For")
        client_ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
        user_key = f"{client_ip}:{request.url.path}"

        now = datetime.now(timezone.utc).timestamp()
        window_start = now - window_seconds

        with self._lock:
            valid_hits = [t for t in self._hits[user_key] if t > window_start]
            if len(valid_hits) >= max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Maximum {max_requests} requests per {window_seconds}s.",
                    headers={"Retry-After": str(window_seconds)},
                )
            valid_hits.append(now)
            self._hits[user_key] = valid_hits

        return True


_store = SlidingWindowStore()


def rate_limit_voice(request: Request) -> bool:
    """Rate limit voice assistant queries (max 20 req/min)."""
    return _store.check(request, max_requests=20, window_seconds=60)


def rate_limit_plan(request: Request) -> bool:
    """Rate limit route planning requests (max 40 req/min)."""
    return _store.check(request, max_requests=40, window_seconds=60)
