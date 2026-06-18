"""
Jobs (Employer) category — API routes.

An APIRouter holding the jobs endpoints. Include it under /api to reproduce
the paths below (mirrors the lifestyle router):

    app.include_router(jobs_router, prefix="/api")
    # -> /api/zipcode/{zip}/location-indices/jobs/breakdown/
    # -> /api/zipcode/{zip}/location-indices/jobs/

The data lives in the ``employer`` schema; the user-facing concept is "jobs".

NOTE: the second query's endpoint path wasn't fully specified (its comment was
'housing-market-trends → location_summary.indices[]'). It's an aggregated
job-market score for the zip, so it's exposed at
'/zipcode/{zip}/location-indices/jobs/'. Rename the route below if it should
live somewhere else (e.g. '/.../jobs/score/').
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.schema_manager import get_schema_session
from core.categories.employer.schemas import (
    JobsBreakdownResponse,
    JobsScoreResponse,
)
from .service import JobsService

router = APIRouter(tags=["Jobs"])


# -- Breakdown -----------------------------------------------------------------


@router.get(
    "/zipcode/{zip}/location-indices/jobs/breakdown/",
    response_model=JobsBreakdownResponse,
    status_code=status.HTTP_200_OK,
    summary="Per-industry employer breakdown by zipcode",
    description=(
        "Returns the per-industry employer breakdown for a zipcode — one entry "
        "per NAICS sector with zip- and county-level establishment, employment "
        "and payroll figures — ordered by rank ascending."
    ),
)
async def get_breakdown(
    zip: str,
    db: AsyncSession = Depends(get_schema_session("employer")),
) -> JobsBreakdownResponse:
    return await JobsService.get_breakdown(session=db, zipcode=zip)


# -- Score ---------------------------------------------------------------------


@router.get(
    "/zipcode/{zip}/location-indices/jobs/",
    response_model=JobsScoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Aggregated job-market score by zipcode",
    description=(
        "Returns an aggregated job-market summary for a zipcode: the job-market "
        "score (sum of sector share %), the number of sectors and the total "
        "number of establishments."
    ),
)
async def get_score(
    zip: str,
    db: AsyncSession = Depends(get_schema_session("employer")),
) -> JobsScoreResponse:
    return await JobsService.get_score(session=db, zipcode=zip)