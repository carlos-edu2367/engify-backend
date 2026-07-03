"""
Tokens da integração Arcaika (máquina-a-máquina), **distintos** dos tokens de
usuário humano (`type` != "access"/"refresh").

- Access token: JWT curto assinado com `settings.jwt_secret`, claim
  `type="integration"`, carregando `conn_id`, `team_id` e `scope`.
- Refresh/authorization code: strings opacas aleatórias; guardamos apenas o
  hash SHA-256 no banco (nunca o valor puro), como o refresh humano já faz.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import jwt, JWTError

from app.core.config import settings

INTEGRATION_TOKEN_TYPE = "integration"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_integration_access_token(
    conn_id: UUID, team_id: UUID, scopes: list[str]
) -> str:
    payload = {
        "type": INTEGRATION_TOKEN_TYPE,
        "conn_id": str(conn_id),
        "team_id": str(team_id),
        "scope": " ".join(scopes),
        "iat": _now(),
        "exp": _now() + timedelta(minutes=settings.integration_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_integration_access_token(token: str) -> dict:
    """Decodifica e valida um access token de integração.

    Levanta JWTError se assinatura/expiração inválidas ou se o `type` não for
    `integration` (impede que um token de usuário humano seja usado aqui).
    """
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != INTEGRATION_TOKEN_TYPE:
        raise JWTError("Token não é um token de integração")
    return payload


def generate_opaque_secret(nbytes: int = 32) -> str:
    """Gera uma string opaca URL-safe (refresh token, auth code, webhook secret)."""
    return secrets.token_urlsafe(nbytes)


def hash_secret(value: str) -> str:
    """SHA-256 hex de um segredo opaco, para armazenamento e comparação."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def verify_secret(value: str, stored_hash: str) -> bool:
    import hmac as _hmac
    if not value or not stored_hash:
        return False
    return _hmac.compare_digest(hash_secret(value), stored_hash)
