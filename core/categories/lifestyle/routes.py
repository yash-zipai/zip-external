"""
Lifestyle category — API routes.

An APIRouter holding the lifestyle endpoints. The three paths you provided
don't share a common prefix, so this router sets no prefix and each route
carries its full sub-path. Include it so the final paths match your scheme,
e.g. to reproduce the exact /api/... paths you wrote:

    app.include_router(lifestyle_router, prefix="/api")
    # -> /api/zipcode/{zip}/top-places/
    # -> /api/zipcode/{zip}/location-indices/lifestyle/breakdown/
    # -> /api/map/v1/places/pins/

If you'd rather keep lifestyle under /v1 like healthcare and crime, include
with prefix="/v1" instead (the pins path then becomes /v1/map/v1/places/pins/).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.schema_manager import get_schema_session
from core.pagination import PaginationParams, pagination_params
from core.categories.lifestyle.schemas import (
    LifestyleBreakdownResponse,
    MapPinsResponse,
    TopPlacesResponse,
)
from .service import LifestyleService

router = APIRouter(tags=["Lifestyle"])


# -- Top Places ----------------------------------------------------------------


@router.get(
    "/zipcode/{zip}/top-places/",
    response_model=TopPlacesResponse,
    status_code=status.HTTP_200_OK,
    summary="Top lifestyle places by zipcode",
    description=(
        "Returns lifestyle places in the specified zipcode, ordered by category "
        "and rank. Optionally filter by a single category. "
        "Results are paginated (default limit=50, offset=0)."
    ),
)
async def get_top_places(
    zip: str,
    category: str | None = Query(
        default=None,
        description="Filter to a specific category. If empty or omitted, all categories are returned. Valid values: entertainment, restaurants, groceries_markets, sports_fitness, family_kids.",
    ),
    page: PaginationParams = Depends(pagination_params(default_limit=50, max_limit=200)),
    db: AsyncSession = Depends(get_schema_session("lifestyle")),
) -> TopPlacesResponse:
    return await LifestyleService.get_top_places(
        session=db,
        zipcode=zip,
        category=category if category else None,
        limit=page.limit,
        offset=page.offset,
    )


# -- Breakdown -----------------------------------------------------------------


@router.get(
    "/zipcode/{zip}/location-indices/lifestyle/breakdown/",
    response_model=LifestyleBreakdownResponse,
    status_code=status.HTTP_200_OK,
    summary="Lifestyle breakdown by category",
    description=(
        "Aggregates lifestyle places in a zipcode by category, returning the "
        "average rating, place count and total reviews per category, ordered "
        "by average rating descending."
    ),
)
async def get_breakdown(
    zip: str,
    db: AsyncSession = Depends(get_schema_session("lifestyle")),
) -> LifestyleBreakdownResponse:
    return await LifestyleService.get_breakdown(session=db, zipcode=zip)


# -- Map Pins ------------------------------------------------------------------


def _parse_bbox(raw: str | None) -> tuple[float, float, float, float] | None:
    """Parse a 'west,south,east,north' bbox string into floats. (Plain helper, no route.)"""
    if not raw:
        return None
    parts = raw.split(",")
    if len(parts) != 4:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="bbox must be 'west,south,east,north' (4 comma-separated numbers).",
        )
    try:
        west, south, east, north = (float(p) for p in parts)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="bbox values must be numbers.",
        )
    return west, south, east, north


@router.get(
    "/map/v1/places/pins/",
    response_model=MapPinsResponse,
    status_code=status.HTTP_200_OK,
    summary="Lifestyle place map pins",
    description=(
        "Returns lifestyle place locations for map display. Optionally filter "
        "by zipcode, category layers (comma-separated, e.g. layers=entertainment,fitness) "
        "and/or a map bounding box. Pins without coordinates are dropped. "
        "Results are paginated (default limit=200, offset=0)."
    ),
)
async def get_map_pins(
    zipcode: str | None = Query(default=None, description="Filter to a specific zipcode."),
    layers: str | None = Query(
        default=None,
        description="Comma-separated category layers to include. If omitted, all layers are returned.Valid values: entertainment, restaurants, groceries_markets, sports_fitness, family_kids.",
    ),
    bbox: str | None = Query(
        default=None,
        description="Map bounding box as 'west,south,east,north' (lng/lat).",
    ),
    zoom: int | None = Query(default=None, ge=0, le=22, description="Map zoom level (reserved)."),
    page: PaginationParams = Depends(pagination_params(default_limit=200, max_limit=500)),
    db: AsyncSession = Depends(get_schema_session("lifestyle")),
) -> MapPinsResponse:
    return await LifestyleService.get_map_pins(
        session=db,
        zipcode=zipcode,
        layers=layers if layers else None,
        bbox=_parse_bbox(bbox),
        zoom=zoom,
        limit=page.limit,
        offset=page.offset,
    )