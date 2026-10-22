"""
ZipAI — Analytics Pydantic Schemas.

Contains request and response models for analytics APIs.

Endpoints:

    POST /internal/vector/events

    GET /v1/analytics/house/{house_id}/views

    GET /v1/analytics/usage

    GET /v1/analytics/overview

Save as:
core/analytics/schemas.py
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from pydantic import BaseModel, ConfigDict

# ============================================================================
# Request Model (Vector -> FastAPI)
# ============================================================================

class AnalyticsEventRequest(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True) # new added 31/07/2026
    """
    Request body received from Vector.
    """

    event_type: str = Field(..., description="Analytics event type.")

    category: str | None = Field(
        None,
        description="Event category."
    )

    action: str | None = Field(
        None,
        description="Action performed by the user."
    )

    resource_id: str | None = Field(
        None,
        description="Resource identifier (House ID, School ID, etc.)."
    )

    zipcode: str | None = Field(
        None,
        description="Related zipcode."
    )

    user_id: str | None = Field(
        None,
        description="User identifier."
    )

    session_id: str | None = Field(
        None,
        description="Session identifier."
    )

    page_name: str | None = Field(
        None,
        description="Application page name."
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional event metadata."
    )


# ============================================================================
# House View Response
# ============================================================================

class HouseViewResponse(BaseModel):
    """
    Response for:

        GET /v1/analytics/house/{house_id}/views
    """

    house_id: str = Field(
        ...,
        description="House identifier."
    )

    total_views: int = Field(
        ...,
        description="Total number of house views."
    )

    unique_visitors: int = Field(
        ...,
        description="Unique visitors based on session_id."
    )


# ============================================================================
# ZIPAI Usage Response
# ============================================================================

class ZipAIUsageItem(BaseModel):
    """
    Single usage summary row.
    """

    page_name: str | None = Field(
        None,
        description="Application page."
    )

    event_type: str = Field(
        ...,
        description="Analytics event."
    )

    total_events: int = Field(
        ...,
        description="Total number of events."
    )

    unique_users: int = Field(
        ...,
        description="Unique users (based on session_id)."
    )


class ZipAIUsageResponse(BaseModel):
    """
    Response for:

        GET /v1/analytics/usage
    """

    usage: list[ZipAIUsageItem] = Field(
        default_factory=list,
        description="ZIPAI usage summary."
    )


# ============================================================================
# Generic Response
# ============================================================================

class AnalyticsEventResponse(BaseModel):
    """
    Response for:

        POST /internal/vector/events
    """

    message: str = Field(
        ...,
        description="Operation status."
    )


# ============================================================================
# Admin Insights — Overview (user behaviour + engagement)
# Response for: GET /v1/analytics/overview
# ============================================================================

class UserActivity(BaseModel):
    total_users: int = Field(0, description="Distinct users with any tracked activity.")
    active_users: int = Field(0, description="Users active within the window (default 30d).")
    inactive_users: int = Field(0, description="Users seen before but not within the window.")
    new_users: int = Field(0, description="Users whose first activity was within the window.")
    returning_users: int = Field(0, description="Active users who are not brand new.")
    dau: int = Field(0, description="Distinct users active in the last 1 day.")
    wau: int = Field(0, description="Distinct users active in the last 7 days.")
    mau: int = Field(0, description="Distinct users active in the last 30 days.")
    active_window_days: int = Field(30, description="Window used for active/inactive.")


class ZipcodeStat(BaseModel):
    zipcode: str
    users: int = Field(0, description="Distinct users who searched this zipcode.")
    searches: int = Field(0, description="Total searches for this zipcode.")


class IndexUsage(BaseModel):
    total_users: int = Field(0, description="Distinct users across all index categories.")
    by_category: dict[str, int] = Field(default_factory=dict)


class ResourceStat(BaseModel):
    resource_id: str
    views: int = 0


class PageStat(BaseModel):
    page_name: str | None = None
    events: int = 0


class DayCount(BaseModel):
    day: str
    events: int = 0


class ContentEngagement(BaseModel):
    total_events: int = 0
    total_sessions: int = 0
    top_houses: list[ResourceStat] = Field(default_factory=list)
    top_pages: list[PageStat] = Field(default_factory=list)
    events_per_day: list[DayCount] = Field(default_factory=list)


class InsightsOverviewResponse(BaseModel):
    """Response for GET /v1/analytics/overview."""
    users: UserActivity
    top_zipcodes: list[ZipcodeStat] = Field(default_factory=list)
    index_usage: IndexUsage = Field(default_factory=IndexUsage)
    content: ContentEngagement = Field(default_factory=ContentEngagement)

# ============================================================================
# Trending Zipcodes — demand trend (this period vs previous period)
# Response for: GET /v1/analytics/trending-zipcodes
# ============================================================================

class TrendingZipcode(BaseModel):
    zipcode: str
    current_searches: int = Field(0, description="Searches in the current window.")
    previous_searches: int = Field(0, description="Searches in the previous window.")
    users: int = Field(0, description="Distinct users searching this zipcode now.")
    change_pct: float | None = Field(None, description="% change vs previous window (null if new).")
    trend: str = Field("flat", description="up | down | flat | new")


class TrendingZipcodesResponse(BaseModel):
    """Response for GET /v1/analytics/trending-zipcodes."""
    period_days: int = Field(7, description="Length of each comparison window, in days.")
    items: list[TrendingZipcode] = Field(default_factory=list)


# ============================================================================
# Peak Usage Hours (activity heatmap)  ->  GET /v1/analytics/activity-heatmap
# ============================================================================

class HeatmapCell(BaseModel):
    dow: int = Field(..., description="Day of week: 0=Sunday ... 6=Saturday.")
    day_name: str
    hour: int = Field(..., description="Hour of day, 0-23.")
    events: int = 0


class ActivityHeatmapResponse(BaseModel):
    days: int = 30
    cells: list[HeatmapCell] = Field(default_factory=list)
    busiest: HeatmapCell | None = None


# ============================================================================
# User Journey Funnel  ->  GET /v1/analytics/user-journey-funnel
# ============================================================================

class FunnelStep(BaseModel):
    step: str
    label: str
    users: int = 0
    pct_of_top: float = 0.0
    drop_from_prev_pct: float = 0.0


class UserJourneyFunnelResponse(BaseModel):
    days: int = 30
    steps: list[FunnelStep] = Field(default_factory=list)


# ============================================================================
# Session Quality  ->  GET /v1/analytics/session-quality
# ============================================================================

class SessionQualityResponse(BaseModel):
    days: int = 30
    total_sessions: int = 0
    avg_events_per_session: float = 0.0
    avg_session_seconds: float = 0.0
    avg_session_minutes: float = 0.0
    bounce_rate_pct: float = 0.0


# ============================================================================
# Search-to-View Conversion  ->  GET /v1/analytics/search-to-view-conversion
# ============================================================================

class SearchToViewConversionResponse(BaseModel):
    days: int = 30
    searchers: int = 0
    converters: int = 0
    conversion_rate_pct: float = 0.0


# ============================================================================
# API 9 — Market price stats (sold above / below list price)
# Response for: GET /v1/analytics/market-price-stats
# ============================================================================

from datetime import date  # API 9 ke liye


class MarketPriceArea(BaseModel):
    """Ek zipcode + city ka market summary, pichle 12 mahine ka."""

    zipcode: str
    city: str | None = None
    property_class: str = Field("all", description="'all' ya single_family etc.")

    sales_12m: int = Field(0, description="Pichle 12 mahine me bike ghar.")
    sales_3m: int = Field(0, description="Pichle 3 mahine me bike ghar.")
    sales_6m: int = Field(0, description="Pichle 6 mahine me bike ghar.")
    sales_9m: int = Field(0, description="Pichle 9 mahine me bike ghar.")

    count_above: int = Field(0, description="Asking se upar bike.")
    pct_above: float | None = Field(None, description="Upar bike, percentage me.")

    count_at: int = Field(0, description="Exactly asking pe bike.")
    pct_at: float | None = Field(None, description="Asking pe bike, percentage me.")

    count_below: int = Field(0, description="Asking se neeche bike.")
    pct_below: float | None = Field(None, description="Neeche bike, percentage me.")

    median_pct_above: float | None = Field(
        None, description="Upar bike gharon me typical kitna % upar.")
    median_amount_above: float | None = Field(
        None, description="Upar bike gharon me typical kitne dollar upar.")

    median_pct_below: float | None = Field(
        None, description="Neeche bike gharon me typical kitna % neeche.")
    median_amount_below: float | None = Field(
        None, description="Neeche bike gharon me typical kitne dollar neeche.")

    median_sale_price: float | None = None
    median_list_price: float | None = None


class MarketPriceStatsResponse(BaseModel):
    """
    Response for GET /v1/analytics/market-price-stats

    areas ek LIST hai, ek object nahi. 94010 me Burlingame aur
    Hillsborough dono hain -- Burlingame ka median $2.9M, mila ke
    $3.85M, jo kisi ka bhi sach nahi. Isliye alag-alag rows.
    """

    zipcode: str
    compared_to: str = Field(
        "original_list_price",
        description=(
            "Kis price se tulna hui. Original list price se, kyunki "
            "price_change events sirf May 2026 se hain. UI pe "
            "'compared to original list price' likhna zaroori hai."
        ),
    )
    areas: list[MarketPriceArea] = Field(default_factory=list)


class MarketPriceSale(BaseModel):
    """Ek bika hua ghar."""

    listing_key_numeric: str
    address: str | None = None
    city: str | None = None
    zipcode: str | None = None
    property_class: str | None = None

    bedrooms: float | None = None
    bathrooms: int | None = None
    living_area: float | None = None

    sale_date: date
    list_price: float
    close_price: float
    amount_vs_list: float = Field(
        ..., description="close_price - list_price. Positive = upar bika.")
    pct_vs_list: float = Field(
        ..., description="Wahi farq percentage me. Positive = upar bika.")

    latitude: float | None = None
    longitude: float | None = None


class MarketPriceSalesResponse(BaseModel):
    """Response for GET /v1/analytics/market-price-stats/sales"""

    zipcode: str
    city: str | None = None
    window_months: int = 3
    direction: str = Field("all", description="over | under | all")
    total: int = Field(0, description="Pagination ke liye kul rows.")
    limit: int = 50
    offset: int = 0
    sales: list[MarketPriceSale] = Field(default_factory=list)