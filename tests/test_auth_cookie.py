from types import SimpleNamespace

from fastapi import Response

from app.http.routers import auth


def test_refresh_cookie_uses_lax_without_secure_in_dev(monkeypatch):
    response = Response()
    monkeypatch.setattr(auth, "settings", SimpleNamespace(environment="dev", api_prefix="/api/v1"))

    auth._set_refresh_cookie(response, "refresh.jwt")

    set_cookie = response.headers["set-cookie"]
    assert "refresh_token=refresh.jwt" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/api/v1/auth/refresh" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Secure" not in set_cookie


def test_refresh_cookie_uses_none_with_secure_outside_dev(monkeypatch):
    response = Response()
    monkeypatch.setattr(auth, "settings", SimpleNamespace(environment="prod", api_prefix="/api/v1"))

    auth._set_refresh_cookie(response, "refresh.jwt")

    set_cookie = response.headers["set-cookie"]
    assert "refresh_token=refresh.jwt" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/api/v1/auth/refresh" in set_cookie
    assert "SameSite=none" in set_cookie
    assert "Secure" in set_cookie
