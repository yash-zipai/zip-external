"""
ZipAI — Cost of Living Service Layer.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import (
    cached,
    col_breakdown_cache,
    col_trend_cache,
)
from core.categories.cost_of_living.repository import (
    get_col_breakdown as repo_get_col_breakdown,
    get_col_trends as repo_get_col_trends,
)
from core.categories.cost_of_living.schemas import (
    CostOfLivingBreakdownResponse,
    CostOfLivingTrendItem,
    CostOfLivingTrendResponse,
)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


class CostOfLivingService:
    @staticmethod
    @cached(col_breakdown_cache)
    async def get_col_breakdown(
        session: AsyncSession,
        zipcode: str,
    ) -> CostOfLivingBreakdownResponse | None:
        row = await repo_get_col_breakdown(session, zipcode)
        if not row:
            return None
        
        return CostOfLivingBreakdownResponse(
            zipcode=row.get("zipcode"),
            city=row.get("city"),
            snapshot_date=_to_str(row.get("snapshot_date")),
            col_index=_to_float(row.get("col_index")),
            median_annual_income=_to_float(row.get("median_annual_income")),
            median_monthly_income=_to_float(row.get("median_monthly_income")),
            income_tax_rate=_to_float(row.get("income_tax_rate")),
            property_tax_rate=_to_float(row.get("property_tax_rate")),
            sales_tax_rate=_to_float(row.get("sales_tax_rate")),
            grocery_est=_to_float(row.get("grocery_est")),
            gas_est=_to_float(row.get("gas_est")),
            dining_est=_to_float(row.get("dining_est")),
            gym=_to_float(row.get("gym")),
            childcare=_to_float(row.get("childcare")),
            total_monthly_estimate=_to_float(row.get("total_monthly_estimate")),
            grocery_share_pct=_to_float(row.get("grocery_share_pct")),
            gas_share_pct=_to_float(row.get("gas_share_pct")),
            childcare_share_pct=_to_float(row.get("childcare_share_pct")),
            mortgage_rate_pct=_to_float(row.get("mortgage_rate_pct")),
        )

    @staticmethod
    @cached(col_trend_cache)
    async def get_col_trends(
        session: AsyncSession,
        zipcode: str,
    ) -> CostOfLivingTrendResponse:
        rows = await repo_get_col_trends(session, zipcode)
        trends = [
            CostOfLivingTrendItem(
                trend_date=_to_str(row.get("trend_date")),
                metric=row.get("metric"),
                value=_to_float(row.get("value")),
            )
            for row in rows
        ]
        return CostOfLivingTrendResponse(zipcode=zipcode, trends=trends)
