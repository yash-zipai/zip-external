from fastapi import APIRouter, BackgroundTasks, Depends

from core.schema_manager import get_schema_session
from core.cache import cached, analytics_stats_cache
from .schemas import TrackIn, TrackAck, ClickStatsResponse
from .service import AnalyticsService

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])


@router.post("/track", response_model=TrackAck)
async def track(body: TrackIn, background: BackgroundTasks):
    background.add_task(AnalyticsService.forward_to_vector, body.model_dump())
    return TrackAck(ok=True)


@router.get("/stats/{metric_key:path}", response_model=ClickStatsResponse)
@cached(analytics_stats_cache)
async def stats(metric_key: str,
                session=Depends(lambda: get_schema_session("analytics"))):
    counts = await AnalyticsService.get_stats(session, metric_key)
    return ClickStatsResponse(metric_key=metric_key, **counts)