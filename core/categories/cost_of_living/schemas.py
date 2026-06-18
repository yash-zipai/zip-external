"""
ZipAI — Cost of Living Pydantic response schemas.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── COL Breakdown ────────────────────────────────────────────────────────────


class CostOfLivingBreakdownResponse(BaseModel):
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


# ── Housing Market Trends ────────────────────────────────────────────────────


class CostOfLivingTrendItem(BaseModel):
    trend_date: str | None = None
    metric: str | None = None
    value: float | None = None


class CostOfLivingTrendResponse(BaseModel):
    zipcode: str
    trends: list[CostOfLivingTrendItem] = Field(default_factory=list)
