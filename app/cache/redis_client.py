"""Redis-backed cache for user recommendation feeds.

Recommendation feeds are expensive to rank and change rarely between requests,
so we cache them per (user, model, k) with a short TTL. Every lookup logs a
HIT or MISS so the cache's behavior is observable in the server logs.

Design choice: every Redis call degrades gracefully. If Redis is unreachable,
helpers log a warning and behave as a permanent miss (get -> None, set/delete ->
no-op) so the API keeps serving uncached rather than erroring.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os

import redis

logger = logging.getLogger("cinemind.cache")

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "60"))
# LLM-backed responses (/ask, /why) are far more expensive than a feed and change
# rarely (the corpus is static; /why is invalidated when the user re-rates), so
# they get a much longer TTL.
LLM_CACHE_TTL_SECONDS = int(os.getenv("LLM_CACHE_TTL_SECONDS", "86400"))  # 24h

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


def _delete_pattern(pattern: str) -> int:
    """Delete every key matching a glob pattern; 0 on Redis error."""
    try:
        keys = list(client.scan_iter(match=pattern))
        return client.delete(*keys) if keys else 0
    except redis.RedisError as exc:
        logger.warning("cache unavailable on INVALIDATE (%s): %s", pattern, exc)
        return 0


def invalidate_user(user_id: int) -> int:
    """Delete a user's cached feeds AND /why explanations — both go stale the
    moment the user's ratings change. Returns how many keys were removed."""
    removed = _delete_pattern(f"feed:{user_id}:*") + _delete_pattern(f"why:{user_id}:*")
    logger.info("cache INVALIDATE user=%s removed=%s", user_id, removed)
    return removed


# --- generic response cache (used by /ask and /why) ------------------------

def ask_key(question: str, k: int) -> str:
    """Cache key for an /ask request. The question is normalized (case +
    whitespace) so trivially different phrasings of the same question hit the
    same entry; hashed to keep the key bounded and Redis-safe."""
    norm = " ".join(question.lower().split())
    digest = hashlib.sha256(f"{norm}|{k}".encode()).hexdigest()[:16]
    return f"ask:{digest}"


def why_key(user_id: int, movie_id: int) -> str:
    return f"why:{user_id}:{movie_id}"


def get_cached(key: str) -> dict | None:
    """Generic cached-JSON GET with HIT/MISS logging; a Redis error is a miss."""
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


def set_cached(key: str, payload: dict, ttl: int = LLM_CACHE_TTL_SECONDS) -> None:
    try:
        client.setex(key, ttl, json.dumps(payload))
    except redis.RedisError as exc:
        logger.warning("cache unavailable on SET (%s): %s", key, exc)


def invalidate_ask() -> int:
    """Drop all cached /ask answers — call when retrieval changes (e.g. after a
    re-embed/enrichment), since a question may now resolve differently."""
    removed = _delete_pattern("ask:*")
    logger.info("cache INVALIDATE ask removed=%s", removed)
    return removed
