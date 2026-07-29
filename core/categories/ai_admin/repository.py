"""
AI Admin — Repository (raw SQL over rag.query_analytics).

Definition of "answered" vs "unanswered":
  answered   = no error, routed to a real specialist, and a known intent
  unanswered = an error occurred, OR it fell back, OR the intent was unknown

These clauses are constant strings (no user input) so they are safe to
interpolate into the SQL.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


ANSWERED_CLAUSE = "(error IS NULL AND agent_used <> 'fallback_agent' AND intent <> 'unknown')"
UNANSWERED_CLAUSE = "(error IS NOT NULL OR agent_used = 'fallback_agent' OR intent = 'unknown')"


async def _rows(session: AsyncSession, sql: str, params: dict | None = None) -> list[dict]:
    res = await session.execute(text(sql), params or {})
    return [dict(r._mapping) for r in res.fetchall()]


async def _one(session: AsyncSession, sql: str, params: dict | None = None) -> dict:
    res = await session.execute(text(sql), params or {})
    row = res.fetchone()
    return dict(row._mapping) if row else {}


async def overview(session: AsyncSession, days: int) -> dict:
    return await _one(session, f"""
        SELECT
            COUNT(*) AS total_questions,
            COUNT(DISTINCT session_id) AS unique_sessions,
            COUNT(*) FILTER (WHERE {ANSWERED_CLAUSE})   AS answered,
            COUNT(*) FILTER (WHERE {UNANSWERED_CLAUSE}) AS unanswered
        FROM rag.query_analytics
        WHERE created_at >= now() - (:days * interval '1 day')
    """, {"days": days})


async def intent_distribution(session: AsyncSession, days: int) -> list[dict]:
    return await _rows(session, f"""
        SELECT intent,
               COUNT(*) AS questions,
               COUNT(DISTINCT session_id) AS sessions,
               COALESCE(ROUND(100.0 * COUNT(*) FILTER (WHERE {ANSWERED_CLAUSE})
                              / NULLIF(COUNT(*), 0), 1), 0) AS answered_rate_pct
        FROM rag.query_analytics
        WHERE created_at >= now() - (:days * interval '1 day')
        GROUP BY intent
        ORDER BY questions DESC
    """, {"days": days})


async def top_questions(session: AsyncSession, days: int, limit: int) -> list[dict]:
    return await _rows(session, f"""
        SELECT MAX(query) AS question,
               COUNT(*) AS times_asked,
               COUNT(DISTINCT session_id) AS unique_sessions,
               COALESCE(ROUND(100.0 * COUNT(*) FILTER (WHERE {ANSWERED_CLAUSE})
                              / NULLIF(COUNT(*), 0), 1), 0) AS answered_rate_pct,
               to_char(MAX(created_at), 'YYYY-MM-DD HH24:MI') AS last_asked
        FROM rag.query_analytics
        WHERE created_at >= now() - (:days * interval '1 day')
          AND query IS NOT NULL AND btrim(query) <> ''
        GROUP BY lower(btrim(query))
        ORDER BY times_asked DESC
        LIMIT :limit
    """, {"days": days, "limit": limit})


async def questions_over_time(session: AsyncSession, days: int) -> list[dict]:
    return await _rows(session, f"""
        SELECT to_char(date_trunc('day', created_at), 'YYYY-MM-DD') AS day,
               COUNT(*) AS questions,
               COUNT(*) FILTER (WHERE {UNANSWERED_CLAUSE}) AS unanswered
        FROM rag.query_analytics
        WHERE created_at >= now() - (:days * interval '1 day')
        GROUP BY 1
        ORDER BY 1
    """, {"days": days})


async def top_unanswered(session: AsyncSession, days: int, limit: int) -> list[dict]:
    return await _rows(session, f"""
        SELECT MAX(query) AS question,
               COUNT(*) AS times_asked,
               COUNT(DISTINCT session_id) AS unique_sessions,
               to_char(MAX(created_at), 'YYYY-MM-DD HH24:MI') AS last_asked
        FROM rag.query_analytics
        WHERE created_at >= now() - (:days * interval '1 day')
          AND {UNANSWERED_CLAUSE}
          AND query IS NOT NULL AND btrim(query) <> ''
        GROUP BY lower(btrim(query))
        ORDER BY times_asked DESC
        LIMIT :limit
    """, {"days": days, "limit": limit})
