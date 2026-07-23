"""
ZipAI — Jobs (Employer) Data Repository (DAL).

Executes raw SQL queries against the ``employer`` schema.
All queries use parameterised binds — never string interpolation.

Updated to match the new ``/v1/jobs`` API contract:

  * get_breakdown    -> GET /v1/jobs/zipcode/{zip}/breakdown      (top 5 sectors)
  * get_index_score  -> GET /v1/jobs/zipcode/{zip}/index-scores   (zip aggregate)

ASSUMPTIONS (please confirm with the employer data team):
  1. ``employer.zip_snapshots`` exposes ``county_fips`` and ``snapshot_year``
     columns. The original queries never selected them; the new contract needs
     both. If they live elsewhere (e.g. a county dimension table), adjust the
     JOIN/SELECT accordingly.
  2. ``jobs_index_score`` is a 0–100 employer-diversity score. The spec only
     says "derived from employer diversity / top-sector concentration" without
     giving a formula, so this uses an inverse Herfindahl–Hirschman index:

         score = ROUND( (1 - Σ (share_pct / 100)^2) * 100 )

     Higher = more diverse / less top-sector concentration (a single sector at
     100% share -> 0; many evenly-sized sectors -> near 100). Swap this
     expression in get_index_score() if the data team defines it differently.
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
    Query 1 — Top-5 per-industry employer breakdown for a zipcode.

    Joins the zip snapshot to its industry/employer stats and returns the five
    top-ranked industry sectors (rank ascending). ``zipcode``, ``city``,
    ``county_fips`` and ``snapshot_year`` come from the snapshot and are
    constant across the rows for a given zipcode.

    Note: ``employment_county`` (total jobs) and ``payroll_k_county`` (annual
    payroll in $1,000s) are county-level Census figures.

    Returns:
        A list of up to five dicts, one per industry sector.
    """
    sql = text("""
        SELECT
        s.zipcode,
        s.city,
        s.county_fips,
        s.zip_snapshot_year,
        z.rank,
        z.naics_code,
        z.sector_name,
        z.establishments_zip,
        z.share_pct,
        z.employment_county,
        z.payroll_k_county,
        z.establishments_county
       FROM employer.zip_snapshots s
       LEFT JOIN employer.zip_industry_employer_stats z
       ON s.snapshot_id = z.snapshot_id
       WHERE s.zipcode = :zip
       ORDER BY z.rank ASC 
       LIMIT 5;

    """)

    result = await session.execute(sql, {"zip": zipcode})
    rows = [dict(row._mapping) for row in result.fetchall()]

    # logger.debug("repo_get_breakdown", zipcode=zipcode, sectors=len(rows))
    return rows


async def get_index_score(
    session: AsyncSession,
    zipcode: str,
) -> dict[str, Any] | None:
    """
    Query 2 — Aggregated jobs index score for a zipcode.

    Rolls the per-industry rows into a single summary: a 0–100 jobs index score
    (employer diversity / inverse top-sector concentration), the top-ranked
    sector name, and the total number of establishments in the zip.

    Returns:
        A single dict, or ``None`` if the zipcode has no snapshot.
    """
    sql = text("""
         WITH latest_snap AS (
    SELECT snapshot_id, city, county_fips, zip_snapshot_year
    FROM employer.zip_snapshots
    WHERE zipcode = :zip
    ORDER BY zip_snapshot_year DESC NULLS LAST
    LIMIT 1
)
SELECT
    :zip                                       AS zipcode,
    MAX(ls.city)                               AS city,
    MAX(ls.county_fips)                        AS county_fips,
    COALESCE(MAX(ls.zip_snapshot_year), 0)     AS zip_snapshot_year,
    CASE
        WHEN COUNT(z.snapshot_id) = 0 THEN NULL
        ELSE ROUND((1 - SUM(POWER(COALESCE(z.share_pct, 0) / 100.0, 2))) * 100)::int
    END                                        AS jobs_index_score,
    (ARRAY_AGG(z.sector_name ORDER BY z.rank ASC))[1] AS top_sector,
    SUM(z.establishments_zip)                  AS establishment_count
FROM latest_snap ls
LEFT JOIN employer.zip_industry_employer_stats z
    ON z.snapshot_id = ls.snapshot_id;
    """)

    result = await session.execute(sql, {"zip": zipcode})
    row = result.fetchone()

    # logger.debug("repo_get_index_score", zipcode=zipcode, found=row is not None)
    return dict(row._mapping) if row is not None else None
