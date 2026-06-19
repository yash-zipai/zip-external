"""
Jobs (Employer) category — API routes.

An APIRouter holding the jobs endpoints. Include it under /v1/jobs to
reproduce the new (Planned) paths below:

    app.include_router(jobs_router, prefix="/v1/jobs")
    # -> /v1/jobs/zipcode/{zip}/breakdown
    # -> /v1/jobs/zipcode/{zip}/index-scores

The data lives in the ``employer`` schema; the user-facing concept is "jobs".

Migration note (old -> new):
    GET /api/zipcode/{zip}/location-indices/jobs/breakdown/
        -> GET /v1/jobs/zipcode/{zip}/breakdown
    GET /api/zipcode/{zip}/location-indices/
        -> GET /v1/jobs/zipcode/{zip}/index-scores
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.schema_manager import get_schema_session
from core.categories.employer.schemas import (
    JobsBreakdownResponse,
    JobsIndexScoreResponse,
)
from .service import JobsService

router = APIRouter(tags=["Jobs"])


# -- Breakdown -----------------------------------------------------------------


@router.get(
    "/zipcode/{zip}/breakdown",
    response_model=JobsBreakdownResponse,
    status_code=status.HTTP_200_OK,
    summary="Top-5 per-industry employer breakdown by zipcode",
    description=(
        "Returns the top 5 industry sectors for a zipcode — one entry per NAICS "
        "sector with zip-level establishment/share figures and county-level "
        "employment and payroll — ordered by rank ascending. Powers the jobs "
        "index-card pop-up."
    ),
)
async def get_breakdown(
    zip: str,
    db: AsyncSession = Depends(get_schema_session("employer")),
) -> JobsBreakdownResponse:
    return await JobsService.get_breakdown(session=db, zipcode=zip)


# -- Index score ---------------------------------------------------------------


@router.get(
    "/zipcode/{zip}/index-scores",
    response_model=JobsIndexScoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Aggregated jobs index score by zipcode",
    description=(
        "Returns the zip-level jobs aggregate: a 0–100 jobs index score "
        "(employer diversity / top-sector concentration), the top sector, the "
        "total establishment count and the snapshot year. Powers the jobs "
        "index card."
    ),
)
async def get_index_score(
    zip: str,
    db: AsyncSession = Depends(get_schema_session("employer")),
) -> JobsIndexScoreResponse:
    return await JobsService.get_index_score(session=db, zipcode=zip)