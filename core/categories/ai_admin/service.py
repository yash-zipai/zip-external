"""
AI Admin — Service layer. Shapes repository rows into response models.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.categories.ai_admin import repository as repo
from core.categories.ai_admin.schemas import (
    AiAdminOverviewResponse,
    IntentDistributionResponse,
    IntentStat,
    QuestionsDayCount,
    QuestionsOverTimeResponse,
    TopQuestion,
    TopQuestionsResponse,
    TopUnansweredResponse,
    UnansweredQuestion,
)

from core.cache import (
    cached,
    ai_overview_cache,
    ai_top_questions_cache,
    ai_intent_cache,
    ai_over_time_cache,
    ai_top_unanswered_cache,
)

class AiAdminService:

    @staticmethod
    @cached(ai_overview_cache)
    async def get_overview(session: AsyncSession, days: int = 30) -> AiAdminOverviewResponse:
        d = await repo.overview(session, days)
        total = int(d.get("total_questions", 0) or 0)
        answered = int(d.get("answered", 0) or 0)
        unanswered = int(d.get("unanswered", 0) or 0)
        rate = round(100.0 * answered / total, 1) if total else 0.0

        intents = await repo.intent_distribution(session, days)
        by_intent = {r["intent"]: int(r["questions"] or 0) for r in intents}

        return AiAdminOverviewResponse(
            days=days,
            total_questions=total,
            unique_sessions=int(d.get("unique_sessions", 0) or 0),
            answered=answered,
            unanswered=unanswered,
            answered_rate_pct=rate,
            by_intent=by_intent,
        )

    @staticmethod
    @cached(ai_top_questions_cache)
    async def get_top_questions(session: AsyncSession, days: int = 30, limit: int = 20) -> TopQuestionsResponse:
        rows = await repo.top_questions(session, days, limit)
        items = [
            TopQuestion(
                question=str(r["question"]),
                times_asked=int(r["times_asked"] or 0),
                unique_sessions=int(r["unique_sessions"] or 0),
                answered_rate_pct=float(r["answered_rate_pct"] or 0),
                last_asked=r["last_asked"],
            )
            for r in rows
        ]
        return TopQuestionsResponse(days=days, items=items)

    @staticmethod
    @cached(ai_intent_cache)
    async def get_intent_distribution(session: AsyncSession, days: int = 30) -> IntentDistributionResponse:
        rows = await repo.intent_distribution(session, days)
        items = [
            IntentStat(
                intent=str(r["intent"]),
                questions=int(r["questions"] or 0),
                sessions=int(r["sessions"] or 0),
                answered_rate_pct=float(r["answered_rate_pct"] or 0),
            )
            for r in rows
        ]
        return IntentDistributionResponse(days=days, items=items)

    @staticmethod
    @cached(ai_over_time_cache)
    async def get_questions_over_time(session: AsyncSession, days: int = 30) -> QuestionsOverTimeResponse:
        rows = await repo.questions_over_time(session, days)
        items = [
            QuestionsDayCount(
                day=r["day"],
                questions=int(r["questions"] or 0),
                unanswered=int(r["unanswered"] or 0),
            )
            for r in rows
        ]
        return QuestionsOverTimeResponse(days=days, items=items)

    @staticmethod
    @cached(ai_top_unanswered_cache)
    async def get_top_unanswered(session: AsyncSession, days: int = 30, limit: int = 20) -> TopUnansweredResponse:
        rows = await repo.top_unanswered(session, days, limit)
        items = [
            UnansweredQuestion(
                question=str(r["question"]),
                times_asked=int(r["times_asked"] or 0),
                unique_sessions=int(r["unique_sessions"] or 0),
                last_asked=r["last_asked"],
            )
            for r in rows
        ]
        return TopUnansweredResponse(days=days, items=items)
