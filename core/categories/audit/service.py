"""
ZipAI — Audit Service Layer.

Orchestrates the repository call and maps the result to a typed
Pydantic response. Follows the same pattern as CrimeService /
HealthcareService — business logic lives here, not in the route.

NOTE: No caching on this service — INSERT operations are never cached.
The actual COMMIT happens in the repository layer (repository.py).

Save as: core/categories/audit/service.py
"""

from __future__ import annotations

import time

from sqlalchemy.ext.asyncio import AsyncSession

from core.categories.audit.schemas import (
    AiConversationLogRequest,
    AiConversationLogResponse,
)
from core.categories.audit.repository import insert_conversation_log

# from logging import get_logger
# logger = get_logger(__name__)


class AuditService:
    """Business logic for the audit conversation-log endpoint."""

    @staticmethod
    async def log_user_prompt(
        session: AsyncSession,
        payload: AiConversationLogRequest,
    ) -> AiConversationLogResponse:
        """
        Persist a user prompt to the audit table.

        Validates the payload (Pydantic already handles this), calls the
        repository to run the INSERT via the DB function (which commits),
        and returns the new record ID wrapped in a typed response.
        """
        t0 = time.monotonic()

        new_id = await insert_conversation_log(
            session=session,
            prompt_text=payload.prompt_text,
            user_id=payload.user_id,
            session_id=payload.session_id,
            event_id=payload.event_id,
            notes=payload.notes,
            type=payload.type,
        )

        duration_ms = int((time.monotonic() - t0) * 1000)

        # logger.info(
        #     "audit_log_inserted",
        #     new_id=new_id,
        #     user_id=payload.user_id,
        #     session_id=payload.session_id,
        #     type=payload.type,
        #     duration_ms=duration_ms,
        # )

        return AiConversationLogResponse(
            success=True,
            id=new_id,
            message="Conversation log saved successfully.",
        )