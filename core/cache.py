"""
ZipAI — Healthcare TTL Cache Utilities.

In-memory TTL caches for healthcare API responses.
Each endpoint gets its own cache instance with configurable TTL and max size.

Upgrade path: swap ``cachetools.TTLCache`` for a Redis-backed cache
(same decorator interface) when horizontal scaling requires shared state.
"""

from __future__ import annotations

import asyncio
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
top_places_cache: TTLCache = TTLCache(maxsize=256, ttl=900)    
breakdown_cache: TTLCache = TTLCache(maxsize=256, ttl=900)     
index_scores_cache: TTLCache = TTLCache(maxsize=64, ttl=900)  
map_pins_cache: TTLCache = TTLCache(maxsize=256, ttl=900)       

#crime
crime_summary_cache      = TTLCache(maxsize=256, ttl=900)
crime_breakdown_cache    = TTLCache(maxsize=256, ttl=900)
crime_index_scores_cache = TTLCache(maxsize=256, ttl=900)
crime_insights_cache     = TTLCache(maxsize=256, ttl=900)

#lifestyle
lifestyle_top_places_cache   = TTLCache(maxsize=256, ttl=900)
lifestyle_breakdown_cache    = TTLCache(maxsize=256, ttl=900)
lifestyle_index_scores_cache = TTLCache(maxsize=256, ttl=900)
lifestyle_map_pins_cache     = TTLCache(maxsize=256, ttl=900)

#schools
schools_k12_cache = TTLCache(maxsize=256, ttl=900)
schools_higher_ed_cache = TTLCache(maxsize=256, ttl=900)
schools_breakdown_cache = TTLCache(maxsize=256, ttl=900)
schools_details_cache = TTLCache(maxsize=1024, ttl=900)
schools_map_pins_cache = TTLCache(maxsize=256, ttl=900)

#cost_of_living
col_breakdown_cache     = TTLCache(maxsize=256, ttl=900)
col_trend_cache         = TTLCache(maxsize=256, ttl=900)
col_index_scores_cache  = TTLCache(maxsize=256, ttl=900)

#employer
jobs_breakdown_cache = TTLCache(maxsize=256, ttl=900)
jobs_score_cache     = TTLCache(maxsize=256, ttl=900)

#audit
audit_logs_cache = TTLCache(maxsize=256, ttl=900)

#analytics (admin insights)
analytics_house_views_cache = TTLCache(maxsize=256, ttl=900)
analytics_usage_cache       = TTLCache(maxsize=16,   ttl=900)
analytics_overview_cache    = TTLCache(maxsize=8,    ttl=300)
analytics_trending_cache    = TTLCache(maxsize=64,   ttl=300)
analytics_heatmap_cache     = TTLCache(maxsize=32,   ttl=600)
analytics_funnel_cache      = TTLCache(maxsize=32,   ttl=300)
analytics_session_cache     = TTLCache(maxsize=32,   ttl=300)
analytics_conversion_cache  = TTLCache(maxsize=32,   ttl=300)

#ai_admin
ai_overview_cache       = TTLCache(maxsize=8,  ttl=120)
ai_top_questions_cache  = TTLCache(maxsize=32, ttl=120)
ai_intent_cache         = TTLCache(maxsize=8,  ttl=120)
ai_over_time_cache      = TTLCache(maxsize=16, ttl=120)
ai_top_unanswered_cache = TTLCache(maxsize=32, ttl=120)

#data_audit
audit_ingestion_cache    = TTLCache(maxsize=16, ttl=300)
audit_freshness_cache    = TTLCache(maxsize=8,  ttl=300)
audit_counts_cache       = TTLCache(maxsize=8,  ttl=300)
audit_coverage_cache     = TTLCache(maxsize=8,  ttl=300)
audit_coverage_gaps_cache = TTLCache(maxsize=32, ttl=300)
audit_quality_cache      = TTLCache(maxsize=8,  ttl=300)
audit_new_listings_cache         = TTLCache(maxsize=64, ttl=60)
audit_new_listings_summary_cache = TTLCache(maxsize=16, ttl=60)


#market  (MLS market-analysis charts — signal.listing_fact)
# signal.* only changes when the external MLS loader runs (at most daily — see
# signal.load_state), so trend charts keep for an hour: a cold cache is the slow
# path, and 15 min bought no freshness. Drill-downs keep their shorter TTLs.
MARKET_TREND_TTL = 3600
market_home_price_trend_cache     = TTLCache(maxsize=256, ttl=MARKET_TREND_TTL)
market_value_per_sqft_cache       = TTLCache(maxsize=256, ttl=MARKET_TREND_TTL)
market_price_drop_pressure_cache  = TTLCache(maxsize=256, ttl=MARKET_TREND_TTL)
market_price_cuts_cache           = TTLCache(maxsize=256, ttl=300)   # drill-down, shorter TTL
market_fresh_supply_cache         = TTLCache(maxsize=256, ttl=MARKET_TREND_TTL)
market_homes_sold_cache           = TTLCache(maxsize=256, ttl=MARKET_TREND_TTL)
market_inventory_cache            = TTLCache(maxsize=256, ttl=MARKET_TREND_TTL)
market_speed_to_sell_cache        = TTLCache(maxsize=256, ttl=MARKET_TREND_TTL)
market_listings_cache             = TTLCache(maxsize=256, ttl=300)   # drill-down, shorter TTL
market_price_distribution_cache   = TTLCache(maxsize=256, ttl=900)   # Graph 4 drill-down
market_dom_breakdown_cache        = TTLCache(maxsize=256, ttl=900)   # Graph 5 drill-down
market_closed_monthly_cache       = TTLCache(maxsize=256, ttl=MARKET_TREND_TTL)   # shared by price trend / $/sqft / homes sold / leverage / reductions
market_buyer_leverage_cache       = TTLCache(maxsize=256, ttl=MARKET_TREND_TTL)
market_price_reductions_cache     = TTLCache(maxsize=256, ttl=MARKET_TREND_TTL)

#rate  (Freddie Mac mortgage rates)
rate_current_cache = TTLCache(maxsize=8,  ttl=1800)
rate_history_cache = TTLCache(maxsize=16, ttl=1800)

#saller agent
agent_profile_cache          = TTLCache(maxsize=512, ttl=900)
agent_listings_cache         = TTLCache(maxsize=512, ttl=300)
agent_invites_summary_cache  = TTLCache(maxsize=512, ttl=120)
agent_invites_cache          = TTLCache(maxsize=512, ttl=120)
agent_people_cache           = TTLCache(maxsize=512, ttl=120)
agent_invited_by_cache       = TTLCache(maxsize=512, ttl=900)

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

    The DB session is excluded from the cache key because sessions are
    ephemeral — whether it is passed as the first positional argument or as
    ``session=``.

    Concurrent misses for the same key are coalesced: the first caller runs
    the query and every other caller awaits that same result instead of
    issuing a duplicate query (e.g. the Signals feed and rail both asking for
    ``available-inventory`` at the same moment).
    """

    def decorator(func: Callable) -> Callable:
        # key -> Future of the call currently computing that key (per event loop / worker)
        inflight: dict[str, asyncio.Future] = {}

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if "session" in kwargs:
                key_kwargs = {k: v for k, v in kwargs.items() if k != "session"}
                key = make_cache_key(*args, **key_kwargs)
            else:
                # Skip the first arg (session) for the cache key
                key = make_cache_key(*args[1:], **kwargs)

            if key in cache_instance:
                return cache_instance[key]

            pending = inflight.get(key)
            if pending is not None:
                try:
                    return await asyncio.shield(pending)
                except asyncio.CancelledError:
                    if pending.cancelled():
                        # The leading request was cancelled (client went away);
                        # compute it ourselves with our own session.
                        return await wrapper(*args, **kwargs)
                    raise

            fut: asyncio.Future = asyncio.get_running_loop().create_future()
            inflight[key] = fut
            try:
                result = await func(*args, **kwargs)
            except asyncio.CancelledError:
                fut.cancel()
                raise
            except BaseException as exc:
                fut.set_exception(exc)
                fut.exception()  # mark retrieved: no "never retrieved" warning if nobody waited
                raise
            else:
                cache_instance[key] = result
                fut.set_result(result)
                return result
            finally:
                inflight.pop(key, None)

        # Expose a way to manually clear the cache
        wrapper.cache = cache_instance  # type: ignore[attr-defined]
        wrapper.cache_clear = cache_instance.clear  # type: ignore[attr-defined]
        return wrapper

    return decorator