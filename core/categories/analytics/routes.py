"""
Analytics API Routes.

Included by main.py WITHOUT a prefix:

    app.include_router(analytics_router)

Available Endpoints:

    POST /internal/vector/events

    GET /v1/analytics/house/{house_id}/views

    GET /v1/analytics/usage

    GET /v1/analytics/overview

    GET /v1/analytics/trending-zipcodes

    GET /v1/analytics/activity-heatmap

    GET /v1/analytics/user-journey-funnel

    GET /v1/analytics/session-quality

    GET /v1/analytics/search-to-view-conversion

Save as:
core/analytics/routes.py
"""

from fastapi import APIRouter, Depends, HTTPException, status,Request
from sqlalchemy.ext.asyncio import AsyncSession
import traceback
from core.schema_manager import get_schema_session

from .schemas import (
    AnalyticsEventRequest,
    HouseViewResponse,
    ZipAIUsageResponse,
    InsightsOverviewResponse,
    TrendingZipcodesResponse,
    ActivityHeatmapResponse,
    UserJourneyFunnelResponse,
    SessionQualityResponse,
    SearchToViewConversionResponse,
)

from .service import AnalyticsService


router = APIRouter(tags=["Analytics"])


# ============================================================================
# Internal Vector Endpoint
# ============================================================================

@router.post(
    "/internal/vector/events",
    status_code=status.HTTP_201_CREATED,
    summary="Receive analytics events from Vector",
    description="Internal endpoint used by Vector.dev to send analytics events.",
)
async def receive_vector_event(
    request: Request,
    db: AsyncSession = Depends(get_schema_session("analytics")),
):
    # Vector's HTTP sink batches events into a JSON ARRAY: [ {...}, {...} ].
    body = await request.json()
    raw_events = body if isinstance(body, list) else [body]

    for raw in raw_events:
        event = AnalyticsEventRequest(**raw)
        await AnalyticsService.insert_event(session=db, event=event)

    return {"message": f"{len(raw_events)} event(s) received successfully"}

# ============================================================================
# API 1
# How many people viewed this house
# ============================================================================

@router.get(
    "/v1/analytics/house/{house_id}/views",
    response_model=HouseViewResponse,
    status_code=status.HTTP_200_OK,
    summary="House View Analytics",
    description="Returns total views and unique visitors for a house.",
)
async def get_house_views(
    house_id: str,
    db: AsyncSession = Depends(get_schema_session("analytics")),
):

    result = await AnalyticsService.get_house_views(
        session=db,
        house_id=house_id,
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail="House analytics not found",
        )

    return result


# ============================================================================
# API 2
# How people use ZIPAI
# ============================================================================

@router.get(
    "/analytics/usage",
    response_model=ZipAIUsageResponse,
)
async def get_zipai_usage(
    db: AsyncSession = Depends(get_schema_session("analytics")),
):

    result = await AnalyticsService.get_zipai_usage(session=db)

    return result

# ============================================================================
# API 3
# Admin insights overview (user behaviour + engagement)
# ============================================================================

@router.get(
    "/analytics/overview",
    response_model=InsightsOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Admin Insights Overview",
    description="User behaviour + engagement metrics for the admin dashboard.",
)
async def get_analytics_overview(
    db: AsyncSession = Depends(get_schema_session("analytics")),
):

    result = await AnalyticsService.get_insights_overview(session=db)

    return result


# ============================================================================
# API 4
# Trending zipcodes — where demand is moving (client-facing highlight)
# ============================================================================

@router.get(
    "/analytics/trending-zipcodes",
    response_model=TrendingZipcodesResponse,
    status_code=status.HTTP_200_OK,
    summary="Trending Zipcodes",
    description="Top searched zipcodes with a period-over-period demand trend (up/down/new).",
)
async def get_trending_zipcodes(
    days: int = 7,
    limit: int = 10,
    db: AsyncSession = Depends(get_schema_session("analytics")),
):

    result = await AnalyticsService.get_trending_zipcodes(
        session=db,
        days=days,
        limit=limit,
    )

    return result


# ============================================================================
# API 5 — Peak usage hours (activity heatmap: day-of-week x hour)
# ============================================================================

@router.get(
    "/analytics/activity-heatmap",
    response_model=ActivityHeatmapResponse,
    status_code=status.HTTP_200_OK,
    summary="Peak Usage Hours (activity heatmap)",
    description="Event activity by day-of-week x hour-of-day, for a heatmap. Param: days.",
)
async def get_activity_heatmap(
    days: int = 30,
    db: AsyncSession = Depends(get_schema_session("analytics")),
):
    return await AnalyticsService.get_activity_heatmap(session=db, days=days)


# ============================================================================
# API 6 — User journey funnel (searched -> viewed house -> viewed index)
# ============================================================================

@router.get(
    "/analytics/user-journey-funnel",
    response_model=UserJourneyFunnelResponse,
    status_code=status.HTTP_200_OK,
    summary="User Journey Funnel",
    description="Funnel: searched a zip -> viewed a house -> viewed an index, with drop-off. Param: days.",
)
async def get_user_journey_funnel(
    days: int = 30,
    db: AsyncSession = Depends(get_schema_session("analytics")),
):
    return await AnalyticsService.get_user_journey_funnel(session=db, days=days)


# ============================================================================
# API 7 — Session quality (depth of a visit)
# ============================================================================

@router.get(
    "/analytics/session-quality",
    response_model=SessionQualityResponse,
    status_code=status.HTTP_200_OK,
    summary="Session Quality",
    description="Avg events per session, avg session length, and bounce rate. Param: days.",
)
async def get_session_quality(
    days: int = 30,
    db: AsyncSession = Depends(get_schema_session("analytics")),
):
    return await AnalyticsService.get_session_quality(session=db, days=days)


# ============================================================================
# API 8 — Search-to-view conversion
# ============================================================================

@router.get(
    "/analytics/search-to-house-view-rate",
    response_model=SearchToViewConversionResponse,
    status_code=status.HTTP_200_OK,
    summary="Search-to-View Conversion",
    description="Of users who searched a zipcode, what % went on to view a house. Param: days.",
)
async def get_search_to_view_conversion(
    days: int = 30,
    db: AsyncSession = Depends(get_schema_session("analytics")),
):
    return await AnalyticsService.get_search_to_view_conversion(session=db, days=days)
