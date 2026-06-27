"""Redis-backed cache for user recommendation feeds.

Recommendation feeds are expensive to rank and change rarely between requests,
so we cache them per (user, model, k) with a short TTL. Every lookup logs a
HIT or MISS so the cache's behavior is observable in the server logs.

Design choice: every Redis call degrades gracefully. If Redis is unreachable,
helpers log a warning and behave as a permanent miss (get -> None, set/delete ->
no-op) so the API keeps serving uncached rather than erroring.
"""

from __future__ import annotations

import json
import logging
import os

import redis

logger = logging.getLogger("cinemind.cache")

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "60"))

# decode_responses -> str in/out instead of bytes.
client = redis.from_url(REDIS_URL, decode_responses=True)


def feed_key(user_id: int, model: str, k: int) -> str:
    return f"feed:{user_id}:{model}:{k}"


def get_cached_feed(user_id: int, model: str, k: int) -> dict | None:
    key = feed_key(user_id, model, k)
    try:
        raw = client.get(key)
    except redis.RedisError as exc:
        logger.warning("cache unavailable on GET (%s): %s", key, exc)
        return None
    if raw is None:
        logger.info("cache MISS %s", key)
        return None
    logger.info("cache HIT %s", key)
    return json.loads(raw)


def set_cached_feed(user_id: int, model: str, k: int, payload: dict) -> None:
    key = feed_key(user_id, model, k)
    try:
        client.setex(key, CACHE_TTL_SECONDS, json.dumps(payload))
    except redis.RedisError as exc:
        logger.warning("cache unavailable on SET (%s): %s", key, exc)


def invalidate_user(user_id: int) -> int:
    """Delete all cached feeds for a user. Returns how many keys were removed."""
    pattern = f"feed:{user_id}:*"
    try:
        keys = list(client.scan_iter(match=pattern))
        removed = client.delete(*keys) if keys else 0
    except redis.RedisError as exc:
        logger.warning("cache unavailable on INVALIDATE (%s): %s", pattern, exc)
        return 0
    logger.info("cache INVALIDATE user=%s removed=%s", user_id, removed)
    return removed
