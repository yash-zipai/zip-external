"""
Data Audit — Service layer. Shapes repository rows into response models.

Same shape as ai_admin/service.py: @staticmethod + @cached(named_cache), and
the DB session is always passed POSITIONALLY (the cache key skips arg[0]).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.categories.data_audit import repository as repo
from core.cache import (
    cached,
    audit_ingestion_cache,
    audit_freshness_cache,
    audit_counts_cache,
    audit_coverage_cache,
    audit_coverage_gaps_cache,
    audit_quality_cache,
    audit_new_listings_cache,
    audit_new_listings_summary_cache,
)
from core.categories.data_audit.schemas import (
    CityCount,
    CompletenessRow,
    CoverageGapRow,
    CoverageGapsResponse,
    CoverageResponse,
    CoverageRow,
    DataQualityResponse,
    FreshnessResponse,
    FreshnessRow,
    IngestionActivityResponse,
    IngestionDayCount,
    NewListingItem,
    NewListingsResponse,
    NewListingsSummaryResponse,
    RecordCountRow,
    RecordCountsResponse,
    StatusCount,
)


class DataAuditService:

    @staticmethod
    @cached(audit_ingestion_cache)
    async def get_ingestion_activity(session: AsyncSession, days: int = 30) -> IngestionActivityResponse:
        rows = await repo.ingestion_activity(session, days)
        items = [
            IngestionDayCount(
                day=str(r["day"]),
                category=str(r["category"]),
                ingested=int(r["ingested"] or 0),
            )
            for r in rows
        ]
        return IngestionActivityResponse(days=days, items=items)

    @staticmethod
    @cached(audit_freshness_cache)
    async def get_freshness(session: AsyncSession, stale_days: int = 30) -> FreshnessResponse:
        rows = await repo.freshness(session, stale_days)
        items = [
            FreshnessRow(
                dataset=str(r["dataset"]),
                last_ingested=r.get("last_ingested"),
                latest_period=r.get("latest_period"),
                is_stale=bool(r.get("is_stale")),
            )
            for r in rows
        ]
        return FreshnessResponse(stale_after_days=stale_days, items=items)

    @staticmethod
    @cached(audit_counts_cache)
    async def get_record_counts(session: AsyncSession) -> RecordCountsResponse:
        rows = await repo.record_counts(session)
        items = [
            RecordCountRow(category=str(r["category"]), rows=int(r["rows"] or 0))
            for r in rows
        ]
        total = sum(i.rows for i in items)
        return RecordCountsResponse(total_rows=total, items=items)

    @staticmethod
    @cached(audit_coverage_cache)
    async def get_coverage(session: AsyncSession) -> CoverageResponse:
        rows = await repo.coverage(session)
        items = [
            CoverageRow(
                category=str(r["category"]),
                zipcodes_covered=int(r["zipcodes_covered"] or 0),
            )
            for r in rows
        ]
        return CoverageResponse(items=items)

    @staticmethod
    @cached(audit_coverage_gaps_cache)
    async def get_coverage_gaps(
        session: AsyncSession,
        days: int = 30,
        limit: int = 20,
        category: str | None = None,
    ) -> CoverageGapsResponse:
        rows = await repo.coverage_gaps(session, days, limit, category)
        items = [
            CoverageGapRow(
                category=str(r["category"]),
                zipcode=str(r["zipcode"]),
                searches=int(r["searches"] or 0),
                users=int(r["users"] or 0),
            )
            for r in rows
        ]
        return CoverageGapsResponse(days=days, category=category, items=items)

    @staticmethod
    @cached(audit_quality_cache)
    async def get_data_quality(session: AsyncSession) -> DataQualityResponse:
        rows = await repo.completeness(session)
        items = [
            CompletenessRow(
                category=str(r["category"]),
                field_checked=str(r["field_checked"]),
                total=int(r["total"] or 0),
                missing=int(r["missing"] or 0),
                missing_pct=float(r["missing_pct"] or 0),
            )
            for r in rows
        ]
        return DataQualityResponse(items=items)

    @staticmethod
    @cached(audit_new_listings_cache)
    async def get_new_listings(
        session: AsyncSession,
        days: int = 7,
        limit: int = 50,
        offset: int = 0,
        postal_code: str | None = None,
        city: str | None = None,
        status: str | None = None,
    ) -> NewListingsResponse:
        rows = await repo.new_listings(
            session, days, limit, offset,
            postal_code=postal_code,
            city=(f"%{city}%" if city else None),  # ILIKE wildcards
            status=status,
        )
        items = [
            NewListingItem(
                listing_key_numeric=str(r["listing_key_numeric"]),
                listing_id=r.get("listing_id"),
                standard_status=r.get("standard_status"),
                address=r.get("address"),
                city=r.get("city"),
                state=r.get("state"),
                postal_code=r.get("postal_code"),
                latitude=_f(r.get("latitude")),
                longitude=_f(r.get("longitude")),
                list_price=_f(r.get("list_price")),
                bedrooms=_f(r.get("bedrooms")),
                bathrooms=_f(r.get("bathrooms")),
                living_area=_f(r.get("living_area")),
                property_class=r.get("property_class"),
                is_lease_listing=bool(r.get("is_lease_listing")),
                listing_office_name=r.get("listing_office_name"),
                listing_member_name=r.get("listing_member_name"),
                property_type=r.get("property_type"),
                year_built=r.get("year_built"),
                lot_size_acres=r.get("lot_size_acres"),
                listed_at=r.get("listed_at"),
            )
            for r in rows
        ]
        return NewListingsResponse(
            days=days, returned=len(items), limit=limit, offset=offset, items=items,
        )
 
    @staticmethod
    @cached(audit_new_listings_summary_cache)
    async def get_new_listings_summary(session: AsyncSession, days: int = 7) -> NewListingsSummaryResponse:
        totals = await repo.new_listings_summary(session, days)
        by_status = await repo.new_listings_by_status(session, days)
        top_cities = await repo.new_listings_top_cities(session, days)
 
        return NewListingsSummaryResponse(
            days=days,
            total_new_listings=int(totals.get("total_new_listings", 0) or 0),
            for_sale=int(totals.get("for_sale", 0) or 0),
            for_lease=int(totals.get("for_lease", 0) or 0),
            zipcodes_covered=int(totals.get("zipcodes_covered", 0) or 0),
            by_status=[
                StatusCount(standard_status=str(r["standard_status"] or "(unknown)"),
                            listings=int(r["listings"] or 0))
                for r in by_status
            ],
            top_cities=[
                CityCount(city=str(r["city"]), listings=int(r["listings"] or 0))
                for r in top_cities
            ],
        )
 