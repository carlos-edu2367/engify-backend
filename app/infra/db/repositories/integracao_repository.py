"""Implementações SQLAlchemy dos repositórios da integração Arcaika."""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.providers.repo.integracao_repo import (
    ArcaikaConnectionRepository, IntegrationEventRepository,
    OAuthAuthorizationCodeRepository, AuthorizationCodeData,
)
from app.domain.entities.integracao import (
    ArcaikaConnection, IntegrationEvent, EventStatus,
)
from app.infra.db.models.integracao_model import (
    ArcaikaConnectionModel, IntegrationEventModel, OAuthAuthorizationCodeModel,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ArcaikaConnectionRepositoryImpl(ArcaikaConnectionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, connection: ArcaikaConnection) -> ArcaikaConnection:
        stmt = select(ArcaikaConnectionModel).where(
            ArcaikaConnectionModel.id == connection.id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            model = ArcaikaConnectionModel.from_domain(connection)
            self._session.add(model)
        else:
            model.update_from_domain(connection)
        await self._session.flush()
        return model.to_domain()

    async def get_by_id(self, conn_id: UUID) -> ArcaikaConnection | None:
        result = await self._session.execute(
            select(ArcaikaConnectionModel).where(ArcaikaConnectionModel.id == conn_id)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def get_by_team(self, team_id: UUID) -> ArcaikaConnection | None:
        result = await self._session.execute(
            select(ArcaikaConnectionModel).where(ArcaikaConnectionModel.team_id == team_id)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def get_by_organizacao(self, organizacao_id: UUID) -> ArcaikaConnection | None:
        result = await self._session.execute(
            select(ArcaikaConnectionModel).where(
                ArcaikaConnectionModel.arcaika_organizacao_id == organizacao_id
            )
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None


class IntegrationEventRepositoryImpl(IntegrationEventRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, event: IntegrationEvent) -> IntegrationEvent:
        stmt = select(IntegrationEventModel).where(IntegrationEventModel.id == event.id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            model = IntegrationEventModel.from_domain(event)
            self._session.add(model)
        else:
            model.update_from_domain(event)
        await self._session.flush()
        return model.to_domain()

    async def list_due(self, limit: int, now: datetime | None = None) -> list[IntegrationEvent]:
        now = now or _now()
        stmt = (
            select(IntegrationEventModel)
            .where(
                IntegrationEventModel.status.in_(
                    [EventStatus.PENDING.value, EventStatus.FAILED.value]
                ),
                or_(
                    IntegrationEventModel.next_retry_at.is_(None),
                    IntegrationEventModel.next_retry_at <= now,
                ),
            )
            .order_by(IntegrationEventModel.created_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [m.to_domain() for m in result.scalars().all()]


class OAuthAuthorizationCodeRepositoryImpl(OAuthAuthorizationCodeRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, code_hash, client_id, team_id, user_id, arcaika_organizacao_id,
        default_responsavel_id, default_categoria_id, redirect_uri, scopes,
        code_challenge, code_challenge_method, expires_at,
    ) -> None:
        model = OAuthAuthorizationCodeModel(
            code_hash=code_hash,
            client_id=client_id,
            team_id=team_id,
            user_id=user_id,
            arcaika_organizacao_id=arcaika_organizacao_id,
            default_responsavel_id=default_responsavel_id,
            default_categoria_id=default_categoria_id,
            redirect_uri=redirect_uri,
            scopes=scopes,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            expires_at=expires_at,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_by_code_hash(self, code_hash: str) -> AuthorizationCodeData | None:
        result = await self._session.execute(
            select(OAuthAuthorizationCodeModel).where(
                OAuthAuthorizationCodeModel.code_hash == code_hash
            )
        )
        m = result.scalar_one_or_none()
        if not m:
            return None
        return AuthorizationCodeData(
            id=m.id, client_id=m.client_id, team_id=m.team_id, user_id=m.user_id,
            arcaika_organizacao_id=m.arcaika_organizacao_id,
            default_responsavel_id=m.default_responsavel_id,
            default_categoria_id=m.default_categoria_id,
            redirect_uri=m.redirect_uri, scopes=list(m.scopes or []),
            code_challenge=m.code_challenge, code_challenge_method=m.code_challenge_method,
            expires_at=m.expires_at, used=m.used,
        )

    async def mark_used(self, code_id: UUID) -> None:
        result = await self._session.execute(
            select(OAuthAuthorizationCodeModel).where(OAuthAuthorizationCodeModel.id == code_id)
        )
        m = result.scalar_one_or_none()
        if m:
            m.used = True
            await self._session.flush()
