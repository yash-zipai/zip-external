"""
Analytics API Routes.

Included by main.py WITHOUT a prefix:

    app.include_router(analytics_router)

Available Endpoints:

    POST /internal/vector/events

    GET /v1/analytics/house/{house_id}/views

    GET /v1/analytics/usage

    GET /v1/analytics/trending-zipcodes

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
    TrendingZipcodesResponse
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
    "/v1/analytics/usage",
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
    "/v1/analytics/overview",
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
    "/v1/analytics/trending-zipcodes",
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