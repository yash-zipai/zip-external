"""
ZipAI — Audit Pydantic schemas.

Only one endpoint — POST to insert a user prompt into the DB.

Save as: core/categories/audit/schemas.py
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AiConversationLogRequest(BaseModel):
    """
    Request body for POST /v1/audit/conversation-logs.

    Called every time a user sends a message in the chat.
    Only prompt_text is required — all other fields are optional.
    """

    prompt_text: str = Field(
        ...,
        description="The exact text the user typed into the chat.",
    )
    user_id: int | None = Field(
        None,
        description="Authenticated user ID. Pass null for guest/unauthenticated users.",
    )
    session_id: str | None = Field(
        None,
        max_length=100,
        description=(
            "Session identifier — generate once per chat open with "
            "crypto.randomUUID() and reuse for every message in that tab."
        ),
    )
    event_id: str | None = Field(
        None,
        max_length=100,
        description="External event / ticket ID to link this prompt to (nullable).",
    )
    notes: str | None = Field(
        None,
        max_length=1000,
        description="Optional internal annotation (usually null at insert time).",
    )
    type: str | None = Field(
        None,
        max_length=100,
        description=(
            "Page or source that sent the prompt. "
            "e.g. 'school-search', 'home', 'dashboard', 'school-detail'. "
            "Each page in your frontend should hardcode its own value here."
        ),
    )


class AiConversationLogResponse(BaseModel):
    """
    Response for POST /v1/audit/conversation-logs.

    Returns the new record ID so the frontend can reference it if needed.
    """

    success: bool = Field(True, description="Always True on successful insert.")
    id: int = Field(..., description="Auto-generated primary key of the new row.")
    message: str = Field("Conversation log saved successfully.")