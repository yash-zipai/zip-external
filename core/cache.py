"""
ZipAI — Healthcare TTL Cache Utilities.

In-memory TTL caches for healthcare API responses.
Each endpoint gets its own cache instance with configurable TTL and max size.

Upgrade path: swap ``cachetools.TTLCache`` for a Redis-backed cache
(same decorator interface) when horizontal scaling requires shared state.
"""

from __future__ import annotations

import functools
import hashlib
import json
from typing import Any, Callable

from cachetools import TTLCache

# from app.core.logging import get_logger

# logger = get_logger(__name__)

# ── Cache instances ───────────────────────────────────────────────────────────
# Separate caches per endpoint so TTLs and eviction are independent.

#healthcare
top_places_cache: TTLCache = TTLCache(maxsize=256, ttl=900)     # 15 min
breakdown_cache: TTLCache = TTLCache(maxsize=256, ttl=900)      # 15 min
index_scores_cache: TTLCache = TTLCache(maxsize=64, ttl=1800)   # 30 min
map_pins_cache: TTLCache = TTLCache(maxsize=256, ttl=900)       # 15 min

#crime
crime_summary_cache   = TTLCache(maxsize=1024, ttl=300)   # ← match breakdown_cache's numbers
crime_breakdown_cache = TTLCache(maxsize=1024, ttl=300)   # ← match breakdown_cache's numbers


#lifestyle
lifestyle_top_places_cache = TTLCache(maxsize=1024, ttl=300)
lifestyle_breakdown_cache  = TTLCache(maxsize=1024, ttl=300)
lifestyle_map_pins_cache   = TTLCache(maxsize=1024, ttl=300)

#schools
schools_k12_cache = TTLCache(maxsize=256, ttl=900)
schools_higher_ed_cache = TTLCache(maxsize=256, ttl=900)
schools_breakdown_cache = TTLCache(maxsize=256, ttl=900)
schools_details_cache = TTLCache(maxsize=1024, ttl=900)
schools_map_pins_cache = TTLCache(maxsize=256, ttl=900)

#cost_of_living
col_breakdown_cache = TTLCache(maxsize=256, ttl=900)
col_trend_cache = TTLCache(maxsize=256, ttl=900)




def make_cache_key(*args: Any, **kwargs: Any) -> str:
    """
    Build a deterministic, hashable cache key from arbitrary arguments.

    Serialises args/kwargs to a canonical JSON string, then SHA-256 hashes
    it for a fixed-length key that plays nicely with any cache backend.
    """
    raw = json.dumps({"a": args, "k": kwargs}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def cached(cache_instance: TTLCache) -> Callable:
    """
    Async-aware TTL cache decorator.

    Usage::

        @cached(top_places_cache)
        async def get_top_places(session, zipcode, ...):
            ...

    The first positional argument (``session``) is excluded from the cache
    key because DB sessions are ephemeral and not hashable.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Skip the first arg (session) for the cache key
            key = make_cache_key(*args[1:], **kwargs)

            if key in cache_instance:
                # logger.debug(
                #     "cache_hit",
                #     func=func.__name__,
                #     key_prefix=key[:12],
                # )
                return cache_instance[key]

            result = await func(*args, **kwargs)
            cache_instance[key] = result

            # logger.debug(
            #     "cache_miss",
            #     func=func.__name__,
            #     key_prefix=key[:12],
            #     cache_size=len(cache_instance),
            # )
            return result

        # Expose a way to manually clear the cache
        wrapper.cache = cache_instance  # type: ignore[attr-defined]
        wrapper.cache_clear = cache_instance.clear  # type: ignore[attr-defined]
        return wrapper

    return decorator
