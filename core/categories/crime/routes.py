"""
Crime category — API routes.

An APIRouter holding the crime endpoints. It is included by app.py the same
way as the healthcare router, e.g.:

    app.include_router(crime_router, prefix="/v1")

which yields the final paths:
    /v1/zipinsights/{zip}
    /v1/zipcode/{zip}/location-indices/crime/breakdown

NOTE on paths: the two endpoints you provided don't share a common prefix
(unlike healthcare's "/healthcare"), so this router sets no prefix and each
route carries its full sub-path. If these endpoints should live under "/api"
instead of "/v1", include the router with prefix="/api" (or edit the route
paths below to match your URL scheme).
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.schema_manager import get_schema_session
from core.categories.crime.schemas import (
    CrimeBreakdownResponse,
    CrimeSummaryResponse,
)
from .service import CrimeService

router = APIRouter(tags=["Crime"])


# -- Crime Summary -------------------------------------------------------------


@router.get(
    "/zipinsights/{zip}",
    response_model=CrimeSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Per-year crime summary by zipcode",
    description=(
        "Returns a per-year crime summary for the specified zipcode using the "
        "current crime history. Each year reports total incidents and a rate "
        "index, plus a violent/property split. Ordered by year ascending."
    ),
)
async def get_crime_summary(
    zip: str,
    db: AsyncSession = Depends(get_schema_session("crime")),
) -> CrimeSummaryResponse:
    return await CrimeService.get_crime_summary(session=db, zipcode=zip)


# -- Crime Breakdown -----------------------------------------------------------


@router.get(
    "/zipcode/{zip}/location-indices/crime/breakdown",
    response_model=CrimeBreakdownResponse,
    status_code=status.HTTP_200_OK,
    summary="Crime breakdown for the most recent year",
    description=(
        "Returns the per crime-type breakdown for the specified zipcode's most "
        "recent available year, ordered by rate descending."
    ),
)
async def get_crime_breakdown(
    zip: str,
    db: AsyncSession = Depends(get_schema_session("crime")),
) -> CrimeBreakdownResponse:
    return await CrimeService.get_crime_breakdown(session=db, zipcode=zip)