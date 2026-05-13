"""Redis-backed TTL cache for data-source responses."""
from __future__ import annotations

import functools
import hashlib
import logging
import pickle
from typing import Any, Callable, TypeVar

import redis

from premarket.config import get_settings

log = logging.getLogger(__name__)

T = TypeVar("T")

_settings = get_settings()
_client: redis.Redis | None = None


def get_client() -> redis.Redis:
    """Lazy Redis client. Decode disabled because values are pickled bytes."""
    global _client
    if _client is None:
        _client = redis.Redis.from_url(_settings.redis_url, decode_responses=False)
    return _client


def _make_key(prefix: str, args: tuple, kwargs: dict) -> str:
    """Stable hash of call arguments."""
    payload = repr((args, sorted(kwargs.items()))).encode("utf-8")
    digest = hashlib.sha1(payload).hexdigest()
    return f"premarket:{prefix}:{digest}"


def cached(ttl: int) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorate a function to memoize results in Redis with TTL seconds.

    Falls through to the wrapped call if Redis is unreachable.
    """

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        prefix = f"{fn.__module__}.{fn.__qualname__}"

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            key = _make_key(prefix, args, kwargs)
            client = get_client()
            try:
                raw = client.get(key)
                if raw is not None:
                    return pickle.loads(raw)  # type: ignore[return-value] # noqa: S301
            except Exception as exc:  # noqa: BLE001 -- cache must never break callers
                log.warning("cache read failed key=%s err=%s", key, exc)

            value = fn(*args, **kwargs)
            try:
                client.set(key, pickle.dumps(value), ex=ttl)
            except Exception as exc:  # noqa: BLE001 -- same reason
                log.warning("cache write failed key=%s err=%s", key, exc)
            return value

        return wrapper

    return decorator
