"""
AI Admin — Pydantic response schemas.

Analytics over rag.query_analytics (the per-question log written by the
LangGraph pipeline). Powers the "AI Admin" dashboard: what people ask,
how often, and whether the AI could answer.

Endpoints (all under /v1/ai-admin):
    GET /overview
    GET /top-questions
    GET /intent-distribution
    GET /questions-over-time
    GET /top-unanswered
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AiAdminOverviewResponse(BaseModel):
    """Headline tiles for the AI Admin dashboard."""
    days: int = 30
    total_questions: int = Field(0, description="Total questions asked in the window.")
    unique_sessions: int = Field(0, description="Distinct chat sessions that asked.")
    answered: int = Field(0, description="Questions the AI answered with a specialist agent.")
    unanswered: int = Field(0, description="Questions that fell back / were unknown / errored.")
    answered_rate_pct: float = Field(0.0, description="answered / total, %.")
    by_intent: dict[str, int] = Field(default_factory=dict, description="Question count per intent.")


class TopQuestion(BaseModel):
    question: str
    times_asked: int = Field(0, description="How many times this question was asked.")
    unique_sessions: int = Field(0, description="Distinct sessions that asked it.")
    answered_rate_pct: float = Field(0.0, description="% of times it was answered.")
    last_asked: str | None = Field(None, description="Most recent time asked.")


class TopQuestionsResponse(BaseModel):
    days: int = 30
    items: list[TopQuestion] = Field(default_factory=list)


class IntentStat(BaseModel):
    intent: str
    questions: int = 0
    sessions: int = 0
    answered_rate_pct: float = 0.0


class IntentDistributionResponse(BaseModel):
    days: int = 30
    items: list[IntentStat] = Field(default_factory=list)


class QuestionsDayCount(BaseModel):
    day: str
    questions: int = 0
    unanswered: int = 0


class QuestionsOverTimeResponse(BaseModel):
    days: int = 30
    items: list[QuestionsDayCount] = Field(default_factory=list)


class UnansweredQuestion(BaseModel):
    question: str
    times_asked: int = 0
    unique_sessions: int = 0
    last_asked: str | None = None


class TopUnansweredResponse(BaseModel):
    """The data-gap backlog: questions the AI couldn't answer, ranked."""
    days: int = 30
    items: list[UnansweredQuestion] = Field(default_factory=list)
