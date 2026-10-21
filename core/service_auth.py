"""
Service-to-service auth: only ZipData's Django (and ZipAI) may call this service.

Callers sign each request with a short-lived HMAC token in ``X-ZipAI-Service-Token``:

    v1.<unix seconds>.<user id or ->.<hex HMAC-SHA256(SERVICE_AUTH_SECRET, "v1.<ts>.<user>")>

SERVICE_AUTH_MODE (environment):
  off      no check (the old behaviour)
  log      verify and log failures, but serve the request (turn this on first)
  enforce  reject a missing, stale or forged token with 401; and when the request names a
           member (a ``/user/<id>`` path or a ``user-id`` header), reject it with 403 unless
           the token names the same member, so one member's documents can't be fetched by
           asking for another id.

``/health`` and the docs are always open. Same token format as zipai-rag's app/core/service_auth.py.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

HEADER = "X-ZipAI-Service-Token"
OPEN_PATHS = ("/health", "/docs", "/redoc", "/openapi.json")
_USER_IN_PATH = re.compile(r"/user/([^/]+)")


def verify(token: str | None, secret: str, max_age_s: int = 120, now: float | None = None) -> tuple[str | None, str]:
    """(user id or "-", "") for a valid token, else (None, reason)."""
    if not token:
        return None, "missing"
    parts = token.split(".")
    if len(parts) != 4 or parts[0] != "v1":
        return None, "malformed"
    version, ts_raw, user, mac = parts
    expected = hmac.new(secret.encode(), f"{version}.{ts_raw}.{user}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, mac):
        return None, "bad_signature"
    try:
        ts = int(ts_raw)
    except ValueError:
        return None, "malformed"
    if abs((now if now is not None else time.time()) - ts) > max_age_s:
        return None, "expired"
    return user, ""


def _named_member(request: Request) -> str | None:
    match = _USER_IN_PATH.search(request.url.path)
    if match:
        return match.group(1)
    return request.headers.get("user-id")


class ServiceAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        mode = os.getenv("SERVICE_AUTH_MODE", "off").strip().lower()
        if mode == "off" or request.url.path.startswith(OPEN_PATHS):
            return await call_next(request)
        secret = os.getenv("SERVICE_AUTH_SECRET", "")
        if not secret:
            logger.error("service_auth_secret_missing mode=%s", mode)
            if mode == "enforce":
                return JSONResponse({"error": "UNAUTHORIZED"}, status_code=401)
            return await call_next(request)
        user, reason = verify(request.headers.get(HEADER), secret)
        if user is None:
            logger.warning("service_auth_failed reason=%s path=%s mode=%s", reason, request.url.path, mode)
            if mode == "enforce":
                return JSONResponse({"error": "UNAUTHORIZED"}, status_code=401)
            return await call_next(request)
        named = _named_member(request)
        if named is not None and user != "-" and named != user:
            logger.warning("service_auth_member_mismatch path=%s mode=%s", request.url.path, mode)
            if mode == "enforce":
                return JSONResponse({"error": "FORBIDDEN"}, status_code=403)
        elif named is not None and user == "-":
            logger.warning("service_auth_member_unsigned path=%s mode=%s", request.url.path, mode)
            if mode == "enforce":
                return JSONResponse({"error": "FORBIDDEN"}, status_code=403)
        return await call_next(request)
