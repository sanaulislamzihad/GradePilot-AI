"""Sliding-window rate limiters.

`MemoryLimiter` counts within one process, which is enough for a single API
worker. With several workers (or several containers) each process would allow
the full limit, so production uses `RedisLimiter`, which keeps one shared count
per key in Redis. If Redis cannot be reached the limiter lets requests through
and logs the problem: an outage of the limiter must not lock everyone out.
"""

import logging
import math
import threading
import time
import uuid
from collections import defaultdict, deque
from typing import Protocol

logger = logging.getLogger("gradepilot.rate_limit")


class Limiter(Protocol):
    max_attempts: int
    window_seconds: int

    def hit(self, key: str) -> int | None:
        """Record an attempt. Returns seconds to wait if the key is over the limit."""

    def reset(self, key: str | None = None) -> None: ...


class MemoryLimiter:
    def __init__(self, name: str, max_attempts: int, window_seconds: int) -> None:
        self.name = name
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str) -> int | None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window_seconds:
                hits.popleft()
            if len(hits) >= self.max_attempts:
                return int(self.window_seconds - (now - hits[0])) + 1
            hits.append(now)
            return None

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)


# Atomic check-and-record on a sorted set of attempt timestamps.
# Returns -1 when the attempt is allowed, otherwise the seconds to wait.
_SLIDING_WINDOW = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
if redis.call('ZCARD', key) >= limit then
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  return math.floor(window - (now - tonumber(oldest[2]))) + 1
end
redis.call('ZADD', key, now, ARGV[4])
redis.call('EXPIRE', key, math.ceil(window))
return -1
"""


class RedisLimiter:
    def __init__(self, name: str, max_attempts: int, window_seconds: int, client) -> None:
        self.name = name
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._client = client
        self._script = client.register_script(_SLIDING_WINDOW)
        self._warned_at = 0.0

    def _key(self, key: str) -> str:
        return f"gradepilot:ratelimit:{self.name}:{key}"

    def hit(self, key: str) -> int | None:
        try:
            result = int(self._script(
                keys=[self._key(key)],
                args=[time.time(), self.window_seconds, self.max_attempts, uuid.uuid4().hex],
            ))
        except Exception as exc:  # noqa: BLE001 - any Redis failure: allow, and say so
            now = time.monotonic()
            if now - self._warned_at > 60:
                self._warned_at = now
                logger.error("Rate limiter unavailable, allowing requests: %s", type(exc).__name__)
            return None
        return None if result < 0 else max(1, math.ceil(result))

    def reset(self, key: str | None = None) -> None:
        pattern = self._key(key) if key else self._key("*")
        for found in self._client.scan_iter(match=pattern):
            self._client.delete(found)


def build_limiter(name: str, max_attempts: int, window_seconds: int, redis_url: str = "") -> Limiter:
    if not redis_url:
        return MemoryLimiter(name, max_attempts, window_seconds)
    import redis

    client = redis.Redis.from_url(redis_url, socket_timeout=0.5, socket_connect_timeout=0.5)
    return RedisLimiter(name, max_attempts, window_seconds, client)
