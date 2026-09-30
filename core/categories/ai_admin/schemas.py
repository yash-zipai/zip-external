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
    GET /user-categories
    GET /user-questions
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


class UserCategoryRow(BaseModel):
    """One person and one category — a row the client can open."""
    person: str = Field(..., description="user_id when signed in, otherwise session_id. Pass this back to /user-questions.")
    user_id: str | None = Field(None, description="Set only for signed-in askers.")
    user_kind: str = Field("anonymous", description="signed_in | anonymous.")
    category: str = Field(..., description="Question type. Pass this back to /user-questions.")
    questions: int = Field(0, description="Questions this person asked in this category.")
    answered_rate_pct: float = Field(0.0, description="% of them the AI answered.")
    person_total: int = Field(0, description="All questions this person asked, across categories.")
    last_asked: str | None = None


class UserCategoriesResponse(BaseModel):
    days: int = 30
    signed_in_only: bool = False
    items: list[UserCategoryRow] = Field(default_factory=list)


class UserQuestion(BaseModel):
    question: str
    category: str
    asked_at: str | None = None
    agent_used: str | None = None
    outcome: str | None = None
    source: str | None = Field(None, description="typed, or the suggestion it came from.")
    city: str | None = None
    total_latency_ms: int | None = None
    answered: bool = False


class UserQuestionsResponse(BaseModel):
    """What one person asked — the rows behind a UserCategoryRow."""
    days: int = 90
    person: str
    category: str | None = Field(None, description="Absent when every category was requested.")
    items: list[UserQuestion] = Field(default_factory=list)