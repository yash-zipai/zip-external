"""
AI Admin — API routes.

Register in app/api/v1/router.py:

    from app.ai_admin.routes import router as ai_admin_router
    router.include_router(ai_admin_router)

Endpoints (grouped under "AI Admin" in Swagger), all under /v1/ai-admin:
    GET /overview             — headline tiles
    GET /top-questions        — most-asked questions (how many people ask each)
    GET /intent-distribution  — questions by type (permit / fee / unknown)
    GET /questions-over-time  — daily volume + unanswered
    GET /top-unanswered       — data-gap backlog
    GET /user-categories      — who asked what, by category
    GET /user-questions       — the questions behind one of those rows
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from .service import AiAdminService

from core.schema_manager import get_schema_session

from .schemas import (
    AiAdminOverviewResponse,
    IntentDistributionResponse,
    QuestionsOverTimeResponse,
    TopQuestionsResponse,
    TopUnansweredResponse,
    UserCategoriesResponse,
    UserQuestionsResponse,
)

router = APIRouter(prefix="/ai-admin", tags=["AI Admin"])


@router.get(
    "/overview",
    response_model=AiAdminOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="AI Admin — Overview",
    description="Headline tiles: total questions, unique sessions, answered vs unanswered, and by-intent counts. Param: days.",
)
async def get_overview(
    days: int = 30,
    db: AsyncSession = Depends(get_schema_session("rag")),
):
    return await AiAdminService.get_overview(db, days=days)


@router.get(
    "/top-questions",
    response_model=TopQuestionsResponse,
    status_code=status.HTTP_200_OK,
    summary="AI Admin — Top Questions",
    description="Most-asked questions and how many people (sessions) asked each. Params: days, limit.",
)
async def get_top_questions(
    days: int = 30,
    limit: int = 20,
    db: AsyncSession = Depends(get_schema_session("rag")),
):
    return await AiAdminService.get_top_questions(db, days=days, limit=limit)


@router.get(
    "/intent-distribution",
    response_model=IntentDistributionResponse,
    status_code=status.HTTP_200_OK,
    summary="AI Admin — Question Types (intent)",
    description="Question counts by intent (permit / fee_schedule / unknown), with per-intent answered rate. Param: days.",
)
async def get_intent_distribution(
    days: int = 30,
    db: AsyncSession = Depends(get_schema_session("rag")),
):
    return await AiAdminService.get_intent_distribution(db, days=days)


@router.get(
    "/questions-over-time",
    response_model=QuestionsOverTimeResponse,
    status_code=status.HTTP_200_OK,
    summary="AI Admin — Questions Over Time",
    description="Questions per day and how many were unanswered (for a trend chart). Param: days.",
)
async def get_questions_over_time(
    days: int = 30,
    db: AsyncSession = Depends(get_schema_session("rag")),
):
    return await AiAdminService.get_questions_over_time(db, days=days)


@router.get(
    "/top-unanswered",
    response_model=TopUnansweredResponse,
    status_code=status.HTTP_200_OK,
    summary="AI Admin — Top Unanswered (data-gap backlog)",
    description="Questions the AI couldn't answer (fallback / unknown / error), ranked — what to add data for next. Params: days, limit.",
)
async def get_top_unanswered(
    days: int = 30,
    limit: int = 20,
    db: AsyncSession = Depends(get_schema_session("rag")),
):
    return await AiAdminService.get_top_unanswered(db, days=days, limit=limit)


@router.get(
    "/user-categories",
    response_model=UserCategoriesResponse,
    status_code=status.HTTP_200_OK,
    summary="AI Admin — Who asked what",
    description=(
        "One row per person and category, most active person first. Each row carries "
        "`person` and `category` — pass both to /user-questions to open it. "
        "A person is their user_id when signed in, otherwise their session_id. "
        "Params: days, limit, signed_in_only."
    ),
)
async def get_user_categories(
    days: int = 30,
    limit: int = 200,
    signed_in_only: bool = Query(False, description="Exclude anonymous askers."),
    db: AsyncSession = Depends(get_schema_session("rag")),
):
    return await AiAdminService.get_user_categories(
        db, days=days, limit=limit, signed_in_only=signed_in_only
    )


@router.get(
    "/user-questions",
    response_model=UserQuestionsResponse,
    status_code=status.HTTP_200_OK,
    summary="AI Admin — One person's questions",
    description=(
        "The questions behind a /user-categories row. Pass that row's `person` and "
        "`category`; omit `category` for everything this person asked. "
        "Params: person (required), category, days, limit."
    ),
)
async def get_user_questions(
    person: str = Query(..., description="The `person` value from /user-categories."),
    category: str | None = Query(None, description="The `category` value from that row. Omit for all."),
    days: int = 90,
    limit: int = 200,
    db: AsyncSession = Depends(get_schema_session("rag")),
):
    return await AiAdminService.get_user_questions(
        db, person=person, days=days, limit=limit, category=category
    )