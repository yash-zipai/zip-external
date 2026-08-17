"""
ZipAI — Rate (mortgage) Data Repository (DAL).

Reads signal.mortgage_rate (weekly Freddie Mac PMMS values, loaded from FRED).
All queries use bound parameters.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_current(session: AsyncSession) -> dict[str, Any] | None:
    """
    Latest weekly rate plus the week-over-week change for both terms.

    Uses LAG() so a single row carries the current value and the delta versus
    the previous week. Returns None if the table is empty.
    """
    sql = text("""
        WITH ranked AS (
            SELECT rate_date,
                   rate_30yr,
                   rate_15yr,
                   rate_30yr - LAG(rate_30yr) OVER (ORDER BY rate_date) AS change_30yr_wow,
                   rate_15yr - LAG(rate_15yr) OVER (ORDER BY rate_date) AS change_15yr_wow
            FROM   signal.mortgage_rate
        )
        SELECT rate_date, rate_30yr, rate_15yr, change_30yr_wow, change_15yr_wow
        FROM   ranked
        ORDER  BY rate_date DESC
        LIMIT  1
    """)
    result = await session.execute(sql)
    row = result.fetchone()
    return dict(row._mapping) if row is not None else None


async def get_history(session: AsyncSession, months: int | None = None) -> list[dict[str, Any]]:
    """
    Weekly rate series, oldest first. Feeds both line charts (30-yr and 15-yr).

    Args:
        months: If given, restrict to the last N months; otherwise return all history.
    """
    if months is not None:
        sql = text("""
            SELECT rate_date, rate_30yr, rate_15yr
            FROM   signal.mortgage_rate
            WHERE  rate_date >= (now()::date - make_interval(months => :months))
            ORDER  BY rate_date
        """)
        params = {"months": months}
    else:
        sql = text("""
            SELECT rate_date, rate_30yr, rate_15yr
            FROM   signal.mortgage_rate
            ORDER  BY rate_date
        """)
        params = {}

    result = await session.execute(sql, params)
    return [dict(r._mapping) for r in result.fetchall()]