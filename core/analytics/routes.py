"""
ZipAI — Analytics API routes.
POST /v1/analytics/track            -> record a click/view (forwarded to Vector)
GET  /v1/analytics/stats/{metric}   -> read aggregate counts for the frontend
"""
from __future__ import annotations
from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.schema_manager import get_schema_session
from core.categories.analytics.schemas import TrackIn, TrackAck, ClickStatsResponse
from core.categories.analytics.service import AnalyticsService

router = APIRouter(tags=["Analytics"])


@router.post(
    "/v1/analytics/track",
    response_model=TrackAck,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Record a click / view event",
    description="Frontend calls this on every click/view. It forwards the event "
                "to Vector in the background and returns instantly.",
)
async def track(body: TrackIn, background: BackgroundTasks) -> TrackAck:
    background.add_task(AnalyticsService.forward_to_vector, body.model_dump())
    return TrackAck(ok=True)


@router.get(
    "/v1/analytics/stats/{metric_key:path}",
    response_model=ClickStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get click/view counts for a metric key",
    description="Returns total clicks, unique people, and unique people this month "
                "for a metric_key like 'house:123' or 'index:lifestyle'.",
)
async def stats(
    metric_key: str,
    db: AsyncSession = Depends(get_schema_session("analytics")),
) -> ClickStatsResponse:
    return await AnalyticsService.get_stats(db, metric_key)
