"""
Healthcare category — API routes.

An APIRouter (prefix="/healthcare") holding all healthcare endpoints.
It is included by app.py with: app.include_router(healthcare_router, prefix="/v1")
so the final paths are /v1/healthcare/...
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.schema_manager import get_schema_session
from core.pagination import PaginationParams, pagination_params
from core.categories.healthcare.schemas import (
    BreakdownResponse,
    HealthcareIndexResponse,
    MapPinsResponse,
    TopPlacesResponse,
)
from .service import HealthcareService, MapPinsService

router = APIRouter(prefix="/healthcare", tags=["Healthcare"])


# -- Top Places ----------------------------------------------------------------


@router.get(
    "/zipcode/{zip}/top-places",
    response_model=TopPlacesResponse,
    status_code=status.HTTP_200_OK,
    summary="Top healthcare providers by zipcode",
    description=(
        "Returns healthcare providers in the specified zipcode, ordered by "
        "category and rank. Optionally filter by a single category. "
        "Results are paginated (default limit=50, offset=0)."
    ),
)
async def get_top_places(
    zip: str,
    category: str | None = Query(
        default=None,
        description=(
            "Filter to a specific category. If empty or omitted, all categories "
            "are returned. Valid values: hospitals, urgent_care, pediatrics, "
            "dentists, clinics, pharmacies."
        ),
    ),
    page: PaginationParams = Depends(pagination_params(default_limit=50, max_limit=200)),
    db: AsyncSession = Depends(get_schema_session("healthcare")),
) -> TopPlacesResponse:
    category_filter = category if category else None
    return await HealthcareService.get_top_places(
        session=db,
        zipcode=zip,
        category=category_filter,
        limit=page.limit,
        offset=page.offset,
    )


# -- Breakdown -----------------------------------------------------------------


@router.get(
    "/zipcode/{zip}/breakdown",
    response_model=BreakdownResponse,
    status_code=status.HTTP_200_OK,
    summary="Healthcare breakdown by category bucket",
    description=(
        "Aggregates providers in a zipcode into broader buckets "
        "(hospital_urgent, pediatrics, dental, primary_care) and returns "
        "a composite score for each bucket."
    ),
)
async def get_breakdown(
    zip: str,
    db: AsyncSession = Depends(get_schema_session("healthcare")),
) -> BreakdownResponse:
    return await HealthcareService.get_breakdown(session=db, zipcode=zip)


# -- Index Scores --------------------------------------------------------------


@router.get(
    "/index-scores",
    response_model=HealthcareIndexResponse,
    status_code=status.HTTP_200_OK,
    summary="Healthcare index scores per zipcode",
    description=(
        "Returns a composite healthcare index score for each zipcode, "
        "calculated as avg_rating x ln(total_reviews). "
        "Optionally filter to a single zipcode. Results are paginated "
        "and sorted by score descending."
    ),
)
async def get_index_scores(
    zipcode: str | None = Query(
        default=None,
        description="Filter to a specific zipcode. If omitted, returns all zipcodes.",
    ),
    page: PaginationParams = Depends(pagination_params(default_limit=50, max_limit=200)),
    db: AsyncSession = Depends(get_schema_session("healthcare")),
) -> HealthcareIndexResponse:
    return await HealthcareService.get_index_scores(
        session=db,
        zipcode=zipcode,
        limit=page.limit,
        offset=page.offset,
    )


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
    "/places/pins/",
    response_model=MapPinsResponse,
    status_code=status.HTTP_200_OK,
    summary="Healthcare provider map pins",
    description=(
        "Returns healthcare provider locations for map display. "
        "Optionally filter by zipcode and/or category layers "
        "(comma-separated, e.g. layers=hospitals,dentists). "
        "Pins without coordinates are dropped. "
        "Results are paginated (default limit=200, offset=0)."
    ),
)
async def get_map_pins(
    zipcode: str | None = Query(
        default=None,
        description="Filter to a specific zipcode.",
    ),
    layers: str | None = Query(
        default=None,
        description=(
            "Comma-separated category layers to include. "
            "Valid values: hospitals, urgent_care, pediatrics, "
            "dentists, clinics, pharmacies, mental_health. "
            "If omitted, all layers are returned."
        ),
    ),
    bbox: str | None = Query(
        default=None,
        description="Map bounding box as 'west,south,east,north' (lng/lat).",
    ),
    zoom: int | None = Query(
        default=None, ge=0, le=22, description="Map zoom level (reserved)."
    ),
    page: PaginationParams = Depends(pagination_params(default_limit=200, max_limit=500)),
    db: AsyncSession = Depends(get_schema_session("healthcare")),
) -> MapPinsResponse:
    return await MapPinsService.get_map_pins(
        session=db,
        zipcode=zipcode,
        layers=layers if layers else None,
        bbox=_parse_bbox(bbox),
        zoom=zoom,
        limit=page.limit,
        offset=page.offset,
    )