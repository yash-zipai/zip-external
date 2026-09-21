"""
MLS data quality — service layer.
"""

from datetime import datetime, timedelta, timezone

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


def _sync_status(gap, outstanding, last_repair_at) -> str:
    """Name the state of the gap in the words the dashboard shows.

    completed    no gap
    in_progress  a gap, repairs queued, and one ran in the last 24 hours
    stalled      a gap, repairs queued, but nothing has run in 24 hours
    pending      a gap, and nothing queued against it

    "In progress" has to mean something is actually moving. Work that has sat
    untouched for a day is stuck, and saying otherwise would tell the reader
    it is being handled when it is not.

    Kept in one place so /status and /source-target never disagree.
    """
    if not gap:
        return "completed"
    if not outstanding:
        return "pending"
    if last_repair_at is None:
        return "stalled"

    now = datetime.now(timezone.utc)
    if last_repair_at.tzinfo is None:
        last_repair_at = last_repair_at.replace(tzinfo=timezone.utc)
    return "in_progress" if now - last_repair_at < timedelta(hours=24) else "stalled"


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
                mls_as_of=None,
                we_have=None,
                zipai_as_of=None,
                gap=None,
                sync_status="pending",
                repairs_outstanding=0,
                checks_failing=0,
                checks_run=0,
                last_checked=None,
                hours_since_check=None,
                ran_today=False,
            )

        gap = row.get("gap")
        outstanding = row.get("repairs_outstanding") or 0

        return DQStatusResponse(
            data_age_days=row["data_age_days"],
            has_gap=bool(gap) or row["checks_failing"] > 0,
            mls_has=row["mls_has"],
            mls_as_of=row["mls_as_of"],
            we_have=row["we_have"],
            zipai_as_of=row["zipai_as_of"],
            gap=gap,
            sync_status=_sync_status(gap, outstanding, row.get("last_repair_at")),
            repairs_outstanding=outstanding,
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

        status_row = await DQRepository.fetch_status(session) or {}
        outstanding = status_row.get("repairs_outstanding") or 0

        return SourceTargetResponse(
            mls_has=row["mls_has"],
            we_have=row["we_have"],
            difference=row["difference"],
            sync_status=_sync_status(
                row["difference"], outstanding, status_row.get("last_repair_at")
            ),
            checked_at=row["checked_at"],
        )

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
            repairs_since_check=await DQRepository.fetch_repairs_since_check(session),
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
        include_repaired: bool = False,
    ) -> CheckListingsResponse:
        rows = await DQRepository.fetch_listings(
            session, check_name, limit, offset, include_repaired
        )
        label = await DQRepository.fetch_label(session, check_name)
        counts = await DQRepository.fetch_listing_counts(session, check_name)

        # The three counts are reported beside the list rather than folded
        # into one number: "39 outstanding of 72 flagged" says something
        # "39" on its own does not.
        return CheckListingsResponse(
            check_name=check_name,
            label=label,
            flagged=counts["flagged"],
            repaired=counts["repaired"],
            outstanding=counts["outstanding"],
            total=len(rows),
            items=[AffectedListing(**r) for r in rows],
        )