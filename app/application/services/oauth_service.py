"""
Authorization Server OAuth 2.0 (Authorization Code + PKCE) restrito ao client
Arcaika. Estabelece o vínculo consentido organização ↔ time e emite os tokens
de integração máquina-a-máquina.
"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import logging
from uuid import UUID

from app.core.config import settings
from app.application.providers.repo.integracao_repo import (
    ArcaikaConnectionRepository, OAuthAuthorizationCodeRepository,
)
from app.application.providers.uow import UOWProvider
from app.domain.entities.integracao import ArcaikaConnection, ConnectionScope
from app.domain.entities.user import User
from app.domain.errors import DomainError
from app.infra.security.pkce import verify_code_challenge, SUPPORTED_METHODS
from app.infra.security.integration_tokens import (
    create_integration_access_token, generate_opaque_secret, hash_secret, verify_secret,
)

_ALLOWED_SCOPES = {s.value for s in ConnectionScope}
logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class TokenResult:
    access_token: str
    refresh_token: str
    expires_in: int
    scope: str
    team_id: UUID


class OAuthArcaikaService:
    def __init__(
        self,
        code_repo: OAuthAuthorizationCodeRepository,
        connection_repo: ArcaikaConnectionRepository,
        uow: UOWProvider,
    ):
        self.code_repo = code_repo
        self.connection_repo = connection_repo
        self.uow = uow

    # ── /oauth/authorize (admin Engify consente) ─────────────────────────────

    async def authorize_consent(self, user: User, req) -> str:
        """Valida o pedido, grava um authorization code e retorna o redirect_to."""
        if req.client_id != settings.arcaika_oauth_client_id:
            raise DomainError("client_id desconhecido")
        if req.redirect_uri not in settings.arcaika_redirect_uri_allowlist:
            raise DomainError("redirect_uri não autorizada")
        if req.code_challenge_method not in SUPPORTED_METHODS:
            raise DomainError("code_challenge_method não suportado")

        requested = [s for s in req.scope.split(" ") if s]
        if not requested or any(s not in _ALLOWED_SCOPES for s in requested):
            raise DomainError("Escopo inválido")

        code = generate_opaque_secret()
        expires_at = _now() + timedelta(seconds=settings.oauth_auth_code_expire_seconds)
        await self.code_repo.create(
            code_hash=hash_secret(code),
            client_id=req.client_id,
            team_id=user.team.id,
            user_id=user.id,
            arcaika_organizacao_id=req.arcaika_organizacao_id,
            default_responsavel_id=req.default_responsavel_id,
            default_categoria_id=req.default_categoria_id,
            redirect_uri=req.redirect_uri,
            scopes=requested,
            code_challenge=req.code_challenge,
            code_challenge_method=req.code_challenge_method,
            expires_at=expires_at,
        )
        await self.uow.commit()

        sep = "&" if "?" in req.redirect_uri else "?"
        redirect_to = f"{req.redirect_uri}{sep}code={code}"
        if req.state:
            redirect_to += f"&state={req.state}"
        return redirect_to

    # ── /oauth/token ─────────────────────────────────────────────────────────

    def _authenticate_client(self, client_id: str, client_secret: str) -> None:
        import hmac
        ok = (
            client_id == settings.arcaika_oauth_client_id
            and bool(settings.arcaika_oauth_client_secret)
            and hmac.compare_digest(client_secret or "", settings.arcaika_oauth_client_secret)
        )
        if not ok:
            raise DomainError("Autenticação de client inválida")

    async def exchange_code(
        self, client_id: str, client_secret: str,
        code: str, code_verifier: str, redirect_uri: str,
    ) -> TokenResult:
        self._authenticate_client(client_id, client_secret)

        data = await self.code_repo.get_by_code_hash(hash_secret(code))
        if data is None or data.used:
            raise DomainError("Authorization code inválido")
        if data.client_id != client_id or data.redirect_uri != redirect_uri:
            raise DomainError("Authorization code não confere com o client/redirect")
        if data.expires_at < _now():
            raise DomainError("Authorization code expirado")
        if not verify_code_challenge(code_verifier, data.code_challenge, data.code_challenge_method):
            raise DomainError("Falha na verificação PKCE")

        await self.code_repo.mark_used(data.id)

        connection = await self._resolve_connection(data)
        result = self._issue_tokens(connection, data.scopes)
        await self.connection_repo.save(connection)
        await self.uow.commit()
        logger.info("Arcaika connection %s issued an integration token", connection.id)
        return result

    async def refresh(
        self, client_id: str, client_secret: str, refresh_token: str
    ) -> TokenResult:
        self._authenticate_client(client_id, client_secret)

        conn_id = self._conn_id_from_refresh(refresh_token)
        connection = (
            await self.connection_repo.get_by_id_for_update(conn_id)
            if conn_id else None
        )
        if connection is None or not connection.is_active:
            raise DomainError("Refresh token inválido")
        if (
            connection.refresh_token_expires_at is None
            or connection.refresh_token_expires_at <= _now()
        ):
            raise DomainError("Refresh token expirado")
        if not verify_secret(refresh_token, connection.refresh_token_hash or ""):
            raise DomainError("Refresh token inválido")

        scopes = [s.value for s in connection.scopes]
        result = self._issue_tokens(connection, scopes)
        await self.connection_repo.save(connection)
        await self.uow.commit()
        logger.info("Arcaika connection %s rotated its integration refresh token", connection.id)
        return result

    # ── helpers ──────────────────────────────────────────────────────────────

    async def _resolve_connection(self, data) -> ArcaikaConnection:
        by_team = await self.connection_repo.get_by_team(data.team_id)
        by_org = await self.connection_repo.get_by_organizacao(data.arcaika_organizacao_id)

        if by_team and by_team.arcaika_organizacao_id != data.arcaika_organizacao_id:
            raise DomainError("Este time já está vinculado a outra organização Arcaika")
        if by_org and by_org.team_id != data.team_id:
            raise DomainError("Esta organização Arcaika já está vinculada a outro time")

        scopes = [ConnectionScope(s) for s in data.scopes]
        existing = by_team or by_org
        if existing is not None:
            existing.status = existing.status  # noqa: (mantém)
            existing.scopes = scopes
            existing.default_responsavel_id = data.default_responsavel_id
            existing.default_categoria_id = data.default_categoria_id
            if not existing.is_active:
                # reativa vínculo previamente revogado
                from app.domain.entities.integracao import ConnectionStatus
                existing.status = ConnectionStatus.ACTIVE
                existing.revoked_at = None
            return existing

        return ArcaikaConnection(
            team_id=data.team_id,
            arcaika_organizacao_id=data.arcaika_organizacao_id,
            scopes=scopes,
            default_responsavel_id=data.default_responsavel_id,
            default_categoria_id=data.default_categoria_id,
            webhook_secret=generate_opaque_secret(),
        )

    def _issue_tokens(self, connection: ArcaikaConnection, scopes: list[str]) -> TokenResult:
        access = create_integration_access_token(connection.id, connection.team_id, scopes)
        # Refresh opaco prefixado pelo conn_id p/ lookup sem coluna indexada extra.
        refresh = f"{connection.id}.{generate_opaque_secret()}"
        refresh_expires_at = _now() + timedelta(days=settings.integration_refresh_token_expire_days)
        connection.rotate_refresh(hash_secret(refresh), refresh_expires_at)
        return TokenResult(
            access_token=access,
            refresh_token=refresh,
            expires_in=settings.integration_token_expire_minutes * 60,
            scope=" ".join(scopes),
            team_id=connection.team_id,
        )

    @staticmethod
    def _conn_id_from_refresh(refresh_token: str) -> UUID | None:
        try:
            return UUID((refresh_token or "").split(".", 1)[0])
        except (ValueError, IndexError):
            return None
