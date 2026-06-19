"""
ZipAI — Cost of Living Service Layer.
<<<<<<< HEAD

Holds new-scheme methods (index-scores, nested breakdown) plus the legacy
methods (flat breakdown, housing-market-trends) for back-compat. Legacy methods
are intentionally NOT cached, so they don't share a cache key with the new
methods (the cache decorator keys on args only, not the function name).

Save as: core/categories/cost_of_living/service.py
=======
>>>>>>> 693e6ee (feat: implement TTL caching module and developed api's schools and cost of living categories)
"""

from __future__ import annotations

<<<<<<< HEAD
from collections import OrderedDict
=======
>>>>>>> 693e6ee (feat: implement TTL caching module and developed api's schools and cost of living categories)
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import (
    cached,
    col_breakdown_cache,
<<<<<<< HEAD
    col_index_scores_cache,
)
from core.categories.cost_of_living.repository import (
    get_col_breakdown as repo_get_col_breakdown,
    get_col_index_scores as repo_get_col_index_scores,
    get_col_trends as repo_get_col_trends,
)
from core.categories.cost_of_living.schemas import (
    ColHousing,
    ColIncome,
    ColMonthlyCosts,
    ColTrendPoint,
    ColTrendSeries,
    CostOfLivingBreakdownLegacyResponse,
    CostOfLivingBreakdownResponse,
    CostOfLivingIndexScoresResponse,
=======
    col_trend_cache,
)
from core.categories.cost_of_living.repository import (
    get_col_breakdown as repo_get_col_breakdown,
    get_col_trends as repo_get_col_trends,
)
from core.categories.cost_of_living.schemas import (
    CostOfLivingBreakdownResponse,
>>>>>>> 693e6ee (feat: implement TTL caching module and developed api's schools and cost of living categories)
    CostOfLivingTrendItem,
    CostOfLivingTrendResponse,
)

<<<<<<< HEAD
# Preferred ordering of trend metrics in the new breakdown (others appended).
_METRIC_ORDER = ["mortgage_rate", "grocery_cpi", "dining_cpi", "gas_price"]

=======
>>>>>>> 693e6ee (feat: implement TTL caching module and developed api's schools and cost of living categories)

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
<<<<<<< HEAD

    # ── NEW: index scores ─────────────────────────────────────────────────────
    @staticmethod
    @cached(col_index_scores_cache)
    async def get_col_index_scores(
        session: AsyncSession,
        zipcode: str,
    ) -> CostOfLivingIndexScoresResponse | None:
        row = await repo_get_col_index_scores(session, zipcode)
        if not row:
            return None
        return CostOfLivingIndexScoresResponse(
            zipcode=row.get("zipcode"),
            city=row.get("city"),
            affordability_score=_to_float(row.get("affordability_score")),
            median_annual_income=_to_float(row.get("median_annual_income")),
            total_monthly_estimate=_to_float(row.get("total_monthly_estimate")),
            snapshot_date=_to_str(row.get("snapshot_date")),
        )

    # ── NEW: nested breakdown ─────────────────────────────────────────────────
=======
>>>>>>> 693e6ee (feat: implement TTL caching module and developed api's schools and cost of living categories)
    @staticmethod
    @cached(col_breakdown_cache)
    async def get_col_breakdown(
        session: AsyncSession,
        zipcode: str,
    ) -> CostOfLivingBreakdownResponse | None:
        row = await repo_get_col_breakdown(session, zipcode)
        if not row:
            return None
<<<<<<< HEAD

        income = ColIncome(
            median_annual_income=_to_float(row.get("median_annual_income")),
            median_monthly_income=_to_float(row.get("median_monthly_income")),
            income_tax_rate=_to_float(row.get("income_tax_rate")),
            property_tax_rate=_to_float(row.get("property_tax_rate")),
            sales_tax_rate=_to_float(row.get("sales_tax_rate")),
        )
        monthly_costs = ColMonthlyCosts(
            grocery_est=_to_float(row.get("grocery_est")),
            gas_est=_to_float(row.get("gas_est")),
            dining_est=_to_float(row.get("dining_est")),
            gym=_to_float(row.get("gym")),
            childcare=_to_float(row.get("childcare")),
            total_monthly_estimate=_to_float(row.get("total_monthly_estimate")),
        )
        housing = ColHousing(
            mortgage_rate_pct=_to_float(row.get("mortgage_rate_pct")),
        )

        trend_rows = await repo_get_col_trends(session, zipcode)
        series_map: "OrderedDict[str, list[ColTrendPoint]]" = OrderedDict()
        for r in trend_rows:
            metric = r.get("metric")
            if metric is None:
                continue
            series_map.setdefault(metric, []).append(
                ColTrendPoint(
                    date=_to_str(r.get("trend_date")),
                    value=_to_float(r.get("value")),
                )
            )
        ordered_metrics = [m for m in _METRIC_ORDER if m in series_map]
        ordered_metrics += [m for m in series_map if m not in _METRIC_ORDER]
        trends = [ColTrendSeries(metric=m, series=series_map[m]) for m in ordered_metrics]

        return CostOfLivingBreakdownResponse(
            zipcode=row.get("zipcode"),
            affordability_score=_to_float(row.get("affordability_score")),
            income=income,
            monthly_costs=monthly_costs,
            housing=housing,
            trends=trends,
        )

    # ── LEGACY: flat breakdown (uncached) ─────────────────────────────────────
    @staticmethod
    async def get_col_breakdown_legacy(
        session: AsyncSession,
        zipcode: str,
    ) -> CostOfLivingBreakdownLegacyResponse | None:
        row = await repo_get_col_breakdown(session, zipcode)
        if not row:
            return None
        return CostOfLivingBreakdownLegacyResponse(
            zipcode=row.get("zipcode"),
            city=row.get("city"),
            snapshot_date=_to_str(row.get("snapshot_date")),
            col_index=_to_float(row.get("affordability_score")),
=======
        
        return CostOfLivingBreakdownResponse(
            zipcode=row.get("zipcode"),
            city=row.get("city"),
            snapshot_date=_to_str(row.get("snapshot_date")),
            col_index=_to_float(row.get("col_index")),
>>>>>>> 693e6ee (feat: implement TTL caching module and developed api's schools and cost of living categories)
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

<<<<<<< HEAD
    # ── LEGACY: housing-market-trends (uncached) ──────────────────────────────
    @staticmethod
=======
    @staticmethod
    @cached(col_trend_cache)
>>>>>>> 693e6ee (feat: implement TTL caching module and developed api's schools and cost of living categories)
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
<<<<<<< HEAD
        return CostOfLivingTrendResponse(zipcode=zipcode, trends=trends)
=======
        return CostOfLivingTrendResponse(zipcode=zipcode, trends=trends)
>>>>>>> 693e6ee (feat: implement TTL caching module and developed api's schools and cost of living categories)
