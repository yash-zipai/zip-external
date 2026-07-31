"""
Data Audit API Routes.

Included by main.py WITH the shared /v1 prefix:

    from app.data_audit.routes import router as data_audit_router
    app.include_router(data_audit_router, prefix="/v1")

Router prefix is "/data-audit", so the final paths are:

    GET /v1/data-audit/ingestion-activity     ?days=30
    GET /v1/data-audit/freshness              ?stale_days=30
    GET /v1/data-audit/record-counts
    GET /v1/data-audit/coverage
    GET /v1/data-audit/coverage-gaps          ?category=crime&days=30&limit=20
    GET /v1/data-audit/data-quality
    GET /v1/data-audit/new-listings           ?days=7&limit=50&offset=0&postal_code=&city=&status=
    GET /v1/data-audit/new-listings/summary   ?days=7

All queries fully-qualify their tables (schema.table), so the schema session
below is only used to open a connection — "analytics" is picked because the
coverage-gaps endpoint also reads analytics.user_events.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.schema_manager import get_schema_session

from .schemas import (
    CoverageGapsResponse,
    CoverageResponse,
    DataQualityResponse,
    FreshnessResponse,
    IngestionActivityResponse,
    RecordCountsResponse,
    NewListingsResponse,
    NewListingsSummaryResponse,
)
from .service import DataAuditService


router = APIRouter(prefix="/data-audit", tags=["Data Audit"])


# ============================================================================
# 1) Ingestion activity — new rows ingested per day, per category
# ============================================================================
@router.get(
    "/ingestion-activity",
    response_model=IngestionActivityResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingestion Activity",
    description="New rows ingested per day, per category, over the last N days.",
)
async def get_ingestion_activity(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_schema_session("analytics")),
):
    return await DataAuditService.get_ingestion_activity(db, days=days)


# ============================================================================
# 2) Freshness — last ingested + latest data period + stale flag
# ============================================================================
@router.get(
    "/freshness",
    response_model=FreshnessResponse,
    status_code=status.HTTP_200_OK,
    summary="Data Freshness",
    description="Per category: when it was last ingested, the latest data period, "
                "and whether it is stale (last ingest older than stale_days).",
)
async def get_freshness(
    stale_days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_schema_session("analytics")),
):
    return await DataAuditService.get_freshness(db, stale_days=stale_days)


# ============================================================================
# 3) Record counts — rows per category (current data)
# ============================================================================
@router.get(
    "/record-counts",
    response_model=RecordCountsResponse,
    status_code=status.HTTP_200_OK,
    summary="Record Counts",
    description="Number of current rows we hold per category, plus the grand total.",
)
async def get_record_counts(
    db: AsyncSession = Depends(get_schema_session("analytics")),
):
    return await DataAuditService.get_record_counts(db)


# ============================================================================
# 4) Coverage — distinct zipcodes with data per category
# ============================================================================
@router.get(
    "/coverage",
    response_model=CoverageResponse,
    status_code=status.HTTP_200_OK,
    summary="Zipcode Coverage",
    description="How many distinct zipcodes we hold data for, per category.",
)
async def get_coverage(
    db: AsyncSession = Depends(get_schema_session("analytics")),
):
    return await DataAuditService.get_coverage(db)


# ============================================================================
# 5) Coverage gaps — zipcodes users searched that a category doesn't cover
#    Category-aware: a zip with healthcare but no crime is a CRIME gap only.
# ============================================================================
@router.get(
    "/coverage-gaps",
    response_model=CoverageGapsResponse,
    status_code=status.HTTP_200_OK,
    summary="Coverage Gaps",
    description="Zipcodes users searched (per category) that we have NO data for. "
                "Optional `category` narrows to one category (crime, healthcare, "
                "lifestyle, schools, cost_of_living, employer).",
)
async def get_coverage_gaps(
    category: str | None = Query(None, description="Filter to one category; omit for all."),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=200),
    db: AsyncSession = Depends(get_schema_session("analytics")),
):
    return await DataAuditService.get_coverage_gaps(
        db, days=days, limit=limit, category=category,
    )


# ============================================================================
# 6) Data quality — completeness (%) + duplicates
# ============================================================================
@router.get(
    "/data-quality",
    response_model=DataQualityResponse,
    status_code=status.HTTP_200_OK,
    summary="Data Quality",
    description="Completeness (missing key fields) for crime & healthcare, plus "
                "duplicate healthcare providers within a zipcode.",
)
async def get_data_quality(
    db: AsyncSession = Depends(get_schema_session("analytics")),
):
    return await DataAuditService.get_data_quality(db)


# ============================================================================
# 7) New property listings (MLS / IDX) — public-safe
# ============================================================================
@router.get(
    "/new-listings",
    response_model=NewListingsResponse,
    status_code=status.HTTP_200_OK,
    summary="New Property Listings",
    description="Recently listed properties (public-safe: internet_list=TRUE and "
                "allowed statuses only). Filter by days/postal_code/city/status; paginated.",
)
async def get_new_listings(
    days: int = Query(7, ge=1, le=365, description="How far back to look, in days."),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    postal_code: str | None = Query(None, description="Exact ZIP match."),
    city: str | None = Query(None, description="City name (partial match)."),
    status: str | None = Query(None, description="Narrow to one allowed status."),
    db: AsyncSession = Depends(get_schema_session("analytics")),
):
    return await DataAuditService.get_new_listings(
        db, days=days, limit=limit, offset=offset,
        postal_code=postal_code, city=city, status=status,
    )
 
 
# ============================================================================
# 8) New listings summary — "how many properties were newly listed"
# ============================================================================
@router.get(
    "/new-listings/summary",
    response_model=NewListingsSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="New Listings Summary",
    description="How many properties were newly listed in the window: totals, "
                "sale vs lease, zipcodes covered, breakdown by status and top cities.",
)
async def get_new_listings_summary(
    days: int = Query(7, ge=1, le=365),
    db: AsyncSession = Depends(get_schema_session("analytics")),
):
    return await DataAuditService.get_new_listings_summary(db, days=days)
 