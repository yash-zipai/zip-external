"""
Cost of Living category — API routes.
<<<<<<< HEAD

Included by main.py WITHOUT a prefix:

    app.include_router(cost_of_living_router)

so each route carries its full path. Four routes total — the two NEW spec
endpoints plus the two LEGACY endpoints kept alive for migration:

    NEW    /v1/cost-of-living/zipcode/{zip}/index-scores
    NEW    /v1/cost-of-living/zipcode/{zip}/breakdown
    LEGACY /api/zipcode/{zip}/location-indices/col/breakdown/
    LEGACY /api/zipcode/{zip}/housing-market-trends/

Save as: core/categories/cost_of_living/routes.py
=======
>>>>>>> 693e6ee (feat: implement TTL caching module and developed api's schools and cost of living categories)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.schema_manager import get_schema_session
from core.categories.cost_of_living.schemas import (
<<<<<<< HEAD
    CostOfLivingBreakdownLegacyResponse,
    CostOfLivingBreakdownResponse,
    CostOfLivingIndexScoresResponse,
=======
    CostOfLivingBreakdownResponse,
>>>>>>> 693e6ee (feat: implement TTL caching module and developed api's schools and cost of living categories)
    CostOfLivingTrendResponse,
)
from .service import CostOfLivingService

router = APIRouter(tags=["Cost of Living"])


<<<<<<< HEAD
# == NEW: Index Scores =========================================================


@router.get(
    "/v1/cost-of-living/zipcode/{zip}/index-scores",
    response_model=CostOfLivingIndexScoresResponse,
    status_code=status.HTTP_200_OK,
    summary="Cost of living index card by zipcode",
    description=(
        "Returns the ZIP-level cost-of-living aggregate from the latest snapshot: "
        "affordability score, median annual income and total monthly estimate. "
        "No cost line items, tax breakdown or trend series."
    ),
)
async def get_col_index_scores(
    zip: str,
    db: AsyncSession = Depends(get_schema_session("cost_of_living")),
) -> CostOfLivingIndexScoresResponse:
    result = await CostOfLivingService.get_col_index_scores(session=db, zipcode=zip)
    if not result:
        raise HTTPException(status_code=404, detail="Cost of living data not found")
    return result


# == NEW: Breakdown (nested) ===================================================


@router.get(
    "/v1/cost-of-living/zipcode/{zip}/breakdown",
    response_model=CostOfLivingBreakdownResponse,
    status_code=status.HTTP_200_OK,
    summary="Cost of living breakdown by zipcode (nested)",
    description=(
        "Returns the nested cost-of-living breakdown for the latest snapshot: "
        "income & taxes, monthly cost line items, housing, and per-metric trend "
        "series (mortgage_rate, grocery_cpi, dining_cpi, gas_price)."
    ),
=======
@router.get(
    "/api/zipcode/{zip}/location-indices/col/breakdown/",
    response_model=CostOfLivingBreakdownResponse,
    status_code=status.HTTP_200_OK,
    summary="Cost of living breakdown in a ZIP code",
>>>>>>> 693e6ee (feat: implement TTL caching module and developed api's schools and cost of living categories)
)
async def get_col_breakdown(
    zip: str,
    db: AsyncSession = Depends(get_schema_session("cost_of_living")),
) -> CostOfLivingBreakdownResponse:
    result = await CostOfLivingService.get_col_breakdown(session=db, zipcode=zip)
    if not result:
        raise HTTPException(status_code=404, detail="Cost of living data not found")
    return result
<<<<<<< HEAD
=======


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
>>>>>>> 693e6ee (feat: implement TTL caching module and developed api's schools and cost of living categories)
