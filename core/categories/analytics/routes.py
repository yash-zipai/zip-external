"""
Analytics API Routes.

Included by main.py WITHOUT a prefix:

    app.include_router(analytics_router)

Available Endpoints:

    POST /internal/vector/events

    GET /v1/analytics/house/{house_id}/views

    GET /v1/analytics/usage

Save as:
core/analytics/routes.py
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import traceback
from core.schema_manager import get_schema_session

from .schemas import (
    AnalyticsEventRequest,
    HouseViewResponse,
    ZipAIUsageResponse,
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
    payload: AnalyticsEventRequest,
    db: AsyncSession = Depends(get_schema_session("analytics")),
):
    try:
        await AnalyticsService.insert_event(
            session=db,
            event=payload,
        )

        return {
            "message": "Event received successfully"
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

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

    return ZipAIUsageResponse(usage=result)