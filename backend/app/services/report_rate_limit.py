"""Redis-backed fixed-window rate limits for report GraphQL mutations, with in-process fallback.

Production: point REDIS_URL at a shared Redis so limits apply across all API workers.
If Redis is unavailable, the in-process store is used (best-effort; not reliable with
multiple workers or restarts — see docs/README).
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from typing import Literal, Optional

import redis
from redis.exceptions import RedisError
from strawberry.exceptions import GraphQLError

from app.core.config import settings

logger = logging.getLogger("trailintel.ratelimit")

MutationKind = Literal["submit", "upvote"]

# Lua: INCR key, EXPIRE on first use (fixed window from first hit in this window)
_INCR_EXPIRE_LUA = """
local c = redis.call('INCR', KEYS[1])
if c == 1 then
  redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
end
return c
"""

_redis_conn: Optional[redis.Redis] = None
_redis_probe_done = False
_lock = threading.Lock()
_memory: dict[str, tuple[float, int]] = {}


def reset_in_memory_store_for_tests() -> None:
    """Clear in-process counters (pytest only)."""
    global _memory
    _memory = {}


def reset_rate_limit_state_for_tests() -> None:
    """Clear memory counters and Redis keys matching ``ratelimit:graphql:*`` (pytest only)."""
    global _redis_probe_done, _redis_conn
    reset_in_memory_store_for_tests()
    _redis_probe_done = False
    _redis_conn = None
    try:
        client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=0.35,
            socket_timeout=0.35,
        )
        batch: list[str | bytes] = []
        for key in client.scan_iter(match="ratelimit:graphql:*", count=100):
            batch.append(key)
            if len(batch) >= 50:
                client.delete(*batch)
                batch.clear()
        if batch:
            client.delete(*batch)
        client.close()
    except (RedisError, OSError, TimeoutError):
        pass


def _sanitize_client_id(raw: str) -> str:
    cleaned = raw.strip()[:256]
    return cleaned if cleaned else "unknown"


def _redis_client() -> Optional[redis.Redis]:
    global _redis_conn, _redis_probe_done
    if _redis_probe_done:
        return _redis_conn
    try:
        client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=0.35,
            socket_timeout=0.35,
        )
        client.ping()
        _redis_conn = client
    except (RedisError, OSError, TimeoutError) as exc:
        logger.warning(
            "report_rate_limit.redis_unavailable_using_memory",
            extra={"error": str(exc)},
        )
        _redis_conn = None
    _redis_probe_done = True
    return _redis_conn


def _redis_increment(key: str, window_sec: int) -> int:
    client = _redis_client()
    if client is None:
        raise RedisError("redis not available")
    count = client.eval(_INCR_EXPIRE_LUA, 1, key, str(window_sec))
    return int(count)


def _memory_increment(full_key: str, window_sec: int) -> int:
    """Fixed window from first request; reset when window elapses."""
    now = time.time()
    with _lock:
        rec = _memory.get(full_key)
        if rec is None or now - rec[0] >= float(window_sec):
            _memory[full_key] = (now, 1)
            return 1
        start, cnt = rec
        cnt += 1
        _memory[full_key] = (start, cnt)
        return cnt


def check_report_mutation(kind: MutationKind, client_id_raw: str) -> None:
    """Raise strawberry.exceptions.GraphQLError when limit exceeded."""
    if not settings.rate_limit_reports_enabled:
        return

    client_id = _sanitize_client_id(client_id_raw)
    window = settings.rate_limit_window_seconds
    max_req = (
        settings.rate_limit_submit_max_per_window
        if kind == "submit"
        else settings.rate_limit_upvote_max_per_window
    )

    key_suffix = hashlib.sha256(f"{kind}:{client_id}".encode()).hexdigest()[:24]
    redis_key = f"ratelimit:graphql:report:{kind}:{key_suffix}"

    try:
        count = _redis_increment(redis_key, window)
    except (RedisError, OSError, TimeoutError, TypeError, ValueError):
        count = _memory_increment(f"{kind}:{client_id}", window)

    if count > max_req:
        raise GraphQLError(
            "Too many requests for this operation from your network. Please wait and try again.",
            extensions={"code": "RATE_LIMITED"},
        )
