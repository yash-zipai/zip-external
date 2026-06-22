"""
Schools category — API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.schema_manager import get_schema_session
from core.categories.schools.schemas import (
    EducationBreakdownResponse,
    SchoolDetailResponse,
    SchoolHigherEdResponse,
    SchoolK12Response,
    SchoolMapPinsResponse,
)
from .service import SchoolService

router = APIRouter(tags=["Schools"])


@router.get(
    "/v1/zipcode/{zip}/schools/",
    response_model=SchoolK12Response,
    status_code=status.HTTP_200_OK,
    summary="K-12 schools in a ZIP code",
)
async def get_schools_k12(
    zip: str,
    db: AsyncSession = Depends(get_schema_session("schools")),
) -> SchoolK12Response:
    return await SchoolService.get_schools_k12(session=db, zipcode=zip)


@router.get(
    "/v1/zipcode/{zip}/colleges-universities/",
    response_model=SchoolHigherEdResponse,
    status_code=status.HTTP_200_OK,
    summary="Higher ed (colleges and universities) in a ZIP code",
)
async def get_schools_higher_ed(
    zip: str,
    db: AsyncSession = Depends(get_schema_session("schools")),
) -> SchoolHigherEdResponse:
    return await SchoolService.get_schools_higher_ed(session=db, zipcode=zip)


@router.get(
    "/api/zipcode/{zip}/location-indices/education/breakdown/",
    response_model=EducationBreakdownResponse,
    status_code=status.HTTP_200_OK,
    summary="Education breakdown in a ZIP code",
)
async def get_education_breakdown(
    zip: str,
    db: AsyncSession = Depends(get_schema_session("schools")),
) -> EducationBreakdownResponse:
    return await SchoolService.get_education_breakdown(session=db, zipcode=zip)


@router.get(
    "/api/place/{canonical_place_id}/details/",
    response_model=SchoolDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Detail modal for a specific school",
)
async def get_school_details(
    canonical_place_id: str,
    db: AsyncSession = Depends(get_schema_session("schools")),
) -> SchoolDetailResponse:
    result = await SchoolService.get_school_details(session=db, nces_id=canonical_place_id)
    if not result:
        raise HTTPException(status_code=404, detail="School not found")
    return result


def _parse_bbox(raw: str | None) -> tuple[float, float, float, float] | None:
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
    "/api/map/v1/places/pins/",
    response_model=SchoolMapPinsResponse,
    status_code=status.HTTP_200_OK,
    summary="Map overlay for schools",
)
async def get_map_pins(
    layers: str | None = Query(default=None, description="Layers filter (e.g. layers=schools)"),
    bbox: str | None = Query(default=None, description="Map bounding box as 'west,south,east,north'"),
    db: AsyncSession = Depends(get_schema_session("schools")),
) -> SchoolMapPinsResponse:
    return await SchoolService.get_map_pins(session=db, bbox=_parse_bbox(bbox))
