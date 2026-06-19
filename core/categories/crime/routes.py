"""
Crime category — API routes.

An APIRouter holding the crime endpoints (new scheme). Include it the same way
as the other category routers, with prefix="/v1":

    app.include_router(crime_router, prefix="/v1")

which yields the final paths:
    /v1/crime/zipcode/{zip}/index-scores
    /v1/crime/zipcode/{zip}/breakdown
    /v1/crime/zipcode/{zip}/insights

The routes are namespaced under "/crime/..." so they don't collide with the
other categories' map/index routes.

Save as: core/categories/crime/routes.py
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.schema_manager import get_schema_session
from core.categories.crime.schemas import (
    CrimeBreakdownResponse,
    CrimeIndexScoresResponse,
    CrimeInsightsResponse,
)
from .service import CrimeService

router = APIRouter(tags=["Crime"])


# -- Index Scores --------------------------------------------------------------


@router.get(
    "/crime/zipcode/{zip}/index-scores",
    response_model=CrimeIndexScoresResponse,
    status_code=status.HTTP_200_OK,
    summary="Crime index card by zipcode",
    description=(
        "Returns the ZIP-level crime aggregate for the latest year: crime index, "
        "safety percentage, safety level, and violent/property totals. "
        "No offenses list or chart series."
    ),
)
async def get_index_scores(
    zip: str,
    db: AsyncSession = Depends(get_schema_session("crime")),
) -> CrimeIndexScoresResponse:
    return await CrimeService.get_index_scores(session=db, zipcode=zip)


# -- Breakdown -----------------------------------------------------------------


@router.get(
    "/crime/zipcode/{zip}/breakdown",
    response_model=CrimeBreakdownResponse,
    status_code=status.HTTP_200_OK,
    summary="Crime breakdown by zipcode",
    description=(
        "Returns the latest-year summary (crime index, violent/property totals), "
        "the top 5 offenses by count, and a year-over-year trend block. "
        "No monthly series."
    ),
)
async def get_breakdown(
    zip: str,
    db: AsyncSession = Depends(get_schema_session("crime")),
) -> CrimeBreakdownResponse:
    return await CrimeService.get_breakdown(session=db, zipcode=zip)


# -- Insights ------------------------------------------------------------------


@router.get(
    "/crime/zipcode/{zip}/insights",
    response_model=CrimeInsightsResponse,
    status_code=status.HTTP_200_OK,
    summary="Crime monthly series by zipcode",
    description=(
        "Returns the monthly crime-rate series for the listing neighborhood chart "
        "(last 23 months by default), oldest first."
    ),
)
async def get_insights(
    zip: str,
    months: int = Query(
        default=23, ge=1, le=120,
        description="Number of trailing months to return (default 23).",
    ),
    db: AsyncSession = Depends(get_schema_session("crime")),
) -> CrimeInsightsResponse:
    return await CrimeService.get_insights(session=db, zipcode=zip, months=months)