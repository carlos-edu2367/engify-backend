from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Response, Cookie, Request
from typing import Annotated
from uuid import UUID
from app.core.limiter import limiter
from app.http.schemas.auth import (
    LoginRequest, TokenResponse, RefreshResponse,
    RegisterRequest, RecoveryRequestBody,
    RecoveryVerifyRequest, RecoveryResetRequest, UserResponse,
)
from app.http.schemas.common import MessageResponse
from app.http.dependencies.services import UserServiceDep, RecoveryServiceDep
from app.http.dependencies.auth import CurrentUser
from app.application.dtos.user import Login, RegisterUser, CreateRecoveryCode
from app.infra.security.jwt import (
    create_access_token, create_refresh_token, decode_refresh_token
)
from app.infra.cache.client import get_redis
from app.infra.cache.keys import revoked_token_key
from jose import JWTError
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["Auth"])

_REFRESH_COOKIE = "refresh_token"
_COOKIE_MAX_AGE = settings.refresh_token_expire_days * 24 * 60 * 60


def _refresh_cookie_path() -> str:
    return "/"


def _refresh_cookie_samesite() -> str:
    return "lax" if settings.environment == "dev" else "none"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.environment != "dev",
        samesite=_refresh_cookie_samesite(),
        max_age=_COOKIE_MAX_AGE,
        path=_refresh_cookie_path(),
        domain=settings.refresh_cookie_domain,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=_REFRESH_COOKIE,
        path=_refresh_cookie_path(),
        domain=settings.refresh_cookie_domain,
        secure=settings.environment != "dev",
        samesite=_refresh_cookie_samesite(),
    )


def _trusted_origins() -> set[str]:
    origins = {origin.rstrip("/") for origin in settings.allowed_origins if origin}
    if settings.frontend_url:
        origins.add(settings.frontend_url.rstrip("/"))
    return origins


def _enforce_trusted_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    candidate = origin or referer

    if not candidate:
        return

    trusted = _trusted_origins()
    normalized = candidate.rstrip("/")
    if origin:
        if normalized not in trusted:
            raise HTTPException(status_code=403, detail="Origem nao autorizada")
        return

    if not any(normalized == allowed or normalized.startswith(f"{allowed}/") for allowed in trusted):
        raise HTTPException(status_code=403, detail="Origem nao autorizada")


def _refresh_ttl(payload: dict) -> int:
    exp = payload.get("exp", 0)
    return max(int(exp - datetime.now(timezone.utc).timestamp()), 1)


async def _revoke_refresh_payload(payload: dict) -> None:
    jti = payload.get("jti")
    if not jti:
        return
    redis = get_redis()
    await redis.set(revoked_token_key(jti), "1", ex=_refresh_ttl(payload))


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, response: Response, svc: UserServiceDep):
    _enforce_trusted_origin(request)
    dto = Login(email=body.email, cpf=body.cpf, senha=body.senha)
    user = await svc.login(dto)
    if not user:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    access_token = create_access_token(user.id, user.team.id, user.role.value)
    refresh_token = create_refresh_token(user.id, user.team.id, user.role.value)
    _set_refresh_cookie(response, refresh_token)

    return TokenResponse(
        access_token=access_token,
        user_id=user.id,
        team_id=user.team.id,
        role=user.role,
        nome=user.nome,
    )


@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest, svc: UserServiceDep):
    dto = RegisterUser(
        nome=body.nome,
        senha=body.senha,
        cpf=body.cpf,
        solicitacao_id=body.solicitacao_id,
    )
    user = await svc.register(dto)
    return UserResponse(
        id=user.id,
        nome=user.nome,
        email=user.email,
        role=user.role,
        team_id=user.team.id,
    )


@router.post("/refresh", response_model=RefreshResponse)
@limiter.limit("30/minute")
async def refresh_token(
    request: Request,
    response: Response,
    refresh_token: Annotated[str | None, Cookie(alias=_REFRESH_COOKIE)] = None,
):
    _enforce_trusted_origin(request)

    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token ausente")

    try:
        payload = decode_refresh_token(refresh_token)
    except JWTError:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Refresh token inválido ou expirado")

    # Verifica se o token foi revogado por logout
    jti = payload.get("jti")
    if jti:
        redis = get_redis()
        if await redis.exists(revoked_token_key(jti)):
            _clear_refresh_cookie(response)
            raise HTTPException(status_code=401, detail="Sessão encerrada. Faça login novamente.")

    new_access = create_access_token(
        user_id=UUID(payload["sub"]),
        team_id=UUID(payload["team_id"]),
        role=payload["role"],
    )
    new_refresh = create_refresh_token(
        user_id=UUID(payload["sub"]),
        team_id=UUID(payload["team_id"]),
        role=payload["role"],
    )
    await _revoke_refresh_payload(payload)
    _set_refresh_cookie(response, new_refresh)

    return RefreshResponse(access_token=new_access)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    _: CurrentUser,
    refresh_token: Annotated[str | None, Cookie(alias=_REFRESH_COOKIE)] = None,
):
    """Revoga o refresh token e encerra a sessão."""
    _enforce_trusted_origin(request)
    if refresh_token:
        try:
            payload = decode_refresh_token(refresh_token)
            await _revoke_refresh_payload(payload)
        except JWTError:
            pass  # token já inválido — só limpar o cookie

    _clear_refresh_cookie(response)
    return MessageResponse(message="Logout realizado com sucesso")


@router.post("/recovery", response_model=MessageResponse)
@limiter.limit("5/minute")
async def request_recovery(request: Request, body: RecoveryRequestBody, svc: RecoveryServiceDep):
    dto = CreateRecoveryCode(email=body.email, cpf=body.cpf)
    await svc.create_recovery(dto)
    # Sempre retorna sucesso — não revelar se o usuário existe
    return MessageResponse(message="Se o usuário existir, um código foi enviado")


@router.post("/recovery/verify", response_model=MessageResponse)
@limiter.limit("5/minute")
async def verify_recovery(request: Request, body: RecoveryVerifyRequest, svc: RecoveryServiceDep):
    await svc.verify_recovery(user_id=body.user_id, recovery_code=body.code)
    return MessageResponse(message="Código válido")


@router.post("/recovery/reset", response_model=MessageResponse)
@limiter.limit("5/minute")
async def reset_password(request: Request, body: RecoveryResetRequest, svc: RecoveryServiceDep):
    await svc.update_password(
        user_id=body.user_id,
        recovery_code=body.code,
        new_password=body.new_password,
    )
    return MessageResponse(message="Senha alterada com sucesso")


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser):
    return UserResponse(
        id=user.id,
        nome=user.nome,
        email=user.email,
        role=user.role,
        team_id=user.team.id,
    )
