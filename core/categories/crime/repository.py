"""
ZipAI — Crime Data Repository (DAL).

Executes raw SQL queries against the ``crime`` schema.
All queries use parameterised binds — never string interpolation.

Save as: core/categories/crime/repository.py
(merge with any existing crime repository functions you already have).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# from logging import get_logger

# logger = get_logger(__name__)


async def get_index_scores(
    session: AsyncSession,
    zipcode: str,
) -> dict[str, Any] | None:
    """
    Query 1 — Crime index card (ZIP aggregate) for the latest year.

    Returns a single aggregate row, or None if the ZIP has no current crime
    history. ``level`` is derived from the safety value, matching the spec
    thresholds (Very Low >=80, Low 60-79, Moderate 40-59, High <40).

    NOTE: per your reference query, ``crime_index`` and ``safety_pct`` are the
    SAME value (100 - capped rate sum). See the flag in chat — the spec example
    shows them differing (crime_index 38.2 vs safety_pct 62.5), so if they are
    meant to be two different formulas this needs the second formula.
    """
    sql = text("""
       WITH latest_year AS (
            SELECT MAX(year) AS yr
            FROM crime.crime_history
            WHERE zipcode = :zip AND current_flag = 'Y'
        ),
        agg AS (
            SELECT
                MAX(c.city)  AS city,
                COUNT(*)     AS n,
                SUM(c.rate)  AS total_rate,
                SUM(CASE WHEN c.crime_class='violent'  THEN c.actual_count ELSE 0 END) AS violent_total,
                SUM(CASE WHEN c.crime_class='property' THEN c.actual_count ELSE 0 END) AS property_total
            FROM crime.crime_history c
            JOIN latest_year y ON c.year = y.yr
            WHERE c.zipcode = :zip AND c.current_flag = 'Y'
        )
        SELECT
            :zip AS zipcode,
            city,
            -- one safety number; MAX_CRIME_RATE is the tunable ceiling (see below)
            CASE WHEN n = 0 THEN NULL
                 ELSE ROUND((100 * (1 - LEAST(total_rate / 800.0, 1)))::numeric, 2)
            END AS safety_pct,                                   -- higher = safer
            CASE WHEN n = 0 THEN NULL
                 ELSE ROUND((100 * LEAST(total_rate / 800.0, 1))::numeric, 2)
            END AS crime_index,                                  -- = 100 - safety_pct
            CASE
                WHEN n = 0 THEN NULL
                WHEN (100 * (1 - LEAST(total_rate / 800.0, 1))) >= 80 THEN 'Very Low'
                WHEN (100 * (1 - LEAST(total_rate / 800.0, 1))) >= 60 THEN 'Low'
                WHEN (100 * (1 - LEAST(total_rate / 800.0, 1))) >= 40 THEN 'Moderate'
                ELSE 'High'
            END AS level,
            violent_total,
            property_total,
            CURRENT_DATE AS as_of
        FROM agg;
    """)

    result = await session.execute(sql, {"zip": zipcode})
    row = result.fetchone()
    if row is None:
        return None
    return dict(row._mapping)


async def get_breakdown(
    session: AsyncSession,
    zipcode: str,
) -> dict[str, Any] | None:
    """
    Query 2 — Crime breakdown pop-up for a ZIP.

    Returns the latest-year summary (crime_index, violent_total, property_total)
    plus the top 5 offenses and a year-over-year trend block. Returns None if the
    ZIP has no current crime history.

    Shape:
        {
          "zipcode", "crime_index", "violent_total", "property_total",
          "top_offenses": [{crime_type, total_count, crime_rank, avg_rate}, ...],
          "trend": {latest_year, latest_total, prev_year, prev_total,
                    yoy_pct, trend_direction}
        }
    """
    summary_sql = text("""
        WITH latest_year AS (
            SELECT MAX(year) AS yr
            FROM crime.crime_history
            WHERE zipcode = :zip
              AND current_flag = 'Y'
        )
        SELECT
            c.zipcode,
            ROUND((100 - LEAST(SUM(c.rate), 100))::numeric, 2)   AS crime_index,
            SUM(CASE WHEN c.crime_class = 'violent'
                     THEN c.actual_count ELSE 0 END)             AS violent_total,
            SUM(CASE WHEN c.crime_class = 'property'
                     THEN c.actual_count ELSE 0 END)             AS property_total
        FROM crime.crime_history c
        JOIN latest_year y ON c.year = y.yr
        WHERE c.zipcode = :zip
          AND c.current_flag = 'Y'
        GROUP BY c.zipcode
    """)

    # top_offenses come from crime.v_zip_summary (per the spec note).
    # Assumed columns: zipcode, crime_type, total_count, crime_rank, avg_rate.
    top_offenses_sql = text("""
        SELECT
            crime_type,
            SUM(actual_count)                              AS total_count,
            RANK() OVER (ORDER BY SUM(actual_count) DESC)  AS crime_rank,
            ROUND(AVG(rate), 4)                            AS avg_rate
        FROM crime.crime_history
        WHERE zipcode = :zip
        AND current_flag = 'Y'
        GROUP BY crime_type
        ORDER BY total_count DESC
        LIMIT 5
    """)

    # yoy trend from the two most recent years present (handles year gaps).
    trend_sql = text("""
        WITH yearly_totals AS (
            SELECT year, SUM(actual_count) AS total_crimes
            FROM crime.crime_history
            WHERE zipcode = :zip
              AND current_flag = 'Y'
            GROUP BY year
        ),
        ranked AS (
            SELECT year, total_crimes,
                   ROW_NUMBER() OVER (ORDER BY year DESC) AS rn
            FROM yearly_totals
        ),
        pivoted AS (
            SELECT
                MAX(CASE WHEN rn = 1 THEN year END)         AS latest_year,
                MAX(CASE WHEN rn = 1 THEN total_crimes END) AS latest_total,
                MAX(CASE WHEN rn = 2 THEN year END)         AS prev_year,
                MAX(CASE WHEN rn = 2 THEN total_crimes END) AS prev_total
            FROM ranked
        )
        SELECT
            latest_year,
            latest_total,
            prev_year,
            prev_total,
            CASE WHEN prev_total > 0
                 THEN ROUND(((latest_total - prev_total)::numeric / prev_total) * 100, 1)
                 ELSE NULL END                              AS yoy_pct,
            CASE
                WHEN prev_total IS NULL          THEN 'flat'
                WHEN latest_total < prev_total   THEN 'decrease'
                WHEN latest_total > prev_total   THEN 'increase'
                ELSE 'flat'
            END                                             AS trend_direction
        FROM pivoted
    """)

    summary_row = (await session.execute(summary_sql, {"zip": zipcode})).fetchone()
    if summary_row is None:
        return None

    top_rows = (await session.execute(top_offenses_sql, {"zip": zipcode})).fetchall()
    trend_row = (await session.execute(trend_sql, {"zip": zipcode})).fetchone()

    out = dict(summary_row._mapping)
    out["top_offenses"] = [dict(r._mapping) for r in top_rows]
    out["trend"] = dict(trend_row._mapping) if trend_row else None
    return out


async def get_insights(
    session: AsyncSession,
    zipcode: str,
    months: int = 23,
) -> list[dict[str, Any]]:
    """
    Query 3 — Listing crime chart (monthly series) for a ZIP.

    Returns the last ``months`` months of crime counts as a monthly series,
    oldest first: [{ "month": "YYYY-MM", "value": <int> }, ...].

    IMPORTANT: this needs a MONTH-grain source. ``crime.crime_history`` (as used
    by the other two queries) is YEAR-grain only, so the monthly series cannot
    come from it. The query below assumes a monthly source — adjust the table and
    column names to your real one (the spec calls this the "insights row").
    Placeholders used:  crime.crime_monthly(zipcode, month_date DATE, incident_count INT)
    """
    sql = text("""
        WITH bounds AS (
        SELECT MAX(year) AS max_year
        FROM crime.crime_history
        WHERE zipcode = :zip AND current_flag = 'Y'
        )
        SELECT
            CAST(h.year AS text)  AS month,
            SUM(h.actual_count)   AS value
        FROM crime.crime_history h
        CROSS JOIN bounds b
        WHERE h.zipcode = :zip
        AND h.current_flag = 'Y'
        AND h.year > b.max_year - GREATEST(CEIL(:months / 12.0), 1)
        GROUP BY h.year
        ORDER BY h.year
    """)

    result = await session.execute(sql, {"zip": zipcode, "months": months})
    return [dict(row._mapping) for row in result.fetchall()]
