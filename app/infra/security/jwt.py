from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from jose import jwt, JWTError
from app.core.config import settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: UUID, team_id: UUID, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "team_id": str(team_id),
        "role": role,
        "type": "access",
        "iat": _now(),
        "exp": _now() + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: UUID, team_id: UUID, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "team_id": str(team_id),
        "role": role,
        "type": "refresh",
        "jti": str(uuid4()),  # ID único para revogação por logout
        "iat": _now(),
        "exp": _now() + timedelta(days=settings.refresh_token_expire_days),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """
    Decodifica e valida o token JWT.
    Levanta JWTError em caso de token inválido ou expirado.
    """
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def decode_access_token(token: str) -> dict:
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise JWTError("Token não é um access token")
    return payload


def decode_refresh_token(token: str) -> dict:
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise JWTError("Token não é um refresh token")
    return payload
