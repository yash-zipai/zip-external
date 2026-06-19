"""
ZipAI — Cost of Living Pydantic response schemas.
<<<<<<< HEAD

Contains BOTH the new-scheme contracts and the legacy ones, so existing
endpoints keep working during migration:
  NEW:
    - CostOfLivingIndexScoresResponse  (index card)
    - CostOfLivingBreakdownResponse    (nested: income / monthly_costs / housing / trends)
  LEGACY (kept for back-compat):
    - CostOfLivingBreakdownLegacyResponse (flat breakdown)
    - CostOfLivingTrendResponse           (housing-market-trends)

Save as: core/categories/cost_of_living/schemas.py
=======
>>>>>>> 693e6ee (feat: implement TTL caching module and developed api's schools and cost of living categories)
"""

from __future__ import annotations

from pydantic import BaseModel, Field


<<<<<<< HEAD
# == NEW: Index Scores =========================================================


class CostOfLivingIndexScoresResponse(BaseModel):
    """Response for GET /v1/cost-of-living/zipcode/{zip}/index-scores."""

    zipcode: str | None = Field(None, description="Queried zipcode.")
    city: str | None = Field(None, description="City name for the zipcode.")
    affordability_score: float | None = Field(None, description="Affordability score, 0-100.")
    median_annual_income: float | None = Field(None, description="Median annual income.")
    total_monthly_estimate: float | None = Field(None, description="Estimated total monthly cost.")
    snapshot_date: str | None = Field(None, description="Date of the snapshot used.")


# == NEW: Breakdown (nested) ===================================================


class ColIncome(BaseModel):
    median_annual_income: float | None = None
    median_monthly_income: float | None = None
    income_tax_rate: float | None = None
    property_tax_rate: float | None = None
    sales_tax_rate: float | None = None


class ColMonthlyCosts(BaseModel):
    grocery_est: float | None = None
    gas_est: float | None = None
    dining_est: float | None = None
    gym: float | None = None
    childcare: float | None = None
    total_monthly_estimate: float | None = None


class ColHousing(BaseModel):
    mortgage_rate_pct: float | None = None


class ColTrendPoint(BaseModel):
    date: str | None = Field(None, description="Point date (YYYY-MM-DD).")
    value: float | None = Field(None, description="Metric value at that date.")


class ColTrendSeries(BaseModel):
    metric: str = Field(
        ..., description="Metric: mortgage_rate | grocery_cpi | dining_cpi | gas_price."
    )
    series: list[ColTrendPoint] = Field(default_factory=list, description="Points, oldest first.")


class CostOfLivingBreakdownResponse(BaseModel):
    """Response for GET /v1/cost-of-living/zipcode/{zip}/breakdown (nested)."""

    zipcode: str | None = Field(None, description="Queried zipcode.")
    affordability_score: float | None = Field(None, description="Affordability score, 0-100.")
    income: ColIncome = Field(default_factory=ColIncome)
    monthly_costs: ColMonthlyCosts = Field(default_factory=ColMonthlyCosts)
    housing: ColHousing = Field(default_factory=ColHousing)
    trends: list[ColTrendSeries] = Field(default_factory=list)


# == LEGACY: flat breakdown (kept for back-compat) =============================


class CostOfLivingBreakdownLegacyResponse(BaseModel):
    """Legacy flat response for GET /api/zipcode/{zip}/location-indices/col/breakdown/."""

=======
# ── COL Breakdown ────────────────────────────────────────────────────────────


class CostOfLivingBreakdownResponse(BaseModel):
>>>>>>> 693e6ee (feat: implement TTL caching module and developed api's schools and cost of living categories)
    zipcode: str | None = None
    city: str | None = None
    snapshot_date: str | None = None
    col_index: float | None = None
    median_annual_income: float | None = None
    median_monthly_income: float | None = None
    income_tax_rate: float | None = None
    property_tax_rate: float | None = None
    sales_tax_rate: float | None = None
    grocery_est: float | None = None
    gas_est: float | None = None
    dining_est: float | None = None
    gym: float | None = None
    childcare: float | None = None
    total_monthly_estimate: float | None = None
    grocery_share_pct: float | None = None
    gas_share_pct: float | None = None
    childcare_share_pct: float | None = None
    mortgage_rate_pct: float | None = None


<<<<<<< HEAD
# == LEGACY: housing-market-trends (kept for back-compat) ======================
=======
# ── Housing Market Trends ────────────────────────────────────────────────────
>>>>>>> 693e6ee (feat: implement TTL caching module and developed api's schools and cost of living categories)


class CostOfLivingTrendItem(BaseModel):
    trend_date: str | None = None
    metric: str | None = None
    value: float | None = None


class CostOfLivingTrendResponse(BaseModel):
    zipcode: str
<<<<<<< HEAD
    trends: list[CostOfLivingTrendItem] = Field(default_factory=list)
=======
    trends: list[CostOfLivingTrendItem] = Field(default_factory=list)
>>>>>>> 693e6ee (feat: implement TTL caching module and developed api's schools and cost of living categories)
