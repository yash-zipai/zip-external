"""
Data Audit — Service layer. Shapes repository rows into response models.

Same shape as ai_admin/service.py: @staticmethod + @cached(named_cache), and
the DB session is always passed POSITIONALLY (the cache key skips arg[0]).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.data_audit import repository as repo
from app.data_audit.cache import (
    cached,
    audit_ingestion_cache,
    audit_freshness_cache,
    audit_counts_cache,
    audit_coverage_cache,
    audit_coverage_gaps_cache,
    audit_quality_cache,
)
from app.data_audit.schemas import (
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
    RecordCountRow,
    RecordCountsResponse,
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