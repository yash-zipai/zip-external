"""
Cost of Living category — API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.schema_manager import get_schema_session
from core.categories.cost_of_living.schemas import (
    CostOfLivingBreakdownResponse,
    CostOfLivingTrendResponse,
)
from .service import CostOfLivingService

router = APIRouter(tags=["Cost of Living"])


@router.get(
    "/api/zipcode/{zip}/location-indices/col/breakdown/",
    response_model=CostOfLivingBreakdownResponse,
    status_code=status.HTTP_200_OK,
    summary="Cost of living breakdown in a ZIP code",
)
async def get_col_breakdown(
    zip: str,
    db: AsyncSession = Depends(get_schema_session("cost_of_living")),
) -> CostOfLivingBreakdownResponse:
    result = await CostOfLivingService.get_col_breakdown(session=db, zipcode=zip)
    if not result:
        raise HTTPException(status_code=404, detail="Cost of living data not found")
    return result


@router.get(
    "/api/zipcode/{zip}/housing-market-trends/",
    response_model=CostOfLivingTrendResponse,
    status_code=status.HTTP_200_OK,
    summary="Housing market trends in a ZIP code",
)
async def get_housing_market_trends(
    zip: str,
    db: AsyncSession = Depends(get_schema_session("cost_of_living")),
) -> CostOfLivingTrendResponse:
    return await CostOfLivingService.get_col_trends(session=db, zipcode=zip)
