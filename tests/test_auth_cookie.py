from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request

from app.http.routers import auth
from app.infra.security.jwt import create_refresh_token, decode_refresh_token


def test_refresh_cookie_uses_lax_without_secure_in_dev(monkeypatch):
    response = Response()
    monkeypatch.setattr(
        auth,
        "settings",
        SimpleNamespace(
            environment="dev",
            api_prefix="/api/v1",
            refresh_cookie_domain=None,
            frontend_url="http://localhost:5174",
            allowed_origins=["http://localhost:5174"],
        ),
    )

    auth._set_refresh_cookie(response, "refresh.jwt")

    set_cookie = response.headers["set-cookie"]
    assert "refresh_token=refresh.jwt" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/api/v1/auth" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Secure" not in set_cookie


def test_refresh_cookie_uses_none_with_secure_outside_dev(monkeypatch):
    response = Response()
    monkeypatch.setattr(auth, "settings", SimpleNamespace(environment="prod", api_prefix="/api/v1", refresh_cookie_domain=None))

    auth._set_refresh_cookie(response, "refresh.jwt")

    set_cookie = response.headers["set-cookie"]
    assert "refresh_token=refresh.jwt" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/api/v1/auth" in set_cookie
    assert "SameSite=none" in set_cookie
    assert "Secure" in set_cookie


def test_cookie_can_be_scoped_to_parent_domain(monkeypatch):
    response = Response()
    monkeypatch.setattr(
        auth,
        "settings",
        SimpleNamespace(environment="prod", api_prefix="/api/v1", refresh_cookie_domain=".engify.app"),
    )

    auth._set_refresh_cookie(response, "refresh.jwt")

    assert "Domain=.engify.app" in response.headers["set-cookie"]


def test_rejects_untrusted_origin(monkeypatch):
    monkeypatch.setattr(
        auth,
        "settings",
        SimpleNamespace(frontend_url="https://app.engify.app", allowed_origins=["https://app.engify.app"]),
    )
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/refresh",
            "headers": [(b"origin", b"https://evil.example")],
        }
    )

    with pytest.raises(HTTPException) as exc:
        auth._enforce_trusted_origin(request)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_refresh_rotates_cookie_and_revokes_previous_token(monkeypatch):
    user_id = uuid4()
    team_id = uuid4()
    old_token = create_refresh_token(user_id, team_id, "admin")
    old_jti = decode_refresh_token(old_token)["jti"]
    revoked_keys: dict[str, tuple[str, int]] = {}

    class RedisStub:
        async def exists(self, key: str) -> int:
            return 0

        async def set(self, key: str, value: str, ex: int) -> None:
            revoked_keys[key] = (value, ex)

    monkeypatch.setattr(auth, "get_redis", lambda: RedisStub())
    monkeypatch.setattr(
        auth,
        "settings",
        SimpleNamespace(
            environment="dev",
            api_prefix="/api/v1",
            refresh_cookie_domain=None,
            frontend_url="http://localhost:5174",
            allowed_origins=["http://localhost:5174"],
        ),
    )

    response = Response()
    result = await auth.refresh_token(
        Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/v1/auth/refresh",
                "headers": [(b"origin", b"http://localhost:5174")],
            }
        ),
        response,
        old_token,
    )

    assert result.access_token
    assert f"revoked:{old_jti}" in revoked_keys
    set_cookie = response.headers["set-cookie"]
    assert "refresh_token=" in set_cookie
    new_cookie_value = set_cookie.split("refresh_token=", 1)[1].split(";", 1)[0]
    assert new_cookie_value != old_token
