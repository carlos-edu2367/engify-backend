"""
OAuth 2.0 Authorization Server (Authorization Code + PKCE) — client Arcaika.

- POST /oauth/authorize : consentimento do admin Engify (autenticado). Vincula o
  time do admin a uma organização Arcaika e devolve o redirect com o code.
- POST /oauth/token     : troca de code por tokens (client-authenticated) e refresh.
"""
from fastapi import APIRouter, Form, HTTPException

from app.http.schemas.integracao import AuthorizeConsentRequest, AuthorizeConsentResponse, TokenResponse
from app.http.dependencies.auth import AdminUser
from app.http.dependencies.services import OAuthServiceDep
from app.domain.errors import DomainError

router = APIRouter(prefix="/oauth", tags=["OAuth / Integração"])


@router.post("/authorize", response_model=AuthorizeConsentResponse)
async def authorize(body: AuthorizeConsentRequest, user: AdminUser, svc: OAuthServiceDep):
    """Consentimento do admin Engify. O admin escolhe o responsável padrão das
    obras criadas pela integração (default_responsavel_id)."""
    try:
        redirect_to = await svc.authorize_consent(user, body)
    except DomainError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return AuthorizeConsentResponse(redirect_to=redirect_to)


@router.post("/token", response_model=TokenResponse)
async def token(
    svc: OAuthServiceDep,
    grant_type: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...),
    code: str | None = Form(None),
    code_verifier: str | None = Form(None),
    redirect_uri: str | None = Form(None),
    refresh_token: str | None = Form(None),
):
    try:
        if grant_type == "authorization_code":
            if not (code and code_verifier and redirect_uri):
                raise HTTPException(status_code=400, detail="Parâmetros do authorization_code ausentes")
            result = await svc.exchange_code(client_id, client_secret, code, code_verifier, redirect_uri)
        elif grant_type == "refresh_token":
            if not refresh_token:
                raise HTTPException(status_code=400, detail="refresh_token ausente")
            result = await svc.refresh(client_id, client_secret, refresh_token)
        else:
            raise HTTPException(status_code=400, detail="grant_type não suportado")
    except DomainError as e:
        # OAuth: falhas de client/credencial → 400 invalid_grant/invalid_client
        raise HTTPException(status_code=400, detail=str(e))

    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        expires_in=result.expires_in,
        scope=result.scope,
        engify_team_id=result.team_id,
    )
