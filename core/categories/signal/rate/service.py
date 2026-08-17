"""
ZipAI — Rate (mortgage) Service Layer.

Orchestrates repository calls, applies TTL caching, and maps raw rows to typed
Pydantic responses for the Rate page (two line charts + Today's Numbers card).

Add these caches to core/cache.py (in the #rate block):
    rate_current_cache = TTLCache(maxsize=8,  ttl=1800)
    rate_history_cache = TTLCache(maxsize=16, ttl=1800)
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import cached, rate_current_cache, rate_history_cache
from core.categories.signal.rate import repository as repo
from core.categories.signal.rate.schemas import (
    RateCurrentResponse,
    RateHistoryPoint,
    RateHistoryResponse,
)


def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class RateService:
    """Business logic for the Rate endpoints."""

    @staticmethod
    @cached(rate_current_cache)
    async def get_current(session: AsyncSession) -> RateCurrentResponse:
        """Latest rate + weekly change (Today's Numbers card)."""
        row = await repo.get_current(session)
        if row is None:
            return RateCurrentResponse()
        return RateCurrentResponse(
            rate_date=row.get("rate_date"),
            rate_30yr=_f(row.get("rate_30yr")),
            rate_15yr=_f(row.get("rate_15yr")),
            change_30yr_wow=_f(row.get("change_30yr_wow")),
            change_15yr_wow=_f(row.get("change_15yr_wow")),
        )

    @staticmethod
    @cached(rate_history_cache)
    async def get_history(session: AsyncSession, months: int | None = None) -> RateHistoryResponse:
        """Weekly series feeding the 30-yr and 15-yr line charts."""
        rows = await repo.get_history(session, months=months)
        points = [
            RateHistoryPoint(
                rate_date=r["rate_date"],
                rate_30yr=_f(r.get("rate_30yr")),
                rate_15yr=_f(r.get("rate_15yr")),
            )
            for r in rows
        ]
        return RateHistoryResponse(points=points)