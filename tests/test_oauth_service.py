from types import SimpleNamespace
from uuid import uuid4
from urllib.parse import urlparse, parse_qs

import pytest

from app.application.services.oauth_service import OAuthArcaikaService
from app.application.providers.repo.integracao_repo import AuthorizationCodeData
from app.http.schemas.integracao import AuthorizeConsentRequest
from app.infra.security.integration_tokens import decode_integration_access_token
from app.domain.errors import DomainError

# Vetor PKCE (RFC 7636)
VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
REDIRECT = "https://arcaika.example/callback"


@pytest.fixture(autouse=True)
def _configure(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "arcaika_oauth_client_id", "arcaika")
    monkeypatch.setattr(settings, "arcaika_oauth_client_secret", "topsecret")
    monkeypatch.setattr(settings, "arcaika_oauth_redirect_uris", REDIRECT)


class _FakeCodeRepo:
    def __init__(self):
        self.store = {}

    async def create(self, code_hash, client_id, team_id, user_id, arcaika_organizacao_id,
                     default_responsavel_id, default_categoria_id, redirect_uri, scopes,
                     code_challenge, code_challenge_method, expires_at):
        self.store[code_hash] = AuthorizationCodeData(
            id=uuid4(), client_id=client_id, team_id=team_id, user_id=user_id,
            arcaika_organizacao_id=arcaika_organizacao_id,
            default_responsavel_id=default_responsavel_id,
            default_categoria_id=default_categoria_id, redirect_uri=redirect_uri,
            scopes=scopes, code_challenge=code_challenge,
            code_challenge_method=code_challenge_method, expires_at=expires_at, used=False,
        )

    async def get_by_code_hash(self, code_hash):
        return self.store.get(code_hash)

    async def mark_used(self, code_id):
        for rec in self.store.values():
            if rec.id == code_id:
                rec.used = True


class _FakeConnRepo:
    def __init__(self):
        self.by_id = {}

    async def save(self, c):
        self.by_id[c.id] = c
        return c

    async def get_by_id(self, conn_id):
        return self.by_id.get(conn_id)

    async def get_by_team(self, team_id):
        return next((c for c in self.by_id.values() if c.team_id == team_id), None)

    async def get_by_organizacao(self, org_id):
        return next((c for c in self.by_id.values() if c.arcaika_organizacao_id == org_id), None)


class _FakeUow:
    async def commit(self):
        pass


def _svc():
    return OAuthArcaikaService(_FakeCodeRepo(), _FakeConnRepo(), _FakeUow())


def _user():
    return SimpleNamespace(id=uuid4(), team=SimpleNamespace(id=uuid4()))


def _consent(org_id=None, resp_id=None):
    return AuthorizeConsentRequest(
        client_id="arcaika", redirect_uri=REDIRECT, scope="obras:read obras:write",
        code_challenge=CHALLENGE, code_challenge_method="S256", state="xyz",
        arcaika_organizacao_id=org_id or uuid4(),
        default_responsavel_id=resp_id or uuid4(),
    )


def _code_from(redirect_to):
    return parse_qs(urlparse(redirect_to).query)["code"][0]


@pytest.mark.asyncio
async def test_authorize_then_exchange_happy_path():
    svc = _svc()
    user = _user()
    redirect_to = await svc.authorize_consent(user, _consent())
    assert redirect_to.startswith(REDIRECT)
    assert "state=xyz" in redirect_to
    code = _code_from(redirect_to)

    result = await svc.exchange_code("arcaika", "topsecret", code, VERIFIER, REDIRECT)
    assert result.team_id == user.team.id
    payload = decode_integration_access_token(result.access_token)
    assert payload["team_id"] == str(user.team.id)
    assert result.refresh_token.startswith(str(list(svc.connection_repo.by_id)[0]))


@pytest.mark.asyncio
async def test_wrong_client_secret_rejected():
    svc = _svc()
    redirect_to = await svc.authorize_consent(_user(), _consent())
    code = _code_from(redirect_to)
    with pytest.raises(DomainError):
        await svc.exchange_code("arcaika", "ERRADO", code, VERIFIER, REDIRECT)


@pytest.mark.asyncio
async def test_bad_pkce_verifier_rejected():
    svc = _svc()
    redirect_to = await svc.authorize_consent(_user(), _consent())
    code = _code_from(redirect_to)
    with pytest.raises(DomainError):
        await svc.exchange_code("arcaika", "topsecret", code, "verifier-errado", REDIRECT)


@pytest.mark.asyncio
async def test_code_single_use():
    svc = _svc()
    redirect_to = await svc.authorize_consent(_user(), _consent())
    code = _code_from(redirect_to)
    await svc.exchange_code("arcaika", "topsecret", code, VERIFIER, REDIRECT)
    with pytest.raises(DomainError):
        await svc.exchange_code("arcaika", "topsecret", code, VERIFIER, REDIRECT)


@pytest.mark.asyncio
async def test_redirect_uri_not_in_allowlist():
    svc = _svc()
    bad = _consent()
    bad.redirect_uri = "https://evil.example/callback"
    with pytest.raises(DomainError):
        await svc.authorize_consent(_user(), bad)


@pytest.mark.asyncio
async def test_refresh_token_rotation():
    svc = _svc()
    redirect_to = await svc.authorize_consent(_user(), _consent())
    code = _code_from(redirect_to)
    first = await svc.exchange_code("arcaika", "topsecret", code, VERIFIER, REDIRECT)
    refreshed = await svc.refresh("arcaika", "topsecret", first.refresh_token)
    assert refreshed.refresh_token != first.refresh_token  # rotacionou
    # o refresh antigo não vale mais
    with pytest.raises(DomainError):
        await svc.refresh("arcaika", "topsecret", first.refresh_token)


@pytest.mark.asyncio
async def test_org_already_linked_to_other_team():
    svc = _svc()
    org = uuid4()
    # 1º vínculo
    r1 = await svc.authorize_consent(_user(), _consent(org_id=org))
    await svc.exchange_code("arcaika", "topsecret", _code_from(r1), VERIFIER, REDIRECT)
    # 2º time tentando a MESMA organização
    r2 = await svc.authorize_consent(_user(), _consent(org_id=org))
    with pytest.raises(DomainError):
        await svc.exchange_code("arcaika", "topsecret", _code_from(r2), VERIFIER, REDIRECT)
