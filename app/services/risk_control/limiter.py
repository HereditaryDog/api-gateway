from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque


class TokenBucketLimiter:
    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self._tokens = float(capacity)
        self._updated_at = time.monotonic()
        self._lock = asyncio.Lock()

    async def allow(self) -> bool:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._updated_at
            self._updated_at = now
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
            if self._tokens >= 1:
                self._tokens -= 1
                return True
            return False


class SlidingWindowLimiter:
    def __init__(self, window_seconds: int = 60):
        self.window_seconds = window_seconds
        self._hits = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str, limit: int) -> bool:
        async with self._lock:
            now = time.monotonic()
            bucket = self._hits[key]
            cutoff = now - self.window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True
