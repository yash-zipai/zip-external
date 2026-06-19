"""
ZipAI — Cost of Living Data Repository (DAL).

Executes raw SQL queries against the ``cost_of_living`` schema.
All queries use parameterised binds — never string interpolation.

Save as: core/categories/cost_of_living/repository.py
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_col_index_scores(
    session: AsyncSession,
    zipcode: str,
) -> dict[str, Any] | None:
    """
    Query 1 — Cost-of-living index card (ZIP aggregate, latest snapshot).

    Returns a trimmed subset of the latest snapshot: affordability score,
    median annual income and the total monthly estimate. No line items, taxes
    or trend series. Returns None if the ZIP has no snapshot.
    """
    sql = text("""
        WITH latest_snapshot AS (
            SELECT *
            FROM cost_of_living.col_snapshot
            WHERE zipcode = :zip
            ORDER BY snapshot_date DESC
            LIMIT 1
        )
        SELECT
            s.zipcode,
            s.city,
            s.snapshot_date,
            s.affordability_score,
            i.median_annual_income,
            mc.total_monthly_estimate
        FROM latest_snapshot s
        LEFT JOIN cost_of_living.col_income i
               ON s.snapshot_id = i.snapshot_id
        LEFT JOIN cost_of_living.col_monthly_costs mc
               ON s.snapshot_id = mc.snapshot_id
    """)
    result = await session.execute(sql, {"zip": zipcode})
    row = result.fetchone()
    return dict(row._mapping) if row else None


async def get_col_breakdown(
    session: AsyncSession,
    zipcode: str,
) -> dict[str, Any] | None:
    """
    Query 2 — Full cost-of-living detail for the latest snapshot.

    Flat row containing affordability score, income, taxes, monthly costs and
    housing. The service nests these into income/monthly_costs/housing objects
    and merges the trend series. Returns None if the ZIP has no snapshot.
    """
    sql = text("""
        WITH latest_snapshot AS (
            SELECT *
            FROM cost_of_living.col_snapshot
            WHERE zipcode = :zip
            ORDER BY snapshot_date DESC
            LIMIT 1
        )
        SELECT
            s.zipcode,
            s.city,
            s.snapshot_date,
            s.affordability_score,
            i.median_annual_income,
            i.median_monthly_income,
            i.income_tax_rate,
            i.property_tax_rate,
            i.sales_tax_rate,
            mc.grocery_est,
            mc.gas_est,
            mc.dining_est,
            mc.gym,
            mc.childcare,
            mc.total_monthly_estimate,
            mc.grocery_share_pct,
            mc.gas_share_pct,
            mc.childcare_share_pct,
            h.mortgage_rate_pct
        FROM latest_snapshot s
        LEFT JOIN cost_of_living.col_income i
               ON s.snapshot_id = i.snapshot_id
        LEFT JOIN cost_of_living.col_monthly_costs mc
               ON s.snapshot_id = mc.snapshot_id
        LEFT JOIN cost_of_living.col_housing h
               ON s.snapshot_id = h.snapshot_id
    """)
    result = await session.execute(sql, {"zip": zipcode})
    row = result.fetchone()
    return dict(row._mapping) if row else None


async def get_col_trends(
    session: AsyncSession,
    zipcode: str,
) -> list[dict[str, Any]]:
    """
    Query 3 — Cost-of-living trend points for a ZIP.

    One row per (metric, date). Ordered by metric then date so the service can
    group consecutive rows into per-metric series in chronological order.
    """
    sql = text("""
        SELECT
            trend_date,
            metric,
            value
        FROM cost_of_living.col_trend
        WHERE zipcode = :zip
        ORDER BY metric, trend_date
    """)
    result = await session.execute(sql, {"zip": zipcode})
    return [dict(row._mapping) for row in result.fetchall()]