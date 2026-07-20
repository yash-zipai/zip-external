from pydantic import BaseModel


class TrackIn(BaseModel):
    metric_key: str
    user_id: str | None = None
    session_id: str | None = None
    url: str | None = None


class TrackAck(BaseModel):
    ok: bool = True


class ClickStatsResponse(BaseModel):
    metric_key: str
    total_clicks: int = 0
    unique_people: int = 0
    this_month_people: int = 0