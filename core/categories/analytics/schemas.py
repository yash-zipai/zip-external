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


# ============================================================================
# Request Model (Vector -> FastAPI)
# ============================================================================

class AnalyticsEventRequest(BaseModel):
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
