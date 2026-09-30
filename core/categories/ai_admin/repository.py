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

# One definition of a category, used by every endpoint that groups by one.
# `viewapi` is shown as MLS, matching intent_distribution — without this the
# drill-down would filter on a category name the list never shows.
CATEGORY_EXPR = (
    "CASE WHEN intent = 'viewapi' THEN 'MLS' "
    "ELSE COALESCE(NULLIF(btrim(intent), ''), 'unknown') END"
)

# A signed-in asker is their user_id; an anonymous one is their session.
# Same rule as the insights side, so both dashboards count people alike.
PERSON_EXPR = "COALESCE(user_id::text, session_id::text)"


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
        SELECT {CATEGORY_EXPR} AS intent,
               COUNT(*) AS questions,
               COUNT(DISTINCT session_id) AS sessions,
               COALESCE(ROUND(100.0 * COUNT(*) FILTER (WHERE {ANSWERED_CLAUSE})
                              / NULLIF(COUNT(*), 0), 1), 0) AS answered_rate_pct
        FROM rag.query_analytics
        WHERE created_at >= now() - (:days * interval '1 day')
        GROUP BY {CATEGORY_EXPR}
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


# ===========================================================
# Who asked what — the list, and the questions behind a row
# ===========================================================

async def user_categories(
    session: AsyncSession,
    days: int,
    limit: int,
    signed_in_only: bool = False,
) -> list[dict]:
    """One row per person and category: the drill-down list.

    `person_total` rides on every row so the client can show a person's
    share without a second query.
    """
    return await _rows(session, f"""
        WITH q AS (
            SELECT {PERSON_EXPR}      AS person,
                   user_id::text      AS user_id,
                   {CATEGORY_EXPR}    AS category,
                   created_at,
                   {ANSWERED_CLAUSE}  AS is_answered
            FROM rag.query_analytics
            WHERE created_at >= now() - (:days * interval '1 day')
              AND {PERSON_EXPR} IS NOT NULL
              AND (:signed_in_only = false OR user_id IS NOT NULL)
        ),
        per_cat AS (
            SELECT person,
                   MAX(user_id) AS user_id,
                   category,
                   COUNT(*)     AS questions,
                   COALESCE(ROUND(100.0 * COUNT(*) FILTER (WHERE is_answered)
                                  / NULLIF(COUNT(*), 0), 1), 0) AS answered_rate_pct,
                   to_char(MAX(created_at), 'YYYY-MM-DD HH24:MI') AS last_asked
            FROM q
            GROUP BY person, category
        )
        SELECT person,
               user_id,
               CASE WHEN user_id IS NULL THEN 'anonymous' ELSE 'signed_in' END AS user_kind,
               category,
               questions,
               answered_rate_pct,
               SUM(questions) OVER (PARTITION BY person) AS person_total,
               last_asked
        FROM per_cat
        ORDER BY SUM(questions) OVER (PARTITION BY person) DESC,
                 questions DESC
        LIMIT :limit
    """, {"days": days, "limit": limit, "signed_in_only": signed_in_only})


async def user_questions(
    session: AsyncSession,
    person: str,
    days: int,
    limit: int,
    category: str | None = None,
) -> list[dict]:
    """The questions behind one row of `user_categories`.

    `category` is the value that row showed, so it is matched through the
    same expression the list grouped by. Omit it for everything this
    person asked.
    """
    return await _rows(session, f"""
        SELECT to_char(created_at, 'YYYY-MM-DD HH24:MI') AS asked_at,
               query                                     AS question,
               {CATEGORY_EXPR}                           AS category,
               agent_used,
               outcome,
               source,
               city,
               total_latency_ms,
               {ANSWERED_CLAUSE}                         AS answered
        FROM rag.query_analytics
        WHERE {PERSON_EXPR} = :person
          AND (CAST(:category AS text) IS NULL OR {CATEGORY_EXPR} = CAST(:category AS text))
          AND created_at >= now() - (:days * interval '1 day')
          AND query IS NOT NULL AND btrim(query) <> ''
        ORDER BY created_at DESC
        LIMIT :limit
    """, {"person": person, "category": category, "days": days, "limit": limit})