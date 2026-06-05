import json
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
from app.infra.cache.keys import revoked_token_key, rotated_refresh_key
from jose import JWTError
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["Auth"])

_REFRESH_COOKIE = "refresh_token"
_COOKIE_MAX_AGE = settings.refresh_token_expire_days * 24 * 60 * 60
_REFRESH_ROTATION_GRACE_SECONDS = 30


def _refresh_cookie_path() -> str:
    return f"{settings.api_prefix.rstrip('/')}/auth"


def _request_is_https(request: Request | None) -> bool:
    if request is None:
        return False
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto.split(",", 1)[0].strip().lower() == "https":
        return True
    return request.url.scheme == "https"


def _refresh_cookie_secure(request: Request | None = None) -> bool:
    return settings.environment != "dev" or _request_is_https(request)


def _refresh_cookie_samesite(request: Request | None = None) -> str:
    configured = getattr(settings, "refresh_cookie_samesite", None)
    if settings.environment == "dev" and _request_is_https(request):
        return "none"
    if configured:
        return configured
    return "lax" if settings.environment == "dev" else "none"
_COOKIE_SAMESITE = settings.refresh_cookie_samesite  # configurável via REFRESH_COOKIE_SAMESITE


def _set_refresh_cookie(response: Response, token: str, request: Request | None = None) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=_refresh_cookie_secure(request),
        samesite=_refresh_cookie_samesite(request),
        max_age=_COOKIE_MAX_AGE,
        path=_refresh_cookie_path(),
        domain=settings.refresh_cookie_domain,
    )


def _clear_refresh_cookie(response: Response, request: Request | None = None) -> None:
    response.delete_cookie(
        key=_REFRESH_COOKIE,
        path=_refresh_cookie_path(),
        domain=settings.refresh_cookie_domain,
        secure=_refresh_cookie_secure(request),
        samesite=_refresh_cookie_samesite(request),
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


def _rotated_refresh_payload(access_token: str, refresh_token: str) -> str:
    return json.dumps(
        {
            "reason": "rotated",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "reuse_until": int(datetime.now(timezone.utc).timestamp()) + _REFRESH_ROTATION_GRACE_SECONDS,
        }
    )


def _parse_rotated_refresh_payload(value: str | bytes | None) -> dict | None:
    if not value:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    if data.get("reason") != "rotated":
        return None
    if not data.get("access_token") or not data.get("refresh_token"):
        return None
    try:
        reuse_until = int(data.get("reuse_until", 0))
    except (TypeError, ValueError):
        return None
    if reuse_until < int(datetime.now(timezone.utc).timestamp()):
        return None
    return data


async def _cache_rotated_refresh_payload(payload: dict, access_token: str, refresh_token: str) -> None:
    jti = payload.get("jti")
    if not jti:
        return
    redis = get_redis()
    await redis.set(
        rotated_refresh_key(jti),
        _rotated_refresh_payload(access_token, refresh_token),
        ex=_REFRESH_ROTATION_GRACE_SECONDS,
    )


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
    _set_refresh_cookie(response, refresh_token, request)

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
        _clear_refresh_cookie(response, request)
        raise HTTPException(status_code=401, detail="Refresh token inválido ou expirado")

    # Verifica se o token foi revogado por logout
    jti = payload.get("jti")
    if jti:
        redis = get_redis()
        if await redis.exists(revoked_token_key(jti)):
            rotated_payload = _parse_rotated_refresh_payload(await redis.get(rotated_refresh_key(jti)))
            if rotated_payload:
                _set_refresh_cookie(response, rotated_payload["refresh_token"], request)
                return RefreshResponse(access_token=rotated_payload["access_token"])
            _clear_refresh_cookie(response, request)
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
    await _cache_rotated_refresh_payload(payload, new_access, new_refresh)
    _set_refresh_cookie(response, new_refresh, request)

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

    _clear_refresh_cookie(response, request)
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
