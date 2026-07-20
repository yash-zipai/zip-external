from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_click_counts(session: AsyncSession, metric_key: str):
    row = (await session.execute(text("""
        SELECT
            COUNT(*)                                              AS total_clicks,
            COUNT(DISTINCT COALESCE(user_id, session_id))        AS unique_people,
            COUNT(DISTINCT COALESCE(user_id, session_id))
                FILTER (WHERE created_at >= date_trunc('month', now())) AS this_month_people
        FROM analytics.page_clicks
        WHERE metric_key = :k
    """), {"k": metric_key})).mappings().first()
    return row or {"total_clicks": 0, "unique_people": 0, "this_month_people": 0}


async def insert_click_direct(session, metric_key, user_id, session_id, url):
    # Fallback path only (used if Vector is ever off). Vector is the normal path.
    await session.execute(text("""
        INSERT INTO analytics.page_clicks (metric_key, user_id, session_id, url, created_at)
        VALUES (:k, :u, :s, :url, now())
    """), {"k": metric_key, "u": user_id, "s": session_id, "url": url})
    await session.commit()