"""
Rate (mortgage) category — API routes.

Two charts for the Rate page, both from signal.mortgage_rate:
  - 30-year fixed rate line   (from /rate/history/, field rate_30yr)
  - 15-year fixed rate line   (from /rate/history/, field rate_15yr)
Plus /rate/current/ for the "Today's Numbers" stat card.

Include under /v1:
    app.include_router(rate_router, prefix="/v1")
    # -> /v1/rate/current/
    # -> /v1/rate/history/
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.schema_manager import get_schema_session
from core.categories.signal.rate.schemas import RateCurrentResponse, RateHistoryResponse
from .service import RateService

router = APIRouter(tags=["Rate"])

# mortgage_rate lives in the `signal` schema
_db = get_schema_session("signal")


@router.get(
    "/rate/current/",
    response_model=RateCurrentResponse,
    summary="Latest mortgage rate + weekly change",
    description="Latest 30-yr and 15-yr fixed rates with the week-over-week change (Today's Numbers card).",
)
async def rate_current(
    db: AsyncSession = Depends(_db),
) -> RateCurrentResponse:
    return await RateService.get_current(db)


@router.get(
    "/rate/history/",
    response_model=RateHistoryResponse,
    summary="Weekly mortgage rate history (30-yr & 15-yr)",
    description=(
        "Weekly Freddie Mac series, oldest first. Each point carries both rate_30yr "
        "and rate_15yr — the frontend draws two line charts from this one response. "
        "Optionally limit to the last N months with ?months=."
    ),
)
async def rate_history(
    months: int | None = Query(
        default=None, ge=1, le=600,
        description="Restrict to the last N months. Omit for full history.",
    ),
    db: AsyncSession = Depends(_db),
) -> RateHistoryResponse:
    return await RateService.get_history(db, months=months)