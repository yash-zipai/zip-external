"""
MLS data quality — service layer.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from core.categories.mls.repository import DQRepository
from core.categories.mls.schemas import (
    AffectedListing,
    CheckListingsResponse,
    DQCheck,
    DQChecksResponse,
    DQStatusResponse,
    SourceTargetResponse,
    StatusBreakdownResponse,
    StatusRow,
)


class DQService:
    """Serves the stored results of the data quality checks."""

    @staticmethod
    async def get_status(session: AsyncSession) -> DQStatusResponse:
        row = await DQRepository.fetch_status(session)

        if not row or row.get("last_checked") is None:
            # Nothing on record. Saying so plainly beats returning zeros,
            # which would read on screen as "everything is fine".
            return DQStatusResponse(
                data_age_days=None,
                has_gap=False,
                mls_has=None,
                we_have=None,
                gap=None,
                checks_failing=0,
                checks_run=0,
                last_checked=None,
                hours_since_check=None,
                ran_today=False,
            )

        gap = row.get("gap")
        return DQStatusResponse(
            data_age_days=row["data_age_days"],
            has_gap=bool(gap) or row["checks_failing"] > 0,
            mls_has=row["mls_has"],
            we_have=row["we_have"],
            gap=gap,
            checks_failing=row["checks_failing"],
            checks_run=row["checks_run"],
            last_checked=row["last_checked"],
            hours_since_check=row["hours_since_check"],
            ran_today=row["ran_today"],
        )

    @staticmethod
    async def get_source_target(session: AsyncSession) -> SourceTargetResponse:
        row = await DQRepository.fetch_source_target(session)
        if not row:
            return SourceTargetResponse()
        return SourceTargetResponse(**row)

    @staticmethod
    async def get_status_breakdown(session: AsyncSession) -> StatusBreakdownResponse:
        rows = await DQRepository.fetch_status_breakdown(session)

        items = [
            StatusRow(
                status=r["status"],
                mls_has=r["mls_has"],
                we_have=r["we_have"],
                difference=r["difference"],
                error=r["error"],
            )
            for r in rows
        ]

        return StatusBreakdownResponse(
            checked_at=rows[0]["checked_at"] if rows else None,
            total=len(items),
            items=items,
        )

    @staticmethod
    async def get_checks(session: AsyncSession) -> DQChecksResponse:
        rows = await DQRepository.fetch_checks(session)

        items = [
            DQCheck(
                check_name=r["check_name"],
                label=r["label"],
                severity_level=r["severity_level"],
                fix_window=r["fix_window"],
                value=r["value"],
                threshold=r["threshold"],
                passed=r["passed"],
                listings_recorded=r["listings_recorded"],
                repaired=r["repaired"],
                outstanding=r["outstanding"],
                value_a_week_ago=r["value_a_week_ago"],
                direction=r["direction"],
            )
            for r in rows
        ]

        return DQChecksResponse(
            checked_at=rows[0]["run_at"] if rows else None,
            total=len(items),
            failing=sum(1 for i in items if not i.passed),
            items=items,
        )

    @staticmethod
    async def get_listings(
        session: AsyncSession,
        check_name: str,
        limit: int = 100,
        offset: int = 0,
    ) -> CheckListingsResponse:
        rows = await DQRepository.fetch_listings(session, check_name, limit, offset)
        label = await DQRepository.fetch_label(session, check_name)

        return CheckListingsResponse(
            check_name=check_name,
            label=label,
            total=len(rows),
            items=[AffectedListing(**r) for r in rows],
        )