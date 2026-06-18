"""
ZipAI — Crime Data Repository (DAL).

Executes raw SQL queries against the ``crime`` schema.
All queries use parameterised binds — never string interpolation.

The SQL mirrors the original queries provided by the crime data team.
Only rows flagged as current (``current_flag = 'Y'``) are considered.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# from logging import get_logger

# logger = get_logger(__name__)


async def get_crime_summary(
    session: AsyncSession,
    zipcode: str,
) -> list[dict[str, Any]]:
    """
    Query 1 — Per-year crime summary for a zipcode.

    Aggregates the *current* crime history for a single zipcode into one row
    per year, splitting counts/rates into violent and property classes while
    also reporting the all-class totals.

    Returns:
        A list of dicts, one per year, ordered by year ascending.
    """
    sql = text("""
        WITH crime_summary AS (
            SELECT
                zipcode,
                city,
                year,
                SUM(actual_count)                                                    AS total_crimes,
                SUM(rate)                                                            AS crime_rate_index,
                SUM(CASE WHEN crime_class = 'violent'  THEN actual_count ELSE 0 END) AS violent_count,
                SUM(CASE WHEN crime_class = 'violent'  THEN rate         ELSE 0 END) AS violent_rate,
                SUM(CASE WHEN crime_class = 'property' THEN actual_count ELSE 0 END) AS property_count,
                SUM(CASE WHEN crime_class = 'property' THEN rate         ELSE 0 END) AS property_rate
            FROM crime.crime_history
            WHERE zipcode = :zip
              AND current_flag = 'Y'
            GROUP BY zipcode, city, year
        )
        SELECT *
        FROM crime_summary
        ORDER BY year
    """)

    result = await session.execute(sql, {"zip": zipcode})
    rows = [dict(row._mapping) for row in result.fetchall()]

    # logger.debug("repo_get_crime_summary", zipcode=zipcode, years=len(rows))
    return rows


async def get_crime_breakdown(
    session: AsyncSession,
    zipcode: str,
) -> list[dict[str, Any]]:
    """
    Query 2 — Crime breakdown for a zipcode's most recent year.

    Returns one row per crime type for the latest available (current) year,
    ordered by rate descending. The ``year`` column is included in the SELECT
    so callers can report which year the breakdown refers to (all rows share
    the same max year).
    """
    sql = text("""
        SELECT
            crime_type,
            crime_class,
            actual_count,
            rate,
            year
        FROM crime.crime_history
        WHERE zipcode = :zip
          AND current_flag = 'Y'
          AND year = (
                SELECT MAX(year)
                FROM crime.crime_history
                WHERE zipcode = :zip
                  AND current_flag = 'Y'
            )
        ORDER BY rate DESC
    """)

    result = await session.execute(sql, {"zip": zipcode})
    rows = [dict(row._mapping) for row in result.fetchall()]

    # logger.debug("repo_get_crime_breakdown", zipcode=zipcode, types=len(rows))
    return rows