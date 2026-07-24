"""
ZipAI — Analytics Pydantic Schemas.

Contains request and response models for analytics APIs.

Endpoints:

    POST /internal/vector/events

    GET /v1/analytics/house/{house_id}/views

    GET /v1/analytics/usage

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