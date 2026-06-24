"""
ZipAI — Audit API route.

Single POST endpoint — called every time a user sends a chat message.
Include in app.py with prefix="/v1":

    app.include_router(audit_router, prefix="/v1")

Final path:
    POST /v1/audit/conversation-logs

Save as: core/categories/audit/routes.py
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.schema_manager import get_schema_session
from core.categories.audit.schemas import (
    AiConversationLogRequest,
    AiConversationLogResponse,
)
from core.categories.audit.service import AuditService

router = APIRouter(tags=["Audit"])


@router.post(
    "/audit/conversation-logs",
    response_model=AiConversationLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a user chat prompt",
    description=(
        "Called every time a user types and sends a message in the chat. "
        "Saves the prompt text along with session, event, page type, and "
        "user identifiers into ai.AiConversationLogs. "
        "Only prompt_text is required — all other fields are optional. "
        "Returns the new record ID."
    ),
)
async def log_user_prompt(
    payload: AiConversationLogRequest,
    # CHANGED: "audit" -> "ai" so it matches the schema where the
    # table and function actually live (ai.AiConversationLogs).
    db: AsyncSession = Depends(get_schema_session("ai")),
) -> AiConversationLogResponse:
    return await AuditService.log_user_prompt(session=db, payload=payload)