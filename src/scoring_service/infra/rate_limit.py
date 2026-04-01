from __future__ import annotations
import time
from collections import defaultdict, deque
from fastapi import HTTPException, Request, status
from scoring_service.config import Settings

class InMemoryRateLimiter:
    def __init__(self):
        self._events: dict[str, deque[float]] = defaultdict(deque)
    def check(self, key: str, *, limit: int, window_seconds: int) -> None:
        now = time.time()
        bucket = self._events[key]
        while bucket and bucket[0] <= now - window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="rate limit exceeded")
        bucket.append(now)

rate_limiter = InMemoryRateLimiter()

async def enforce_rate_limit(request: Request) -> None:
    settings: Settings = request.app.state.settings
    client_ip = request.client.host if request.client else "unknown"
    rate_limiter.check(f"{client_ip}:{request.url.path}",
        limit=settings.rate_limit_requests, window_seconds=settings.rate_limit_window_seconds)
