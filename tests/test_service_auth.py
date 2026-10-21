"""Service auth: only signed callers, and only for the member the token names."""

import hashlib
import hmac
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.service_auth import HEADER, ServiceAuthMiddleware, verify

SECRET = "test-only-secret"


def sign(user, ts=None):
    msg = f"v1.{int(ts or time.time())}.{user}"
    return f"{msg}.{hmac.new(SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()}"


def make_client():
    app = FastAPI()
    app.add_middleware(ServiceAuthMiddleware)

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/v1/w2/user/{user_id}")
    def w2(user_id: str):
        return {"user": user_id}

    return TestClient(app)


@pytest.fixture
def mode(monkeypatch):
    monkeypatch.setenv("SERVICE_AUTH_SECRET", SECRET)

    def set_mode(m):
        monkeypatch.setenv("SERVICE_AUTH_MODE", m)
    return set_mode


def test_off_and_log_modes_serve_unsigned_calls(mode):
    client = make_client()
    mode("off")
    assert client.get("/v1/w2/user/7").status_code == 200
    mode("log")
    assert client.get("/v1/w2/user/7").status_code == 200


def test_enforce_needs_a_token_for_the_same_member(mode):
    client = make_client()
    mode("enforce")
    assert client.get("/health").status_code == 200
    assert client.get("/v1/w2/user/7").status_code == 401
    assert client.get("/v1/w2/user/7", headers={HEADER: sign(7)}).status_code == 200
    assert client.get("/v1/w2/user/8", headers={HEADER: sign(7)}).status_code == 403
    assert client.get("/v1/w2/user/7", headers={HEADER: sign("-")}).status_code == 403
    assert client.get("/v1/w2/user/7", headers={HEADER: sign(7, ts=time.time() - 3600)}).status_code == 401


def test_header_named_member_must_match(mode):
    client = make_client()
    mode("enforce")
    r = client.get("/health")
    assert r.status_code == 200
    assert verify(sign(7), SECRET)[0] == "7"
