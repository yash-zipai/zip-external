"""
Analytics API Routes.

Included by main.py with the /v1 prefix:

    app.include_router(analytics_router, prefix="/v1")

Endpoints:
    POST /v1/analytics/track          -> called by the WEBSITE (frontend). Writes a log line.
    POST /v1/internal/vector/events   -> called by VECTOR. Inserts into the DB.
    GET  /v1/analytics/house/{house_id}/views
    GET  /v1/analytics/usage
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.schema_manager import get_schema_session

from .schemas import (
    AnalyticsEventRequest,
    HouseViewResponse,
    ZipAIUsageResponse,
)

from .service import AnalyticsService

from .logger import log_event


router = APIRouter(tags=["Analytics"])


def _client_ip(request: Request) -> str | None:
    """Best-effort client IP, honouring a proxy/load-balancer's X-Forwarded-For."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


# ============================================================================
# Public tracking endpoint — called by the website frontend.
#
#   frontend -> /v1/analytics/track -> log line -> Vector -> /internal/vector/events -> DB
#
# The browser sends what it knows (zipcode, session, page, device); here we
# stamp on the things the browser can't be trusted for (IP, country).
# ============================================================================

@router.post(
    "/v1/analytics/track",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Track an analytics event from the website",
    description="Public endpoint the website frontend calls to record a user event.",
)
async def track_event(payload: AnalyticsEventRequest, request: Request):
    # Server-side enrichment: IP from the request, country from an edge header
    # (e.g. Cloudflare's CF-IPCountry) if present. Both land in metadata (JSONB).
    meta = dict(payload.metadata or {})
    meta.setdefault("ip", _client_ip(request))
    meta.setdefault("country", request.headers.get("cf-ipcountry"))

    log_event(
        event_type=payload.event_type,
        category=payload.category,
        action=payload.action,
        user_id=payload.user_id,
        session_id=payload.session_id,
        resource_id=payload.resource_id,
        zipcode=payload.zipcode,
        page_name=payload.page_name,
        metadata=meta,
    )

    return {"message": "event logged"}


# ============================================================================
# Internal Vector endpoint — called by Vector (accepts a batched JSON array).
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
# API 1 — How many people viewed this house
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
# API 2 — How people use ZIPAI
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