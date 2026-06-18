"""
ZipAI — Jobs (Employer) Data Repository (DAL).

Executes raw SQL queries against the ``employer`` schema.
All queries use parameterised binds — never string interpolation.

The SQL mirrors the original queries provided by the employer data team.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# from logging import get_logger

# logger = get_logger(__name__)


async def get_breakdown(
    session: AsyncSession,
    zipcode: str,
) -> list[dict[str, Any]]:
    """
    Query 1 — Per-industry employer breakdown for a zipcode.

    Joins the zip snapshot to its industry/employer stats and returns one row
    per industry sector, ordered by rank ascending. ``zipcode``, ``city``,
    ``latitude`` and ``longitude`` come from the snapshot and are constant
    across the rows for a given zipcode.

    Returns:
        A list of dicts, one per industry sector.
    """
    sql = text("""
        SELECT
            s.zipcode,
            s.city,
            z.rank,
            z.naics_code,
            z.sector_name,
            z.establishments_zip,
            z.share_pct,
            z.employment_zip_suppressed,
            z.payroll_k_zip_suppressed,
            z.employment_county,
            z.payroll_k_county,
            z.establishments_county,
            s.latitude,
            s.longitude
        FROM employer.zip_snapshots s
        JOIN employer.zip_industry_employer_stats z
            ON s.snapshot_id = z.snapshot_id
        WHERE s.zipcode = :zip
        ORDER BY z.rank ASC
    """)

    result = await session.execute(sql, {"zip": zipcode})
    rows = [dict(row._mapping) for row in result.fetchall()]

    # logger.debug("repo_get_breakdown", zipcode=zipcode, sectors=len(rows))
    return rows


async def get_score(
    session: AsyncSession,
    zipcode: str,
) -> dict[str, Any] | None:
    """
    Query 2 — Aggregated job-market score for a zipcode.

    Rolls the per-industry rows into a single summary: the job-market score
    (sum of sector share %), the number of sectors and the total number of
    establishments.

    Returns:
        A single dict, or ``None`` if the zipcode has no snapshot.
    """
    sql = text("""
        SELECT
            s.zipcode,
            s.city,
            ROUND(SUM(z.share_pct), 2)   AS job_market_score,
            COUNT(*)                     AS sector_count,
            SUM(z.establishments_zip)    AS total_establishments
        FROM employer.zip_snapshots s
        JOIN employer.zip_industry_employer_stats z
            ON s.snapshot_id = z.snapshot_id
        WHERE s.zipcode = :zip
        GROUP BY s.zipcode, s.city
    """)

    result = await session.execute(sql, {"zip": zipcode})
    row = result.fetchone()

    # logger.debug("repo_get_score", zipcode=zipcode, found=row is not None)
    return dict(row._mapping) if row is not None else None