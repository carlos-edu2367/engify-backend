from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Response, Cookie, Request
from typing import Annotated
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


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.environment != "dev",
        samesite="lax",
        max_age=_COOKIE_MAX_AGE,
        path="/api/v1/auth/refresh",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_REFRESH_COOKIE, path="/api/v1/auth/refresh")


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, response: Response, svc: UserServiceDep):
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
async def refresh_token(
    response: Response,
    refresh_token: Annotated[str | None, Cookie(alias=_REFRESH_COOKIE)] = None,
):
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

    from uuid import UUID
    new_access = create_access_token(
        user_id=UUID(payload["sub"]),
        team_id=UUID(payload["team_id"]),
        role=payload["role"],
    )
    return RefreshResponse(access_token=new_access)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    _: CurrentUser,
    refresh_token: Annotated[str | None, Cookie(alias=_REFRESH_COOKIE)] = None,
):
    """Revoga o refresh token e encerra a sessão."""
    if refresh_token:
        try:
            payload = decode_refresh_token(refresh_token)
            jti = payload.get("jti")
            if jti:
                exp = payload.get("exp", 0)
                ttl = max(int(exp - datetime.now(timezone.utc).timestamp()), 1)
                redis = get_redis()
                await redis.set(revoked_token_key(jti), "1", ex=ttl)
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
