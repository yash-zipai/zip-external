"""
ZipAI — Crime Service Layer.

Orchestrates repository calls, applies caching, and maps raw dicts
to typed Pydantic response models. All business logic for crime
endpoints lives here.
"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

# from logging import get_logger
from core.categories.crime.schemas import (
    CrimeBreakdownItem,
    CrimeBreakdownResponse,
    CrimeSummaryResponse,
    CrimeSummaryYear,
)
from core.cache import (
    cached,
    crime_breakdown_cache,
    crime_summary_cache,
)
from core.categories.crime.repository import (
    get_crime_breakdown as repo_get_crime_breakdown,
    get_crime_summary as repo_get_crime_summary,
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
    @cached(crime_summary_cache)
    async def get_crime_summary(
        session: AsyncSession,
        zipcode: str,
    ) -> CrimeSummaryResponse:
        """Retrieve the per-year crime summary for a zipcode."""
        t0 = time.monotonic()

        rows = await repo_get_crime_summary(session, zipcode)

        years = [
            CrimeSummaryYear(
                year=_to_int(row.get("year")),
                city=row.get("city"),
                total_crimes=_to_int(row.get("total_crimes")),
                crime_rate_index=_to_float(row.get("crime_rate_index")),
                violent_count=_to_int(row.get("violent_count")),
                violent_rate=_to_float(row.get("violent_rate")),
                property_count=_to_int(row.get("property_count")),
                property_rate=_to_float(row.get("property_rate")),
            )
            for row in rows
        ]

        duration_ms = int((time.monotonic() - t0) * 1000)
        # logger.info(
        #     "svc_get_crime_summary",
        #     zipcode=zipcode,
        #     years_returned=len(years),
        #     duration_ms=duration_ms,
        # )

        return CrimeSummaryResponse(zipcode=zipcode, years=years)

    @staticmethod
    @cached(crime_breakdown_cache)
    async def get_crime_breakdown(
        session: AsyncSession,
        zipcode: str,
    ) -> CrimeBreakdownResponse:
        """Retrieve the crime breakdown for a zipcode's most recent year."""
        t0 = time.monotonic()

        rows = await repo_get_crime_breakdown(session, zipcode)

        items = [
            CrimeBreakdownItem(
                crime_type=row["crime_type"],
                crime_class=row.get("crime_class"),
                actual_count=_to_int(row.get("actual_count")),
                rate=_to_float(row.get("rate")),
            )
            for row in rows
        ]

        # Every row shares the same (max) year; surface it at the top level.
        year: int | None = None
        if rows:
            raw_year = rows[0].get("year")
            year = int(raw_year) if raw_year is not None else None

        duration_ms = int((time.monotonic() - t0) * 1000)
        # logger.info(
        #     "svc_get_crime_breakdown",
        #     zipcode=zipcode,
        #     year=year,
        #     items_returned=len(items),
        #     duration_ms=duration_ms,
        # )

        return CrimeBreakdownResponse(zipcode=zipcode, year=year, items=items)