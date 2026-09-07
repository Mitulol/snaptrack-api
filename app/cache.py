"""Redis cache-aside helper for hot read paths.

Every operation is wrapped so a Redis outage degrades to a cache miss instead
of a request failure — the API stays up (slower) if Redis is down. The client
is created lazily and can be swapped in tests via :func:`set_cache_client`.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis

from app.config import settings

logger = logging.getLogger("snaptrack.cache")

_client: redis.Redis | None = None


def get_cache_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def set_cache_client(client: redis.Redis | None) -> None:
    """Test hook: inject a fakeredis client (or ``None`` to reset)."""
    global _client
    _client = client


def cache_get_json(key: str) -> Any | None:
    try:
        raw = get_cache_client().get(key)
    except redis.RedisError as exc:  # pragma: no cover - exercised via fakeredis
        logger.warning("cache get failed for %s: %s", key, exc)
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def cache_set_json(key: str, value: Any, ttl_seconds: int | None = None) -> None:
    ttl = ttl_seconds if ttl_seconds is not None else settings.photo_cache_ttl_seconds
    try:
        get_cache_client().set(key, json.dumps(value, default=str), ex=ttl)
    except redis.RedisError as exc:  # pragma: no cover - exercised via fakeredis
        logger.warning("cache set failed for %s: %s", key, exc)


def cache_delete(*keys: str) -> None:
    if not keys:
        return
    try:
        get_cache_client().delete(*keys)
    except redis.RedisError as exc:  # pragma: no cover - exercised via fakeredis
        logger.warning("cache delete failed for %s: %s", keys, exc)


def photo_cache_key(photo_id: int) -> str:
    return f"photo:{photo_id}"
