"""
MLS data quality — API routes.

An APIRouter (prefix="/mls/dq") holding the reconciliation endpoints.
It is included by app.py with:
    from core.categories.mls.routes import router as mls_dq_router
    app.include_router(mls_dq_router, prefix="/v1")
so the final paths are /v1/mls/dq/...

Six routes, ordered the way the dashboard reads — the broad question first,
narrowing down to individual listings. None of them call the MLS: the checks
already did that and wrote the results away, so a page opens in milliseconds
rather than the several minutes a check run takes.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.schema_manager import get_schema_session
from core.pagination import PaginationParams, pagination_params
from core.categories.mls.schemas import (
    CheckListingsResponse,
    MLSChecksResponse,
    MLSStatusResponse,
    PhotoStatusBreakdownResponse,
    SourceTargetResponse,
    StatusBreakdownResponse,
)
from core.categories.mls.service import MLSService

router = APIRouter(prefix="/mls/dq", tags=["MLS Data Quality"])


# -- Status --------------------------------------------------------------------


@router.get(
    "/status",
    response_model=MLSStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Data quality status at a glance",
    description=(
        "Returns whether our data is in step with the MLS, how many checks "
        "are failing, and when the checks last ran. Whether the checks ran "
        "and whether the data is fresh are reported separately: a page that "
        "has not refreshed and data that has not refreshed look the same "
        "otherwise."
    ),
)
async def get_status(
    db: AsyncSession = Depends(get_schema_session("mls")),
) -> MLSStatusResponse:
    return await MLSService.get_status(session=db)


# -- Source against target -----------------------------------------------------


@router.get(
    "/source-target",
    response_model=SourceTargetResponse,
    status_code=status.HTTP_200_OK,
    summary="Total homes at the MLS against total homes held",
    description=(
        "The headline reconciliation. The MLS figure comes from live calls to "
        "the feed and ours from this database, so the difference is a real "
        "source-to-target gap rather than two views of the same table."
    ),
)
async def get_source_target(
    db: AsyncSession = Depends(get_schema_session("mls")),
) -> SourceTargetResponse:
    return await MLSService.get_source_target(session=db)


# -- Status breakdown ----------------------------------------------------------


@router.get(
    "/status-breakdown",
    response_model=StatusBreakdownResponse,
    status_code=status.HTTP_200_OK,
    summary="Home counts by listing status, against the MLS",
    description=(
        "The same comparison split by listing status, which shows where a "
        "total gap actually sits. A status may carry an error instead of "
        "counts when the feed returned an incomplete list for it.\n\n"
        "The counts are a snapshot from when the checks ran. "
        "`repairs_since_check` says how many listings have been repaired "
        "since, so a reader knows the figures have moved without us "
        "guessing at the new ones."
    ),
)
async def get_status_breakdown(
    db: AsyncSession = Depends(get_schema_session("mls")),
) -> StatusBreakdownResponse:
    return await MLSService.get_status_breakdown(session=db)


# -- Photos by status ----------------------------------------------------------


@router.get(
    "/photos/status-breakdown",
    response_model=PhotoStatusBreakdownResponse,
    status_code=status.HTTP_200_OK,
    summary="Photos by listing status, against the MLS",
    description=(
        "Full-size photos at the MLS against photos held here, in total and "
        "split by listing status, which shows where a photo gap sits.\n\n"
        "The MLS figure is the MLS's own photo count for the listings in its "
        "feed. Each row says whether that figure was read live from the MLS "
        "when the check ran, or taken from the count stored with each listing "
        "(used for statuses with too many homes to read live every run). "
        "A snapshot from when the check ran, not a live reading."
    ),
)
async def get_photo_status_breakdown(
    db: AsyncSession = Depends(get_schema_session("mls")),
) -> PhotoStatusBreakdownResponse:
    return await MLSService.get_photo_status_breakdown(session=db)


# -- Checks --------------------------------------------------------------------


@router.get(
    "/checks",
    response_model=MLSChecksResponse,
    status_code=status.HTTP_200_OK,
    summary="Every data quality check with its latest result",
    description=(
        "Returns each check with today's value, the value a week ago, and the "
        "direction between them. Failing checks are listed first, then by "
        "severity. The direction matters more than the count: a number is a "
        "fact, a rising number is a decision."
    ),
)
async def get_checks(
    db: AsyncSession = Depends(get_schema_session("mls")),
) -> MLSChecksResponse:
    return await MLSService.get_checks(session=db)


# -- Listings behind a check ---------------------------------------------------


@router.get(
    "/checks/{check_name}/listings",
    response_model=CheckListingsResponse,
    status_code=status.HTTP_200_OK,
    summary="The listings behind one check",
    description=(
        "Returns the homes a check flagged, with our values beside the MLS "
        "values where both are known. Every count on the dashboard leads "
        "here: a number nobody can open is a number nobody trusts.\n\n"
        "Listings already repaired through the reconciliation API are left "
        "out. A check result is a snapshot from when it ran, so without this "
        "a list of outstanding work would keep showing work already done. "
        "Pass include_repaired=true to see them anyway. The response carries "
        "flagged, repaired and outstanding counts alongside the page."
    ),
)
async def get_check_listings(
    check_name: str,
    include_repaired: bool = Query(
        False,
        description="Include listings already repaired. Off by default.",
    ),
    page: PaginationParams = Depends(pagination_params(default_limit=100, max_limit=500)),
    db: AsyncSession = Depends(get_schema_session("mls")),
) -> CheckListingsResponse:
    return await MLSService.get_listings(
        session=db,
        check_name=check_name,
        limit=page.limit,
        offset=page.offset,
        include_repaired=include_repaired,
    )