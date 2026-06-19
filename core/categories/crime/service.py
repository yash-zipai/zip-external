"""
ZipAI — Crime Service Layer.

Orchestrates repository calls, applies caching, and maps raw dicts
to typed Pydantic response models. All business logic for crime
endpoints lives here.

Save as: core/categories/crime/service.py
"""

from __future__ import annotations

import time
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

# from logging import get_logger
from core.categories.crime.schemas import (
    CrimeBreakdownResponse,
    CrimeIndexScoresResponse,
    CrimeInsightsResponse,
    CrimeMonthPoint,
    CrimeRateSeries,
    CrimeTopOffense,
    CrimeTrend,
)
from core.cache import (
    cached,
    crime_breakdown_cache,
    crime_index_scores_cache,
    crime_insights_cache,
)
from core.categories.crime.repository import (
    get_breakdown as repo_get_breakdown,
    get_index_scores as repo_get_index_scores,
    get_insights as repo_get_insights,
)

# logger = get_logger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _to_float(value: Any) -> float | None:
    """Safely convert a Decimal/numeric DB value to a Python float."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int:
    """Safely convert a numeric DB value to an int, defaulting to 0."""
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


class CrimeService:
    """Business logic for crime API endpoints."""

    @staticmethod
    @cached(crime_index_scores_cache)
    async def get_index_scores(
        session: AsyncSession,
        zipcode: str,
    ) -> CrimeIndexScoresResponse:
        """Retrieve the ZIP-level crime index card."""
        t0 = time.monotonic()

        row = await repo_get_index_scores(session, zipcode)

        if row is None:
            # No current crime history for this ZIP — return a zeroed aggregate.
            return CrimeIndexScoresResponse(
                zipcode=zipcode,
                city=None,
                crime_index=None,
                level=None,
                violent_total=0,
                property_total=0,
                safety_pct=None,
                as_of=None,
            )

        duration_ms = int((time.monotonic() - t0) * 1000)
        # logger.info("svc_get_index_scores", zipcode=zipcode, duration_ms=duration_ms)

        return CrimeIndexScoresResponse(
            zipcode=zipcode,
            city=row.get("city"),
            crime_index=_to_float(row.get("crime_index")),
            level=row.get("level"),
            violent_total=_to_int(row.get("violent_total")),
            property_total=_to_int(row.get("property_total")),
            safety_pct=_to_float(row.get("safety_pct")),
            as_of=row.get("as_of"),
        )

    @staticmethod
    @cached(crime_breakdown_cache)
    async def get_breakdown(
        session: AsyncSession,
        zipcode: str,
    ) -> CrimeBreakdownResponse:
        """Retrieve the crime breakdown pop-up (summary + top offenses + trend)."""
        t0 = time.monotonic()

        data = await repo_get_breakdown(session, zipcode)

        if data is None:
            return CrimeBreakdownResponse(
                zipcode=zipcode,
                crime_index=None,
                violent_total=0,
                property_total=0,
                top_offenses=[],
                trend=None,
            )

        top_offenses = [
            CrimeTopOffense(
                crime_type=o.get("crime_type"),
                total_count=_to_int(o.get("total_count")),
                crime_rank=o.get("crime_rank"),
                avg_rate=_to_float(o.get("avg_rate")),
            )
            for o in data.get("top_offenses", [])
        ]

        t = data.get("trend")
        trend = (
            CrimeTrend(
                latest_year=t.get("latest_year"),
                latest_total=_to_int(t.get("latest_total")),
                prev_year=t.get("prev_year"),
                prev_total=_to_int(t.get("prev_total")),
                yoy_pct=_to_float(t.get("yoy_pct")),
                trend_direction=t.get("trend_direction"),
            )
            if t
            else None
        )

        duration_ms = int((time.monotonic() - t0) * 1000)
        # logger.info("svc_get_breakdown", zipcode=zipcode, duration_ms=duration_ms)

        return CrimeBreakdownResponse(
            zipcode=zipcode,
            crime_index=_to_float(data.get("crime_index")),
            violent_total=_to_int(data.get("violent_total")),
            property_total=_to_int(data.get("property_total")),
            top_offenses=top_offenses,
            trend=trend,
        )

    @staticmethod
    @cached(crime_insights_cache)
    async def get_insights(
        session: AsyncSession,
        zipcode: str,
        months: int = 23,
    ) -> CrimeInsightsResponse:
        """Retrieve the monthly crime-rate series for the listing chart."""
        t0 = time.monotonic()

        rows = await repo_get_insights(session, zipcode, months=months)

        series = [
            CrimeMonthPoint(month=r.get("month"), value=_to_int(r.get("value")))
            for r in rows
        ]

        # as_of: data freshness date. Defaulting to today; swap for a real
        # freshness column from your monthly source if you have one.
        as_of = date.today()

        duration_ms = int((time.monotonic() - t0) * 1000)
        # logger.info("svc_get_insights", zipcode=zipcode, points=len(series),
        #             duration_ms=duration_ms)

        return CrimeInsightsResponse(
            zipcode=zipcode,
            crime_rate=CrimeRateSeries(monthly_series=series, as_of=as_of),
            mock=False,
        )