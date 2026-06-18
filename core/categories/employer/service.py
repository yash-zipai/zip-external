"""
ZipAI — Jobs (Employer) Service Layer.

Orchestrates repository calls, applies caching, and maps raw dicts
to typed Pydantic response models. All business logic for jobs
endpoints lives here.
"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

# from logging import get_logger
from core.categories.employer.schemas import (
    JobsBreakdownResponse,
    JobsIndustryItem,
    JobsScoreResponse,
)
from core.cache import (
    cached,
    jobs_breakdown_cache,
    jobs_score_cache,
)
from core.categories.employer.repository import (
    get_breakdown as repo_get_breakdown,
    get_score as repo_get_score,
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
    """Convert a numeric DB value to int, defaulting to 0."""
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _to_int_opt(value: Any) -> int | None:
    """Convert a numeric DB value to int, returning None when absent/unparseable."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class JobsService:
    """Business logic for jobs (employer) API endpoints."""

    @staticmethod
    @cached(jobs_breakdown_cache)
    async def get_breakdown(
        session: AsyncSession,
        zipcode: str,
    ) -> JobsBreakdownResponse:
        """Retrieve the per-industry employer breakdown for a zipcode."""
        t0 = time.monotonic()

        rows = await repo_get_breakdown(session, zipcode)

        items = [
            JobsIndustryItem(
                rank=_to_int_opt(row.get("rank")),
                naics_code=row.get("naics_code"),
                sector_name=row.get("sector_name"),
                establishments_zip=_to_int_opt(row.get("establishments_zip")),
                share_pct=_to_float(row.get("share_pct")),
                employment_zip_suppressed=_to_int_opt(row.get("employment_zip_suppressed")),
                payroll_k_zip_suppressed=_to_int_opt(row.get("payroll_k_zip_suppressed")),
                employment_county=_to_int_opt(row.get("employment_county")),
                payroll_k_county=_to_int_opt(row.get("payroll_k_county")),
                establishments_county=_to_int_opt(row.get("establishments_county")),
            )
            for row in rows
        ]

        # zipcode/city/lat/lng come from the snapshot — constant across rows.
        first = rows[0] if rows else {}
        city = first.get("city")
        latitude = _to_float(first.get("latitude"))
        longitude = _to_float(first.get("longitude"))

        duration_ms = int((time.monotonic() - t0) * 1000)
        # logger.info("svc_get_breakdown", zipcode=zipcode,
        #             sectors_returned=len(items), duration_ms=duration_ms)

        return JobsBreakdownResponse(
            zipcode=zipcode,
            city=city,
            latitude=latitude,
            longitude=longitude,
            items=items,
        )

    @staticmethod
    @cached(jobs_score_cache)
    async def get_score(
        session: AsyncSession,
        zipcode: str,
    ) -> JobsScoreResponse:
        """Retrieve the aggregated job-market score for a zipcode."""
        t0 = time.monotonic()

        row = await repo_get_score(session, zipcode)

        duration_ms = int((time.monotonic() - t0) * 1000)
        # logger.info("svc_get_score", zipcode=zipcode,
        #             found=row is not None, duration_ms=duration_ms)

        if row is None:
            # No snapshot for this zip — return an empty/zeroed summary.
            return JobsScoreResponse(zipcode=zipcode, city=None)

        return JobsScoreResponse(
            zipcode=zipcode,
            city=row.get("city"),
            job_market_score=_to_float(row.get("job_market_score")),
            sector_count=_to_int(row.get("sector_count")),
            total_establishments=_to_int(row.get("total_establishments")),
        )